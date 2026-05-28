from __future__ import annotations

"""InsightService — Claude Sonnet 4.5 orchestration for Phase 5 AI Insights.

D-14: status state machine: success | fallback | failed.
D-15: Fallback summary = "Generare AI eșuată — raport bazat pe anomalii detectate automat".
AI-06: Number cross-check — up to 2 retries before triggering fallback.
AI-07: Fallback behavior when all Claude retries fail.
AI-08: Token usage tracked in result dict.
D-model: MODEL="claude-sonnet-4-5" — LOCKED, do NOT change (CLAUDE.md, STATE.md decision).

T-05-03-02: structlog logs only counts, dates, rule names, attempt numbers.
            Never log prompt text, raw_response content, or context_json fields.
T-05-03-03: AsyncAnthropic instantiated ONLY inside run() method body (INFRA-05).
T-05-03-04: MODEL constant is "claude-sonnet-4-5" — locked. Any change visible in code review.
"""

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

# AsyncAnthropic imported at module level for testability (patch target).
# Instantiated ONLY inside method body per INFRA-05 (never at module level).
from anthropic import AsyncAnthropic

# Module-level constants — NOT inside class body
_MAX_CLAUDE_RETRIES = 2  # attempts 0, 1, 2 = 3 total (AI-06)
MODEL = "claude-sonnet-4-5"  # LOCKED — do NOT change (D-model, CLAUDE.md, STATE.md)
MAX_TOKENS = 4096
TEMPERATURE = 0.2

log = structlog.get_logger(__name__)


