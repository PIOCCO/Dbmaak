from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


def validate_booking_window(
    *,
    appointment_start: datetime,
    timezone: str,
    min_lead_time: timedelta = timedelta(hours=2),
    max_days_ahead: int = 60,
) -> None:
    tz = ZoneInfo(timezone)
    now = datetime.now(tz)
    if appointment_start.tzinfo is None:
        appointment_start = appointment_start.replace(tzinfo=tz)
    else:
        appointment_start = appointment_start.astimezone(tz)

    if appointment_start < now + min_lead_time:
        raise ValueError("Appointment must be at least 2 hours in the future.")
    if appointment_start.date() > (now.date() + timedelta(days=max_days_ahead)):
        raise ValueError(f"Appointments can only be booked up to {max_days_ahead} days ahead.")

    if appointment_start.minute not in (0, 30):
        raise ValueError("Appointments must start on the hour or half-hour.")


def parse_iso_date(value: str) -> date:
    return date.fromisoformat(value)


def parse_iso_datetime(value: str, timezone: str) -> datetime:
    tz = ZoneInfo(timezone)
    if "T" in value:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=tz)
        return dt.astimezone(tz)
    d = date.fromisoformat(value)
    return datetime(d.year, d.month, d.day, 9, 0, tzinfo=tz)
