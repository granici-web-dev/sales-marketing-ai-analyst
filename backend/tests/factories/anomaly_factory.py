from __future__ import annotations

"""factory-boy factories for anomaly detection test data.

Provides DetectedProblemRowFactory, LeadWithNoTouchFactory, StuckOfferLeadFactory
for building row dicts used in unit and integration tests without a real DB connection.

Decisions locked by Phase 4 CONTEXT.md:
  D-01: UPSERT on (tenant_id, date, rule_id) — one aggregate row per rule per day
  D-02: context_json holds count + lead_ids/salesperson_ids + key metric value
  D-06: slow_first_touch loss = count × avg_deal_size × 0.25
  D-07: stuck_offer loss = sum(estimated_value) × trailing_close_rate
  D-08: junk_lead_quality loss = junk_count × avg_deal_size × trailing_close_rate
  D-11: junk IDs computed once per run_all_rules() call
  D-20: thresholds locked — slow_first_touch 5h, stuck_offer 15d, drop 35%, sp 30%
"""

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

import factory

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
TODAY = date(2026, 5, 28)


class DetectedProblemRowFactory(factory.Factory):
    """Builds detected_problems row dicts with realistic Sofa Belle values.

    Meta.model = dict — produces plain dicts, not ORM instances.
    Usable without a database or SQLAlchemy session.

    D-01: One aggregate row per rule per day per tenant.
    D-19: All monetary columns as Decimal (NUMERIC(12,2)), never float.
    """

    class Meta:
        model = dict  # plain dicts — not ORM instances

    tenant_id = TENANT_ID
    date = factory.LazyFunction(lambda: TODAY)
    rule_id = "slow_first_touch"
    severity = "high"
    metric = "time_to_first_touch_minutes"
    current_value = Decimal("360.00")
    expected_value = Decimal("300.00")
    estimated_loss_ron = Decimal("5000.00")
    context_json = factory.LazyFunction(
        lambda: {"count": 2, "lead_ids": ["ext-001", "ext-002"], "worst_hours_elapsed": 6.0}
    )


class LeadWithNoTouchFactory(factory.Factory):
    """Builds raw_mefi_lead dict representing a yesterday-created lead with no contact attempt.

    Used to test slow_first_touch rule (ANOM-01, ANOM-02, D-14):
    - Lead created yesterday (kpi_date)
    - time_to_first_touch_minutes = None (no contact attempt)
    - lifecycle = active (not junk)

    D-14: slow_first_touch checks yesterday-only leads where time_to_first_touch > 300 minutes.
    """

    class Meta:
        model = dict

    tenant_id = TENANT_ID
    external_id = factory.Sequence(lambda n: f"lead-notouched-{n:04d}")
    created_at_local = factory.LazyFunction(lambda: TODAY)
    salesperson_external_id = "sp-001"
    time_to_first_touch_minutes = None  # no contact attempt
    lifecycle = "active"
    funnel_stage = "lead"


class StuckOfferLeadFactory(factory.Factory):
    """Builds a lead in 'oferta' stage with last_status_changed > 15 days ago.

    Used to test stuck_offer rule (ANOM-03, D-20):
    - funnel_stage = oferta
    - lifecycle = active
    - last_status_changed_at > 15 days ago (fires at 20 days by default)
    - estimated_value set for loss formula (D-07)

    D-07: stuck_offer loss = sum(estimated_value) × trailing_close_rate.
    """

    class Meta:
        model = dict

    tenant_id = TENANT_ID
    external_id = factory.Sequence(lambda n: f"lead-stuck-{n:04d}")
    funnel_stage = "oferta"
    lifecycle = "active"
    last_status_changed_at = factory.LazyFunction(lambda: TODAY - timedelta(days=20))
    estimated_value = Decimal("25000.00")


# ── Builder helpers ────────────────────────────────────────────────────────────


def make_detected_problem_row(**overrides) -> dict:
    """Build a detected_problems row dict with optional overrides.

    Delegates to DetectedProblemRowFactory.build() so overrides are
    applied on top of the factory defaults.

    D-01: Useful for testing UPSERT idempotency and conflict resolution.
    """
    return DetectedProblemRowFactory.build(**overrides)


def make_daily_kpi_baseline_rows(n: int = 30, kpi_date: date = TODAY) -> list[dict]:
    """Build n daily_kpi row dicts for the trailing baseline window.

    Returns n dicts representing daily_kpi rows for the baseline calculation window.
    Each row has a different date, counting back from kpi_date - 1.

    Used for testing trend-based anomaly rules (ANOM-04, ANOM-05) that require
    at least 7 baseline rows (D-13: 7-day minimum baseline window).

    Args:
        n: Number of baseline rows to generate (default 30).
        kpi_date: The reference date; rows cover [kpi_date-n, kpi_date-1].

    Returns:
        List of n dicts with tenant_id, date, conversion_l_to_v, conversion_o_to_c, avg_deal_size.
    """
    return [
        {
            "tenant_id": TENANT_ID,
            "date": kpi_date - timedelta(days=i),
            "conversion_l_to_v": Decimal("0.3200"),
            "conversion_o_to_c": Decimal("0.1500"),
            "avg_deal_size": Decimal("22000.00"),
        }
        for i in range(1, n + 1)
    ]
