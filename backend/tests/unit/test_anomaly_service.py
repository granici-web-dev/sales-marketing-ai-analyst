from __future__ import annotations

"""Unit tests for AnomalyService — RED-state contracts for Phase 4 anomaly detection.

Tests mock AsyncSession — no live DB required.
All tests will fail with ImportError until Plan 04-02 (Wave 1) implements
app.services.anomaly.anomaly_service.AnomalyService.

Requirements: ANOM-01, ANOM-02, ANOM-03, ANOM-04, ANOM-05, ANOM-06, ANOM-07

Rule-specific specs:
  ANOM-01: AnomalyService class with run_all_rules() orchestrator
  ANOM-02: slow_first_touch — lead no contact 5+ business hours (D-06, D-14, D-20)
  ANOM-03: stuck_offer — oferta stage 15+ days (D-07, D-20)
  ANOM-04: showroom_traffic_drop — L→V drops 35%+ below baseline (D-04, D-05, D-13, D-20)
  ANOM-05: underperforming_salesperson — win rate 30%+ below team avg (D-03, D-05, D-20)
  ANOM-06: junk_lead_quality — junk rate 25%+ of total (D-08, D-11, D-20)
  ANOM-07: junk IDs computed once and passed to all non-junk rules (D-11)
"""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
TODAY = date(2026, 5, 28)


def _make_service(mock_session=None):
    """Build AnomalyService with mocked AsyncSession.

    Import is deferred so the file parses (RED) even before Plan 04-02 implements AnomalyService.
    Returns (service, session) tuple.
    """
    from app.services.anomaly.anomaly_service import AnomalyService  # noqa: PLC0415

    session = mock_session or AsyncMock()
    return AnomalyService(session, TENANT_ID), session


