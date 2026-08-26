"""factory-boy factories for AI insights test data.

Provides DailyInsightRowFactory, DailyInsightResponseDictFactory, KpiSnapshotFactory,
DetectedProblemInputFactory and related builder helpers for building row dicts used
in unit and integration tests without a real DB connection.

Decisions locked by Phase 5 CONTEXT.md:
  D-01: Rich DailyInsightResponse schema (summary, problems[], positives[], warnings[],
        weekly_action_plan[]) — not the leaner REQUIREMENTS.md schema
  D-02: problems[] hard max 3, top-3 by estimated_loss_ron descending
  D-04: problems[].id = rule_id from detected_problems (traceable link)
  D-05: Full Pydantic schema with ActionItem, Problem, Positive, Warning
  D-06: User message = yesterday KPI snapshot + detected_problems rows
  D-14: status machine: success | fallback | failed
  D-15: Fallback uses same schema with "Generare AI eșuată" summary
  D-16: daily_insights table with all token/cost columns
  D-19: All monetary values as Decimal, never float
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import factory

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
TODAY = date(2026, 5, 28)


# ── ActionItem factory ─────────────────────────────────────────────────────────


class ActionItemFactory(factory.Factory):
    """Builds ActionItem dicts matching DailyInsightResponse.Problem.actions[].

    D-10: deadline must be a relative Romanian label (Azi, Mâine, etc.).
    D-12: expected_outcome must name a metric and target value.
    D-09: owner must be a real Sofa Belle salesperson name or role.
    """

    class Meta:
        model = dict

    order = 1
    description = "Contactați lead-urile noi în primele 2 ore"
    owner = "Roibu Valeria"
    deadline = "Azi"
    expected_outcome = "Rata de răspuns scade de la 3h la sub 2h"


# ── Problem factory ───────────────────────────────────────────────────────────


class ProblemFactory(factory.Factory):
    """Builds Problem dicts matching DailyInsightResponse.problems[].

    D-04: id = rule_id from detected_problems for traceable link.
    D-19: estimated_loss_ron as Decimal, not float.
    """

    class Meta:
        model = dict

    id = "slow_first_touch"
    severity = "high"
    category = "sales"
    title = "Timp de răspuns lent"
    description = (
        "3 lead-uri nu au fost contactate în primele 5 ore de business. "
        "Estimăm o pierdere de ~5.000 RON."
    )
    estimated_loss_ron = Decimal("5000.00")
    actions = factory.LazyFunction(lambda: [ActionItemFactory.build()])


# ── Positive factory ──────────────────────────────────────────────────────────


class PositiveFactory(factory.Factory):
    """Builds Positive dicts matching DailyInsightResponse.positives[].

    D-09: references real Sofa Belle salesperson names (Raileanu Leon).
    """

    class Meta:
        model = dict

    title = "Raileanu Leon — performanță excelentă"
    description = "8.3% conversie L→C"
    recommendation = "Distribuiți mai multe lead-uri showroom"


# ── Warning factory ───────────────────────────────────────────────────────────


class WarningFactory(factory.Factory):
    """Builds Warning dicts matching DailyInsightResponse.warnings[].

    Warnings are weak signals — not full problems with actions.
    """

    class Meta:
        model = dict

    title = "Oferte în așteptare"
    description = "2 oferte la limita de 14 zile fără activitate"


# ── DailyInsightResponseDict factory ─────────────────────────────────────────


class DailyInsightResponseDictFactory(factory.Factory):
    """Builds the full DailyInsightResponse payload as a plain dict.

    D-01: Rich schema — summary + problems[] + positives[] + warnings[] +
          weekly_action_plan[] + generated_at.
    D-02: problems[] hard max 3; factory builds 1 problem by default.
    D-03: weekly_action_plan is 5-7 flat action strings (Claude synthesizes it).
    D-19: estimated_loss_ron values as Decimal.
    """

    class Meta:
        model = dict

    summary = "Zi cu rezultate mixte. Există 3 probleme de prioritat înaltă."
    problems = factory.LazyFunction(lambda: [ProblemFactory.build()])
    positives = factory.LazyFunction(lambda: [PositiveFactory.build()])
    warnings = factory.LazyFunction(lambda: [WarningFactory.build()])
    weekly_action_plan = factory.LazyFunction(
        lambda: [
            "Acțiune 1",
            "Acțiune 2",
            "Acțiune 3",
            "Acțiune 4",
            "Acțiune 5",
        ]
    )
    generated_at = factory.LazyFunction(
        lambda: datetime(2026, 5, 28, 6, 0, 0, tzinfo=UTC)
    )


# ── DailyInsightRow factory (DB rows) ────────────────────────────────────────


class DailyInsightRowFactory(factory.Factory):
    """Builds daily_insights DB row dicts.

    D-16: Mirrors daily_insights table columns including status, token fields,
          cost_usd, raw_response, payload_json.
    D-14: status machine: success | fallback | failed.
    """

    class Meta:
        model = dict

    tenant_id = TENANT_ID
    date = factory.LazyFunction(lambda: TODAY)
    status = "success"
    payload_json = factory.LazyFunction(lambda: DailyInsightResponseDictFactory.build())
    generated_at = factory.LazyFunction(
        lambda: datetime(2026, 5, 28, 6, 5, 0, tzinfo=UTC)
    )
    input_tokens = 3000
    output_tokens = 2000
    cost_usd = Decimal("0.039000")
    raw_response = '{"summary": "test"}'


# ── KpiSnapshot factory ───────────────────────────────────────────────────────


class KpiSnapshotFactory(factory.Factory):
    """Builds daily_kpi row dicts for the user message KPI snapshot.

    D-06: Compact snapshot — leads_total, visits_count, offers_count,
          contracts_closed, conversion rates, wow_delta_pct, avg_deal_size.
    D-19: Conversion rates and deltas as Decimal.
    """

    class Meta:
        model = dict

    tenant_id = TENANT_ID
    date = TODAY
    leads_total = 12
    visits_count = 4
    offers_count = 5
    contracts_closed = 1
    conversion_l_to_v = Decimal("0.3333")
    conversion_v_to_o = Decimal("0.8000")
    conversion_o_to_c = Decimal("0.2000")
    conversion_l_to_c = Decimal("0.0833")
    avg_deal_size = Decimal("20000.00")
    wow_delta_pct = Decimal("-0.0500")
    mom_delta_pct = Decimal("0.1200")


# ── DetectedProblemInput factory (input to Claude) ────────────────────────────


class DetectedProblemInputFactory(factory.Factory):
    """Builds detected_problems row dicts as passed to build_user_message().

    D-06: Fields: rule_id, severity, estimated_loss_ron, current_value,
          expected_value, context_json.
    D-19: Monetary and numeric values as Decimal.
    AI-SPEC §4b.4: context_json filtered to strip PII before API call.
    """

    class Meta:
        model = dict

    rule_id = "slow_first_touch"
    severity = "high"
    estimated_loss_ron = Decimal("5000.00")
    current_value = Decimal("360.00")
    expected_value = Decimal("300.00")
    context_json = factory.LazyFunction(
        lambda: {"count": 2, "worst_hours_elapsed": 6.0}
    )


# ── Builder helpers ────────────────────────────────────────────────────────────


def make_insight_row(**overrides) -> dict:
    """Build a daily_insights DB row dict with optional field overrides.

    D-16: Convenience wrapper for DailyInsightRowFactory.build().
    """
    return DailyInsightRowFactory.build(**overrides)


def make_kpi_snapshot(**overrides) -> dict:
    """Build a compact daily_kpi snapshot dict with optional overrides.

    D-06: Used as the kpi_snapshot input to build_user_message().
    """
    return KpiSnapshotFactory.build(**overrides)


def make_detected_problem_input(**overrides) -> dict:
    """Build a detected_problems input row dict with optional overrides.

    D-06: Used as items in the detected_problems input to build_user_message().
    """
    return DetectedProblemInputFactory.build(**overrides)


def make_three_anomaly_day() -> list[dict]:
    """Build a list of 3 DetectedProblemInput dicts with distinct rule_ids.

    D-02: Simulates a day where 3 different anomaly rules fired.
    Returns top-3 by estimated_loss_ron descending (as Python pre-selects for Claude).

    Rule IDs used:
      1. slow_first_touch — high severity, 5000 RON estimated loss
      2. stuck_offer — medium severity, 3750 RON estimated loss
      3. junk_lead_quality — medium severity, 2640 RON estimated loss
    """
    return [
        DetectedProblemInputFactory.build(
            rule_id="slow_first_touch",
            severity="high",
            estimated_loss_ron=Decimal("5000.00"),
            current_value=Decimal("360.00"),
            expected_value=Decimal("300.00"),
            context_json={"count": 2, "worst_hours_elapsed": 6.0},
        ),
        DetectedProblemInputFactory.build(
            rule_id="stuck_offer",
            severity="medium",
            estimated_loss_ron=Decimal("3750.00"),
            current_value=Decimal("20.00"),
            expected_value=Decimal("15.00"),
            context_json={"count": 1, "days_stuck": 20},
        ),
        DetectedProblemInputFactory.build(
            rule_id="junk_lead_quality",
            severity="medium",
            estimated_loss_ron=Decimal("2640.00"),
            current_value=Decimal("26.70"),
            expected_value=Decimal("25.00"),
            context_json={"junk_count": 8, "total_leads": 30},
        ),
    ]
