"""Unit tests for InsightService — RED-state contracts for Phase 5.

All tests will fail with ImportError until Plan 05-02 (Wave 2) implements
app.services.insights.insight_service.InsightService.

Tests mock AsyncSession and AsyncAnthropic — no live DB or Anthropic API required.

Requirements: AI-06, AI-07, D-14, D-15

Patterns tested:
  AI-06: Number cross-check — up to 2 regenerations before fallback
  AI-07: Fallback behavior when all Claude retries fail
  D-14: status machine: success | fallback | failed
  D-15: Fallback summary = "Generare AI eșuată — raport bazat pe anomalii detectate automat"
  D-16: raw_response preserved on failure for debugging
  D-19: cost_usd computed as Decimal with correct formula
  D-18: InsightService constructor follows AnomalyService pattern (session + tenant_id)
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from tests.factories.insight_factory import (
    make_detected_problem_input,
    make_kpi_snapshot,
)

TENANT_ID_STR = "00000000-0000-0000-0000-000000000001"
TENANT_ID = UUID(TENANT_ID_STR)


def _make_service(mock_session=None):
    """Build InsightService with mocked AsyncSession.

    Import deferred — file parses (RED) before Plan 05-02 implements InsightService.
    Returns (service, session) tuple.
    """
    from app.services.insights.insight_service import InsightService  # deferred (INFRA-05)

    session = mock_session or AsyncMock()
    return InsightService(session, TENANT_ID), session


def _make_tool_block_mock(payload_dict: dict) -> MagicMock:
    """Build a mock ToolUseBlock that returns payload_dict as .input."""
    block = MagicMock()
    block.type = "tool_use"
    block.input = payload_dict
    return block


def _make_usage_mock(input_tokens: int = 3000, output_tokens: int = 2000) -> MagicMock:
    """Build a mock Usage object with token counts."""
    usage = MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens
    usage.cache_read_input_tokens = 0
    usage.cache_creation_input_tokens = 0
    return usage


def _make_anthropic_response_mock(payload_dict: dict, input_tokens: int = 3000,
                                   output_tokens: int = 2000) -> MagicMock:
    """Build a mock Anthropic Message response with a tool_use block."""
    response = MagicMock()
    response.content = [_make_tool_block_mock(payload_dict)]
    response.usage = _make_usage_mock(input_tokens, output_tokens)
    return response


class TestInsightServiceRun:
    """Tests for InsightService.run() — AI-06, AI-07, D-14."""

    @pytest.mark.asyncio
    async def test_run_returns_success_status_on_valid_response(self) -> None:
        """InsightService.run() returns ('dict', 'success') on valid Claude tool response (D-14).

        Claude returns a valid DailyInsightResponse via tool_use block.
        Number cross-check passes.
        Result: (insight_dict, 'success').
        """

        # Build a valid payload that number validator will accept
        payload = {
            "summary": "Zi cu 12 lead-uri. Rata de conversie este de 8.3%.",
            "problems": [
                {
                    "id": "slow_first_touch",
                    "severity": "high",
                    "category": "sales",
                    "title": "Timp de răspuns lent",
                    "description": "Estimăm o pierdere de ~5.000 RON.",
                    "estimated_loss_ron": "5000.00",
                    "actions": [
                        {
                            "order": 1,
                            "description": "Contactați lead-urile urgent",
                            "owner": "Roibu Valeria",
                            "deadline": "Azi",
                            "expected_outcome": "Rata de răspuns sub 2h",
                        }
                    ],
                }
            ],
            "positives": [
                {
                    "title": "Performanță bună",
                    "description": "Conversie de 8.3% în showroom",
                    "recommendation": "Continuați strategia",
                }
            ],
            "warnings": [],
            "weekly_action_plan": [
                "Acțiune 1", "Acțiune 2", "Acțiune 3",
                "Acțiune 4", "Acțiune 5",
            ],
            "generated_at": "2026-05-28T06:00:00+00:00",
        }

        mock_response = _make_anthropic_response_mock(payload)
        mock_session = AsyncMock()

        service, _ = _make_service(mock_session)

        # Patch out DB fetches and Anthropic client
        service._fetch_detected_problems = AsyncMock(
            return_value=[make_detected_problem_input()]
        )
        service._fetch_kpi_snapshot = AsyncMock(return_value=make_kpi_snapshot())

        with patch("app.services.insights.insight_service.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create = AsyncMock(return_value=mock_response)

            result_dict, status = await service.run(date.today())

        assert status == "success", (
            f"InsightService.run() must return 'success' on valid response, got '{status}' (D-14)"
        )
        assert "payload" in result_dict, "Result dict must have 'payload' key"

    @pytest.mark.asyncio
    async def test_run_returns_fallback_on_three_validation_failures(self) -> None:
        """InsightService.run() returns 'fallback' after 3 failed number validations (AI-06, AI-07).

        D-14: After all retries fail, returns ('dict', 'fallback').
        AI-07: Fallback is built from detected_problems rows without Claude.
        """

        # Build a payload with fabricated number that will fail number cross-check
        payload = {
            "summary": "ai pierdut 47320 RON luna aceasta",  # fabricated number
            "problems": [],
            "positives": [],
            "warnings": [],
            "weekly_action_plan": ["Acțiune 1", "Acțiune 2", "Acțiune 3", "Acțiune 4", "Acțiune 5"],
            "generated_at": "2026-05-28T06:00:00+00:00",
        }

        mock_response = _make_anthropic_response_mock(payload)
        mock_session = AsyncMock()

        service, _ = _make_service(mock_session)
        service._fetch_detected_problems = AsyncMock(
            return_value=[make_detected_problem_input()]
        )
        service._fetch_kpi_snapshot = AsyncMock(return_value=make_kpi_snapshot())

        with patch("app.services.insights.insight_service.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create = AsyncMock(return_value=mock_response)

            # Patch number validator to always return False (AI-06)
            with patch(
                "app.services.insights.insight_service.InsightService._numbers_match",
                return_value=False,
            ):
                result_dict, status = await service.run(date.today())

        assert status == "fallback", (
            f"After 3 failed number validations, status must be 'fallback', got '{status}' "
            "(AI-06, AI-07)"
        )

    @pytest.mark.asyncio
    async def test_fallback_summary_is_romanian_error_message(self) -> None:
        """Fallback DailyInsightResponse.summary must be the fixed Romanian error string (D-15).

        D-15: summary = "Generare AI eșuată — raport bazat pe anomalii detectate automat"
        Phase 7 frontend reads this string to show the "Generare AI eșuată" banner.
        """

        payload = {
            "summary": "test",
            "problems": [],
            "positives": [],
            "warnings": [],
            "weekly_action_plan": ["A1", "A2", "A3", "A4", "A5"],
            "generated_at": "2026-05-28T06:00:00+00:00",
        }
        mock_response = _make_anthropic_response_mock(payload)
        mock_session = AsyncMock()

        service, _ = _make_service(mock_session)
        service._fetch_detected_problems = AsyncMock(
            return_value=[make_detected_problem_input()]
        )
        service._fetch_kpi_snapshot = AsyncMock(return_value=make_kpi_snapshot())

        with patch("app.services.insights.insight_service.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create = AsyncMock(return_value=mock_response)

            with patch(
                "app.services.insights.insight_service.InsightService._numbers_match",
                return_value=False,
            ):
                result_dict, status = await service.run(date.today())

        assert status == "fallback"
        assert result_dict["payload"]["summary"] == (
            "Generare AI eșuată — raport bazat pe anomalii detectate automat"
        ), (
            f"Fallback summary must be the exact Romanian error message (D-15), "
            f"got: '{result_dict['payload']['summary']}'"
        )

    @pytest.mark.asyncio
    async def test_fallback_problems_from_detected_problems_rows(self) -> None:
        """Fallback problems[] is built from detected_problems rows, each with actions=[] (D-15).

        D-15: Each anomaly row becomes a Problem with id=rule_id, actions=[].
        No actions because Claude never succeeded in generating them.
        """

        # 2 detected problems input
        detected_problems = [
            make_detected_problem_input(rule_id="slow_first_touch"),
            make_detected_problem_input(rule_id="stuck_offer"),
        ]

        payload = {
            "summary": "test",
            "problems": [],
            "positives": [],
            "warnings": [],
            "weekly_action_plan": ["A1", "A2", "A3", "A4", "A5"],
            "generated_at": "2026-05-28T06:00:00+00:00",
        }
        mock_response = _make_anthropic_response_mock(payload)
        mock_session = AsyncMock()

        service, _ = _make_service(mock_session)
        service._fetch_detected_problems = AsyncMock(return_value=detected_problems)
        service._fetch_kpi_snapshot = AsyncMock(return_value=make_kpi_snapshot())

        with patch("app.services.insights.insight_service.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create = AsyncMock(return_value=mock_response)

            with patch(
                "app.services.insights.insight_service.InsightService._numbers_match",
                return_value=False,
            ):
                result_dict, status = await service.run(date.today())

        assert status == "fallback"
        problems = result_dict["payload"]["problems"]
        assert len(problems) == len(detected_problems[:3]), (
            f"Fallback must populate {len(detected_problems)} problems from input rows, "
            f"got {len(problems)} (D-15)"
        )
        for problem in problems:
            assert problem["actions"] == [], (
                f"Fallback problem '{problem['id']}' must have actions=[] (D-15)"
            )

    def test_compute_cost_formula(self) -> None:
        """_compute_cost() uses formula: (input/1M)*3.0 + (output/1M)*15.0 (SPEC.md §10).

        3000 input tokens + 2000 output tokens:
        = (3000/1_000_000)*3.0 + (2000/1_000_000)*15.0
        = 0.009 + 0.030
        = 0.039 USD
        """
        from app.services.insights.insight_service import InsightService  # deferred (INFRA-05)

        mock_usage = _make_usage_mock(input_tokens=3000, output_tokens=2000)
        cost = InsightService._compute_cost(mock_usage)

        assert isinstance(cost, Decimal), (
            f"_compute_cost() must return Decimal, got {type(cost).__name__} (D-19)"
        )
        expected = Decimal("0.039")
        # Allow small floating-point rounding tolerance
        assert abs(cost - expected) < Decimal("0.000001"), (
            f"Cost formula: (3000/1M)*3.0 + (2000/1M)*15.0 = 0.039000, got {cost} (SPEC.md §10)"
        )

    @pytest.mark.asyncio
    async def test_raw_response_preserved_on_failure(self) -> None:
        """result_dict['raw_response'] must be a non-empty string on fallback path (D-16).

        D-16: raw_response column stores last Claude response for debugging on failure.
        Must never be None or empty string on fallback (how else do we debug it?).
        """

        payload = {
            "summary": "test raw",
            "problems": [],
            "positives": [],
            "warnings": [],
            "weekly_action_plan": ["A1", "A2", "A3", "A4", "A5"],
            "generated_at": "2026-05-28T06:00:00+00:00",
        }
        mock_response = _make_anthropic_response_mock(payload)
        mock_session = AsyncMock()

        service, _ = _make_service(mock_session)
        service._fetch_detected_problems = AsyncMock(
            return_value=[make_detected_problem_input()]
        )
        service._fetch_kpi_snapshot = AsyncMock(return_value=make_kpi_snapshot())

        with patch("app.services.insights.insight_service.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create = AsyncMock(return_value=mock_response)

            with patch(
                "app.services.insights.insight_service.InsightService._numbers_match",
                return_value=False,
            ):
                result_dict, status = await service.run(date.today())

        assert status == "fallback"
        assert isinstance(result_dict.get("raw_response"), str), (
            "result_dict['raw_response'] must be a string on fallback (D-16)"
        )
        assert result_dict["raw_response"] != "", (
            "result_dict['raw_response'] must not be empty on fallback — needed for debugging (D-16)"
        )

    @pytest.mark.asyncio
    async def test_zero_anomaly_day_still_runs(self) -> None:
        """InsightService.run() with empty detected_problems still calls Claude (D-13).

        D-13: Zero-anomaly day generates a positive-only report — Claude still runs.
        No error or early return when detected_problems=[] is passed.
        """

        payload = {
            "summary": "Zi excelentă! Toate metricile în parametri normali.",
            "problems": [],
            "positives": [
                {
                    "title": "Conversie showroom excelentă",
                    "description": "10.8% conversie L→C",
                    "recommendation": "Continuați strategia",
                }
            ],
            "warnings": [],
            "weekly_action_plan": ["A1", "A2", "A3", "A4", "A5"],
            "generated_at": "2026-05-28T06:00:00+00:00",
        }
        mock_response = _make_anthropic_response_mock(payload)
        mock_session = AsyncMock()

        service, _ = _make_service(mock_session)
        service._fetch_detected_problems = AsyncMock(return_value=[])  # zero anomalies
        service._fetch_kpi_snapshot = AsyncMock(return_value=make_kpi_snapshot())

        with patch("app.services.insights.insight_service.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create = AsyncMock(return_value=mock_response)

            result_dict, status = await service.run(date.today())

        # Must not raise; Claude must have been called
        mock_client.messages.create.assert_called_once(), (
            "Claude must be called even on zero-anomaly day (D-13)"
        )
        assert status in ("success", "fallback"), (
            f"Zero-anomaly day must complete without raising; got status='{status}' (D-13)"
        )
