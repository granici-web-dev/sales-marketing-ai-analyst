"""Unit tests for number_validator module — RED-state contracts for Phase 5.

All tests will fail with ImportError until Plan 05-02 (Wave 2) implements
app.services.insights.number_validator.extract_numbers_from_text and cross_check.

Requirements: AI-06

Patterns tested:
  AI-06: Number cross-check — extracted narrative numbers must match input KPI/anomaly values ±2%
  Romanian number formatting: . as thousands separator, , as decimal separator
  Cross-check passes if numbers in text match kpi_snapshot or estimated_loss_ron values
  Cross-check fails if numbers in text deviate >2% from any input value (fabrication detection)
"""

from __future__ import annotations

from decimal import Decimal


class TestExtractNumbersFromText:
    """Tests for extract_numbers_from_text() — AI-06 Romanian number extraction."""

    def test_extract_romanian_formatted_number(self) -> None:
        """Romanian thousands separator: '23.400 RON' → 23400.0 (AI-06).

        In Romanian, . is the thousands separator (e.g., 23.400 = 23400).
        The extractor must handle this format and return the numeric value.
        """
        from app.services.insights.number_validator import (
            extract_numbers_from_text,  # deferred (INFRA-05)
        )

        result = extract_numbers_from_text("23.400 RON pierdere estimată")
        assert 23400.0 in result, (
            f"'23.400 RON' in Romanian format must extract as 23400.0, got {result} (AI-06)"
        )

    def test_extract_percentage(self) -> None:
        """Romanian decimal comma: '8,3% conversie' → 8.3 (AI-06).

        In Romanian, , is the decimal separator (e.g., 8,3 = 8.3).
        Percentages are common in KPI summaries.
        """
        from app.services.insights.number_validator import (
            extract_numbers_from_text,  # deferred (INFRA-05)
        )

        result = extract_numbers_from_text("8,3% conversie L→C în showroom")
        assert 8.3 in result, (
            f"'8,3%' in Romanian decimal format must extract as 8.3, got {result} (AI-06)"
        )

    def test_extract_plain_integer(self) -> None:
        """Plain integer '351 lead-uri' → 351.0 (AI-06).

        Plain integers without separators must also be extracted.
        """
        from app.services.insights.number_validator import (
            extract_numbers_from_text,  # deferred (INFRA-05)
        )

        result = extract_numbers_from_text("351 lead-uri înregistrate în total")
        assert 351.0 in result, (
            f"'351' must extract as 351.0, got {result} (AI-06)"
        )


class TestCrossCheck:
    """Tests for cross_check() — AI-06 number grounding validation."""

    def test_cross_check_passes_within_tolerance(self) -> None:
        """Numbers in summary matching input KPI values within ±2% → cross_check returns True (AI-06).

        If summary mentions '12 leads' and kpi_snapshot has leads_total=12,
        the value is grounded — cross_check must pass.
        """
        from unittest.mock import MagicMock  # deferred (INFRA-05)

        from app.services.insights.number_validator import cross_check  # deferred (INFRA-05)

        # Mock DailyInsightResponse with summary mentioning 12 leads (matches kpi_snapshot)
        parsed = MagicMock()
        parsed.summary = "Ziua a adus 12 lead-uri noi în pipeline."
        parsed.problems = []

        kpi = {"leads_total": 12, "contracts_closed": 1}
        problems_input = []

        result = cross_check(parsed, kpi, problems_input)
        assert result is True, (
            "cross_check must return True when '12' in summary matches kpi_snapshot['leads_total']=12 "
            "(within ±2% tolerance, AI-06)"
        )

    def test_cross_check_fails_on_fabricated_ron(self) -> None:
        """Fabricated RON amount not matching any input value → cross_check returns False (AI-06).

        If summary claims 'ai pierdut 47320 RON' but the only estimated_loss_ron is 5000,
        47320 is > 2% from 5000 — this is a hallucinated figure.
        cross_check must return False to trigger a regeneration.
        """
        from unittest.mock import MagicMock  # deferred (INFRA-05)

        from app.services.insights.number_validator import cross_check  # deferred (INFRA-05)

        parsed = MagicMock()
        parsed.summary = "ai pierdut 47320 RON luna aceasta"
        parsed.problems = []

        kpi = {"leads_total": 12}
        problems_input = [
            {"rule_id": "slow_first_touch", "estimated_loss_ron": Decimal("5000.00")}
        ]

        result = cross_check(parsed, kpi, problems_input)
        assert result is False, (
            "cross_check must return False when '47320 RON' has no matching input value "
            "(47320 vs. estimated_loss_ron=5000, difference > 2% — fabrication detected, AI-06)"
        )

    def test_cross_check_passes_with_two_percent_tolerance(self) -> None:
        """Value in text = 5050, input value = 5000 → 1% difference → cross_check returns True (AI-06).

        ±2% tolerance: 5050 / 5000 - 1 = 1% → passes.
        Allows natural rounding in Romanian text (e.g., "~5.050 RON" when actual is 5000).
        """
        from unittest.mock import MagicMock  # deferred (INFRA-05)

        from app.services.insights.number_validator import cross_check  # deferred (INFRA-05)

        parsed = MagicMock()
        parsed.summary = "Estimăm o pierdere de ~5050 RON din lead-uri lente."
        parsed.problems = []

        kpi = {"leads_total": 12}
        problems_input = [
            {"rule_id": "slow_first_touch", "estimated_loss_ron": Decimal("5000.00")}
        ]

        result = cross_check(parsed, kpi, problems_input)
        assert result is True, (
            "cross_check must return True when text value 5050 is within 1% of input 5000 "
            "(±2% tolerance, AI-06)"
        )

    def test_cross_check_zero_anomaly_day(self) -> None:
        """Zero-anomaly day with no numbers in summary → cross_check returns True (D-13, AI-06).

        When detected_problems is empty and summary has no numeric values,
        there are no numbers to cross-check — validation trivially passes.
        """
        from unittest.mock import MagicMock  # deferred (INFRA-05)

        from app.services.insights.number_validator import cross_check  # deferred (INFRA-05)

        parsed = MagicMock()
        parsed.summary = "Zi liniștită. Toți vânzătorii lucrează conform planului."
        parsed.problems = []

        kpi = {}
        problems_input = []

        result = cross_check(parsed, kpi, problems_input)
        assert result is True, (
            "cross_check must return True on zero-anomaly day with no numbers in summary (D-13)"
        )
