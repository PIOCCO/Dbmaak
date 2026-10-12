from __future__ import annotations

from enum import StrEnum


class ToolName(StrEnum):
    GET_BUSINESS_INFO = "get_business_info"
    GET_OPENING_HOURS = "get_opening_hours"
    LOOKUP_SERVICE = "lookup_service"
    CHECK_AVAILABILITY = "check_availability"
    CREATE_BOOKING = "create_booking"
    REQUEST_HUMAN_HANDOFF = "request_human_handoff"


class ToolAuthorizationError(PermissionError):
    pass


# Tools allowed for a standard inbound caller session.
DEFAULT_ALLOWED_TOOLS: frozenset[ToolName] = frozenset(ToolName)


def authorize_tool(tool: ToolName, *, allowed: frozenset[ToolName] | None = None) -> None:
    allowed_set = allowed or DEFAULT_ALLOWED_TOOLS
    if tool not in allowed_set:
        raise ToolAuthorizationError(f"Tool '{tool}' is not authorized for this session")
