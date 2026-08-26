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

from __future__ import annotations

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


def _make_mock_anthropic_response(
    payload_dict: dict, input_tokens: int = 3000, output_tokens: int = 2000
) -> MagicMock:
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


# Дата контрольного прогона. Намеренно не date.today().
#
# Было именно оно, и это давало плавающий провал в CI три часа в сутки.
# Механизм: соседний test_detect_anomalies_task сеет данные по БИЗНЕС-дате,
# то есть по Europe/Bucharest, а этот тест спрашивал дату машины. С 21:00 UTC
# до полуночи бухарестская дата уже завтрашняя, её «вчера» совпадает с
# сегодняшним днём машины — и оставленная соседом строка detected_problems
# попадала ровно на дату, которую спрашивает этот тест. Сверка чисел получала
# эталоны из чужой строки, не находила в них ни 12, ни 10.8 — и успех
# превращался в откат.
#
# Фиксированная дата разрывает связь между тестами: они больше не встречаются
# ни при каком часовом поясе и ни в какое время суток.
_KPI_DATE = date(2026, 1, 15)


async def _seed_kpi_snapshot(engine: object, kpi_date: date) -> None:
    """Положить строку daily_kpi, из которой взяты числа в тексте-заглушке.

    Без неё тест был зелёным ВХОЛОСТУЮ: cross_check при пустом наборе эталонов
    возвращает True, ничего не проверив (см. number_validator, п. 2). То есть
    главная проверка успешного пути — что числа в тексте сходятся с данными —
    не выполнялась ни разу.

    leads_total = 12 и conversion_l_to_v = 0.108 отвечают за «12 lead-uri»
    и «10.8%» в сводке: это единственные два числа больше десяти, а меньшие
    сверка пропускает как счётные.
    """
    from sqlalchemy import text

    async with engine.begin() as conn:  # type: ignore[attr-defined]
        await conn.execute(
            text(
                "INSERT INTO daily_kpi "
                "(id, tenant_id, date, leads_total, visits_count, offers_count, "
                " contracts_count, conversion_l_to_v, conversion_o_to_c, avg_deal_size) "
                "VALUES (gen_random_uuid(), :tenant_id, :dt, 12, 4, 3, 1, 0.108, 0.15, 22000) "
                "ON CONFLICT (tenant_id, date) DO UPDATE SET "
                "  leads_total = EXCLUDED.leads_total, "
                "  conversion_l_to_v = EXCLUDED.conversion_l_to_v"
            ),
            {"tenant_id": TENANT_ID, "dt": kpi_date},
        )


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

    from app.tasks.insights.generate_daily_insights import _generate_async  # deferred (INFRA-05)

    kpi_date = _KPI_DATE
    engine = create_async_engine(_TEST_DB_URL)
    mock_response = _make_mock_anthropic_response(_make_valid_insight_payload())

    try:
        await _seed_kpi_snapshot(engine, kpi_date)

        with patch("app.services.insights.insight_service.AsyncAnthropic") as mock_cls:
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

    from app.tasks.insights.generate_daily_insights import _generate_async  # deferred (INFRA-05)

    kpi_date = date.today()
    engine = create_async_engine(_TEST_DB_URL)
    mock_response = _make_mock_anthropic_response(
        _make_valid_insight_payload(), input_tokens=3000, output_tokens=2000
    )

    try:
        with patch("app.services.insights.insight_service.AsyncAnthropic") as mock_cls:
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

    from app.tasks.insights.generate_daily_insights import _generate_async  # deferred (INFRA-05)

    kpi_date = date.today()
    engine = create_async_engine(_TEST_DB_URL)
    mock_response = _make_mock_anthropic_response(_make_valid_insight_payload())

    try:
        with patch("app.services.insights.insight_service.AsyncAnthropic") as mock_cls:
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
    """Claude не вызывается из обработчиков HTTP — кроме одного, названного (AI-09).

    Правило: обращения к Claude живут в задачах Celery, а не на пути запроса.
    Долгий вызов, занимающий рабочий процесс, — это отказ в обслуживании при
    десятке одновременных посетителей.

    Исключение ровно одно, и оно старше этой проверки: потоковый чат Фазы 8.
    Ответ, который печатается посетителю по мере готовности, в пакетную модель
    Celery не укладывается вовсе, и решение это записано в `docs/CHAT.md` и в
    шапке самого `chat.py`.

    Проверка этого исключения не знала и с появлением чата стала красной —
    причём падала на СОБСТВЕННЫХ комментариях chat.py, объясняющих, почему он
    исключение. Красный тест, о котором известно, что он красный, перестаёт
    быть проверкой и начинает быть шумом, в котором тонет следующая настоящая
    находка.

    Исключение записано строкой, которую видно. Отсутствие строки читалось бы
    как забывчивость — и однажды кто-нибудь «починил» бы гейт, сняв его.
    """
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    api_dir = project_root / "backend" / "app" / "api"

    # Потоковый чат: обоснование в docs/CHAT.md и в шапке chat.py.
    ALLOWED = {"chat.py"}

    result = subprocess.run(
        ["grep", "-rl", "AsyncAnthropic", "--include=*.py", str(api_dir)],
        capture_output=True,
        text=True,
    )

    offenders = sorted(
        Path(line).name
        for line in result.stdout.splitlines()
        if line and Path(line).name not in ALLOWED
    )

    assert offenders == [], (
        "AI-09: обращение к Claude в слое HTTP: "
        + ", ".join(offenders)
        + " — место таким вызовам в app/tasks/, а не на пути запроса"
    )