class TestDetectSlowFirstTouch:
    """Tests for AnomalyService.detect_slow_first_touch() — ANOM-02, D-06, D-14, D-20."""

    @pytest.mark.asyncio
    async def test_fires_when_lead_has_no_touch_in_5_business_hours(self) -> None:
        """Lead created yesterday, time_to_first_touch_minutes = 360 → fires slow_first_touch.

        ANOM-02: slow_first_touch fires when a yesterday lead has 360 business minutes
        elapsed without contact (360 > 300 threshold from D-20).
        Returns DetectedProblem dict with rule_id="slow_first_touch", severity="high".

        D-20: slow_first_touch threshold = 5 business hours = 300 minutes.
        D-06: loss = count × avg_deal_size × 0.25.
        D-16: business hours Mon–Sun 09:00–19:00 Europe/Bucharest.
        """
        service, session = _make_service()

        # Feed one lead with 360-minute delay (> 300 threshold)
        leads = [
            {
                "tenant_id": TENANT_ID,
                "external_id": "lead-001",
                "created_at_local": TODAY - timedelta(days=1),
                "time_to_first_touch_minutes": 360,
                "lifecycle": "active",
            }
        ]
        baseline = [
            {
                "avg_deal_size": Decimal("22000.00"),
                "conversion_o_to_c": Decimal("0.15"),
            }
        ]

        result = await service.detect_slow_first_touch(  # type: ignore[attr-defined]
            kpi_date=TODAY,
            slow_leads=leads,
            baseline_rows=baseline,
            junk_ids=set(),
        )

        assert result is not None, "detect_slow_first_touch must return a DetectedProblem row"
        assert result["rule_id"] == "slow_first_touch", (
            f"rule_id must be 'slow_first_touch', got '{result.get('rule_id')}'"
        )
        assert result["severity"] == "high", (
            f"severity must be 'high' for slow_first_touch (ROADMAP SC#2), got '{result.get('severity')}'"
        )
        assert result["tenant_id"] == TENANT_ID

    @pytest.mark.asyncio
    async def test_skips_when_lead_created_outside_business_hours(self) -> None:
        """Lead with business-hours-adjusted time_to_first_touch = 0 → returns None.

        ROADMAP SC#2: leads created outside business hours (e.g., 23:00) get adjusted
        time_to_first_touch = 0 if first touch is before 09:00 next day.
        slow_first_touch must not fire when adjusted minutes <= 0.
        """
        service, session = _make_service()

        # Lead with zero business-hours-adjusted time (e.g., outside-hours creation)
        leads = [
            {
                "tenant_id": TENANT_ID,
                "external_id": "lead-afterhours-001",
                "created_at_local": TODAY - timedelta(days=1),
                "time_to_first_touch_minutes": 0,  # adjusted to 0 — created outside hours
                "lifecycle": "active",
            }
        ]
        baseline = [{"avg_deal_size": Decimal("22000.00"), "conversion_o_to_c": Decimal("0.15")}]

        result = await service.detect_slow_first_touch(  # type: ignore[attr-defined]
            kpi_date=TODAY,
            slow_leads=leads,
            baseline_rows=baseline,
            junk_ids=set(),
        )

        assert result is None, (
            "detect_slow_first_touch must return None when lead time = 0 "
            "(adjusted outside-hours creation — ROADMAP SC#2)"
        )

    @pytest.mark.asyncio
    async def test_skips_junk_leads(self) -> None:
        """Lead in junk_ids set → excluded from slow_first_touch count (D-11, ANOM-07).

        D-11: junk IDs computed once and passed to all non-junk rules.
        Junk leads must be excluded from slow_first_touch analysis even if
        time_to_first_touch_minutes > 300.
        """
        service, session = _make_service()

        junk_lead_id = "lead-junk-001"
        leads = [
            {
                "tenant_id": TENANT_ID,
                "external_id": junk_lead_id,
                "created_at_local": TODAY - timedelta(days=1),
                "time_to_first_touch_minutes": 720,  # 12 hours — would fire without junk exclusion
                "lifecycle": "active",
            }
        ]
        baseline = [{"avg_deal_size": Decimal("22000.00"), "conversion_o_to_c": Decimal("0.15")}]

        result = await service.detect_slow_first_touch(  # type: ignore[attr-defined]
            kpi_date=TODAY,
            slow_leads=leads,
            baseline_rows=baseline,
            junk_ids={junk_lead_id},  # lead is in junk set — must be excluded
        )

        assert result is None, (
            "detect_slow_first_touch must return None when all affected leads are junk "
            "(D-11 junk exclusion, ANOM-07)"
        )

    @pytest.mark.asyncio
    async def test_loss_formula_uses_drop_factor_025(self) -> None:
        """Loss = count × avg_deal_size × 0.25 (D-06 drop factor).

        D-06: slow_first_touch estimated_loss_ron = count_affected × avg_deal_size × 0.25.
        The 0.25 factor represents 25% reduced close probability from slow response.
        With 1 lead and avg_deal_size=22000: loss = 1 × 22000 × 0.25 = 5500 RON.
        """
        service, session = _make_service()

        leads = [
            {
                "tenant_id": TENANT_ID,
                "external_id": "lead-001",
                "created_at_local": TODAY - timedelta(days=1),
                "time_to_first_touch_minutes": 360,
                "lifecycle": "active",
            }
        ]
        baseline = [{"avg_deal_size": Decimal("22000.00"), "conversion_o_to_c": Decimal("0.15")}]

        result = await service.detect_slow_first_touch(  # type: ignore[attr-defined]
            kpi_date=TODAY,
            slow_leads=leads,
            baseline_rows=baseline,
            junk_ids=set(),
        )

        assert result is not None
        expected_loss = Decimal("1") * Decimal("22000.00") * Decimal("0.25")  # = 5500.00
        assert result["estimated_loss_ron"] == expected_loss, (
            f"estimated_loss_ron must be count × avg_deal_size × 0.25 = {expected_loss}, "
            f"got {result.get('estimated_loss_ron')} (D-06)"
        )


