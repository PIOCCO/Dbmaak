from __future__ import annotations

from datetime import date, time
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, field_validator, model_validator


class Weekday(StrEnum):
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class TimeRange(BaseModel):
    open: time
    close: time

    @model_validator(mode="after")
    def validate_range(self) -> TimeRange:
        if self.close <= self.open:
            raise ValueError("close must be after open")
        return self


class OpeningHoursEntry(BaseModel):
    weekday: Weekday
    ranges: Annotated[list[TimeRange], Field(min_length=1)]


class HolidayClosure(BaseModel):
    date: date
    reason: str = ""


class ServiceOffering(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    name: str
    description: str = ""
    duration_minutes: int = Field(ge=5, le=480)
    price_amount: float | None = Field(default=None, ge=0)
    price_currency: str = "USD"
    bookable: bool = True


class FAQEntry(BaseModel):
    question: str
    answer: str


class ContactDetails(BaseModel):
    phone: str = ""
    email: str = ""
    address: str = ""
    website: str = ""


class EscalationRules(BaseModel):
    offer_human_after_failed_tool_attempts: int = Field(default=2, ge=0, le=10)
    offer_human_on_low_confidence: bool = True
    human_handoff_message: str = (
        "I'll connect you with a team member who can help further."
    )


class AgentStyle(BaseModel):
    language: str = Field(default="en", description="BCP-47 language tag, e.g. en, nl, es")
    tone: str = Field(default="warm, concise, professional")
    disclose_ai: bool = True


class BusinessProfile(BaseModel):
    """Validated tenant configuration loaded from trusted server-side sources."""

    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")
    display_name: str
    description: str = ""
    timezone: str = "UTC"
    agent_style: AgentStyle = Field(default_factory=AgentStyle)
    contact: ContactDetails = Field(default_factory=ContactDetails)
    opening_hours: list[OpeningHoursEntry] = Field(default_factory=list)
    holidays: list[HolidayClosure] = Field(default_factory=list)
    services: list[ServiceOffering] = Field(default_factory=list)
    faqs: list[FAQEntry] = Field(default_factory=list)
    policies: list[str] = Field(default_factory=list)
    escalation: EscalationRules = Field(default_factory=EscalationRules)
    inbound_phone_numbers: list[str] = Field(default_factory=list)

    @field_validator("inbound_phone_numbers")
    @classmethod
    def normalize_phones(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for raw in values:
            digits = "".join(ch for ch in raw.strip() if ch.isdigit() or ch == "+")
            if not digits.startswith("+") and digits:
                digits = f"+{digits}"
            normalized.append(digits)
        return normalized

    @model_validator(mode="after")
    def unique_service_ids(self) -> BusinessProfile:
        ids = [s.id for s in self.services]
        if len(ids) != len(set(ids)):
            raise ValueError("service ids must be unique within a business")
        return self