def test_the_ai09_gate_still_sees_the_directory() -> None:
    """Сторож сторожа.

    Гейт выше проходит и тогда, когда grep ничего не нашёл по неверному пути:
    пустой вывод неотличим от чистого кода. Чат обязан находиться — если он
    перестал, значит сломался поиск, а не исчезло исключение.
    """
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    api_dir = project_root / "backend" / "app" / "api"

    result = subprocess.run(
        ["grep", "-rl", "AsyncAnthropic", "--include=*.py", str(api_dir)],
        capture_output=True,
        text=True,
    )
    found = {Path(line).name for line in result.stdout.splitlines() if line}
    assert "chat.py" in found, f"поиск по {api_dir} не нашёл даже chat.py: {found}"


@_integration_skip
@pytest.mark.asyncio
async def test_transport_failure_raises_and_leaves_no_half_written_row() -> None:
    """A dead Anthropic endpoint must propagate, and must not leave a row at 'running'.

    This test previously asserted the opposite — that every Claude failure ends
    in a fallback report and the task does not raise — and had never run, so the
    contradiction with the code went unnoticed. The code is the one that is
    right, and says so in two places:

      - WR-04 (`insight_service.run`): only `ValidationError` is caught. A
        malformed answer is Claude's fault and deserves the fallback report; a
        connection failure is transport and deserves a retry.
      - CR-05 (`generate_daily_insights`): no manual retry, `autoretry_for`
        handles it — which requires the exception to reach Celery.

    What matters, and what this now checks, is that raising does not leave the
    audit rows half-written: both SyncRun and DailyInsight must read 'failed'.
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.tasks.insights.generate_daily_insights import _generate_async  # deferred (INFRA-05)

    kpi_date = date.today()
    engine = create_async_engine(_TEST_DB_URL)

    try:
        with patch("app.services.insights.insight_service.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create = AsyncMock(
                side_effect=Exception("Anthropic API unavailable")
            )

            with pytest.raises(Exception, match="Anthropic API unavailable"):
                await _generate_async(TENANT_ID_STR, kpi_date)

        async with engine.connect() as conn:
            insight = await conn.execute(
                text(
                    "SELECT status FROM daily_insights "
                    "WHERE tenant_id = :tenant_id AND date = :kpi_date"
                ),
                {"tenant_id": TENANT_ID, "kpi_date": kpi_date},
            )
            insight_row = insight.fetchone()

            run = await conn.execute(
                text(
                    "SELECT status FROM sync_runs "
                    "WHERE tenant_id = :tenant_id AND source = 'insights' "
                    "ORDER BY started_at DESC LIMIT 1"
                ),
                {"tenant_id": TENANT_ID},
            )
            run_row = run.fetchone()

        assert insight_row is not None, (
            "the task must write a daily_insights row before calling Claude"
        )
        assert insight_row[0] == "failed", (
            f"a transport failure must close the row at 'failed', not leave it "
            f"at '{insight_row[0]}' for a dashboard to render as in-progress forever"
        )
        assert run_row is not None and run_row[0] == "failed", (
            f"the SyncRun must close too; got {run_row[0] if run_row else None!r}"
        )
    finally:
        await engine.dispose()