class TestDetectStuckOffer:
    """Tests for AnomalyService.detect_stuck_offer() — ANOM-03, D-07, D-20."""

    @pytest.mark.asyncio
    async def test_fires_when_offer_no_change_15_days(self) -> None:
        """Lead in oferta stage, last_changed 20 days ago → rule_id="stuck_offer", severity="medium".

        ANOM-03: stuck_offer fires when a lead in 'oferta' stage has not changed
        status for 15+ days (D-20 threshold).
        Severity is "medium" per ROADMAP SC#3.
        """
        service, session = _make_service()

        stuck_leads = [
            {
                "tenant_id": TENANT_ID,
                "external_id": "lead-stuck-001",
                "funnel_stage": "oferta",
                "lifecycle": "active",
                "last_status_changed_at": TODAY - timedelta(days=20),
                "estimated_value": Decimal("25000.00"),
            }
        ]
        baseline = [{"avg_deal_size": Decimal("22000.00"), "conversion_o_to_c": Decimal("0.15")}]

        result = await service.detect_stuck_offer(  # type: ignore[attr-defined]
            kpi_date=TODAY,
            stuck_leads=stuck_leads,
            baseline_rows=baseline,
        )

        assert result is not None, "detect_stuck_offer must fire for leads stuck 20 days (>15 threshold)"
        assert result["rule_id"] == "stuck_offer", (
            f"rule_id must be 'stuck_offer', got '{result.get('rule_id')}'"
        )
        assert result["severity"] == "medium", (
            f"severity must be 'medium' for stuck_offer (ROADMAP SC#3), got '{result.get('severity')}'"
        )

    @pytest.mark.asyncio
    async def test_loss_formula_sum_estimated_value_times_close_rate(self) -> None:
        """estimated_value=25000, close_rate=0.15 → estimated_loss = 3750 (D-07).

        D-07: stuck_offer loss = sum(estimated_value of stuck offers) × trailing_close_rate.
        Single lead: 25000 × 0.15 = 3750 RON.
        """
        service, session = _make_service()

        stuck_leads = [
            {
                "tenant_id": TENANT_ID,
                "external_id": "lead-stuck-001",
                "funnel_stage": "oferta",
                "lifecycle": "active",
                "last_status_changed_at": TODAY - timedelta(days=20),
                "estimated_value": Decimal("25000.00"),
            }
        ]
        baseline = [{"avg_deal_size": Decimal("22000.00"), "conversion_o_to_c": Decimal("0.15")}]

        result = await service.detect_stuck_offer(  # type: ignore[attr-defined]
            kpi_date=TODAY,
            stuck_leads=stuck_leads,
            baseline_rows=baseline,
        )

        assert result is not None
        expected_loss = Decimal("25000.00") * Decimal("0.15")  # = 3750.00
        assert result["estimated_loss_ron"] == expected_loss, (
            f"estimated_loss_ron must be sum(estimated_value) × close_rate = {expected_loss}, "
            f"got {result.get('estimated_loss_ron')} (D-07)"
        )

    @pytest.mark.asyncio
    async def test_null_estimated_value_contributes_zero(self) -> None:
        """Lead with estimated_value=None → adds 0 to sum (D-07 no imputation).

        D-07: leads where estimated_value IS NULL contribute 0 to the sum.
        Two leads, one with value=20000, one with value=None:
        total = 20000 × 0.15 = 3000 (not 2×20000×0.15).
        """
        service, session = _make_service()

        stuck_leads = [
            {
                "tenant_id": TENANT_ID,
                "external_id": "lead-stuck-001",
                "funnel_stage": "oferta",
                "lifecycle": "active",
                "last_status_changed_at": TODAY - timedelta(days=20),
                "estimated_value": Decimal("20000.00"),
            },
            {
                "tenant_id": TENANT_ID,
                "external_id": "lead-stuck-002",
                "funnel_stage": "oferta",
                "lifecycle": "active",
                "last_status_changed_at": TODAY - timedelta(days=16),
                "estimated_value": None,  # NULL — contributes 0 (D-07)
            },
        ]
        baseline = [{"avg_deal_size": Decimal("22000.00"), "conversion_o_to_c": Decimal("0.15")}]

        result = await service.detect_stuck_offer(  # type: ignore[attr-defined]
            kpi_date=TODAY,
            stuck_leads=stuck_leads,
            baseline_rows=baseline,
        )

        assert result is not None
        # sum = 20000 + 0 = 20000; loss = 20000 × 0.15 = 3000
        expected_loss = Decimal("20000.00") * Decimal("0.15")
        assert result["estimated_loss_ron"] == expected_loss, (
            f"NULL estimated_value must contribute 0 (not avg imputation), "
            f"expected loss={expected_loss}, got {result.get('estimated_loss_ron')} (D-07)"
        )


