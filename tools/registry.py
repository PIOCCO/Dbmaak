from __future__ import annotations

from dataclasses import dataclass

from livekit.agents import RunContext, function_tool

from agent.context import SessionContext
from tools import actions
from tools.schemas import (
    BusinessInfoRequest,
    CheckAvailabilityRequest,
    CreateBookingRequest,
    HumanHandoffRequest,
    LookupServiceRequest,
    OpeningHoursRequest,
)


@dataclass
class ToolServices:
    actions: actions.ReceptionistActions


def build_livekit_tools(services: ToolServices) -> list:
    svc = services.actions

    @function_tool(name="get_business_info")
    async def get_business_info(ctx: RunContext[SessionContext], topic: str) -> str:
        result = svc.get_business_info(BusinessInfoRequest(topic=topic))
        return result.message

    @function_tool(name="get_opening_hours")
    async def get_opening_hours(
        ctx: RunContext[SessionContext], date: str | None = None
    ) -> str:
        result = svc.get_opening_hours(OpeningHoursRequest(date=date))
        return result.message

    @function_tool(name="lookup_service")
    async def lookup_service(ctx: RunContext[SessionContext], query: str) -> str:
        result = svc.lookup_service(LookupServiceRequest(query=query))
        return result.message

    @function_tool(name="check_availability")
    async def check_availability(
        ctx: RunContext[SessionContext], service_id: str, starts_at: str
    ) -> str:
        result = svc.check_availability(
            CheckAvailabilityRequest(service_id=service_id, starts_at=starts_at)
        )
        return result.message

    @function_tool(name="create_booking")
    async def create_booking(
        ctx: RunContext[SessionContext],
        service_id: str,
        customer_name: str,
        customer_phone: str,
        starts_at: str,
        idempotency_key: str,
        confirm: bool = False,
    ) -> str:
        result = svc.create_booking(
            CreateBookingRequest(
                service_id=service_id,
                customer_name=customer_name,
                customer_phone=customer_phone,
                starts_at=starts_at,
                idempotency_key=idempotency_key,
                confirm=confirm,
            )
        )
        return result.message

    @function_tool(name="request_human_handoff")
    async def request_human_handoff(ctx: RunContext[SessionContext], reason: str) -> str:
        result = svc.request_human_handoff(HumanHandoffRequest(reason=reason))
        if result.ok:
            await _maybe_transfer(ctx)
        return result.message

    return [
        get_business_info,
        get_opening_hours,
        lookup_service,
        check_availability,
        create_booking,
        request_human_handoff,
    ]


async def _maybe_transfer(ctx: RunContext[SessionContext]) -> None:
    from livekit.agents import get_job_context

    destination = ctx.userdata.handoff_destination
    if not destination:
        return
    job_ctx = get_job_context()
    # Transfer only works for SIP sessions (not local console).
    for participant in job_ctx.room.remote_participants.values():
        try:
            job_ctx.transfer_sip_participant(
                participant=participant,
                transfer_to=destination,
            )
        except Exception:
            continue
