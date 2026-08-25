---
phase: 05-ai-insights
fixed_at: 2026-05-28T12:00:00Z
review_path: .planning/phases/05-ai-insights/05-REVIEW.md
iteration: 1
findings_in_scope: 9
fixed: 9
skipped: 0
status: all_fixed
---

# Phase 05: Code Review Fix Report

**Fixed at:** 2026-05-28T12:00:00Z
**Source review:** .planning/phases/05-ai-insights/05-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 9 (CR-01, CR-02, CR-03, CR-04, WR-01, WR-02, WR-03, WR-04, WR-05)
- Fixed: 9
- Skipped: 0

## Fixed Issues

### CR-01: Pipeline chain is never scheduled

**Files modified:** `backend/app/tasks/celery_app.py`
**Commit:** b28ad833
**Applied fix:** Replaced the two standalone RedBeat entries (daily-mefi-sync at 04:00 and
daily-insights-generation at 06:00) with a single `daily_pipeline` chain entry at 04:00.
The chain uses `daily_pipeline(settings.sofa_belle_tenant_id)` from `sync_mefi_leads.py`,
enforcing PIPE-02 halt semantics. If sync fails, insights will not run against stale data.

---

### CR-02: cross_check systematically rejects valid Claude output

**Files modified:** `backend/app/services/insights/number_validator.py`
**Commit:** 1c5a8716
**Applied fix:** Added `PERCENT_FIELDS` set and percentage-form expansion inside the
`cross_check()` reference-set builder. For each KPI field in the set (conversion rates,
delta percentages), `float_val * 100` is added to `reference_values` alongside the raw
decimal. This prevents systematic false negatives when Claude writes e.g. "10.8%
conversie" but the KPI snapshot stores 0.1080.

---

### CR-03: Hardcoded developer absolute path in AI-09 grep gate

**Files modified:** `backend/tests/integration/test_generate_daily_insights_task.py`
**Commit:** 75bee71a
**Applied fix:** Added `from pathlib import Path` import. Replaced the hardcoded
`project_root` string with `Path(__file__).resolve().parent.parent.parent.parent`.
Changed grep invocation to pass the full `api_dir` path directly (no `cwd=` argument).
Test now works on any machine.

---

### CR-04: deadline: str has no enum enforcement

**Files modified:** `backend/app/schemas/insights/daily_insight_schema.py`, `backend/app/services/insights/insight_service.py`
**Commit:** 08a18ca4
**Applied fix:** Changed `ActionItem.deadline` from bare `str` to
`Literal["Azi", "Mâine", "Săptămâna aceasta", "Luna aceasta"]`. Pydantic now rejects
invalid deadline values and `model_json_schema()` emits an `"enum"` constraint in the
tool schema sent to Claude. Also applied WR-05 in this commit (see below).

---

### WR-01: SyncRun.status always "success" even on fallback

**Files modified:** `backend/app/tasks/etl/generate_daily_insights.py`
**Commit:** 28fb2978
**Applied fix:** Changed `sync_run.status = "success"` to `sync_run.status = status`,
propagating the actual insight outcome ("success" | "fallback") to the SyncRun audit row.
Phase 7 monitoring dashboards reading SyncRun will now correctly detect fallback events.

---

### WR-02: raw_response is empty string when no tool_use block returned

**Files modified:** `backend/app/services/insights/insight_service.py`
**Commit:** e9b81351
**Applied fix:** In the `tool_block is None` branch, `last_raw` is now set to a JSON
serialization of the actual response content (type + first 500 chars of text) instead of
remaining `""`. Provides debugging value when Claude returns non-tool-use responses.
WR-04 was also fixed in this commit (see below).

---

### WR-03: Integration tests mock wrong patch target

**Files modified:** `backend/tests/integration/test_generate_daily_insights_task.py`
**Commit:** f6256b16
**Applied fix:** Replaced all 4 occurrences of
`patch("anthropic.AsyncAnthropic")` with
`patch("app.services.insights.insight_service.AsyncAnthropic")`.
Patching the correct namespace ensures the mock intercepts calls regardless of module
import order and caching in the test suite.

---

### WR-04: Broad except Exception swallows non-Pydantic exceptions

**Files modified:** `backend/app/services/insights/insight_service.py`
**Commit:** e9b81351
**Applied fix:** Narrowed `except Exception` to `except ValidationError`. Non-Pydantic
exceptions (TypeError, AttributeError from unexpected response shapes) now propagate
instead of being silently treated as validation failures. Removed the nested try/except
that was required only because `exc.errors()` is Pydantic-only. Combined with WR-02 fix.

---

### WR-05: weekly_action_plan has no min_length constraint

**Files modified:** `backend/app/schemas/insights/daily_insight_schema.py`, `backend/app/services/insights/insight_service.py`
**Commit:** 08a18ca4
**Applied fix:** Changed `weekly_action_plan: list[str]` to
`weekly_action_plan: list[str] = Field(min_length=1)`. Updated `_build_fallback()` to
provide a minimal action item (`"Revizuiți anomaliile detectate automat și contactați
echipa de vânzări."`) instead of `[]`, satisfying the new constraint. Combined with CR-04 fix.

---

## Skipped Issues

None — all 9 in-scope findings were successfully fixed.

---

_Fixed: 2026-05-28T12:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
