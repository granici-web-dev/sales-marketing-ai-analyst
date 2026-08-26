"""Unit tests for DailyInsightResponse Pydantic schema — RED-state contracts for Phase 5.

All tests will fail with ImportError until Plan 05-02 (Wave 1) implements
app.schemas.insights.daily_insight_schema.DailyInsightResponse.

Requirements: AI-02, D-01 through D-05, D-10, D-19

Patterns tested:
  D-01: Rich DailyInsightResponse schema (full SPEC.md version)
  D-02: problems[] hard max 3 enforced via Pydantic max_length=3
  D-04: problems[].id is a non-empty string (rule_id)
  D-05: Full schema with ActionItem, Problem, Positive, Warning
  D-10: action.deadline must be a relative Romanian label
  D-19: estimated_loss_ron is Decimal, never float
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

# ── Helper to build a valid DailyInsightResponse payload dict ─────────────────

def _make_valid_payload(**overrides) -> dict:
    """Build a minimal valid payload dict for DailyInsightResponse.model_validate()."""
    payload = {
        "summary": "Zi cu rezultate mixte. Există probleme care necesită atenție.",
        "problems": [
            {
                "id": "slow_first_touch",
                "severity": "high",
                "category": "sales",
                "title": "Timp de răspuns lent",
                "description": "3 lead-uri nu au fost contactate în primele 5 ore.",
                "estimated_loss_ron": "5000.00",
                "actions": [
                    {
                        "order": 1,
                        "description": "Contactați lead-urile imediat",
                        "owner": "Roibu Valeria",
                        "deadline": "Azi",
                        "expected_outcome": "Rata de răspuns scade de la 3h la sub 2h",
                    }
                ],
            }
        ],
        "positives": [
            {
                "title": "Raileanu Leon — performanță excelentă",
                "description": "8.3% conversie L→C",
                "recommendation": "Distribuiți mai multe lead-uri showroom",
            }
        ],
        "warnings": [
            {
                "title": "Oferte în așteptare",
                "description": "2 oferte la limita de 14 zile fără activitate",
            }
        ],
        "weekly_action_plan": [
            "Acțiune prioritară 1",
            "Acțiune prioritară 2",
            "Acțiune prioritară 3",
            "Acțiune prioritară 4",
            "Acțiune prioritară 5",
        ],
        "generated_at": "2026-05-28T06:00:00+00:00",
    }
    payload.update(overrides)
    return payload


class TestDailyInsightResponseSchema:
    """Tests for DailyInsightResponse Pydantic schema — AI-02, D-05."""

    def test_schema_validates_valid_payload(self) -> None:
        """DailyInsightResponse.model_validate() succeeds on a well-formed payload (AI-02, D-05).

        All required fields present with correct types.
        estimated_loss_ron must parse as Decimal (D-19).
        """
        from app.schemas.insights.daily_insight_schema import (
            DailyInsightResponse,  # deferred (INFRA-05)
        )

        result = DailyInsightResponse.model_validate(_make_valid_payload())
        assert result.summary != "", "summary must be a non-empty string"
        assert isinstance(result.problems[0].estimated_loss_ron, Decimal), (
            "estimated_loss_ron must be Decimal, not float (D-19)"
        )

    def test_schema_rejects_four_problems(self) -> None:
        """DailyInsightResponse must reject payloads with 4 problems (D-02 max_length=3).

        Pydantic max_length=3 on problems field must raise ValidationError
        when Claude (or a test) provides 4+ problems.
        """
        from pydantic import ValidationError  # deferred (INFRA-05)

        from app.schemas.insights.daily_insight_schema import (
            DailyInsightResponse,  # deferred (INFRA-05)
        )

        problem_dict = {
            "id": "test_rule",
            "severity": "low",
            "category": "sales",
            "title": "Test",
            "description": "Test description.",
            "estimated_loss_ron": "1000.00",
            "actions": [],
        }
        payload = _make_valid_payload(problems=[problem_dict] * 4)

        with pytest.raises(ValidationError) as exc_info:
            DailyInsightResponse.model_validate(payload)

        assert "problems" in str(exc_info.value).lower(), (
            "ValidationError must mention the 'problems' field (D-02 max_length=3)"
        )

    def test_estimated_loss_ron_is_decimal(self) -> None:
        """problems[].estimated_loss_ron must be Decimal, not float (D-19).

        D-19: All monetary values stored as Decimal — never float.
        Pydantic parses string/numeric inputs as Decimal for this field.
        """
        from app.schemas.insights.daily_insight_schema import (
            DailyInsightResponse,  # deferred (INFRA-05)
        )

        result = DailyInsightResponse.model_validate(_make_valid_payload())
        for problem in result.problems:
            assert isinstance(problem.estimated_loss_ron, Decimal), (
                f"Problem '{problem.id}': estimated_loss_ron must be Decimal, "
                f"got {type(problem.estimated_loss_ron).__name__} (D-19)"
            )

    def test_problem_id_is_string(self) -> None:
        """problems[].id must be a non-empty string (D-04).

        D-04: problems[].id = rule_id from detected_problems (e.g., 'slow_first_touch').
        Must be a string with at least 1 character — not None, not int.
        """
        from app.schemas.insights.daily_insight_schema import (
            DailyInsightResponse,  # deferred (INFRA-05)
        )

        result = DailyInsightResponse.model_validate(_make_valid_payload())
        for problem in result.problems:
            assert isinstance(problem.id, str), (
                f"problem.id must be a string (D-04), got {type(problem.id).__name__}"
            )
            assert len(problem.id) > 0, "problem.id must be non-empty (D-04)"

    def test_weekly_action_plan_non_empty(self) -> None:
        """weekly_action_plan must have at least 1 item (D-03).

        D-03: Claude synthesizes weekly_action_plan independently as 5-7 items.
        At minimum, the field must be a non-empty list.
        """
        from app.schemas.insights.daily_insight_schema import (
            DailyInsightResponse,  # deferred (INFRA-05)
        )

        result = DailyInsightResponse.model_validate(_make_valid_payload())
        assert len(result.weekly_action_plan) >= 1, (
            "weekly_action_plan must have at least 1 item (D-03)"
        )

    def test_allowed_deadline_labels(self) -> None:
        """action.deadline must be one of the allowed Romanian relative labels (D-10).

        D-10: Allowed values: Azi, Mâine, Săptămâna aceasta, Luna aceasta.
        System prompt instructs Claude to use these; schema validation confirms.
        """
        from app.schemas.insights.daily_insight_schema import (
            DailyInsightResponse,  # deferred (INFRA-05)
        )

        ALLOWED_DEADLINES = {"Azi", "Mâine", "Săptămâna aceasta", "Luna aceasta"}

        result = DailyInsightResponse.model_validate(_make_valid_payload())
        for problem in result.problems:
            for action in problem.actions:
                assert action.deadline in ALLOWED_DEADLINES, (
                    f"action.deadline='{action.deadline}' is not in allowed set "
                    f"{ALLOWED_DEADLINES} (D-10)"
                )

    def test_action_owner_non_empty(self) -> None:
        """action.owner must be a non-empty string for every action (D-09).

        D-09: owner = real Sofa Belle salesperson name or role (Manager, Marketing Sofa).
        Vague assignments like empty string are caught here.
        """
        from app.schemas.insights.daily_insight_schema import (
            DailyInsightResponse,  # deferred (INFRA-05)
        )

        result = DailyInsightResponse.model_validate(_make_valid_payload())
        for problem in result.problems:
            for action in problem.actions:
                assert action.owner.strip() != "", (
                    f"action.owner must not be empty or whitespace-only (D-09), "
                    f"got '{action.owner}'"
                )

    def test_generated_at_is_datetime(self) -> None:
        """DailyInsightResponse.generated_at must be a datetime instance (D-16).

        generated_at is set server-side by InsightService — not by Claude.
        Pydantic must parse the ISO string into a datetime object.
        """
        from app.schemas.insights.daily_insight_schema import (
            DailyInsightResponse,  # deferred (INFRA-05)
        )

        result = DailyInsightResponse.model_validate(_make_valid_payload())
        assert isinstance(result.generated_at, datetime), (
            f"generated_at must be a datetime, got {type(result.generated_at).__name__} (D-16)"
        )
