from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from business.models import BusinessProfile


class KnowledgeSection(StrEnum):
    OVERVIEW = "overview"
    HOURS = "hours"
    SERVICES = "services"
    FAQ = "faq"
    POLICIES = "policies"
    CONTACT = "contact"
    ESCALATION = "escalation"


@dataclass(frozen=True)
class KnowledgeDocument:
    business_id: str
    section: KnowledgeSection
    title: str
    body: str
    verified: bool = True


class BusinessKnowledgeStore:
    """Simple structured knowledge derived from validated business configuration."""

    def __init__(self, profile: BusinessProfile) -> None:
        self._profile = profile

    @property
    def business_id(self) -> str:
        return self._profile.id

    def all_documents(self) -> list[KnowledgeDocument]:
        p = self._profile
        docs: list[KnowledgeDocument] = [
            KnowledgeDocument(
                business_id=p.id,
                section=KnowledgeSection.OVERVIEW,
                title="Business overview",
                body=f"{p.display_name}. {p.description}".strip(),
            )
        ]
        if p.opening_hours or p.holidays:
            lines: list[str] = []
            for entry in p.opening_hours:
                ranges = ", ".join(
                    f"{r.open.strftime('%H:%M')}-{r.close.strftime('%H:%M')}" for r in entry.ranges
                )
                lines.append(f"{entry.weekday.value}: {ranges}")
            for holiday in p.holidays:
                lines.append(f"Closed {holiday.date.isoformat()}: {holiday.reason}".strip())
            docs.append(
                KnowledgeDocument(
                    business_id=p.id,
                    section=KnowledgeSection.HOURS,
                    title="Opening hours",
                    body="\n".join(lines),
                )
            )
        if p.services:
            service_lines = []
            for svc in p.services:
                price = (
                    f"{svc.price_currency} {svc.price_amount:.2f}"
                    if svc.price_amount is not None
                    else "price on request"
                )
                service_lines.append(
                    f"{svc.name} ({svc.id}): {svc.description} — {svc.duration_minutes} min, {price}"
                )
            docs.append(
                KnowledgeDocument(
                    business_id=p.id,
                    section=KnowledgeSection.SERVICES,
                    title="Services",
                    body="\n".join(service_lines),
                )
            )
        if p.faqs:
            faq_body = "\n".join(f"Q: {f.question}\nA: {f.answer}" for f in p.faqs)
            docs.append(
                KnowledgeDocument(
                    business_id=p.id,
                    section=KnowledgeSection.FAQ,
                    title="FAQs",
                    body=faq_body,
                )
            )
        if p.policies:
            docs.append(
                KnowledgeDocument(
                    business_id=p.id,
                    section=KnowledgeSection.POLICIES,
                    title="Policies",
                    body="\n".join(f"- {policy}" for policy in p.policies),
                )
            )
        contact_bits = [
            bit
            for bit in [
                f"Phone: {p.contact.phone}" if p.contact.phone else "",
                f"Email: {p.contact.email}" if p.contact.email else "",
                f"Address: {p.contact.address}" if p.contact.address else "",
                f"Website: {p.contact.website}" if p.contact.website else "",
            ]
            if bit
        ]
        if contact_bits:
            docs.append(
                KnowledgeDocument(
                    business_id=p.id,
                    section=KnowledgeSection.CONTACT,
                    title="Contact",
                    body="\n".join(contact_bits),
                )
            )
        docs.append(
            KnowledgeDocument(
                business_id=p.id,
                section=KnowledgeSection.ESCALATION,
                title="Escalation",
                body=p.escalation.human_handoff_message,
            )
        )
        return docs
