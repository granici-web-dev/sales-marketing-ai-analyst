"""Unit tests for prompt_builder module — RED-state contracts for Phase 5.

All tests will fail with ImportError until Plan 05-02 (Wave 1) implements
app.services.insights.prompt_builder.build_system_prompt and build_user_message.

Requirements: D-07, D-08, D-09, D-10, D-11, AI-04

Patterns tested:
  D-07: System prompt is a list of blocks; last block has cache_control={"type": "ephemeral"}
  D-08: build_system_prompt() is a Python function returning list[dict] — no file I/O
  D-09: System prompt contains real Sofa Belle salesperson names (roster)
  D-10: System prompt instructs deadline labels: Azi, Mâine, Săptămâna aceasta, Luna aceasta
  D-02: System prompt instructs "Maximum 3 probleme"
  D-06: User message is compact JSON with kpi_snapshot + detected_problems fields
  AI-04: build_user_message caps problems at 3 by estimated_loss_ron descending
"""

from __future__ import annotations

import json
from decimal import Decimal

from tests.factories.insight_factory import make_kpi_snapshot, make_three_anomaly_day


class TestBuildSystemPrompt:
    """Tests for build_system_prompt() — D-07, D-08, D-09, D-10."""

    def test_build_system_prompt_returns_list(self) -> None:
        """build_system_prompt() must return a list with at least 2 blocks (D-07, D-08).

        D-08: System prompt = Python list of text blocks with cache_control.
        At minimum: one content block + one block with cache_control on last.
        """
        from app.services.insights.prompt_builder import build_system_prompt  # deferred (INFRA-05)

        result = build_system_prompt()
        assert isinstance(result, list), (
            f"build_system_prompt() must return a list, got {type(result).__name__}"
        )
        assert len(result) >= 2, (
            f"build_system_prompt() must return at least 2 blocks, got {len(result)} (D-07)"
        )

    def test_last_block_has_cache_control(self) -> None:
        """Last block in system prompt must have cache_control={"type": "ephemeral"} (D-07).

        D-07: cache_control on the last block caches all preceding content.
        This maximizes prompt caching — stable system prompt cached at ~$0.30/MTok.
        """
        from app.services.insights.prompt_builder import build_system_prompt  # deferred (INFRA-05)

        result = build_system_prompt()
        last = result[-1]
        assert "cache_control" in last, (
            "Last system block must have 'cache_control' key (D-07 — caches entire system prompt)"
        )
        assert last["cache_control"] == {"type": "ephemeral"}, (
            f'cache_control must be {{"type": "ephemeral"}}, got {last["cache_control"]} (D-07)'
        )

    def test_system_prompt_contains_salesperson_roster(self) -> None:
        """System prompt must include real Sofa Belle salesperson names (D-09).

        D-09: Salesperson roster injected in system prompt so Claude assigns
        specific names to actions (not generic 'echipa de vânzări').
        Required names: Dragoi Mihaela, Raileanu Leon (known from Phase 3 backfill data).
        """
        from app.services.insights.prompt_builder import build_system_prompt  # deferred (INFRA-05)

        result = build_system_prompt()
        full_text = " ".join(b.get("text", "") for b in result)

        assert "Dragoi Mihaela" in full_text, (
            "System prompt must contain 'Dragoi Mihaela' in the salesperson roster (D-09)"
        )
        assert "Raileanu Leon" in full_text, (
            "System prompt must contain 'Raileanu Leon' in the salesperson roster (D-09)"
        )

    def test_system_prompt_contains_romanian_deadline_labels(self) -> None:
        """System prompt must list the allowed Romanian relative deadline labels (D-10).

        D-10: Claude must be instructed to use Azi, Mâine, Săptămâna aceasta, Luna aceasta.
        Labels in system prompt → Claude respects them in output → validated in schema tests.
        """
        from app.services.insights.prompt_builder import build_system_prompt  # deferred (INFRA-05)

        result = build_system_prompt()
        full_text = " ".join(b.get("text", "") for b in result)

        assert "Azi" in full_text, (
            "System prompt must list 'Azi' as an allowed deadline label (D-10)"
        )
        assert "Mâine" in full_text, (
            "System prompt must list 'Mâine' as an allowed deadline label (D-10)"
        )

    def test_system_prompt_max_3_problems_instruction(self) -> None:
        """System prompt must instruct Claude: maximum 3 problems (D-02, D-08).

        D-02: Hard cap of 3 problems — both Pydantic max_length=3 AND system prompt instruction.
        System prompt text must contain the "Maximum 3" instruction (case-insensitive).
        """
        from app.services.insights.prompt_builder import build_system_prompt  # deferred (INFRA-05)

        result = build_system_prompt()
        full_text = " ".join(b.get("text", "") for b in result)

        has_instruction = "Maximum 3 probleme" in full_text or "maximum 3" in full_text.lower()
        assert has_instruction, (
            "System prompt must instruct Claude 'Maximum 3 probleme' (D-02, D-08). "
            f"Got text snippet: ...{full_text[:200]}..."
        )


