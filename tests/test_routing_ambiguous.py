from pathlib import Path

import pytest

from agent.routing import BusinessRoutingError, resolve_business_id
from business.loader import load_business_profile
from business.registry import BusinessRegistry
from config.settings import Settings
from providers.telephony.base import InboundCallContext


def test_ambiguous_shared_inbound_number_raises(tmp_path: Path) -> None:
    salon = load_business_profile(Path("config/businesses/demo_salon.yaml"))
    clinic = load_business_profile(Path("config/businesses/demo_clinic.yaml"))
    shared = "+15550999"
    salon = salon.model_copy(update={"inbound_phone_numbers": [shared]})
    clinic = clinic.model_copy(update={"inbound_phone_numbers": [shared]})
    registry = BusinessRegistry({salon.id: salon, clinic.id: clinic})
    settings = Settings()
    inbound = InboundCallContext(
        room_name="call-x",
        called_number=shared,
        caller_number=None,
        dispatch_metadata={},
    )
    with pytest.raises(BusinessRoutingError, match="Ambiguous"):
        resolve_business_id(settings=settings, registry=registry, inbound=inbound)
