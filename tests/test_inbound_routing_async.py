import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent.inbound import resolve_inbound_routing
from agent.routing import BusinessRoutingError
from business.registry import BusinessRegistry
from config.settings import Settings
from observability.metrics import get_metrics


@pytest.fixture(autouse=True)
def reset_metrics():
    get_metrics().reset()
    yield
    get_metrics().reset()


@pytest.mark.asyncio
async def test_console_fake_job_uses_default_business(tmp_path) -> None:
    workspace = Path(__file__).resolve().parents[1]
    (tmp_path / "config" / "businesses").mkdir(parents=True)
    (tmp_path / "config" / "businesses" / "demo_salon.yaml").write_text(
        (workspace / "config/businesses/demo_salon.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    settings = Settings(
        business_config_dir=tmp_path / "config" / "businesses",
        default_business_id="demo_salon",
    )
    registry = BusinessRegistry.from_directory(settings.business_config_dir)

    ctx = MagicMock()
    ctx.is_fake_job.return_value = True
    ctx.room.name = "console"
    ctx.job.metadata = ""

    result = await resolve_inbound_routing(ctx, settings=settings, registry=registry)
    assert result.business_id == "demo_salon"
    assert result.console_mode is True


@pytest.mark.asyncio
async def test_sip_timeout_aborts_routing(monkeypatch) -> None:
    import agent.inbound as inbound_mod

    monkeypatch.setattr(inbound_mod, "SIP_PARTICIPANT_WAIT_SECONDS", 0.01)
    settings = Settings()
    registry = BusinessRegistry.from_directory(settings.business_config_dir)

    async def slow_wait(**kwargs):
        await asyncio.sleep(1)

    ctx = MagicMock()
    ctx.is_fake_job.return_value = False
    ctx.room.name = "call-123"
    ctx.job.metadata = ""
    ctx.room.remote_participants.values.return_value = []
    ctx.wait_for_participant = slow_wait

    with pytest.raises(BusinessRoutingError, match="Timed out"):
        await resolve_inbound_routing(ctx, settings=settings, registry=registry)

    assert get_metrics().snapshot().counters.get("sip_participant_timeout", 0) == 1


@pytest.mark.asyncio
async def test_inbound_number_loads_matching_profile() -> None:
    settings = Settings(PHONE_NUMBER_BUSINESS_MAP='{"+15550200":"demo_clinic"}')
    registry = BusinessRegistry.from_directory(settings.business_config_dir)

    from livekit import rtc

    participant = MagicMock()
    participant.kind = rtc.ParticipantKind.PARTICIPANT_KIND_SIP
    participant.attributes = {"sip.trunkPhoneNumber": "+15550200"}

    ctx = MagicMock()
    ctx.is_fake_job.return_value = False
    ctx.room.name = "call-999"
    ctx.job.metadata = ""
    ctx.room.remote_participants.values.return_value = [participant]

    result = await resolve_inbound_routing(ctx, settings=settings, registry=registry)
    assert result.business_id == "demo_clinic"
    assert result.inbound.called_number == "+15550200"
