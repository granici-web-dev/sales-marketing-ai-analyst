"""Unit tests for per-handler behavior of chat tools (Phase 8 Plan 03 — D-02/D-03).

This file covers the 8 handlers that need behavioral assertions beyond the
shape contract verified by ``test_chat_tools_registry.py``:

  Task 2 — get_leads, compare_periods, get_loss_reasons, get_showroom_performance
  Task 3 — get_recent_insight, explain_metric, get_stuck_leads, get_trend
  (Task 3 tests are appended in a subsequent commit when their tools land.)

Every test mocks the wrapped service or the AsyncSession.execute() result;
no live DB or Anthropic call is performed.

LM-3 enforcement: each test asserts ``inspect.signature(handler).parameters``
first param is ``tenant_id`` and the parameter has a UUID-flavored annotation.
"""

from __future__ import annotations

import inspect
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
FROM_DATE = date(2026, 5, 1)
TO_DATE = date(2026, 5, 19)


def _mock_execute_result(rows=None, first=None):
    """Build a mock for session.execute() returning rows/first."""
    result = MagicMock()
    if rows is not None:
        result.all.return_value = rows
        result.fetchall = MagicMock(return_value=rows)
    if first is not None:
        result.first.return_value = first
        result.fetchone = MagicMock(return_value=first)
    return result


def _lm3_signature_assertion(handler) -> None:
    """LM-3: handler's first 3 params are tenant_id, session, inp."""
    params = list(inspect.signature(handler).parameters.values())
    assert params[0].name == "tenant_id"
    # Annotation may be string ("UUID") or actual UUID class — accept both.
    ann = params[0].annotation
    assert ann is UUID or (isinstance(ann, str) and "UUID" in ann), (
        f"tenant_id annotation must reference UUID; got {ann!r}"
    )


# ── Task 2 ─────────────────────────────────────────────────────────────────────


class TestGetLeads:
    """get_leads — thin text() query on v_mefi_leads_active (+ raw for junk)."""

    @pytest.mark.asyncio
    async def test_lm3_signature(self) -> None:
        from app.services.chat.tools.get_leads import _handler

        _lm3_signature_assertion(_handler)

    @pytest.mark.asyncio
    async def test_get_leads_runs_text_query_and_returns_shape(self) -> None:
        from app.services.chat.tools.get_leads import GetLeadsInput, _handler

        # Two MagicMock rows mimicking SELECT output.
        row_a = MagicMock()
        row_a.external_id = 101
        row_a.lifecycle = "active"
        row_a.source_id = 5
        row_a.assigned_to_id = 1
        row_a.created_at_source = None
        row_a.estimated_value = None
        row_b = MagicMock()
        row_b.external_id = 102
        row_b.lifecycle = "lost"
        row_b.source_id = 11
        row_b.assigned_to_id = 2
        row_b.created_at_source = None
        row_b.estimated_value = Decimal("20000.00")

        session = AsyncMock()
        session.execute = AsyncMock(
            return_value=_mock_execute_result(rows=[row_a, row_b])
        )

        inp = GetLeadsInput(lifecycle="all", limit=10)
        result = await _handler(TENANT_ID, session, inp)

        assert session.execute.await_count == 1
        assert isinstance(result, dict)
        assert result["count"] == 2
        assert result["limit"] == 10
        assert len(result["leads"]) == 2

    @pytest.mark.asyncio
    async def test_get_leads_limit_clamped_at_50(self) -> None:
        """Limit cannot exceed 50 (Pydantic validation)."""
        from pydantic import ValidationError

        from app.services.chat.tools.get_leads import GetLeadsInput

        with pytest.raises(ValidationError):
            GetLeadsInput(limit=200)


