from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class CallSessionRecord(Base):
    __tablename__ = "call_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(64), index=True)
    room_name: Mapped[str] = mapped_column(String(255), default="")
    caller_number_redacted: Mapped[str] = mapped_column(String(32), default="")
    status: Mapped[str] = mapped_column(String(32), default="active")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")


class BookingRecord(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        UniqueConstraint("business_id", "idempotency_key", name="uq_booking_idempotency"),
        Index("ix_booking_business_start", "business_id", "starts_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(64), index=True)
    service_id: Mapped[str] = mapped_column(String(64))
    customer_name: Mapped[str] = mapped_column(String(120))
    customer_phone_redacted: Mapped[str] = mapped_column(String(32), default="")
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="confirmed")
    idempotency_key: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
