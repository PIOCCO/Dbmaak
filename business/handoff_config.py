from __future__ import annotations

from business.models import BusinessProfile
from config.settings import Settings


def resolve_handoff_destination(
    *, settings: Settings, profile: BusinessProfile
) -> tuple[str, bool]:
    enabled = profile.escalation.handoff_enabled
    destination = (
        profile.escalation.handoff_destination.strip() or settings.human_handoff_destination.strip()
    )
    return destination, enabled