class TestComparePeriods:
    """compare_periods — calls DashboardReadService twice + delta math."""

    @pytest.mark.asyncio
    async def test_lm3_signature(self) -> None:
        from app.services.chat.tools.compare_periods import _handler

        _lm3_signature_assertion(_handler)

    @pytest.mark.asyncio
    async def test_compare_periods_calls_dashboard_twice_and_computes_deltas(
        self, monkeypatch
    ) -> None:
        from app.services.chat.tools.compare_periods import (
            ComparePeriodsInput,
            PeriodInput,
            _handler,
        )

        # Period A: leads=100, contracts=10, revenue=85000, conv L→C=0.10
        # Period B: leads=80,  contracts=8,  revenue=64000, conv L→C=0.10
        period_a_response = {
            "funnel": {
                "leads": 100,
                "visits": 30,
                "offers": 40,
                "contracts": 10,
            },
            "kpi_cards": {
                "leads_total": 100,
                "contracts_count": 10,
                "revenue": Decimal("85000.00"),
            },
            "conversion_rates": {
                "l_to_c": Decimal("0.1000"),
            },
        }
        period_b_response = {
            "funnel": {
                "leads": 80,
                "visits": 20,
                "offers": 30,
                "contracts": 8,
            },
            "kpi_cards": {
                "leads_total": 80,
                "contracts_count": 8,
                "revenue": Decimal("64000.00"),
            },
            "conversion_rates": {
                "l_to_c": Decimal("0.1000"),
            },
        }

        fake_svc = MagicMock()
        fake_svc.get_sales_dashboard = AsyncMock(
            side_effect=[period_a_response, period_b_response]
        )
        fake_ctor = MagicMock(return_value=fake_svc)
        monkeypatch.setattr(
            "app.services.chat.tools.compare_periods.DashboardReadService", fake_ctor
        )

        session = AsyncMock()
        inp = ComparePeriodsInput(
            period_a=PeriodInput(
                date_from=date(2026, 5, 1), date_to=date(2026, 5, 19)
            ),
            period_b=PeriodInput(
                date_from=date(2026, 4, 1), date_to=date(2026, 4, 30)
            ),
        )
        result = await _handler(TENANT_ID, session, inp)

        # Service constructor invoked once with tenant scoping
        fake_ctor.assert_called_once_with(session, TENANT_ID)
        # get_sales_dashboard called twice (once per period)
        assert fake_svc.get_sales_dashboard.await_count == 2
        # Output has the documented shape
        assert "period_a" in result
        assert "period_b" in result
        assert "deltas" in result
        # leads: (100 - 80) / 80 * 100 = 25.0 %
        assert result["deltas"]["leads"] == "25.0"
        # revenue: (85000 - 64000) / 64000 * 100 = 32.8125 → rounded 1dp → 32.8
        assert result["deltas"]["revenue"] == "32.8"


class TestGetLossReasons:
    """get_loss_reasons — text() query on lifecycle='lost' — NO revenue figures."""

    @pytest.mark.asyncio
    async def test_lm3_signature(self) -> None:
        from app.services.chat.tools.get_loss_reasons import _handler

        _lm3_signature_assertion(_handler)

    @pytest.mark.asyncio
    async def test_get_loss_reasons_by_source(self) -> None:
        from app.services.chat.tools.get_loss_reasons import (
            GetLossReasonsInput,
            _handler,
        )

        row_a = MagicMock()
        row_a.group_key = 5  # source_id=5 → showroom
        row_a.lost_count = 30
        row_b = MagicMock()
        row_b.group_key = 11  # source_id=11 → mail
        row_b.lost_count = 20

        session = AsyncMock()
        session.execute = AsyncMock(
            return_value=_mock_execute_result(rows=[row_a, row_b])
        )

        inp = GetLossReasonsInput(
            date_from=FROM_DATE, date_to=TO_DATE, group_by="source"
        )
        result = await _handler(TENANT_ID, session, inp)

        assert "groups" in result
        assert result["total_lost"] == 50
        names = {g["name"] for g in result["groups"]}
        assert "showroom" in names
        assert "mail" in names
        # NO revenue or estimated_value keys in any group dict.
        for g in result["groups"]:
            assert "revenue" not in g
            assert "estimated_value" not in g


class TestGetShowroomPerformance:
    """get_showroom_performance — text() query group by showroom."""

    @pytest.mark.asyncio
    async def test_lm3_signature(self) -> None:
        from app.services.chat.tools.get_showroom_performance import _handler

        _lm3_signature_assertion(_handler)

    @pytest.mark.asyncio
    async def test_get_showroom_performance_returns_three_showrooms(self) -> None:
        from app.services.chat.tools.get_showroom_performance import (
            GetShowroomPerformanceInput,
            _handler,
        )

        rows = []
        for showroom, leads, visits, offers, contracts in [
            ("Brașov", 80, 40, 30, 10),
            ("București", 120, 60, 50, 15),
            ("Cluj-Napoca", 60, 30, 20, 5),
        ]:
            r = MagicMock()
            r.showroom = showroom
            r.leads = leads
            r.visits = visits
            r.offers = offers
            r.contracts = contracts
            rows.append(r)

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_mock_execute_result(rows=rows))

        inp = GetShowroomPerformanceInput(date_from=FROM_DATE, date_to=TO_DATE)
        result = await _handler(TENANT_ID, session, inp)

        assert len(result["showrooms"]) == 3
        names = {s["showroom"] for s in result["showrooms"]}
        assert names == {"Brașov", "București", "Cluj-Napoca"}

    @pytest.mark.asyncio
    async def test_get_showroom_performance_filters_to_one_showroom(self) -> None:
        from app.services.chat.tools.get_showroom_performance import (
            GetShowroomPerformanceInput,
            _handler,
        )

        rows = []
        for showroom, leads, visits, offers, contracts in [
            ("Brașov", 80, 40, 30, 10),
            ("București", 120, 60, 50, 15),
            ("Cluj-Napoca", 60, 30, 20, 5),
        ]:
            r = MagicMock()
            r.showroom = showroom
            r.leads = leads
            r.visits = visits
            r.offers = offers
            r.contracts = contracts
            rows.append(r)

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_mock_execute_result(rows=rows))

        inp = GetShowroomPerformanceInput(
            date_from=FROM_DATE, date_to=TO_DATE, showroom="Brașov"
        )
        result = await _handler(TENANT_ID, session, inp)

        assert len(result["showrooms"]) == 1
        assert result["showrooms"][0]["showroom"] == "Brașov"


