from __future__ import annotations

import asyncio

from livekit import rtc
from livekit.agents import JobContext

from agent.context import SessionContext
from business.handoff_config import resolve_handoff_destination
from config.settings import get_settings
from observability.logging import get_logger
from observability.metrics import get_metrics

logger = get_logger(__name__)


class HandoffNotAllowedError(PermissionError):
    pass


async def transfer_caller_to_human(
    ctx: JobContext,
    session_ctx: SessionContext,
    *,
    reason: str,
) -> tuple[bool, str]:
    """Safely attempt SIP cold transfer when configured and authorized."""
    metrics = get_metrics()
    destination, enabled = resolve_handoff_destination(
        settings=get_settings(),
        profile=session_ctx.profile,
    )

    if not enabled:
        metrics.increment("handoff_blocked", reason="disabled")
        logger.warning(
            "handoff_blocked",
            business_id=session_ctx.business_id,
            cause="handoff_disabled",
        )
        raise HandoffNotAllowedError("Human handoff is disabled for this business.")

    if not destination:
        metrics.increment("handoff_skipped", reason="no_destination")
        logger.info(
            "handoff_skipped",
            business_id=session_ctx.business_id,
            cause="missing_destination",
        )
        return False, "Handoff requested but no transfer destination is configured."

    sip_participant = _find_sip_participant(ctx)
    if sip_participant is None:
        metrics.increment("handoff_skipped", reason="no_sip_participant")
        logger.info(
            "handoff_skipped",
            business_id=session_ctx.business_id,
            cause="not_sip_call",
        )
        return False, "Handoff is only available on live telephone calls."

    metrics.record_event(
        "handoff_transfer_started",
        business_id=session_ctx.business_id,
        call_id=session_ctx.call_id,
    )
    try:
        transfer_task = ctx.transfer_sip_participant(
            participant=sip_participant,
            transfer_to=destination,
            play_dialtone=True,
        )
        await asyncio.wait_for(transfer_task, timeout=30.0)
        metrics.increment("handoff_success", business_id=session_ctx.business_id)
        logger.info(
            "handoff_success",
            business_id=session_ctx.business_id,
            call_id=session_ctx.call_id,
        )
        return True, "Transfer initiated."
    except Exception as exc:
        metrics.increment("handoff_failed", business_id=session_ctx.business_id)
        logger.error(
            "handoff_failed",
            business_id=session_ctx.business_id,
            call_id=session_ctx.call_id,
            error_type=type(exc).__name__,
        )
        return False, "Transfer could not be completed; please try again or call back."


def _find_sip_participant(ctx: JobContext) -> rtc.RemoteParticipant | None:
    for participant in ctx.room.remote_participants.values():
        if participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
            return participant
    return None
