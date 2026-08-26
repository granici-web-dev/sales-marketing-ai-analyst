"""factory-boy factories for metric table test data.

Provides DailyKpiRowFactory, SalespersonKpiRowFactory, SourceKpiRowFactory
for building row dicts used in unit tests without a real DB connection.

Decisions locked by Phase 3 CONTEXT.md:
  D-04: 7 source categories per day: mail_fb_ig | telefon | whatsapp | site | designer | alte | google
  D-11: NULL deltas when prior data absent (not zero)
  D-16: Revenue as Decimal, never float (NUMERIC(12,2))
  D-17: Only active salespeople (is_active=True) in salesperson rows
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import factory

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
TODAY = date(2026, 5, 24)

# D-04: All 7 source categories in canonical order (CONTEXT.md D-04)
SOURCE_CATEGORIES = ["mail_fb_ig", "telefon", "whatsapp", "site", "designer", "alte", "google"]


class DailyKpiRowFactory(factory.Factory):
    """Builds daily_kpi row dicts with realistic Sofa Belle values.

    Meta.model = dict — produces plain dicts, not ORM instances.
    Usable without a database or SQLAlchemy session.
    """

    class Meta:
        model = dict  # plain dicts — not ORM instances

    tenant_id = TENANT_ID
    date = factory.LazyFunction(lambda: TODAY)

    # Lead volume (METR-03 — 7 categories in daily_kpi)
    leads_total = factory.Sequence(lambda n: 10 + n)
    leads_mail_fb_ig = factory.LazyAttribute(lambda o: max(0, o.leads_total // 3))
    leads_telefon = factory.LazyAttribute(lambda o: max(0, o.leads_total // 6))
    leads_whatsapp = factory.LazyAttribute(lambda o: max(0, o.leads_total // 8))
    leads_site = factory.LazyAttribute(lambda o: max(0, o.leads_total // 5))
    leads_designer = factory.LazyAttribute(lambda o: max(0, o.leads_total // 10))
    leads_alte = factory.LazyAttribute(lambda o: max(0, o.leads_total // 12))

    # Funnel counts (METR-01)
    visits_count = factory.LazyAttribute(lambda o: max(1, o.leads_total // 2))
    offers_count = factory.LazyAttribute(lambda o: max(0, o.visits_count // 2))
    contracts_count = factory.LazyAttribute(lambda o: max(0, o.offers_count // 3))

    # Conversion rates (NUMERIC(5,4) — zero-division guarded — METR-02, SC#2)
    conversion_l_to_v = factory.LazyFunction(lambda: Decimal("0.4000"))
    conversion_v_to_o = factory.LazyFunction(lambda: Decimal("0.5000"))
    conversion_l_to_o = factory.LazyFunction(lambda: Decimal("0.2000"))
    conversion_o_to_c = factory.LazyFunction(lambda: Decimal("0.2500"))
    conversion_l_to_c = factory.LazyFunction(lambda: Decimal("0.0500"))

    # Revenue (NUMERIC(12,2) — D-16: Decimal, never float)
    revenue = factory.LazyFunction(lambda: Decimal("15000.00"))
    avg_deal_size = factory.LazyFunction(lambda: Decimal("15000.00"))

    # WoW/MoM deltas — NULL when no prior data (D-11, METR-05)
    leads_total_wow_delta = None
    leads_total_mom_delta = None
    conversion_l_to_v_wow_delta = None
    conversion_l_to_v_mom_delta = None
    conversion_v_to_o_wow_delta = None
    conversion_v_to_o_mom_delta = None
    conversion_l_to_o_wow_delta = None
    conversion_l_to_o_mom_delta = None
    conversion_o_to_c_wow_delta = None
    conversion_o_to_c_mom_delta = None
    conversion_l_to_c_wow_delta = None
    conversion_l_to_c_mom_delta = None
    revenue_wow_delta = None
    revenue_mom_delta = None
    avg_deal_size_wow_delta = None
    avg_deal_size_mom_delta = None

    # Nullable columns (populated in future iterations)
    spend_meta = None
    spend_google = None
    spend_tiktok = None
    spend_digital_total = None
    web_sessions = None
    web_conversion_rate = None
    cpl_overall = None
    cpl_by_channel = None
    cac = None
    roas = None
    calls_total = None
    calls_answered = None
    calls_missed = None
    avg_call_duration_seconds = None
    avg_sentiment_score = None

    calculated_at = factory.LazyFunction(lambda: datetime.now(UTC))


class SalespersonKpiRowFactory(factory.Factory):
    """Builds salesperson_daily_kpi row dicts with Sofa Belle defaults.

    D-17: Represents an active salesperson (is_active=True filter applied upstream).
    Meta.model = dict — plain dicts.
    """

    class Meta:
        model = dict

    tenant_id = TENANT_ID
    date = factory.LazyFunction(lambda: TODAY)
    salesperson_external_id = factory.Sequence(lambda n: str(100 + n))

    # Per-salesperson KPIs (METR-04)
    leads_assigned = factory.Sequence(lambda n: 3 + n)
    leads_contacted = factory.LazyAttribute(lambda o: max(0, o.leads_assigned - 1))
    visits_conducted = factory.LazyAttribute(lambda o: max(0, o.leads_assigned // 2))
    offers_sent = factory.LazyAttribute(lambda o: max(0, o.visits_conducted // 2))
    deals_won = factory.LazyAttribute(lambda o: max(0, o.offers_sent // 3))
    deals_lost = factory.LazyFunction(lambda: 0)

    # Revenue (D-16: Decimal)
    revenue = factory.LazyFunction(lambda: Decimal("0.00"))
    avg_deal_size = factory.LazyFunction(lambda: Decimal("0.00"))

    # Conversion rates per salesperson
    conversion_l_to_v = factory.LazyFunction(lambda: Decimal("0.5000"))
    conversion_v_to_o = factory.LazyFunction(lambda: Decimal("0.5000"))
    conversion_o_to_c = factory.LazyFunction(lambda: Decimal("0.3000"))
    conversion_l_to_c = factory.LazyFunction(lambda: Decimal("0.1500"))

    # time_to_first_touch — in minutes, business-hours adjusted (D-06)
    # NULL when no history (D-05); default to typical 45-min response
    avg_time_to_first_touch_minutes = factory.LazyFunction(lambda: 45)

    # METR-06: data_completeness_pct — % of leads with estimated_value set
    # NUMERIC(5,2) — e.g. 80.00 = 80%
    data_completeness_pct = factory.LazyFunction(lambda: Decimal("80.00"))

    # Nullable (future telephony)
    calls_made = None
    calls_answered = None
    avg_call_duration_seconds = None
    avg_sentiment_score = None

    calculated_at = factory.LazyFunction(lambda: datetime.now(UTC))


class SourceKpiRowFactory(factory.Factory):
    """Builds source_daily_kpi row dicts for a single source category.

    D-04: source column uses funnel_config category names (not SPEC.md generic names).
    7 rows per day per tenant — one per category.
    Meta.model = dict — plain dicts.
    """

    class Meta:
        model = dict

    tenant_id = TENANT_ID
    date = factory.LazyFunction(lambda: TODAY)
    source = "mail_fb_ig"  # default — override per test

    # METR-03: per-source metrics
    leads = factory.Sequence(lambda n: max(0, 5 - n))
    visits = factory.LazyAttribute(lambda o: max(0, o.leads // 2))
    offers = factory.LazyAttribute(lambda o: max(0, o.visits // 2))
    deals_won = factory.LazyAttribute(lambda o: max(0, o.offers // 3))
    revenue = factory.LazyFunction(lambda: Decimal("0.00"))
    conversion_rate = factory.LazyFunction(lambda: Decimal("0.0000"))

    # Nullable (ad spend populated in Iteration 2)
    ad_spend = None
    cpl = None
    cac = None
    roas = None

    calculated_at = factory.LazyFunction(lambda: datetime.now(UTC))


# ── Builder helpers ────────────────────────────────────────────────────────────


def make_designer_source_row(
    kpi_date: date = TODAY,
    leads: int = 5,
) -> dict:
    """Build a source_daily_kpi row for the 'designer' category.

    D-02: Designer leads derived from status_id=24 in mefi_lead_history.
    Designer is a MEFI status, not a source_id mapping.
    """
    return SourceKpiRowFactory.build(
        source="designer",
        date=kpi_date,
        leads=leads,
    )


def make_seven_source_rows(kpi_date: date = TODAY) -> list[dict]:
    """Build one row per source category for a given date (7 rows — D-04).

    D-04: Exactly 7 categories in canonical order:
    mail_fb_ig | telefon | whatsapp | site | designer | alte | google

    Used in tests asserting that all 7 categories are always emitted,
    even when some have 0 leads.
    """
    return [SourceKpiRowFactory.build(source=cat, date=kpi_date) for cat in SOURCE_CATEGORIES]


def make_daily_kpi_with_deltas(
    kpi_date: date = TODAY,
    leads_total: int = 20,
    prior_leads: int = 16,
) -> dict:
    """Build a daily_kpi row with WoW delta pre-calculated.

    Used for testing delta arithmetic (METR-05):
    wow_delta = (current - prior) / prior
    """
    prior_d = Decimal(str(prior_leads))
    current_d = Decimal(str(leads_total))
    wow = (current_d - prior_d) / prior_d if prior_d != 0 else None

    return DailyKpiRowFactory.build(
        date=kpi_date,
        leads_total=leads_total,
        leads_total_wow_delta=wow,
    )