class TestDetectShowroomTrafficDrop:
    """Tests for AnomalyService.detect_showroom_traffic_drop() — ANOM-04, D-05, D-13, D-20."""

    @pytest.mark.asyncio
    async def test_fires_when_l_to_v_drops_35pct_below_baseline(self) -> None:
        """baseline=0.32, current=0.20 → 37.5% drop → fires showroom_traffic_drop.

        ANOM-04: fires when current L→V conversion drops 35%+ below trailing baseline.
        D-20: 35% threshold — (0.32 - 0.20) / 0.32 = 0.375 = 37.5% → fires.
        """
        service, session = _make_service()

        from tests.factories.anomaly_factory import make_daily_kpi_baseline_rows  # noqa: PLC0415

        baseline_rows = make_daily_kpi_baseline_rows(30)  # 30 days of baseline
        current_kpi = {
            "tenant_id": TENANT_ID,
            "date": TODAY,
            "conversion_l_to_v": Decimal("0.20"),  # 37.5% below baseline 0.32
            "avg_deal_size": Decimal("22000.00"),
            "conversion_o_to_c": Decimal("0.15"),
        }

        result = await service.detect_showroom_traffic_drop(  # type: ignore[attr-defined]
            kpi_date=TODAY,
            current_kpi=current_kpi,
            baseline_rows=baseline_rows,
        )

        assert result is not None, (
            "detect_showroom_traffic_drop must fire when L→V drops 37.5% below baseline "
            "(35% threshold, D-20, ANOM-04)"
        )
        assert result["rule_id"] == "showroom_traffic_drop"

    @pytest.mark.asyncio
    async def test_skips_when_drop_below_35pct_threshold(self) -> None:
        """baseline=0.32, current=0.22 → 31.25% drop → no row (below 35% threshold).

        D-20: 35% threshold — (0.32 - 0.22) / 0.32 = 0.3125 = 31.25% → no fire.
        """
        service, session = _make_service()

        from tests.factories.anomaly_factory import make_daily_kpi_baseline_rows  # noqa: PLC0415

        baseline_rows = make_daily_kpi_baseline_rows(30)
        current_kpi = {
            "tenant_id": TENANT_ID,
            "date": TODAY,
            "conversion_l_to_v": Decimal("0.22"),  # 31.25% drop — below 35% threshold
            "avg_deal_size": Decimal("22000.00"),
            "conversion_o_to_c": Decimal("0.15"),
        }

        result = await service.detect_showroom_traffic_drop(  # type: ignore[attr-defined]
            kpi_date=TODAY,
            current_kpi=current_kpi,
            baseline_rows=baseline_rows,
        )

        assert result is None, (
            "detect_showroom_traffic_drop must return None when drop is 31.25% "
            "(below 35% threshold, D-20)"
        )

    @pytest.mark.asyncio
    async def test_skips_when_fewer_than_7_baseline_rows(self) -> None:
        """available_days=5 → rule skipped, no row (D-13 minimum 7-day baseline).

        D-13: For trend-based rules requiring historical daily_kpi data,
        use 7-day minimum. If < 7 rows exist, skip rule entirely.
        """
        service, session = _make_service()

        from tests.factories.anomaly_factory import make_daily_kpi_baseline_rows  # noqa: PLC0415

        baseline_rows = make_daily_kpi_baseline_rows(5)  # only 5 rows — below 7-day minimum
        current_kpi = {
            "tenant_id": TENANT_ID,
            "date": TODAY,
            "conversion_l_to_v": Decimal("0.10"),  # extreme drop — would fire with enough baseline
            "avg_deal_size": Decimal("22000.00"),
            "conversion_o_to_c": Decimal("0.15"),
        }

        result = await service.detect_showroom_traffic_drop(  # type: ignore[attr-defined]
            kpi_date=TODAY,
            current_kpi=current_kpi,
            baseline_rows=baseline_rows,
        )

        assert result is None, (
            "detect_showroom_traffic_drop must return None when fewer than 7 baseline rows "
            "exist (D-13 minimum window)"
        )


