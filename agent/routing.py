from __future__ import annotations

import re

from business.registry import BusinessRegistry
from config.settings import Settings
from providers.telephony.base import InboundCallContext


class BusinessRoutingError(LookupError):
    pass


def resolve_business_id(
    *,
    settings: Settings,
    registry: BusinessRegistry,
    inbound: InboundCallContext | None,
    console_mode: bool = False,
) -> str:
    """Resolve tenant id from trusted routing metadata — never from LLM/caller input."""

    if inbound and inbound.dispatch_metadata.get("business_id"):
        business_id = str(inbound.dispatch_metadata["business_id"])
        _assert_known(registry, business_id)
        return business_id

    if inbound and inbound.called_number:
        mapped = settings.phone_number_business_map.get(_normalize_e164(inbound.called_number))
        if mapped:
            _assert_known(registry, mapped)
            return mapped
        for profile in registry.list_ids():
            p = registry.get(profile)
            if _normalize_e164(inbound.called_number) in {
                _normalize_e164(n) for n in p.inbound_phone_numbers
            }:
                return p.id

    room_match = _BUSINESS_ROOM_RE.match(inbound.room_name) if inbound else None
    if room_match:
        business_id = room_match.group("business_id")
        _assert_known(registry, business_id)
        return business_id

    if console_mode:
        _assert_known(registry, settings.default_business_id)
        return settings.default_business_id

    raise BusinessRoutingError(
        "Could not resolve business_id from trusted routing metadata. "
        "Configure PHONE_NUMBER_BUSINESS_MAP, profile inbound_phone_numbers, "
        "dispatch metadata business_id, or room prefix biz-<id>-."
    )


def _assert_known(registry: BusinessRegistry, business_id: str) -> None:
    if business_id not in registry.list_ids():
        raise BusinessRoutingError(f"Unknown business_id in routing: {business_id}")


def _normalize_e164(value: str) -> str:
    digits = re.sub(r"[^\d+]", "", value.strip())
    if digits and not digits.startswith("+"):
        digits = f"+{digits}"
    return digits


_BUSINESS_ROOM_RE = re.compile(r"^biz-(?P<business_id>[a-z0-9_]+)-")