# ── Task 3 ─────────────────────────────────────────────────────────────────────


class TestGetRecentInsight:
    """get_recent_insight — wraps InsightReadService."""

    @pytest.mark.asyncio
    async def test_lm3_signature(self) -> None:
        from app.services.chat.tools.get_recent_insight import _handler

        _lm3_signature_assertion(_handler)

    @pytest.mark.asyncio
    async def test_get_recent_insight_today_when_date_null(
        self, monkeypatch
    ) -> None:
        from app.services.chat.tools.get_recent_insight import (
            GetRecentInsightInput,
            _handler,
        )

        fake_svc = MagicMock()
        fake_svc.get_today = AsyncMock(
            return_value={"date": date(2026, 5, 28), "status": "success", "payload": {}}
        )
        fake_svc.get_by_date = AsyncMock()
        fake_ctor = MagicMock(return_value=fake_svc)
        monkeypatch.setattr(
            "app.services.chat.tools.get_recent_insight.InsightReadService", fake_ctor
        )

        session = AsyncMock()
        inp = GetRecentInsightInput()
        result = await _handler(TENANT_ID, session, inp)

        fake_ctor.assert_called_once_with(session, TENANT_ID)
        fake_svc.get_today.assert_awaited_once()
        fake_svc.get_by_date.assert_not_called()
        assert result["insight"]["status"] == "success"

    @pytest.mark.asyncio
    async def test_get_recent_insight_by_date_when_date_provided(
        self, monkeypatch
    ) -> None:
        from app.services.chat.tools.get_recent_insight import (
            GetRecentInsightInput,
            _handler,
        )

        target = date(2026, 5, 15)
        fake_svc = MagicMock()
        fake_svc.get_by_date = AsyncMock(
            return_value={"date": target, "status": "success", "payload": {}}
        )
        fake_svc.get_today = AsyncMock()
        fake_ctor = MagicMock(return_value=fake_svc)
        monkeypatch.setattr(
            "app.services.chat.tools.get_recent_insight.InsightReadService", fake_ctor
        )

        session = AsyncMock()
        inp = GetRecentInsightInput(date=target)
        result = await _handler(TENANT_ID, session, inp)

        fake_svc.get_by_date.assert_awaited_once_with(target)
        fake_svc.get_today.assert_not_called()
        assert result["insight"]["status"] == "success"

    @pytest.mark.asyncio
    async def test_get_recent_insight_returns_null_when_missing(
        self, monkeypatch
    ) -> None:
        from app.services.chat.tools.get_recent_insight import (
            GetRecentInsightInput,
            _handler,
        )

        fake_svc = MagicMock()
        fake_svc.get_today = AsyncMock(return_value=None)
        fake_ctor = MagicMock(return_value=fake_svc)
        monkeypatch.setattr(
            "app.services.chat.tools.get_recent_insight.InsightReadService", fake_ctor
        )

        session = AsyncMock()
        inp = GetRecentInsightInput()
        result = await _handler(TENANT_ID, session, inp)

        assert result == {"insight": None}