class TestDetectUnderperformingSalesperson:
    """Tests for AnomalyService.detect_underperforming_salesperson() — ANOM-05, D-03, D-05, D-20."""

    @pytest.mark.asyncio
    async def test_fires_when_win_rate_30pct_below_team_avg(self) -> None:
        """team_avg=0.06, sp_win_rate=0.04 → 33% below → fires underperforming_salesperson.

        ANOM-05: fires when a salesperson's win rate is 30%+ below the team average.
        D-20: 30% threshold — (0.06 - 0.04) / 0.06 = 0.333 = 33.3% → fires.
        """
        service, session = _make_service()

        salesperson_kpis = [
            {
                "tenant_id": TENANT_ID,
                "salesperson_external_id": "sp-001",
                "conversion_o_to_c": Decimal("0.04"),  # 33% below team avg 0.06 → fires
                "deals_won": 2,
            },
            {
                "tenant_id": TENANT_ID,
                "salesperson_external_id": "sp-002",
                "conversion_o_to_c": Decimal("0.07"),
                "deals_won": 5,
            },
            {
                "tenant_id": TENANT_ID,
                "salesperson_external_id": "sp-003",
                "conversion_o_to_c": Decimal("0.07"),
                "deals_won": 5,
            },
        ]
        baseline = [{"avg_deal_size": Decimal("22000.00"), "conversion_o_to_c": Decimal("0.15")}]

        result = await service.detect_underperforming_salesperson(  # type: ignore[attr-defined]
            kpi_date=TODAY,
            salesperson_kpis=salesperson_kpis,
            baseline_rows=baseline,
        )

        assert result is not None, (
            "detect_underperforming_salesperson must fire when sp win rate is 33% "
            "below team avg (30% threshold, ANOM-05, D-20)"
        )
        assert result["rule_id"] == "underperforming_salesperson"

    @pytest.mark.asyncio
    async def test_salesperson_id_in_context_json(self) -> None:
        """context_json contains salesperson_ids list (D-03).

        D-03: Salesperson-based rules use aggregate model — salesperson_ids list in context_json.
        context_json example: {"count": 1, "salesperson_ids": ["sp-001"], "details": [...]}.
        """
        service, session = _make_service()

        salesperson_kpis = [
            {
                "tenant_id": TENANT_ID,
                "salesperson_external_id": "sp-001",
                "conversion_o_to_c": Decimal("0.02"),  # very low — fires
                "deals_won": 1,
            },
            {
                "tenant_id": TENANT_ID,
                "salesperson_external_id": "sp-002",
                "conversion_o_to_c": Decimal("0.10"),
                "deals_won": 8,
            },
        ]
        baseline = [{"avg_deal_size": Decimal("22000.00"), "conversion_o_to_c": Decimal("0.15")}]

        result = await service.detect_underperforming_salesperson(  # type: ignore[attr-defined]
            kpi_date=TODAY,
            salesperson_kpis=salesperson_kpis,
            baseline_rows=baseline,
        )

        assert result is not None
        assert "salesperson_ids" in result.get("context_json", {}), (
            "context_json must contain 'salesperson_ids' for salesperson-based rules (D-03)"
        )
        assert "sp-001" in result["context_json"]["salesperson_ids"], (
            "Underperforming salesperson ID must appear in context_json.salesperson_ids"
        )

    @pytest.mark.asyncio
    async def test_skips_when_only_one_salesperson(self) -> None:
        """Cannot compute team avg with 1 person → no row.

        A team average requires at least 2 salespeople. With only 1,
        there is no meaningful comparison — skip the rule.
        """
        service, session = _make_service()

        salesperson_kpis = [
            {
                "tenant_id": TENANT_ID,
                "salesperson_external_id": "sp-001",
                "conversion_o_to_c": Decimal("0.01"),  # would fire if team avg existed
                "deals_won": 0,
            }
        ]
        baseline = [{"avg_deal_size": Decimal("22000.00"), "conversion_o_to_c": Decimal("0.15")}]

        result = await service.detect_underperforming_salesperson(  # type: ignore[attr-defined]
            kpi_date=TODAY,
            salesperson_kpis=salesperson_kpis,
            baseline_rows=baseline,
        )

        assert result is None, (
            "detect_underperforming_salesperson must return None with only 1 salesperson "
            "(no meaningful team average can be computed)"
        )


