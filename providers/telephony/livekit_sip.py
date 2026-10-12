from __future__ import annotations

import json

from providers.telephony.base import InboundCallContext


class LiveKitSipRoutingAdapter:
    """Parse trusted telephony attributes from LiveKit SIP participants."""

    def extract_inbound_context(
        self,
        *,
        room_name: str,
        job_metadata: str,
        participant_attributes: dict[str, str] | None,
    ) -> InboundCallContext:
        metadata: dict = {}
        if job_metadata:
            try:
                parsed = json.loads(job_metadata)
                if isinstance(parsed, dict):
                    metadata = parsed
            except json.JSONDecodeError:
                metadata = {"raw_job_metadata": job_metadata}

        attrs = participant_attributes or {}
        # Attribute names follow LiveKit SIP participant attributes (see telephony testing checklist).
        called = (
            attrs.get("sip.trunkPhoneNumber")
            or attrs.get("sip.trunkNumber")
            or attrs.get("sip.to")
            or attrs.get("sip.calledNumber")
            or metadata.get("called_number")
        )
        caller = attrs.get("sip.phoneNumber") or attrs.get("sip.from") or metadata.get(
            "caller_number"
        )
        return InboundCallContext(
            room_name=room_name,
            called_number=str(called) if called else None,
            caller_number=str(caller) if caller else None,
            dispatch_metadata=metadata,
        )
