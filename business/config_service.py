from __future__ import annotations

from business.models import BusinessProfile
from business.registry import BusinessRegistry
from security.tenant import TenantContext


class BusinessConfigService:
    """Tenant-scoped read access to business configuration."""

    def __init__(self, registry: BusinessRegistry) -> None:
        self._registry = registry

    def get_profile(self, tenant: TenantContext) -> BusinessProfile:
        return self._registry.get(tenant.business_id)
