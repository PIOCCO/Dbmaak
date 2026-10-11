from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class InboundCallContext:
    room_name: str
    called_number: str | None
    caller_number: str | None
    dispatch_metadata: dict


class TelephonyRoutingAdapter(Protocol):
    def extract_inbound_context(
        self,
        *,
        room_name: str,
        job_metadata: str,
        participant_attributes: dict[str, str] | None,
    ) -> InboundCallContext: ...
