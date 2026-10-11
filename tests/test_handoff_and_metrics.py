import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agent.handoff import HandoffNotAllowedError, transfer_caller_to_human
from business.handoff_config import resolve_handoff_destination
from business.registry import BusinessRegistry
from config.settings import Settings
from observability.metrics import get_metrics
from security.guards import CallToolGuard, IdempotencyStore
from tools.actions import MOCK_BOOKING_NOTICE, ReceptionistActions
from tools.schemas import HumanHandoffRequest


@pytest.fixture(autouse=True)
def reset_metrics():
    get_metrics().reset()
    yield
    get_metrics().reset()


def test_handoff_disabled_blocks_tool() -> None:
    profile = BusinessRegistry.from_directory(Path("config/businesses")).get("demo_salon")
    profile = profile.model_copy(
        update={"escalation": profile.escalation.model_copy(update={"handoff_enabled": False})}
    )
    actions = ReceptionistActions(
        profile=profile,
        booking_provider=MagicMock(),
        tool_guard=CallToolGuard(min_interval_seconds=0),
        idempotency=IdempotencyStore(),
    )
    result = actions.request_human_handoff(HumanHandoffRequest(reason="Need a person"))
    assert result.ok is False


def test_resolve_handoff_prefers_business_destination() -> None:
    profile = BusinessRegistry.from_directory(Path("config/businesses")).get("demo_salon")
    profile = profile.model_copy(
        update={
            "escalation": profile.escalation.model_copy(
                update={"handoff_destination": "sip:desk@pbx.example"}
            )
        }
    )
    dest, enabled = resolve_handoff_destination(
        settings=Settings(HUMAN_HANDOFF_DESTINATION="+15559998888"),
        profile=profile,
    )
    assert enabled is True
    assert dest == "sip:desk@pbx.example"


@pytest.mark.asyncio
async def test_transfer_skipped_without_sip_participant() -> None:
    profile = BusinessRegistry.from_directory(Path("config/businesses")).get("demo_salon")
    profile = profile.model_copy(
        update={
            "escalation": profile.escalation.model_copy(
                update={"handoff_destination": "+15550001234"}
            )
        }
    )
    session_ctx = MagicMock()
    session_ctx.profile = profile
    session_ctx.business_id = profile.id
    session_ctx.call_id = "call-1"

    job_ctx = MagicMock()
    job_ctx.room.remote_participants.values.return_value = []

    ok, msg = await transfer_caller_to_human(
        job_ctx,
        session_ctx,
        reason="test",
    )
    assert ok is False
    assert "telephone" in msg.lower()
    snap = get_metrics().snapshot()
    assert snap.counters.get("handoff_skipped|reason=no_sip_participant", 0) == 1


@pytest.mark.asyncio
async def test_transfer_blocked_when_disabled() -> None:
    profile = BusinessRegistry.from_directory(Path("config/businesses")).get("demo_salon")
    profile = profile.model_copy(
        update={"escalation": profile.escalation.model_copy(update={"handoff_enabled": False})}
    )
    session_ctx = MagicMock()
    session_ctx.profile = profile
    session_ctx.business_id = profile.id
    session_ctx.call_id = "call-2"

    with pytest.raises(HandoffNotAllowedError):
        await transfer_caller_to_human(MagicMock(), session_ctx, reason="test")


@pytest.mark.asyncio
async def test_transfer_success_records_metric() -> None:
    from livekit import rtc

    profile = BusinessRegistry.from_directory(Path("config/businesses")).get("demo_salon")
    profile = profile.model_copy(
        update={
            "escalation": profile.escalation.model_copy(
                update={"handoff_destination": "+15550001234"}
            )
        }
    )
    session_ctx = MagicMock()
    session_ctx.profile = profile
    session_ctx.business_id = profile.id
    session_ctx.call_id = "call-3"

    sip_participant = MagicMock()
    sip_participant.kind = rtc.ParticipantKind.PARTICIPANT_KIND_SIP

    job_ctx = MagicMock()
    job_ctx.room.remote_participants.values.return_value = [sip_participant]
    loop = asyncio.get_running_loop()
    done = loop.create_future()
    done.set_result(object())
    job_ctx.transfer_sip_participant.return_value = done

    ok, _ = await transfer_caller_to_human(job_ctx, session_ctx, reason="billing")
    assert ok is True
    assert get_metrics().snapshot().counters.get(f"handoff_success|business_id={profile.id}", 0) == 1


def test_mock_booking_success_includes_notice() -> None:
    assert "MOCK BOOKING" in MOCK_BOOKING_NOTICE
