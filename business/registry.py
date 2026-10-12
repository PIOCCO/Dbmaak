from __future__ import annotations

from pathlib import Path

from business.loader import load_business_directory
from business.models import BusinessProfile


class BusinessRegistry:
    """In-memory registry of validated business profiles."""

    def __init__(self, profiles: dict[str, BusinessProfile] | None = None) -> None:
        self._profiles: dict[str, BusinessProfile] = profiles or {}

    @classmethod
    def from_directory(cls, directory: Path) -> BusinessRegistry:
        return cls(load_business_directory(directory))

    def get(self, business_id: str) -> BusinessProfile:
        try:
            return self._profiles[business_id]
        except KeyError as exc:
            raise KeyError(f"Unknown business_id: {business_id}") from exc

    def list_ids(self) -> list[str]:
        return sorted(self._profiles.keys())

    def register(self, profile: BusinessProfile) -> None:
        self._profiles[profile.id] = profile