class TestExplainMetric:
    """explain_metric — pure dict lookup, no DB."""

    @pytest.mark.asyncio
    async def test_lm3_signature(self) -> None:
        from app.services.chat.tools.explain_metric import _handler

        _lm3_signature_assertion(_handler)

    @pytest.mark.asyncio
    async def test_explain_metric_returns_glossary_entry(self) -> None:
        from app.services.chat.tools.explain_metric import (
            ExplainMetricInput,
            _handler,
        )

        session = AsyncMock()  # MUST NOT be touched
        result = await _handler(
            TENANT_ID, session, ExplainMetricInput(metric_name="CAC")
        )

        # session.execute must NOT have been called — pure dict lookup.
        session.execute.assert_not_called()
        assert result["name"] == "CAC"
        assert "definition_ro" in result
        assert "formula" in result
        assert "relevant_for_sofa_belle" in result

    @pytest.mark.asyncio
    async def test_explain_metric_case_insensitive_lookup(self) -> None:
        from app.services.chat.tools.explain_metric import (
            ExplainMetricInput,
            _handler,
        )

        session = AsyncMock()
        # lowercase should still hit CAC
        result = await _handler(
            TENANT_ID, session, ExplainMetricInput(metric_name="cac")
        )
        assert result["name"].upper() == "CAC"

    @pytest.mark.asyncio
    async def test_explain_metric_unknown_returns_friendly_message(self) -> None:
        from app.services.chat.tools.explain_metric import (
            GLOSSARY,
            ExplainMetricInput,
            _handler,
        )

        session = AsyncMock()
        result = await _handler(
            TENANT_ID, session, ExplainMetricInput(metric_name="ZZZ_unknown")
        )

        assert "definition_ro" in result
        assert "glosar" in result["definition_ro"].lower()
        # Glossary itself meets the ≥9 entries contract
        assert len(GLOSSARY) >= 9


class TestGetStuckLeads:
    """get_stuck_leads — wraps DashboardReadService.get_stuck_offers."""

    @pytest.mark.asyncio
    async def test_lm3_signature(self) -> None:
        from app.services.chat.tools.get_stuck_leads import _handler

        _lm3_signature_assertion(_handler)

    @pytest.mark.asyncio
    async def test_get_stuck_leads_passes_days_threshold(self, monkeypatch) -> None:
        from app.services.chat.tools.get_stuck_leads import (
            GetStuckLeadsInput,
            _handler,
        )

        fake_svc = MagicMock()
        fake_svc.get_stuck_offers = AsyncMock(
            return_value=[
                {"external_id": 101, "days_stuck": 20, "salesperson_name": "Roibu Valeria"},
                {"external_id": 102, "days_stuck": 15, "salesperson_name": "Raileanu Leon"},
            ]
        )
        fake_ctor = MagicMock(return_value=fake_svc)
        monkeypatch.setattr(
            "app.services.chat.tools.get_stuck_leads.DashboardReadService", fake_ctor
        )

        session = AsyncMock()
        inp = GetStuckLeadsInput(days=21)
        result = await _handler(TENANT_ID, session, inp)

        # Constructor properly tenant-scoped
        fake_ctor.assert_called_once_with(session, TENANT_ID)
        fake_svc.get_stuck_offers.assert_awaited()
        assert result["days_threshold"] == 21
        assert isinstance(result["leads"], list)
        assert result["count"] == 2


class TestGetTrend:
    """get_trend — time series of one metric via DailyKpiService."""

    @pytest.mark.asyncio
    async def test_lm3_signature(self) -> None:
        from app.services.chat.tools.get_trend import _handler

        _lm3_signature_assertion(_handler)

    @pytest.mark.asyncio
    async def test_get_trend_returns_points(self, monkeypatch) -> None:
        from app.services.chat.tools.get_trend import GetTrendInput, _handler

        # 7-day window: simulate per-day compute_for_date returns
        def _make_row(day_offset: int) -> dict:
            return {
                "date": date(2026, 5, day_offset + 1),
                "leads_total": 10 + day_offset,
                "contracts_count": 1 + (day_offset // 3),
                "revenue": Decimal(str(5000 + day_offset * 100)),
                "conversion_l_to_c": Decimal("0.1000"),
                "conversion_l_to_v": Decimal("0.3000"),
                "conversion_o_to_c": Decimal("0.2500"),
            }

        rows = [_make_row(i) for i in range(7)]
        fake_svc = MagicMock()
        fake_svc.compute_for_date = AsyncMock(side_effect=rows)
        fake_ctor = MagicMock(return_value=fake_svc)
        monkeypatch.setattr(
            "app.services.chat.tools.get_trend.DailyKpiService", fake_ctor
        )

        session = AsyncMock()
        inp = GetTrendInput(metric_name="leads", period_days=7, granularity="day")
        result = await _handler(TENANT_ID, session, inp)

        fake_ctor.assert_called_once_with(session, TENANT_ID)
        assert fake_svc.compute_for_date.await_count == 7
        assert result["metric"] == "leads"
        assert result["granularity"] == "day"
        assert result["period_days"] == 7
        assert len(result["points"]) == 7
        # Decimals serialized as str (DATA-04)
        for point in result["points"]:
            assert isinstance(point["value"], (str, type(None)))
