from __future__ import annotations

"""factory-boy factories for MEFI lead test data.

Provides LeadResponseFactory and CustomFieldFactory for building
MefiLeadResponse instances in unit and integration tests without
needing a real MEFI API connection.
"""

from decimal import Decimal

import factory

from app.schemas.mefi import MefiCustomField, MefiLeadResponse


class CustomFieldFactory(factory.Factory):
    """Builds MefiCustomField instances for testing."""

    class Meta:
        model = MefiCustomField

    field_id = factory.Sequence(lambda n: n + 1)
    value = factory.Faker("word")


class LeadResponseFactory(factory.Factory):
    """Builds MefiLeadResponse instances with realistic Sofa Belle data."""

    class Meta:
        model = MefiLeadResponse

    id = factory.Sequence(lambda n: n + 1000)
    lifecycle = "active"
    estimated_value = factory.LazyFunction(lambda: Decimal("2500.00"))
    custom_fields = factory.LazyFunction(list)
    priority = None
    is_duplicate = False
    created_at = None
    last_contact_at = None
    status_changed_at = None
    status = None
    source = None
    assigned_to = None


def make_showroom_lead(showroom: str = "Brașov", status_id: int = 17) -> MefiLeadResponse:
    """Build a lead with showroom custom field set."""
    cf = MefiCustomField(field_id=14, value=showroom)
    lead = LeadResponseFactory.build(
        custom_fields=[cf],
    )
    return lead


def make_offer_lead(sent: bool = True) -> MefiLeadResponse:
    """Build a lead with offer_sent custom field set."""
    value = "✅DA" if sent else "❌NU"
    cf = MefiCustomField(field_id=20, value=value)
    return LeadResponseFactory.build(custom_fields=[cf])
