from __future__ import annotations

from dataclasses import dataclass

from livekit.agents import RunContext, function_tool

from agent.context import SessionContext
from agent.handoff import HandoffNotAllowedError, transfer_caller_to_human
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
        from livekit.agents import get_job_context

        result = svc.request_human_handoff(HumanHandoffRequest(reason=reason))
        if not result.ok:
            return result.message
        try:
            job_ctx = get_job_context()
            transferred, detail = await transfer_caller_to_human(
                job_ctx, ctx.userdata, reason=reason
            )
        except HandoffNotAllowedError as exc:
            return str(exc)
        if transferred:
            return f"{result.message} {detail}".strip()
        return f"{result.message} {detail}".strip()

    return [
        get_business_info,
        get_opening_hours,
        lookup_service,
        check_availability,
        create_booking,
        request_human_handoff,
    ]
