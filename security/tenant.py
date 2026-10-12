from __future__ import annotations

from dataclasses import dataclass


class TenantScopeError(PermissionError):
    """Raised when a resource access violates tenant isolation."""


@dataclass(frozen=True, slots=True)
class TenantContext:
    """Authorized tenant identity from trusted server-side routing."""

    business_id: str
    call_id: str

    def assert_business(self, business_id: str) -> None:
        if business_id != self.business_id:
            raise TenantScopeError(
                f"Cross-tenant access denied: expected '{self.business_id}', got '{business_id}'."
            )
