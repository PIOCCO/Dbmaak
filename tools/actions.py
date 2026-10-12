from __future__ import annotations

from dataclasses import dataclass

from business.models import BusinessProfile
from knowledge.retrieval import KnowledgeRetriever
from knowledge.store import BusinessKnowledgeStore, KnowledgeSection
from providers.booking.base import BookingProvider
from security.authorization import ToolAuthorizationError, ToolName, authorize_tool
from security.guards import CallToolGuard, IdempotencyStore
from security.tenant import TenantContext
from security.validation import parse_iso_datetime
from business.handoff_config import resolve_handoff_destination
from config.settings import get_settings
from tools.schemas import (
    BusinessInfoRequest,
    CheckAvailabilityRequest,
    CreateBookingRequest,
    HumanHandoffRequest,
    LookupServiceRequest,
    OpeningHoursRequest,
)


MOCK_BOOKING_NOTICE = (
    "[MOCK BOOKING — not a live reservation; for demonstration and testing only]"
)


@dataclass
class ActionResult:
    ok: bool
    message: str
    data: dict | None = None


class ReceptionistActions:
    def __init__(
        self,
        *,
        profile: BusinessProfile,
        booking_provider: BookingProvider,
        tool_guard: CallToolGuard,
        idempotency: IdempotencyStore,
        tenant: TenantContext,
        allowed_tools: frozenset[ToolName] | None = None,
    ) -> None:
        tenant.assert_business(profile.id)
        self._profile = profile
        self._booking = booking_provider
        self._guard = tool_guard
        self._idempotency = idempotency
        self._tenant = tenant
        self._allowed = allowed_tools
        store = BusinessKnowledgeStore(profile)
        self._retriever = KnowledgeRetriever(store)

    @property
    def business_id(self) -> str:
        return self._profile.id

    def _run_tool(self, tool: ToolName) -> None:
        authorize_tool(tool, allowed=self._allowed)
        self._guard.check_and_record(tool.value)

    def get_business_info(self, req: BusinessInfoRequest) -> ActionResult:
        self._run_tool(ToolName.GET_BUSINESS_INFO)
        docs = self._retriever.search(req.topic, limit=2)
        if not docs:
            return ActionResult(
                ok=False,
                message=(
                    "I don't have verified information about that topic. "
                    "I can connect you with a team member if you'd like."
                ),
            )
        body = "\n\n".join(f"{doc.title}: {doc.body}" for doc in docs)
        return ActionResult(
            ok=True,
            message=f"{self._retriever.grounded_answer_prefix()}\n{body}",
            data={"verified": True, "sections": [d.section.value for d in docs]},
        )

    def get_opening_hours(self, req: OpeningHoursRequest) -> ActionResult:
        self._run_tool(ToolName.GET_OPENING_HOURS)
        doc = self._retriever.get_section(KnowledgeSection.HOURS)
        if not doc:
            return ActionResult(ok=False, message="Opening hours are not configured for this business.")
        msg = doc.body
        if req.date:
            msg = f"For {req.date}, refer to regular hours unless listed as a holiday.\n{doc.body}"
        return ActionResult(ok=True, message=msg, data={"verified": True})

    def lookup_service(self, req: LookupServiceRequest) -> ActionResult:
        self._run_tool(ToolName.LOOKUP_SERVICE)
        query = req.query.lower()
        matches = [
            s
            for s in self._profile.services
            if query in s.name.lower() or query in s.id.lower() or query in s.description.lower()
        ]
        if not matches:
            return ActionResult(
                ok=False,
                message="I couldn't find a matching service in our verified catalog.",
            )
        lines = [
            f"{s.name} (id={s.id}): {s.duration_minutes} minutes"
            + (f", {s.price_currency} {s.price_amount:.2f}" if s.price_amount is not None else "")
            for s in matches[:5]
        ]
        return ActionResult(ok=True, message="\n".join(lines), data={"verified": True})

    def check_availability(self, req: CheckAvailabilityRequest) -> ActionResult:
        self._run_tool(ToolName.CHECK_AVAILABILITY)
        starts_at = parse_iso_datetime(req.starts_at, self._profile.timezone)
        slot = self._booking.check_availability(
            business_id=self._profile.id,
            service_id=req.service_id,
            starts_at=starts_at,
        )
        if slot.available:
            return ActionResult(
                ok=True,
                message=(
                    f"[MOCK AVAILABILITY CHECK] The requested time appears available on "
                    f"{starts_at.isoformat()}. Confirm with the caller before booking."
                ),
                data={"available": True, "mock": True},
            )
        return ActionResult(
            ok=False,
            message=slot.reason or "That time is not available.",
            data={"available": False},
        )

    def create_booking(self, req: CreateBookingRequest) -> ActionResult:
        self._run_tool(ToolName.CREATE_BOOKING)
        if not req.confirm:
            return ActionResult(
                ok=False,
                message=(
                    "Please confirm the customer's name, phone number, service, and time "
                    "before setting confirm=true."
                ),
            )
        starts_at = parse_iso_datetime(req.starts_at, self._profile.timezone)
        self._tenant.assert_business(self._profile.id)
        result = self._booking.create_booking(
            business_id=self._profile.id,
            service_id=req.service_id,
            customer_name=req.customer_name,
            customer_phone=req.customer_phone,
            starts_at=starts_at,
            idempotency_key=req.idempotency_key,
        )
        if not result.success:
            return ActionResult(ok=False, message=result.message)
        if not result.is_mock:
            return ActionResult(
                ok=True,
                message=result.message,
                data={
                    "booking_id": result.booking_id,
                    "starts_at": result.confirmed_starts_at.isoformat()
                    if result.confirmed_starts_at
                    else None,
                    "mock": False,
                    "provider_kind": result.provider_kind.value,
                },
            )
        return ActionResult(
            ok=True,
            message=f"{MOCK_BOOKING_NOTICE} {result.message}",
            data={
                "booking_id": result.booking_id,
                "starts_at": result.confirmed_starts_at.isoformat()
                if result.confirmed_starts_at
                else None,
                "mock": True,
                "provider_kind": result.provider_kind.value,
            },
        )

    def request_human_handoff(self, req: HumanHandoffRequest) -> ActionResult:
        try:
            self._run_tool(ToolName.REQUEST_HUMAN_HANDOFF)
        except ToolAuthorizationError as exc:
            return ActionResult(ok=False, message=str(exc))

        _destination, enabled = resolve_handoff_destination(
            settings=get_settings(), profile=self._profile
        )
        if not enabled:
            return ActionResult(
                ok=False,
                message="Human handoff is not available for this line.",
            )
        return ActionResult(
            ok=True,
            message=self._profile.escalation.human_handoff_message,
            data={"handoff_requested": True, "reason": req.reason},
        )
