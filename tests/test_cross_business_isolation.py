from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from business.registry import BusinessRegistry
from persistence.db import get_engine, init_db
from persistence.repositories import BookingRepository
from providers.booking.mock import MockBookingProvider
from security.guards import CallToolGuard, IdempotencyStore
from tools.actions import ReceptionistActions
from tools.schemas import CreateBookingRequest


def test_bookings_isolated_by_business_id(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "iso.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db_path}")
    get_engine.cache_clear()
    from persistence.db import get_session_factory

    get_session_factory.cache_clear()
    init_db()

    registry = BusinessRegistry.from_directory(Path("config/businesses"))
    salon = registry.get("demo_salon")
    clinic = registry.get("demo_clinic")

    tz = ZoneInfo("America/New_York")
    salon_start = datetime.now(tz) + timedelta(days=2)
    while salon_start.weekday() != 1:  # demo_salon is open Tuesdays
        salon_start += timedelta(days=1)
    salon_start = salon_start.replace(hour=10, minute=0, second=0, microsecond=0)

    clinic_start = datetime.now(tz) + timedelta(days=2)
    while clinic_start.weekday() != 0:  # demo_clinic is open Mondays
        clinic_start += timedelta(days=1)
    clinic_start = clinic_start.replace(hour=10, minute=0, second=0, microsecond=0)

    salon_actions = ReceptionistActions(
        profile=salon,
        booking_provider=MockBookingProvider(salon),
        tool_guard=CallToolGuard(min_interval_seconds=0),
        idempotency=IdempotencyStore(),
    )
    clinic_actions = ReceptionistActions(
        profile=clinic,
        booking_provider=MockBookingProvider(clinic),
        tool_guard=CallToolGuard(min_interval_seconds=0),
        idempotency=IdempotencyStore(),
    )

    key = "shared-key-12345678"
    salon_result = salon_actions.create_booking(
        CreateBookingRequest(
            service_id="mens_cut",
            customer_name="Salon Client",
            customer_phone="+15550000001",
            starts_at=salon_start.isoformat(),
            idempotency_key=key,
            confirm=True,
        )
    )
    clinic_result = clinic_actions.create_booking(
        CreateBookingRequest(
            service_id="gp_visit",
            customer_name="Clinic Client",
            customer_phone="+15550000002",
            starts_at=clinic_start.isoformat(),
            idempotency_key=key,
            confirm=True,
        )
    )
    assert salon_result.ok is True
    assert clinic_result.ok is True

    with get_session_factory()() as session:
        salon_booking = BookingRepository(session).find_by_idempotency("demo_salon", key)
        clinic_booking = BookingRepository(session).find_by_idempotency("demo_clinic", key)
        assert salon_booking is not None
        assert clinic_booking is not None
        assert salon_booking.id != clinic_booking.id