class TestDetectJunkLeadQuality:
    """Tests for AnomalyService.detect_junk_lead_quality() — ANOM-06, D-08, D-11, D-20."""

    @pytest.mark.asyncio
    async def test_fires_when_junk_rate_gte_25pct(self) -> None:
        """30 total leads, 8 junk → 26.7% → fires junk_lead_quality.

        ANOM-06: fires when junk lead rate reaches 25%+ of total.
        NOTE: CONTEXT.md D-20 + ROADMAP SC#6 lock threshold at 25%.
        REQUIREMENTS.md baseline says 20% but D-20 overrides to 25%.
        30 total, 8 junk → 8/30 = 26.7% → fires.
        """
        service, session = _make_service()

        total_leads = 30
        junk_count = 8  # 26.7% — above 25% threshold

        baseline = [{"avg_deal_size": Decimal("22000.00"), "conversion_o_to_c": Decimal("0.15")}]

        result = await service.detect_junk_lead_quality(  # type: ignore[attr-defined]
            kpi_date=TODAY,
            total_leads=total_leads,
            junk_count=junk_count,
            baseline_rows=baseline,
        )

        assert result is not None, (
            "detect_junk_lead_quality must fire when junk rate = 26.7% >= 25% threshold "
            "(D-20, ANOM-06)"
        )
        assert result["rule_id"] == "junk_lead_quality"

    @pytest.mark.asyncio
    async def test_skips_when_junk_rate_below_25pct(self) -> None:
        """30 total, 6 junk → 20% → no row (below 25% threshold from D-20).

        D-20 / ROADMAP SC#6: threshold is 25%, not 20%.
        30 total, 6 junk → 6/30 = 20% → does NOT fire.
        """
        service, session = _make_service()

        total_leads = 30
        junk_count = 6  # 20% — below 25% threshold

        baseline = [{"avg_deal_size": Decimal("22000.00"), "conversion_o_to_c": Decimal("0.15")}]

        result = await service.detect_junk_lead_quality(  # type: ignore[attr-defined]
            kpi_date=TODAY,
            total_leads=total_leads,
            junk_count=junk_count,
            baseline_rows=baseline,
        )

        assert result is None, (
            "detect_junk_lead_quality must return None when junk rate = 20% < 25% threshold "
            "(D-20 overrides REQUIREMENTS.md baseline of 20% → use 25%)"
        )

    @pytest.mark.asyncio
    async def test_loss_formula_junk_count_times_deal_size_times_close_rate(self) -> None:
        """8 × 22000 × 0.15 = 26400 (D-08).

        D-08: junk_lead_quality loss = junk_lead_count × avg_deal_size × trailing_close_rate.
        8 × 22000 × 0.15 = 26400 RON.
        """
        service, session = _make_service()

        total_leads = 30
        junk_count = 8

        baseline = [{"avg_deal_size": Decimal("22000.00"), "conversion_o_to_c": Decimal("0.15")}]

        result = await service.detect_junk_lead_quality(  # type: ignore[attr-defined]
            kpi_date=TODAY,
            total_leads=total_leads,
            junk_count=junk_count,
            baseline_rows=baseline,
        )

        assert result is not None
        expected_loss = Decimal("8") * Decimal("22000.00") * Decimal("0.15")  # = 26400.00
        assert result["estimated_loss_ron"] == expected_loss, (
            f"estimated_loss_ron must be junk_count × avg_deal_size × close_rate = {expected_loss}, "
            f"got {result.get('estimated_loss_ron')} (D-08)"
        )


