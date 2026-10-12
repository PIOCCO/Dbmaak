from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from business.registry import BusinessRegistry
from persistence.db import get_engine, get_session_factory, init_db
from persistence.repositories import (
    BookingRepository,
    CallSessionRepository,
    IdempotencyPayloadMismatchError,
    TenantScopedBookingRepository,
)
from providers.booking.mock import MockBookingProvider
from security.tenant import TenantContext, TenantScopeError


@pytest.fixture
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "tenant.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db_path}")
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    init_db()
    yield


def test_mock_provider_rejects_cross_tenant_business_id(db) -> None:
    profile = BusinessRegistry.from_directory(Path("config/businesses")).get("demo_salon")
    tenant = TenantContext(business_id=profile.id, call_id="c1")
    provider = MockBookingProvider(profile, tenant)
    tz = ZoneInfo("America/New_York")
    start = datetime.now(tz) + timedelta(days=5)
    start = start.replace(hour=10, minute=0, second=0, microsecond=0)
    with pytest.raises(TenantScopeError):
        provider.check_availability(
            business_id="demo_clinic",
            service_id="mens_cut",
            starts_at=start,
        )


def test_scoped_repository_rejects_wrong_business_id_in_create(db) -> None:
    tenant = TenantContext(business_id="demo_salon", call_id="c2")
    with get_session_factory()() as session:
        repo = TenantScopedBookingRepository(session, tenant)
        tz = ZoneInfo("UTC")
        starts = datetime(2030, 1, 7, 15, 0, tzinfo=tz)
        record = repo.create(
            service_id="mens_cut",
            customer_name="Test",
            customer_phone_redacted="***1234",
            starts_at=starts,
            duration_minutes=45,
            idempotency_key="idem-12345678",
        )
        assert record.business_id == "demo_salon"
        assert record.provider_kind == "mock"


def test_idempotency_payload_mismatch(db) -> None:
    tenant = TenantContext(business_id="demo_salon", call_id="c3")
    with get_session_factory()() as session:
        repo = TenantScopedBookingRepository(session, tenant)
        tz = ZoneInfo("UTC")
        starts = datetime(2030, 2, 1, 15, 0, tzinfo=tz)
        repo.create(
            service_id="mens_cut",
            customer_name="Alex",
            customer_phone_redacted="***1111",
            starts_at=starts,
            duration_minutes=45,
            idempotency_key="shared-key-99999999",
        )
        with pytest.raises(IdempotencyPayloadMismatchError):
            repo.create(
                service_id="mens_cut",
                customer_name="Different Name",
                customer_phone_redacted="***2222",
                starts_at=starts,
                duration_minutes=45,
                idempotency_key="shared-key-99999999",
            )


def test_call_session_end_is_idempotent(db) -> None:
    with get_session_factory()() as session:
        repo = CallSessionRepository(session)
        repo.start(call_id="sess-1", business_id="demo_salon")
        assert repo.end("sess-1", status="completed") is True
        assert repo.end("sess-1", status="failed") is False


def test_call_session_start_rejects_conflicting_business(db) -> None:
    with get_session_factory()() as session:
        repo = CallSessionRepository(session)
        repo.start(call_id="sess-2", business_id="demo_salon")
        with pytest.raises(TenantScopeError):
            repo.start(call_id="sess-2", business_id="demo_clinic")


def test_repository_lookup_isolated_by_tenant(db) -> None:
    tenant_a = TenantContext(business_id="demo_salon", call_id="a")
    tenant_b = TenantContext(business_id="demo_clinic", call_id="b")
    key = "cross-tenant-key-123456"
    with get_session_factory()() as session:
        BookingRepository(session).for_tenant(tenant_a).create(
            service_id="mens_cut",
            customer_name="A",
            customer_phone_redacted="***1",
            starts_at=datetime(2030, 3, 1, 10, 0, tzinfo=ZoneInfo("UTC")),
            duration_minutes=45,
            idempotency_key=key,
        )
        assert BookingRepository(session).for_tenant(tenant_b).find_by_idempotency(key) is None
