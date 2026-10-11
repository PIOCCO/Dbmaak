from __future__ import annotations

import asyncio
import uuid

from livekit import rtc
from livekit.agents import JobContext

from agent.routing import BusinessRoutingError, _normalize_e164, resolve_business_id
from business.registry import BusinessRegistry
from config.settings import Settings
from observability.logging import get_logger
from observability.metrics import get_metrics
from providers.telephony.base import InboundCallContext
from providers.telephony.livekit_sip import LiveKitSipRoutingAdapter

logger = get_logger(__name__)

SIP_PARTICIPANT_WAIT_SECONDS = 45.0


class InboundRoutingResult:
    def __init__(
        self,
        *,
        business_id: str,
        call_id: str,
        inbound: InboundCallContext,
        console_mode: bool,
        caller_number_redacted: str,
    ) -> None:
        self.business_id = business_id
        self.call_id = call_id
        self.inbound = inbound
        self.console_mode = console_mode
        self.caller_number_redacted = caller_number_redacted


async def resolve_inbound_routing(
    ctx: JobContext,
    *,
    settings: Settings,
    registry: BusinessRegistry,
) -> InboundRoutingResult:
    """Wait for SIP participant on real calls; resolve tenant from trusted metadata only."""
    metrics = get_metrics()
    telephony = LiveKitSipRoutingAdapter()
    console_mode = ctx.is_fake_job()

    participant_attrs: dict[str, str] | None = None
    if not console_mode:
        participant = await _wait_for_sip_participant(ctx)
        if participant is not None:
            participant_attrs = dict(participant.attributes)
            metrics.record_event(
                "sip_participant_linked",
                room=ctx.room.name,
                has_called_number=bool(participant_attrs.get("sip.trunkPhoneNumber")),
            )
        else:
            metrics.increment("sip_participant_timeout")
            logger.error("sip_participant_timeout", room=ctx.room.name)
            raise BusinessRoutingError("Timed out waiting for inbound SIP participant.")

    inbound = telephony.extract_inbound_context(
        room_name=ctx.room.name,
        job_metadata=getattr(ctx.job, "metadata", "") or "",
        participant_attributes=participant_attrs,
    )

    try:
        business_id = resolve_business_id(
            settings=settings,
            registry=registry,
            inbound=inbound,
            console_mode=console_mode,
        )
    except BusinessRoutingError:
        metrics.increment("routing_failed", reason="unknown_tenant")
        raise

    metrics.increment("routing_success", business_id=business_id)
    logger.info(
        "routing_resolved",
        business_id=business_id,
        console_mode=console_mode,
        called_number_present=bool(inbound.called_number),
        routing_source=_routing_source(settings, registry, inbound, business_id),
    )

    call_id = str(inbound.dispatch_metadata.get("call_id") or uuid.uuid4())
    caller_redacted = _redact_phone(inbound.caller_number or "")

    return InboundRoutingResult(
        business_id=business_id,
        call_id=call_id,
        inbound=inbound,
        console_mode=console_mode,
        caller_number_redacted=caller_redacted,
    )


async def _wait_for_sip_participant(ctx: JobContext) -> rtc.RemoteParticipant | None:
    for participant in ctx.room.remote_participants.values():
        if participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
            return participant

    try:
        return await asyncio.wait_for(
            ctx.wait_for_participant(kind=rtc.ParticipantKind.PARTICIPANT_KIND_SIP),
            timeout=SIP_PARTICIPANT_WAIT_SECONDS,
        )
    except TimeoutError:
        return None


def _routing_source(
    settings: Settings,
    registry: BusinessRegistry,
    inbound: InboundCallContext,
    business_id: str,
) -> str:
    if inbound.dispatch_metadata.get("business_id") == business_id:
        return "dispatch_metadata"
    if inbound.called_number:
        called = _normalize_e164(inbound.called_number)
        if settings.phone_number_business_map.get(called):
            return "phone_number_map"
        profile = registry.get(business_id)
        if called in {_normalize_e164(n) for n in profile.inbound_phone_numbers}:
            return "profile_inbound_numbers"
    if inbound.room_name.startswith(f"biz-{business_id}-"):
        return "room_prefix"
    return "default_console" if business_id == settings.default_business_id else "unknown"


def _redact_phone(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) <= 4:
        return ""
    return f"***{digits[-4:]}"
