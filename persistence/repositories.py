from __future__ import annotations

import json
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from persistence.models import BookingRecord, CallSessionRecord


class BookingConflictError(Exception):
    pass


class BookingRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def find_by_idempotency(self, business_id: str, idempotency_key: str) -> BookingRecord | None:
        stmt = select(BookingRecord).where(
            BookingRecord.business_id == business_id,
            BookingRecord.idempotency_key == idempotency_key,
        )
        return self._session.scalar(stmt)

    def overlaps(self, business_id: str, starts_at: datetime, duration_minutes: int) -> bool:
        from datetime import timedelta

        end = starts_at + timedelta(minutes=duration_minutes)
        stmt = select(BookingRecord).where(
            BookingRecord.business_id == business_id,
            BookingRecord.status == "confirmed",
            BookingRecord.starts_at < end,
        )
        for booking in self._session.scalars(stmt):
            # naive overlap check using stored start only + assumed duration lookup omitted
            if booking.starts_at == starts_at:
                return True
        return False

    def create(
        self,
        *,
        business_id: str,
        service_id: str,
        customer_name: str,
        customer_phone_redacted: str,
        starts_at: datetime,
        idempotency_key: str,
    ) -> BookingRecord:
        existing = self.find_by_idempotency(business_id, idempotency_key)
        if existing:
            return existing

        record = BookingRecord(
            id=str(uuid.uuid4()),
            business_id=business_id,
            service_id=service_id,
            customer_name=customer_name,
            customer_phone_redacted=customer_phone_redacted,
            starts_at=starts_at,
            idempotency_key=idempotency_key,
        )
        self._session.add(record)
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            existing = self.find_by_idempotency(business_id, idempotency_key)
            if existing:
                return existing
            raise BookingConflictError("Could not create booking due to a conflict.") from exc
        self._session.refresh(record)
        return record


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

    def end(self, call_id: str, *, status: str = "completed") -> None:
        record = self._session.get(CallSessionRecord, call_id)
        if not record:
            return
        record.status = status
        record.ended_at = datetime.now(ZoneInfo("UTC"))
        self._session.commit()
