from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class AvailabilitySlot:
    starts_at: datetime
    available: bool
    reason: str = ""


@dataclass(frozen=True)
class BookingResult:
    success: bool
    booking_id: str | None
    message: str
    confirmed_starts_at: datetime | None = None


class BookingProvider(ABC):
    @abstractmethod
    def check_availability(
        self,
        *,
        business_id: str,
        service_id: str,
        starts_at: datetime,
    ) -> AvailabilitySlot: ...

    @abstractmethod
    def create_booking(
        self,
        *,
        business_id: str,
        service_id: str,
        customer_name: str,
        customer_phone: str,
        starts_at: datetime,
        idempotency_key: str,
    ) -> BookingResult: ...
