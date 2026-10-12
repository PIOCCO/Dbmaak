from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from business.models import BusinessProfile, Weekday
from persistence.db import get_session_factory
from persistence.repositories import (
    BookingConflictError,
    BookingRepository,
    IdempotencyPayloadMismatchError,
)
from providers.booking.base import AvailabilitySlot, BookingProvider, BookingResult
from providers.booking.types import BookingProviderKind
from security.tenant import TenantContext
from security.validation import validate_booking_window


class MockBookingProvider(BookingProvider):
    """Mock booking backend — persists to local DB; not a live calendar integration."""

    def __init__(self, profile: BusinessProfile, tenant: TenantContext) -> None:
        tenant.assert_business(profile.id)
        self._profile = profile
        self._tenant = tenant

    @property
    def provider_kind(self) -> BookingProviderKind:
        return BookingProviderKind.MOCK

    def check_availability(
        self,
        *,
        business_id: str,
        service_id: str,
        starts_at: datetime,
    ) -> AvailabilitySlot:
        self._tenant.assert_business(business_id)

        service = next((s for s in self._profile.services if s.id == service_id), None)
        if not service or not service.bookable:
            return AvailabilitySlot(
                starts_at=starts_at, available=False, reason="Service is not bookable."
            )

        try:
            validate_booking_window(appointment_start=starts_at, timezone=self._profile.timezone)
        except ValueError as exc:
            return AvailabilitySlot(starts_at=starts_at, available=False, reason=str(exc))

        if not _is_within_open_hours(self._profile, starts_at):
            return AvailabilitySlot(
                starts_at=starts_at, available=False, reason="Outside opening hours."
            )

        session_factory = get_session_factory()
        with session_factory() as session:
            repo = BookingRepository(session).for_tenant(self._tenant)
            if repo.overlaps(starts_at, service.duration_minutes):
                return AvailabilitySlot(
                    starts_at=starts_at, available=False, reason="Slot already booked."
                )

        return AvailabilitySlot(starts_at=starts_at, available=True)

    def create_booking(
        self,
        *,
        business_id: str,
        service_id: str,
        customer_name: str,
        customer_phone: str,
        starts_at: datetime,
        idempotency_key: str,
    ) -> BookingResult:
        self._tenant.assert_business(business_id)

        session_factory = get_session_factory()
        with session_factory() as session:
            existing = BookingRepository(session).for_tenant(self._tenant).find_by_idempotency(
                idempotency_key
            )
            if existing:
                return BookingResult(
                    success=True,
                    booking_id=existing.id,
                    message="Mock booking stored locally (not a live calendar reservation).",
                    confirmed_starts_at=existing.starts_at,
                    provider_kind=self.provider_kind,
                )

        service = next((s for s in self._profile.services if s.id == service_id), None)
        if not service:
            return BookingResult(
                success=False,
                booking_id=None,
                message="Unknown service.",
                provider_kind=self.provider_kind,
            )

        slot = self.check_availability(
            business_id=business_id, service_id=service_id, starts_at=starts_at
        )
        if not slot.available:
            return BookingResult(
                success=False,
                booking_id=None,
                message=slot.reason or "Requested slot is unavailable.",
                provider_kind=self.provider_kind,
            )

        session_factory = get_session_factory()
        with session_factory() as session:
            repo = BookingRepository(session).for_tenant(self._tenant)
            try:
                record = repo.create(
                    service_id=service_id,
                    customer_name=customer_name,
                    customer_phone_redacted=_redact_phone(customer_phone),
                    starts_at=starts_at,
                    duration_minutes=service.duration_minutes,
                    idempotency_key=idempotency_key,
                    provider_kind=self.provider_kind.value,
                )
            except (BookingConflictError, IdempotencyPayloadMismatchError) as exc:
                return BookingResult(
                    success=False,
                    booking_id=None,
                    message=str(exc),
                    provider_kind=self.provider_kind,
                )

        return BookingResult(
            success=True,
            booking_id=record.id,
            message="Mock booking stored locally (not a live calendar reservation).",
            confirmed_starts_at=record.starts_at,
            provider_kind=self.provider_kind,
        )


def _is_within_open_hours(profile: BusinessProfile, starts_at: datetime) -> bool:
    tz = ZoneInfo(profile.timezone)
    local = starts_at.astimezone(tz)
    weekday = Weekday(local.strftime("%A").lower())
    for holiday in profile.holidays:
        if holiday.date == local.date():
            return False

    entries = [e for e in profile.opening_hours if e.weekday == weekday]
    if not entries:
        return False

    t = local.time().replace(tzinfo=None)
    for entry in entries:
        for rng in entry.ranges:
            if rng.open <= t < rng.close:
                return True
    return False


def _redact_phone(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) <= 4:
        return "***"
    return f"***{digits[-4:]}"
