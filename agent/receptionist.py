from __future__ import annotations

import uuid

from livekit.agents import Agent, AgentSession, JobContext, RoomInputOptions, RoomOutputOptions
from agent.context import SessionContext
from agent.prompts import build_system_instructions
from agent.routing import resolve_business_id
from business.registry import BusinessRegistry
from config.settings import Settings, get_settings
from observability.logging import bind_call_context, get_logger
from persistence.db import get_session_factory, init_db
from persistence.repositories import CallSessionRepository
from providers.booking.mock import MockBookingProvider
from providers.telephony.livekit_sip import LiveKitSipRoutingAdapter
from providers.voice.openai_realtime import OpenAIRealtimeVoiceFactory
from security.guards import CallToolGuard, IdempotencyStore
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
) -> SessionContext:
    profile = registry.get(business_id)
    booking = MockBookingProvider(profile)
    actions = ReceptionistActions(
        profile=profile,
        booking_provider=booking,
        tool_guard=CallToolGuard(),
        idempotency=IdempotencyStore(),
    )
    return SessionContext(
        call_id=call_id,
        business_id=business_id,
        profile=profile,
        actions=actions,
        handoff_destination=handoff_destination,
        caller_number_redacted=caller_number_redacted,
    )


async def start_receptionist_session(ctx: JobContext) -> None:
    settings = get_settings()
    registry = BusinessRegistry.from_directory(settings.business_config_dir)
    init_db()

    telephony = LiveKitSipRoutingAdapter()
    participant_attrs: dict[str, str] | None = None
    for participant in ctx.room.remote_participants.values():
        participant_attrs = dict(participant.attributes)
        break

    inbound = telephony.extract_inbound_context(
        room_name=ctx.room.name,
        job_metadata=getattr(ctx.job, "metadata", "") or "",
        participant_attributes=participant_attrs,
    )
    console_mode = not participant_attrs and not inbound.called_number
    business_id = resolve_business_id(
        settings=settings,
        registry=registry,
        inbound=inbound,
        console_mode=console_mode,
    )

    call_id = inbound.dispatch_metadata.get("call_id") or str(uuid.uuid4())
    caller_redacted = _redact_phone(inbound.caller_number or "")

    session_ctx = build_session_context(
        settings=settings,
        registry=registry,
        business_id=business_id,
        call_id=call_id,
        handoff_destination=settings.human_handoff_destination,
        caller_number_redacted=caller_redacted,
    )

    bind_call_context(call_id=call_id, business_id=business_id, room=ctx.room.name)
    logger.info("session_start", business_id=business_id, console_mode=console_mode)

    with get_session_factory()() as db_session:
        CallSessionRepository(db_session).start(
            call_id=call_id,
            business_id=business_id,
            room_name=ctx.room.name,
            caller_number_redacted=caller_redacted,
            metadata={"routing": inbound.dispatch_metadata},
        )

    voice_factory = OpenAIRealtimeVoiceFactory(settings)
    tools = build_livekit_tools(ToolServices(actions=session_ctx.actions))
    instructions = build_system_instructions(session_ctx.profile)

    agent = ReceptionistAgent(instructions=instructions, tools=tools)
    session = AgentSession[SessionContext](
        llm=voice_factory.create_realtime_model(),
        userdata=session_ctx,
        tools=tools,
    )

    await session.start(
        agent=agent,
        room=ctx.room,
        room_input_options=RoomInputOptions(close_on_disconnect=True),
        room_output_options=RoomOutputOptions(transcription_enabled=True),
    )

    @session.on("close")
    def _on_close(_: object) -> None:
        with get_session_factory()() as db_session:
            CallSessionRepository(db_session).end(call_id)


def _redact_phone(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) <= 4:
        return ""
    return f"***{digits[-4:]}"