class TestBuildUserMessage:
    """Tests for build_user_message() — D-06, AI-04."""

    def test_build_user_message_returns_string(self) -> None:
        """build_user_message() must return a string (D-06).

        D-06: User message is a JSON string sent fresh per day (not cached).
        """
        from app.services.insights.prompt_builder import build_user_message  # deferred (INFRA-05)

        result = build_user_message(make_kpi_snapshot(), make_three_anomaly_day())
        assert isinstance(result, str), (
            f"build_user_message() must return a str, got {type(result).__name__} (D-06)"
        )

    def test_user_message_is_valid_json(self) -> None:
        """build_user_message() must return valid JSON with required top-level keys (D-06).

        D-06: JSON structure: {"kpi_snapshot": {...}, "detected_problems": [...]}
        """
        from app.services.insights.prompt_builder import build_user_message  # deferred (INFRA-05)

        result = build_user_message(make_kpi_snapshot(), make_three_anomaly_day())
        data = json.loads(result)  # must not raise

        assert "kpi_snapshot" in data, "User message JSON must have 'kpi_snapshot' key (D-06)"
        assert "detected_problems" in data, (
            "User message JSON must have 'detected_problems' key (D-06)"
        )

    def test_user_message_caps_problems_at_three(self) -> None:
        """build_user_message() must send at most 3 problems to Claude (D-02, AI-04).

        D-02: Even when 4+ anomaly rules fire, only the top 3 by estimated_loss_ron
        descending are sent to Claude. Python selection — not Claude's decision.
        """
        from app.services.insights.prompt_builder import build_user_message  # deferred (INFRA-05)

        four_problems = make_three_anomaly_day() + [
            {
                "rule_id": "extra_rule",
                "severity": "low",
                "estimated_loss_ron": Decimal("1.00"),
                "current_value": Decimal("0.00"),
                "expected_value": Decimal("0.00"),
                "context_json": {},
            }
        ]

        result = build_user_message(make_kpi_snapshot(), four_problems)
        data = json.loads(result)

        assert len(data["detected_problems"]) <= 3, (
            f"build_user_message() must cap problems at 3, got {len(data['detected_problems'])} "
            "(D-02 top-3 selection by estimated_loss_ron descending)"
        )

    def test_user_message_no_pii_in_context_json(self) -> None:
        """User message must not contain customer PII fields in context_json (AI-SPEC §6 PII check).

        AI-SPEC §6: PII payload check — build_user_message() filters context_json
        to only {rule_id, current_value, expected_value}. Phone numbers, email
        addresses, and customer names must never reach the Claude API payload.
        """
        from app.services.insights.prompt_builder import build_user_message  # deferred (INFRA-05)

        problems_with_pii_risk = make_three_anomaly_day()
        result = build_user_message(make_kpi_snapshot(), problems_with_pii_risk)
        data = json.loads(result)

        for p in data["detected_problems"]:
            serialized = str(p)
            assert "email" not in serialized.lower(), (
                "User message must not contain 'email' in problem data (GDPR, AI-SPEC §6)"
            )
            assert "phone" not in serialized.lower(), (
                "User message must not contain 'phone' in problem data (GDPR, AI-SPEC §6)"
            )

    def test_zero_anomaly_user_message(self) -> None:
        """build_user_message() with empty problems list returns detected_problems=[] (D-13).

        D-13: Zero-anomaly day still generates a report — build_user_message must
        accept empty problems list and produce valid JSON with detected_problems=[].
        """
        from app.services.insights.prompt_builder import build_user_message  # deferred (INFRA-05)

        result = build_user_message(make_kpi_snapshot(), [])
        data = json.loads(result)

        assert data["detected_problems"] == [], (
            f"Zero-anomaly day must produce detected_problems=[], "
            f"got: {data['detected_problems']} (D-13)"
        )
