from __future__ import annotations

from pydantic import BaseModel, Field


class BusinessInfoRequest(BaseModel):
    topic: str = Field(description="What the caller wants to know about the business.")


class OpeningHoursRequest(BaseModel):
    date: str | None = Field(
        default=None,
        description="Optional ISO date (YYYY-MM-DD) to check a specific day.",
    )


class LookupServiceRequest(BaseModel):
    query: str = Field(description="Service name or keyword to look up.")


class CheckAvailabilityRequest(BaseModel):
    service_id: str
    starts_at: str = Field(description="ISO datetime for the desired appointment start.")


class CreateBookingRequest(BaseModel):
    service_id: str
    customer_name: str = Field(min_length=2, max_length=120)
    customer_phone: str = Field(min_length=7, max_length=32)
    starts_at: str
    idempotency_key: str = Field(min_length=8, max_length=128)
    confirm: bool = Field(
        default=False,
        description="Must be true after the caller confirmed details.",
    )


class HumanHandoffRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
