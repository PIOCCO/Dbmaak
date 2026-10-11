from __future__ import annotations

from livekit import rtc
from livekit.agents import Agent, AgentSession, JobContext, RoomInputOptions, RoomOutputOptions

from agent.context import SessionContext
from agent.inbound import resolve_inbound_routing
from agent.session_lifecycle import CallSessionFinalizer
from agent.prompts import build_system_instructions
from agent.routing import BusinessRoutingError
from business.registry import BusinessRegistry
from config.settings import Settings, get_settings
from observability.logging import bind_call_context, get_logger
from observability.metrics import get_metrics
from persistence.db import get_session_factory, init_db
from persistence.repositories import CallSessionRepository
from providers.booking.mock import MockBookingProvider
from providers.voice.factory import build_voice_factory
from security.guards import CallToolGuard, IdempotencyStore
from security.tenant import TenantContext
from tools.actions import ReceptionistActions
from tools.registry import ToolServices, build_livekit_tools

logger = get_logger(__name__)


class ReceptionistAgent(Agent):
    def __init__(self, instructions: str, tools: list) -> None:
        super().__init__(instructions=instructions, tools=tools)

    async def on_enter(self) -> None:
        profile = self.session.userdata.profile  # type: ignore[attr-defined]
        greet = (
            f"Greet the caller on behalf of {profile.display_name}. "
            "Ask how you can help today."
        )
        self.session.generate_reply(instructions=greet)


def build_session_context(
    *,
    settings: Settings,
    registry: BusinessRegistry,
    business_id: str,
    call_id: str,
    handoff_destination: str,
    caller_number_redacted: str = "",
    handoff_enabled: bool = True,
) -> SessionContext:
    profile = registry.get(business_id)
    tenant = TenantContext(business_id=business_id, call_id=call_id)
    booking = MockBookingProvider(profile, tenant)
    actions = ReceptionistActions(
        profile=profile,
        booking_provider=booking,
        tool_guard=CallToolGuard(),
        idempotency=IdempotencyStore(),
        tenant=tenant,
    )
    return SessionContext(
        call_id=call_id,
        business_id=business_id,
        profile=profile,
        actions=actions,
        handoff_destination=handoff_destination if handoff_enabled else "",
        caller_number_redacted=caller_number_redacted,
    )


async def start_receptionist_session(ctx: JobContext) -> None:
    settings = get_settings()
    registry = BusinessRegistry.from_directory(settings.business_config_dir)
    init_db()
    metrics = get_metrics()

    try:
        routing = await resolve_inbound_routing(ctx, settings=settings, registry=registry)
    except BusinessRoutingError as exc:
        metrics.increment("session_aborted", reason="routing_failed")
        logger.error("session_aborted", reason="routing_failed", detail=str(exc))
        with get_session_factory()() as db_session:
            CallSessionRepository(db_session).start(
                call_id="unrouted",
                business_id="unknown",
                room_name=ctx.room.name,
                metadata={"error": str(exc)},
            )
            CallSessionRepository(db_session).end("unrouted", status="routing_failed")
        ctx.shutdown(reason=f"routing_failed: {exc}")
        return

    from business.handoff_config import resolve_handoff_destination

    handoff_destination, handoff_enabled = resolve_handoff_destination(
        settings=settings, profile=registry.get(routing.business_id)
    )

    session_ctx = build_session_context(
        settings=settings,
        registry=registry,
        business_id=routing.business_id,
        call_id=routing.call_id,
        handoff_destination=handoff_destination,
        caller_number_redacted=routing.caller_number_redacted,
        handoff_enabled=handoff_enabled,
    )

    bind_call_context(
        call_id=routing.call_id,
        business_id=routing.business_id,
        room=ctx.room.name,
    )
    metrics.increment("session_started", business_id=routing.business_id)
    metrics.record_event(
        "call_lifecycle",
        phase="started",
        business_id=routing.business_id,
        call_id=routing.call_id,
        console_mode=routing.console_mode,
    )
    logger.info(
        "session_start",
        business_id=routing.business_id,
        console_mode=routing.console_mode,
    )

    with get_session_factory()() as db_session:
        CallSessionRepository(db_session).start(
            call_id=routing.call_id,
            business_id=routing.business_id,
            room_name=ctx.room.name,
            caller_number_redacted=routing.caller_number_redacted,
            metadata={"routing": routing.inbound.dispatch_metadata},
        )

    voice_factory = build_voice_factory(settings)
    tools = build_livekit_tools(ToolServices(actions=session_ctx.actions))
    instructions = build_system_instructions(session_ctx.profile)

    agent = ReceptionistAgent(instructions=instructions, tools=tools)
    session = AgentSession[SessionContext](
        llm=voice_factory.create_realtime_model(),
        userdata=session_ctx,
        tools=tools,
    )

    @ctx.room.on("participant_disconnected")
    def _on_participant_disconnected(participant: rtc.RemoteParticipant) -> None:
        if participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
            metrics.increment("caller_disconnected", business_id=routing.business_id)
            metrics.record_event(
                "call_lifecycle",
                phase="caller_disconnected",
                business_id=routing.business_id,
                call_id=routing.call_id,
            )
            logger.info("caller_disconnected", business_id=routing.business_id)

    def _persist_end(status: str) -> None:
        with get_session_factory()() as db_session:
            CallSessionRepository(db_session).end(routing.call_id, status=status)

    finalizer = CallSessionFinalizer(
        call_id=routing.call_id,
        business_id=routing.business_id,
        on_finalize=_persist_end,
    )

    @session.on("close")
    def _on_close(_: object) -> None:
        finalizer.finalize("completed")

    try:
        await session.start(
            agent=agent,
            room=ctx.room,
            room_input_options=RoomInputOptions(close_on_disconnect=True),
            room_output_options=RoomOutputOptions(transcription_enabled=True),
        )
    except Exception as exc:
        metrics.increment("session_failed", business_id=routing.business_id)
        logger.error(
            "session_failed",
            business_id=routing.business_id,
            error_type=type(exc).__name__,
        )
        finalizer.finalize("failed")
        raise
