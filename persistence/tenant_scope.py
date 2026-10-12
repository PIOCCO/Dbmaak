from __future__ import annotations

from security.tenant import TenantContext, TenantScopeError


def require_tenant(tenant: TenantContext, *, business_id: str) -> None:
    tenant.assert_business(business_id)


class TenantScopedMixin:
    def __init__(self, tenant: TenantContext) -> None:
        self._tenant = tenant

    def _enforce(self, business_id: str) -> None:
        try:
            self._tenant.assert_business(business_id)
        except TenantScopeError:
            raise
