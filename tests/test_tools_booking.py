from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from business.registry import BusinessRegistry
from persistence.db import get_engine, init_db
from providers.booking.mock import MockBookingProvider
from security.authorization import ToolAuthorizationError, ToolName
from security.guards import CallToolGuard, IdempotencyStore
from security.tenant import TenantContext
from tools.actions import ReceptionistActions
from tools.schemas import CreateBookingRequest, LookupServiceRequest


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db_path}")
    get_engine.cache_clear()
    get_session_factory = __import__("persistence.db", fromlist=["get_session_factory"]).get_session_factory
    get_session_factory.cache_clear()
    init_db()
    yield


def _actions(business_id: str = "demo_salon", call_id: str = "call-test") -> ReceptionistActions:
    profile = BusinessRegistry.from_directory(Path("config/businesses")).get(business_id)
    tenant = TenantContext(business_id=business_id, call_id=call_id)
    return ReceptionistActions(
        profile=profile,
        booking_provider=MockBookingProvider(profile, tenant),
        tool_guard=CallToolGuard(max_calls_per_tool=20, min_interval_seconds=0),
        idempotency=IdempotencyStore(),
        tenant=tenant,
    )


def test_lookup_service_grounded() -> None:
    result = _actions().lookup_service(LookupServiceRequest(query="color"))
    assert result.ok is True
    assert "color" in result.message.lower()


def test_create_booking_requires_confirm() -> None:
    actions = _actions()
    tz = ZoneInfo("America/New_York")
    start = datetime.now(tz) + timedelta(days=2)
    start = start.replace(hour=10, minute=0, second=0, microsecond=0)
    result = actions.create_booking(
        CreateBookingRequest(
            service_id="mens_cut",
            customer_name="Alex Caller",
            customer_phone="+15551230000",
            starts_at=start.isoformat(),
            idempotency_key="key-001-abcdef",
            confirm=False,
        )
    )
    assert result.ok is False
    assert "confirm" in result.message.lower()


def test_duplicate_idempotency_returns_same_booking() -> None:
    actions = _actions()
    tz = ZoneInfo("America/New_York")
    start = datetime.now(tz) + timedelta(days=3)
    start = start.replace(hour=11, minute=0, second=0, microsecond=0)
    req = CreateBookingRequest(
        service_id="mens_cut",
        customer_name="Alex Caller",
        customer_phone="+15551230000",
        starts_at=start.isoformat(),
        idempotency_key="key-dup-abcdef",
        confirm=True,
    )
    first = actions.create_booking(req)
    second = actions.create_booking(req)
    assert first.ok is True
    assert "MOCK BOOKING" in first.message
    assert second.ok is True
    assert first.data and second.data
    assert first.data["booking_id"] == second.data["booking_id"]


def test_unauthorized_tool_blocked() -> None:
    profile = BusinessRegistry.from_directory(Path("config/businesses")).get("demo_salon")
    tenant = TenantContext(business_id=profile.id, call_id="call-auth")
    actions = ReceptionistActions(
        profile=profile,
        booking_provider=MockBookingProvider(profile, tenant),
        tool_guard=CallToolGuard(),
        idempotency=IdempotencyStore(),
        tenant=tenant,
        allowed_tools=frozenset({ToolName.GET_BUSINESS_INFO}),
    )
    with pytest.raises(ToolAuthorizationError):
        actions.lookup_service(LookupServiceRequest(query="cut"))
