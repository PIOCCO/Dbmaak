"""Booking rows survive process-style restart (new engine/session factory)."""

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from business.registry import BusinessRegistry
from persistence.db import get_engine, get_session_factory, init_db
from persistence.repositories import BookingRepository
from providers.booking.mock import MockBookingProvider
from security.tenant import TenantContext
from tools.actions import ReceptionistActions
from tools.schemas import CreateBookingRequest
from security.guards import CallToolGuard, IdempotencyStore


def test_booking_persists_after_engine_reset(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "restart.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db_path}")

    get_engine.cache_clear()
    get_session_factory.cache_clear()
    init_db()

    profile = BusinessRegistry.from_directory(Path("config/businesses")).get("demo_salon")
    tenant = TenantContext(business_id=profile.id, call_id="restart-call-1")
    actions = ReceptionistActions(
        profile=profile,
        booking_provider=MockBookingProvider(profile, tenant),
        tool_guard=CallToolGuard(min_interval_seconds=0),
        idempotency=IdempotencyStore(),
        tenant=tenant,
    )

    tz = ZoneInfo("America/New_York")
    start = datetime.now(tz) + timedelta(days=3)
    while start.weekday() != 1:  # demo_salon open Tuesdays
        start += timedelta(days=1)
    start = start.replace(hour=10, minute=0, second=0, microsecond=0)

    result = actions.create_booking(
        CreateBookingRequest(
            service_id="mens_cut",
            customer_name="Persist Me",
            customer_phone="+15551230000",
            starts_at=start.isoformat(),
            idempotency_key="restart-key-12345678",
            confirm=True,
        )
    )
    assert result.ok is True
    assert result.data and result.data["booking_id"]

    # Simulate application restart
    get_engine.cache_clear()
    get_session_factory.cache_clear()

    with get_session_factory()() as session:
        record = BookingRepository(session).for_tenant(tenant).find_by_idempotency(
            "restart-key-12345678"
        )
        assert record is not None
        assert record.customer_name == "Persist Me"
        assert record.provider_kind == "mock"
