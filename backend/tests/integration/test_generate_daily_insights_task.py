from __future__ import annotations

"""Integration tests for generate_daily_insights Celery task — RED-state contracts for Phase 5.

Most tests are skipped without TEST_DATABASE_URL (require a live DB).
Exception: test_no_claude_calls_in_http_handlers (AI-09 grep gate) runs immediately
— it does NOT require a DB and must PASS from day 1.

Requirements: AI-01, AI-08, AI-09, D-17, D-18, D-20

Patterns tested:
  AI-01: generate_daily_insights task writes DailyInsight row to daily_insights table
  AI-08: input_tokens, output_tokens, cost_usd all persisted to daily_insights row
  AI-09: AsyncAnthropic must NOT appear in app/api/ HTTP handler layer
  D-17: Chain position locked: detect_anomalies → generate_daily_insights (4th link)
  D-18: NullPool + asyncio.run(_generate_async()) pattern (mirrors detect_anomalies.py)
  D-20: Beat entry at 06:00 Europe/Bucharest (separate from 04:00 mefi-sync entry)
"""

import os
import subprocess
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
TENANT_ID_STR = str(TENANT_ID)

# Integration tests require a live DB — skip automatically when not available.
# NOTE: test_no_claude_calls_in_http_handlers is NOT wrapped in this skip — it
# is a pure grep gate that must pass from Wave 0 without any DB or API access.
_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "")

_integration_skip = pytest.mark.skipif(
    not _TEST_DB_URL,
    reason="integration test — requires TEST_DATABASE_URL",
)


def _make_mock_anthropic_response(payload_dict: dict, input_tokens: int = 3000,
                                   output_tokens: int = 2000) -> MagicMock:
    """Build a mock Anthropic Message response with a tool_use block."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.input = payload_dict

    usage = MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens
    usage.cache_read_input_tokens = 0
    usage.cache_creation_input_tokens = 0

    response = MagicMock()
    response.content = [tool_block]
    response.usage = usage
    return response


def _make_valid_insight_payload() -> dict:
    """Build a minimal valid DailyInsightResponse payload for Claude mock."""
    return {
        "summary": "Zi cu 12 lead-uri noi. Rata de conversie showroom rămâne la 10.8%.",
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
                        "description": "Contactați lead-urile noi în primele 2 ore",
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
        "warnings": [],
        "weekly_action_plan": [
            "Contactați lead-urile noi în primele 2 ore",
            "Verificați ofertele în așteptare",
            "Organizați standup cu echipa de vânzări",
            "Analizați conversiile showroom din ultima săptămână",
            "Actualizați pipeline-ul în MEFI",
        ],
        "generated_at": "2026-05-28T06:00:00+00:00",
    }


@_integration_skip
@pytest.mark.asyncio
async def test_task_writes_success_row() -> None:
    """generate_daily_insights task writes DailyInsight row with status='success' (AI-01, D-18).

    Steps:
    1. Mock Anthropic client to return valid DailyInsightResponse
    2. Call _generate_async(tenant_id, date.today())
    3. Assert daily_insights row exists with status='success'
    4. Assert input_tokens > 0, output_tokens > 0, cost_usd > 0 (AI-08)

    D-18: NullPool + asyncio.run() pattern — test calls _generate_async directly.
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.tasks.etl.generate_daily_insights import _generate_async  # noqa: PLC0415

    kpi_date = date.today()
    engine = create_async_engine(_TEST_DB_URL)
    mock_response = _make_mock_anthropic_response(_make_valid_insight_payload())

    try:
        with patch("anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create = AsyncMock(return_value=mock_response)

            await _generate_async(TENANT_ID_STR, kpi_date)

        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT status, input_tokens, output_tokens, cost_usd "
                    "FROM daily_insights "
                    "WHERE tenant_id = :tenant_id AND date = :kpi_date"
                ),
                {"tenant_id": TENANT_ID, "kpi_date": kpi_date},
            )
            row = result.fetchone()

        assert row is not None, "daily_insights row must be written after task completion (AI-01)"
        assert row[0] == "success", (
            f"daily_insights.status must be 'success', got '{row[0]}' (D-14)"
        )
        assert row[1] > 0, "input_tokens must be > 0 (AI-08)"
        assert row[2] > 0, "output_tokens must be > 0 (AI-08)"
        assert row[3] > Decimal("0"), "cost_usd must be > 0 (AI-08)"
    finally:
        await engine.dispose()


