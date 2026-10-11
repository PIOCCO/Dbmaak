from pathlib import Path

import pytest

from agent.routing import BusinessRoutingError, resolve_business_id
from business.registry import BusinessRegistry
from config.settings import Settings
from providers.telephony.base import InboundCallContext


def test_phone_map_routing() -> None:
    registry = BusinessRegistry.from_directory(Path("config/businesses"))
    settings = Settings(
        PHONE_NUMBER_BUSINESS_MAP='{"+15550100":"demo_salon"}',
        DEFAULT_BUSINESS_ID="demo_salon",
    )
    inbound = InboundCallContext(
        room_name="call-123",
        called_number="+15550100",
        caller_number="+15550001111",
        dispatch_metadata={},
    )
    assert resolve_business_id(settings=settings, registry=registry, inbound=inbound) == "demo_salon"


def test_console_default_business() -> None:
    registry = BusinessRegistry.from_directory(Path("config/businesses"))
    settings = Settings(DEFAULT_BUSINESS_ID="demo_salon")
    inbound = InboundCallContext(
        room_name="console-room",
        called_number=None,
        caller_number=None,
        dispatch_metadata={},
    )
    assert (
        resolve_business_id(
            settings=settings, registry=registry, inbound=inbound, console_mode=True
        )
        == "demo_salon"
    )


def test_unknown_routing_fails_closed() -> None:
    registry = BusinessRegistry.from_directory(Path("config/businesses"))
    settings = Settings(DEFAULT_BUSINESS_ID="demo_salon")
    inbound = InboundCallContext(
        room_name="call-xyz",
        called_number="+19999999999",
        caller_number=None,
        dispatch_metadata={},
    )
    with pytest.raises(BusinessRoutingError):
        resolve_business_id(settings=settings, registry=registry, inbound=inbound, console_mode=False)
