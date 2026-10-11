from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from persistence.models import BookingRecord, CallSessionRecord
from security.tenant import TenantContext, TenantScopeError


class BookingConflictError(Exception):
    pass


class IdempotencyPayloadMismatchError(BookingConflictError):
    pass


class TenantScopedBookingRepository:
    """All booking persistence scoped to a single authorized tenant."""

    def __init__(self, session: Session, tenant: TenantContext) -> None:
        self._session = session
        self._tenant = tenant

    @property
    def tenant(self) -> TenantContext:
        return self._tenant

    def find_by_idempotency(self, idempotency_key: str) -> BookingRecord | None:
        stmt = select(BookingRecord).where(
            BookingRecord.business_id == self._tenant.business_id,
            BookingRecord.idempotency_key == idempotency_key,
        )
        return self._session.scalar(stmt)

    def overlaps(self, starts_at: datetime, duration_minutes: int) -> bool:
        window_start = _as_utc(starts_at)
        window_end = window_start + timedelta(minutes=duration_minutes)
        stmt = select(BookingRecord).where(
            BookingRecord.business_id == self._tenant.business_id,
            BookingRecord.status == "confirmed",
        )
        for booking in self._session.scalars(stmt):
            other_start = _as_utc(booking.starts_at)
            other_end = other_start + timedelta(minutes=booking.duration_minutes)
            if other_end > window_start and other_start < window_end:
                return True
        return False

    def create(
        self,
        *,
        service_id: str,
        customer_name: str,
        customer_phone_redacted: str,
        starts_at: datetime,
        duration_minutes: int,
        idempotency_key: str,
        provider_kind: str = "mock",
    ) -> BookingRecord:
        existing = self.find_by_idempotency(idempotency_key)
        if existing:
            if not _same_booking_payload(
                existing,
                service_id=service_id,
                customer_name=customer_name,
                starts_at=starts_at,
            ):
                raise IdempotencyPayloadMismatchError(
                    "Idempotency key reused with different booking details."
                )
            return existing

        record = BookingRecord(
            id=str(uuid.uuid4()),
            business_id=self._tenant.business_id,
            service_id=service_id,
            customer_name=customer_name,
            customer_phone_redacted=customer_phone_redacted,
            starts_at=_as_utc(starts_at),
            duration_minutes=duration_minutes,
            idempotency_key=idempotency_key,
            provider_kind=provider_kind,
        )
        self._session.add(record)
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            existing = self.find_by_idempotency(idempotency_key)
            if existing:
                if not _same_booking_payload(
                    existing,
                    service_id=service_id,
                    customer_name=customer_name,
                    starts_at=starts_at,
                ):
                    raise IdempotencyPayloadMismatchError(
                        "Idempotency key reused with different booking details."
                    ) from exc
                return existing
            raise BookingConflictError("Could not create booking due to a conflict.") from exc
        self._session.refresh(record)
        return record


class BookingRepository:
    """Unscoped repository — prefer TenantScopedBookingRepository in application code."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def for_tenant(self, tenant: TenantContext) -> TenantScopedBookingRepository:
        return TenantScopedBookingRepository(self._session, tenant)

    def find_by_idempotency(self, business_id: str, idempotency_key: str) -> BookingRecord | None:
        stmt = select(BookingRecord).where(
            BookingRecord.business_id == business_id,
            BookingRecord.idempotency_key == idempotency_key,
        )
        return self._session.scalar(stmt)


class CallSessionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def start(
        self,
        *,
        call_id: str,
        business_id: str,
        room_name: str = "",
        caller_number_redacted: str = "",
        metadata: dict | None = None,
    ) -> CallSessionRecord:
        existing = self._session.get(CallSessionRecord, call_id)
        if existing:
            if existing.business_id != business_id:
                raise TenantScopeError("Call session id bound to a different business.")
            return existing

        record = CallSessionRecord(
            id=call_id,
            business_id=business_id,
            room_name=room_name,
            caller_number_redacted=caller_number_redacted,
            metadata_json=json.dumps(metadata or {}),
        )
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record

    def end(self, call_id: str, *, status: str = "completed") -> bool:
        """Finalize call session once. Returns False if already finalized."""
        record = self._session.get(CallSessionRecord, call_id)
        if not record:
            return False
        if record.ended_at is not None:
            return False
        record.status = status
        record.ended_at = datetime.now(ZoneInfo("UTC"))
        self._session.commit()
        return True

    def get_for_tenant(self, call_id: str, tenant: TenantContext) -> CallSessionRecord | None:
        record = self._session.get(CallSessionRecord, call_id)
        if record is None:
            return None
        tenant.assert_business(record.business_id)
        return record


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=ZoneInfo("UTC"))
    return value.astimezone(ZoneInfo("UTC"))


def _same_booking_payload(
    record: BookingRecord,
    *,
    service_id: str,
    customer_name: str,
    starts_at: datetime,
) -> bool:
    return (
        record.service_id == service_id
        and record.customer_name == customer_name
        and _as_utc(record.starts_at).replace(microsecond=0)
        == _as_utc(starts_at).replace(microsecond=0)
    )