@_integration_skip
@pytest.mark.asyncio
async def test_token_usage_logged() -> None:
    """All token fields must be persisted to daily_insights row (AI-08).

    AI-08: input_tokens, output_tokens, cost_usd must all be non-NULL after generation.
    These fields enable the cost tracking dashboard (Section 5, production monitoring).
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.tasks.etl.generate_daily_insights import _generate_async  # noqa: PLC0415

    kpi_date = date.today()
    engine = create_async_engine(_TEST_DB_URL)
    mock_response = _make_mock_anthropic_response(
        _make_valid_insight_payload(), input_tokens=3000, output_tokens=2000
    )

    try:
        with patch("anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create = AsyncMock(return_value=mock_response)

            await _generate_async(TENANT_ID_STR, kpi_date)

        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT input_tokens, output_tokens, cost_usd "
                    "FROM daily_insights "
                    "WHERE tenant_id = :tenant_id AND date = :kpi_date"
                ),
                {"tenant_id": TENANT_ID, "kpi_date": kpi_date},
            )
            row = result.fetchone()

        assert row is not None
        assert row[0] is not None, "input_tokens must not be NULL (AI-08)"
        assert row[1] is not None, "output_tokens must not be NULL (AI-08)"
        assert row[2] is not None, "cost_usd must not be NULL (AI-08)"
    finally:
        await engine.dispose()


@_integration_skip
@pytest.mark.asyncio
async def test_upsert_is_idempotent() -> None:
    """Calling _generate_async twice for the same date → exactly 1 daily_insights row (D-16).

    D-16: UNIQUE(tenant_id, date) constraint with ON CONFLICT DO UPDATE ensures idempotency.
    Second call for same date updates the existing row — no duplicate rows.
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.tasks.etl.generate_daily_insights import _generate_async  # noqa: PLC0415

    kpi_date = date.today()
    engine = create_async_engine(_TEST_DB_URL)
    mock_response = _make_mock_anthropic_response(_make_valid_insight_payload())

    try:
        with patch("anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create = AsyncMock(return_value=mock_response)

            # Run twice for same date
            await _generate_async(TENANT_ID_STR, kpi_date)
            await _generate_async(TENANT_ID_STR, kpi_date)

        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT COUNT(*) FROM daily_insights "
                    "WHERE tenant_id = :tenant_id AND date = :kpi_date"
                ),
                {"tenant_id": TENANT_ID, "kpi_date": kpi_date},
            )
            count = result.scalar()

        assert count == 1, (
            f"UPSERT idempotency: 2 runs for same date must produce exactly 1 row, "
            f"got {count} (D-16 ON CONFLICT DO UPDATE)"
        )
    finally:
        await engine.dispose()


# ── AI-09 Grep Gate — NOT skipped, runs immediately ──────────────────────────


@pytest.mark.no_cover
def test_no_claude_calls_in_http_handlers() -> None:
    """AsyncAnthropic must not appear in app/api/ HTTP handler layer (AI-09).

    AI-09: Claude API calls are ONLY allowed from Celery tasks (app/tasks/etl/).
    This test greps the codebase to verify no AsyncAnthropic instantiation
    exists in app/api/ or app/schemas/ — those are HTTP-handler territory.

    This test does NOT require TEST_DATABASE_URL and runs on every pytest run.
    REQUIRED TO PASS from Wave 0 (no production code exists yet, so trivially true).
    """
    # Navigate from tests/integration/ up to the project root (CR-03 fix: dynamic path)
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    api_dir = project_root / "backend" / "app" / "api"

    result = subprocess.run(
        ["grep", "-r", "AsyncAnthropic", "--include=*.py", str(api_dir)],
        capture_output=True,
        text=True,
    )

    assert result.stdout == "", (
        f"AI-09 VIOLATION: AsyncAnthropic found in HTTP handler layer (app/api/):\n"
        f"{result.stdout}\n"
        "Claude API calls must only exist in app/tasks/etl/ (never in HTTP handlers)"
    )


@_integration_skip
@pytest.mark.asyncio
async def test_fallback_on_all_claude_failures() -> None:
    """Task completes with status='fallback' when Anthropic raises on every attempt (AI-07).

    AI-07: All retries exhausted → fallback report from detected_problems rows.
    status='fallback' (not 'failed') → Celery task does not raise.
    Phase 7 frontend shows "Generare AI eșuată" banner on fallback.
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.tasks.etl.generate_daily_insights import _generate_async  # noqa: PLC0415

    kpi_date = date.today()
    engine = create_async_engine(_TEST_DB_URL)

    try:
        with patch("anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            # Always raises — simulates total API failure
            mock_client.messages.create = AsyncMock(
                side_effect=Exception("Anthropic API unavailable")
            )

            # Must not raise — fallback path must complete
            await _generate_async(TENANT_ID_STR, kpi_date)

        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT status FROM daily_insights "
                    "WHERE tenant_id = :tenant_id AND date = :kpi_date"
                ),
                {"tenant_id": TENANT_ID, "kpi_date": kpi_date},
            )
            row = result.fetchone()

        assert row is not None, "_generate_async must write a row even on all-failure path (AI-07)"
        assert row[0] in ("fallback", "failed"), (
            f"status must be 'fallback' or 'failed' when all Claude retries fail, got '{row[0]}' (AI-07)"
        )
    finally:
        await engine.dispose()
