from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from business.models import BusinessProfile, Weekday
from persistence.db import get_session_factory
from persistence.repositories import BookingConflictError, BookingRepository
from providers.booking.base import AvailabilitySlot, BookingProvider, BookingResult
from security.validation import validate_booking_window


class MockBookingProvider(BookingProvider):
    """Deterministic mock booking backend backed by SQLAlchemy when configured."""

    def __init__(self, profile: BusinessProfile) -> None:
        self._profile = profile

    def check_availability(
        self,
        *,
        business_id: str,
        service_id: str,
        starts_at: datetime,
    ) -> AvailabilitySlot:
        if business_id != self._profile.id:
            return AvailabilitySlot(starts_at=starts_at, available=False, reason="Unknown business.")

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
            repo = BookingRepository(session)
            if repo.overlaps(business_id, starts_at, service.duration_minutes):
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
        slot = self.check_availability(
            business_id=business_id, service_id=service_id, starts_at=starts_at
        )
        if not slot.available:
            return BookingResult(
                success=False,
                booking_id=None,
                message=slot.reason or "Requested slot is unavailable.",
            )

        session_factory = get_session_factory()
        with session_factory() as session:
            repo = BookingRepository(session)
            try:
                record = repo.create(
                    business_id=business_id,
                    service_id=service_id,
                    customer_name=customer_name,
                    customer_phone_redacted=_redact_phone(customer_phone),
                    starts_at=starts_at,
                    idempotency_key=idempotency_key,
                )
            except BookingConflictError:
                return BookingResult(
                    success=False,
                    booking_id=None,
                    message="Booking could not be confirmed due to a scheduling conflict.",
                )

        return BookingResult(
            success=True,
            booking_id=record.id,
            message="Booking confirmed.",
            confirmed_starts_at=record.starts_at,
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
