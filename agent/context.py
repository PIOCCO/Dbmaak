from __future__ import annotations

from dataclasses import dataclass, field

from business.models import BusinessProfile
from security.guards import CallToolGuard, IdempotencyStore
from tools.actions import ReceptionistActions


@dataclass
class SessionContext:
    call_id: str
    business_id: str
    profile: BusinessProfile
    actions: ReceptionistActions
    handoff_destination: str = ""
    caller_number_redacted: str = ""
    tool_guard: CallToolGuard = field(default_factory=CallToolGuard)
    idempotency: IdempotencyStore = field(default_factory=IdempotencyStore)
