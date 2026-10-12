from __future__ import annotations

from enum import StrEnum


class BookingProviderKind(StrEnum):
    MOCK = "mock"
    LIVE = "live"