class InsightService:
    """Transforms detected_problems + daily_kpi into DailyInsightResponse via Claude Sonnet 4.5.

    Constructor takes AsyncSession and tenant_id — same pattern as AnomalyService.
    All Claude calls are async. Instantiated per-invocation inside _generate_async().

    D-model: model='claude-sonnet-4-5' — do NOT change.
    T-05-03-03: AsyncAnthropic is ONLY instantiated inside InsightService.run() method body.
    """

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id
        self._log = log.bind(tenant_id=str(tenant_id), service="insight_service")

    async def run(self, kpi_date: date) -> tuple[dict, str]:
        """Generate DailyInsightResponse for kpi_date.

        D-14: Returns (result_dict, status) where status in ('success', 'fallback', 'failed').
        AI-06: Retries up to _MAX_CLAUDE_RETRIES times on number mismatch or schema failure.
        AI-07: Returns fallback on exhaustion — never raises unhandled exception.
        T-05-03-03: AsyncAnthropic client instantiated here (not at module level) — INFRA-05.

        Args:
            kpi_date: The business date to generate insights for.

        Returns:
            Tuple of (result_dict, status_string).
            result_dict keys: payload, input_tokens, output_tokens, cost_usd, raw_response.
        """
        # All application imports inside method body (INFRA-05) except AsyncAnthropic
        # (which is imported at module level for testability — see module docstring).
        from app.core.config import settings  # noqa: PLC0415
        from app.schemas.insights.daily_insight_schema import DailyInsightResponse  # noqa: PLC0415
        from app.services.insights.prompt_builder import (  # noqa: PLC0415
            build_system_prompt,
            build_user_message,
        )

        # Fetch input data from DB (or test doubles via _fetch_* methods)
        problems_rows = await self._fetch_detected_problems(kpi_date)
        kpi_row = await self._fetch_kpi_snapshot(kpi_date)

        system_blocks = build_system_prompt()
        user_content = build_user_message(kpi_row, problems_rows)

        tool_schema = {
            "name": "generate_daily_insight",
            "description": "Generează raportul zilnic de business în română pentru Sofa Belle.",
            "input_schema": DailyInsightResponse.model_json_schema(),
        }

        # Instantiate inside method body — INFRA-05 / T-05-03-03
        client = AsyncAnthropic(api_key=settings.anthropic_api_key)

        last_raw: str = ""
        last_usage = None

        for attempt in range(_MAX_CLAUDE_RETRIES + 1):  # 0, 1, 2
            response = await client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                system=system_blocks,
                messages=[{"role": "user", "content": user_content}],
                tools=[tool_schema],
                tool_choice={"type": "tool", "name": "generate_daily_insight"},
            )

            last_usage = response.usage

            tool_block = next(
                (b for b in response.content if b.type == "tool_use"), None
            )

            if tool_block is None:
                # WR-02: Capture whatever Claude returned for debugging (not just "")
                last_raw = json.dumps([
                    {"type": b.type, "text": getattr(b, "text", "")[:500]}
                    for b in response.content
                ])
                self._log.warning("insight.no_tool_block", attempt=attempt)
                continue

            last_raw = json.dumps(tool_block.input)

            from pydantic import ValidationError  # noqa: PLC0415

            try:
                parsed = DailyInsightResponse.model_validate(tool_block.input)
            except ValidationError as exc:
                # WR-04: Only catch ValidationError — non-Pydantic exceptions propagate
                # Log field paths only — not full error text (may contain business data)
                error_locs = [str(e.get("loc", "")) for e in exc.errors()]
                self._log.warning(
                    "insight.pydantic_validation_failed",
                    attempt=attempt,
                    error_locs=error_locs,
                )
                continue

            # AI-06: number cross-check — extracted numbers must match input data ±2%
            if not self._numbers_match(parsed, kpi_row or {}, problems_rows):
                self._log.warning("insight.number_mismatch", attempt=attempt)
                continue

            # SUCCESS PATH
            parsed.generated_at = datetime.now(UTC)
            cost_usd = self._compute_cost(last_usage)

            self._log.info(
                "insight.generated",
                kpi_date=str(kpi_date),
                attempt=attempt,
                input_tokens=last_usage.input_tokens,
                output_tokens=last_usage.output_tokens,
            )

            return (
                {
                    "payload": parsed.model_dump(mode="json"),
                    "input_tokens": last_usage.input_tokens,
                    "output_tokens": last_usage.output_tokens,
                    "cost_usd": cost_usd,
                    "raw_response": last_raw,
                },
                "success",
            )

        # All retries exhausted — return fallback (D-14, D-15)
        self._log.warning(
            "insight.fallback",
            kpi_date=str(kpi_date),
            attempts=_MAX_CLAUDE_RETRIES + 1,
        )
        fallback = self._build_fallback(problems_rows)
        return (
            {
                "payload": fallback.model_dump(mode="json"),
                "input_tokens": last_usage.input_tokens if last_usage else 0,
                "output_tokens": last_usage.output_tokens if last_usage else 0,
                "cost_usd": self._compute_cost(last_usage) if last_usage else Decimal("0"),
                "raw_response": last_raw,
            },
            "fallback",
        )

    @staticmethod
    def _compute_cost(usage: object | None) -> Decimal:
        """Compute cost in USD for a Claude API call.

        Claude Sonnet 4.5 pricing: $3/MTok input, $15/MTok output (SPEC.md Section 10).

        Args:
            usage: Anthropic Usage object with input_tokens and output_tokens.

        Returns:
            Decimal cost in USD. Returns Decimal("0") if usage is None.
        """
        if usage is None:
            return Decimal("0")
        input_tok = (usage.input_tokens or 0) if hasattr(usage, "input_tokens") else 0
        output_tok = (usage.output_tokens or 0) if hasattr(usage, "output_tokens") else 0
        return Decimal(str((input_tok / 1_000_000) * 3.0 + (output_tok / 1_000_000) * 15.0))

    def _numbers_match(
        self,
        parsed: object,
        kpi_snapshot: dict,
        problems_input: list,
    ) -> bool:
        """AI-06: cross-check narrative numbers against input data ±2%.

        Delegates to number_validator.cross_check().
        """
        from app.services.insights.number_validator import cross_check  # noqa: PLC0415
        return cross_check(parsed, kpi_snapshot, problems_input)

    def _build_fallback(self, problems_rows: list) -> object:
        """D-14/D-15: construct DailyInsightResponse from detected_problems without Claude.

        Called when all Claude retries are exhausted.
        summary = 'Generare AI eșuată — raport bazat pe anomalii detectate automat'.
        Each detected_problem row becomes a Problem with actions=[].

        Args:
            problems_rows: list of detected_problems row dicts (from _fetch_detected_problems).

        Returns:
            DailyInsightResponse with fallback content.
        """
        from app.schemas.insights.daily_insight_schema import (  # noqa: PLC0415
            DailyInsightResponse,
            Problem,
        )

        problems = []
        for row in problems_rows[:3]:
            # Handle both dict rows (test fixtures) and ORM objects
            if isinstance(row, dict):
                rule_id = row.get("rule_id", "unknown")
                severity = row.get("severity", "medium")
                loss = row.get("estimated_loss_ron") or Decimal("0")
            else:
                rule_id = getattr(row, "rule_id", "unknown")
                severity = getattr(row, "severity", "medium")
                loss = getattr(row, "estimated_loss_ron", None) or Decimal("0")

            problems.append(
                Problem(
                    id=rule_id,
                    severity=severity,
                    category="sales",
                    title=rule_id.replace("_", " ").title(),
                    description=f"Anomalie detectată: {rule_id}",
                    estimated_loss_ron=Decimal(str(loss)) if not isinstance(loss, Decimal) else loss,
                    actions=[],
                )
            )

        return DailyInsightResponse(
            summary="Generare AI eșuată — raport bazat pe anomalii detectate automat",
            problems=problems,
            positives=[],
            warnings=[],
            weekly_action_plan=["Revizuiți anomaliile detectate automat și contactați echipa de vânzări."],
            generated_at=datetime.now(UTC),
        )

    # ── Private DB fetch helpers ──────────────────────────────────────────────

    async def _fetch_detected_problems(self, kpi_date: date) -> list[dict]:
        """Fetch detected_problems rows for kpi_date, top-3 by estimated_loss_ron DESC.

        Used by run() — can be replaced by AsyncMock in unit tests.

        Args:
            kpi_date: The business date to query.

        Returns:
            list of detected_problems row dicts, at most 3 items.
        """
        from sqlalchemy import select  # noqa: PLC0415
        from app.models.anomaly.detected_problem import DetectedProblem  # noqa: PLC0415

        stmt = (
            select(
                DetectedProblem.rule_id,
                DetectedProblem.severity,
                DetectedProblem.estimated_loss_ron,
                DetectedProblem.current_value,
                DetectedProblem.expected_value,
                DetectedProblem.context_json,
            )
            .where(
                DetectedProblem.tenant_id == self._tenant_id,
                DetectedProblem.date == kpi_date,
            )
            .order_by(DetectedProblem.estimated_loss_ron.desc())
            .limit(3)
        )
        result = await self._session.execute(stmt)
        rows = result.fetchall()
        return [
            {
                "rule_id": row.rule_id,
                "severity": row.severity,
                "estimated_loss_ron": row.estimated_loss_ron,
                "current_value": row.current_value,
                "expected_value": row.expected_value,
                "context_json": row.context_json,
            }
            for row in rows
        ]

    async def _fetch_kpi_snapshot(self, kpi_date: date) -> dict | None:
        """Fetch daily_kpi row for kpi_date.

        Returns dict with KPI fields, or None if no data for this date.
        Used by run() — can be replaced by AsyncMock in unit tests.

        Args:
            kpi_date: The business date to query.

        Returns:
            dict with KPI field values, or None.
        """
        from sqlalchemy import select  # noqa: PLC0415
        from app.models.metrics.daily_kpi import DailyKpi  # noqa: PLC0415

        stmt = select(
            DailyKpi.date,
            DailyKpi.leads_total,
            DailyKpi.visits_count,
            DailyKpi.offers_count,
            DailyKpi.contracts_closed,
            DailyKpi.conversion_l_to_v,
            DailyKpi.conversion_v_to_o,
            DailyKpi.conversion_o_to_c,
            DailyKpi.conversion_l_to_c,
            DailyKpi.avg_deal_size,
            DailyKpi.wow_delta_pct,
            DailyKpi.mom_delta_pct,
        ).where(
            DailyKpi.tenant_id == self._tenant_id,
            DailyKpi.date == kpi_date,
        )
        result = await self._session.execute(stmt)
        row = result.fetchone()
        if row is None:
            return None
        return {
            "date": row.date,
            "leads_total": row.leads_total,
            "visits_count": row.visits_count,
            "offers_count": row.offers_count,
            "contracts_closed": row.contracts_closed,
            "conversion_l_to_v": row.conversion_l_to_v,
            "conversion_v_to_o": row.conversion_v_to_o,
            "conversion_o_to_c": row.conversion_o_to_c,
            "conversion_l_to_c": row.conversion_l_to_c,
            "avg_deal_size": row.avg_deal_size,
            "wow_delta_pct": row.wow_delta_pct,
            "mom_delta_pct": row.mom_delta_pct,
        }