class TestRunAllRules:
    """Tests for AnomalyService.run_all_rules() — ANOM-01, D-11."""

    @pytest.mark.asyncio
    async def test_returns_list_of_detected_problems(self) -> None:
        """run_all_rules returns a list of detected problem dicts (ANOM-01).

        run_all_rules() is the orchestrator method called by the Celery task.
        It calls all 5 detect methods and returns a list of non-None results.
        """
        service, session = _make_service()

        # Mock the individual detect methods to return dummy results
        problem_row = {
            "tenant_id": TENANT_ID,
            "date": TODAY,
            "rule_id": "slow_first_touch",
            "severity": "high",
            "estimated_loss_ron": Decimal("5500.00"),
            "context_json": {},
        }
        service.detect_slow_first_touch = AsyncMock(return_value=problem_row)  # type: ignore[method-assign]
        service.detect_stuck_offer = AsyncMock(return_value=None)  # type: ignore[method-assign]
        service.detect_showroom_traffic_drop = AsyncMock(return_value=None)  # type: ignore[method-assign]
        service.detect_underperforming_salesperson = AsyncMock(return_value=None)  # type: ignore[method-assign]
        service.detect_junk_lead_quality = AsyncMock(return_value=None)  # type: ignore[method-assign]
        service._get_junk_ids = AsyncMock(return_value=set())  # type: ignore[method-assign]

        results = await service.run_all_rules(kpi_date=TODAY)  # type: ignore[attr-defined]

        assert isinstance(results, list), (
            f"run_all_rules must return a list, got {type(results).__name__}"
        )
        # Only 1 non-None result from our mocks
        assert len(results) == 1, (
            f"run_all_rules must filter None results — expected 1 problem, got {len(results)}"
        )
        assert results[0]["rule_id"] == "slow_first_touch"

    @pytest.mark.asyncio
    async def test_junk_ids_computed_once(self) -> None:
        """_get_junk_ids called exactly once regardless of rule count (D-11, ANOM-07).

        D-11: The junk IDs subquery is computed once per run_all_rules() call
        and passed to each non-junk rule method. It must NOT be re-executed
        per rule to avoid redundant DB queries.
        """
        service, session = _make_service()

        # Track how many times _get_junk_ids is called
        mock_get_junk_ids = AsyncMock(return_value={"ext-junk-001"})
        service._get_junk_ids = mock_get_junk_ids  # type: ignore[method-assign]
        service.detect_slow_first_touch = AsyncMock(return_value=None)  # type: ignore[method-assign]
        service.detect_stuck_offer = AsyncMock(return_value=None)  # type: ignore[method-assign]
        service.detect_showroom_traffic_drop = AsyncMock(return_value=None)  # type: ignore[method-assign]
        service.detect_underperforming_salesperson = AsyncMock(return_value=None)  # type: ignore[method-assign]
        service.detect_junk_lead_quality = AsyncMock(return_value=None)  # type: ignore[method-assign]

        await service.run_all_rules(kpi_date=TODAY)  # type: ignore[attr-defined]

        mock_get_junk_ids.assert_called_once(), (
            "_get_junk_ids must be called exactly once per run_all_rules() — "
            "not once per rule (D-11 efficiency requirement)"
        )
