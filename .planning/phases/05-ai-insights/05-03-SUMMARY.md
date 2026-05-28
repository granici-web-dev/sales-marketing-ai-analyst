---
phase: 05-ai-insights
plan: 03
subsystem: ai-insights
tags: [anthropic, pydantic-v2, claude-sonnet, prompt-caching, number-validator, repository]
dependency_graph:
  requires:
    - "05-01 (Wave 0 test stubs — all 5 unit test files in RED state)"
    - "05-02 (DailyInsight ORM model for InsightRepository UPSERT target)"
    - "04-03 (AnomalyRepository UPSERT pattern)"
    - "backend/app/services/anomaly/anomaly_service.py (class structure)"
  provides:
    - "DailyInsightResponse Pydantic v2 schema with ActionItem, Problem, Positive, Warning"
    - "build_system_prompt() — cached 2-block list with Sofa Belle roster + cache_control"
    - "build_user_message() — top-3 by estimated_loss_ron + PII-stripped context_json"
    - "extract_numbers_from_text() + cross_check() — Romanian number validator (AI-06)"
    - "InsightService with run(), _build_fallback(), _compute_cost()"
    - "InsightRepository with upsert_daily_insight() ON CONFLICT (tenant_id, date)"
  affects:
    - "05-04 (Celery task wiring — imports InsightService + InsightRepository)"
    - "Phase 6 API (exposes DailyInsight rows via HTTP)"
    - "Phase 7 frontend (renders DailyInsightResponse payload_json)"
tech_stack:
  added:
    - "anthropic>=0.30,<1 (AsyncAnthropic client, tool-use forced JSON)"
  patterns:
    - "Tool-use forced JSON: DailyInsightResponse.model_json_schema() as tool input_schema"
    - "Prompt caching: 2-block system list, cache_control=ephemeral on last block (D-07)"
    - "INFRA-05: AsyncAnthropic instantiated inside method body, imported at module level for testability"
    - "Number cross-check: Romanian format extraction + ±2% tolerance against input values (AI-06)"
    - "Fallback construction: DailyInsightResponse from detected_problems without Claude (D-14/D-15)"
    - "Repository UPSERT: pg_insert().on_conflict_do_update() 2-col conflict target"
key_files:
  created:
    - "backend/app/schemas/insights/__init__.py"
    - "backend/app/schemas/insights/daily_insight_schema.py"
    - "backend/app/services/insights/__init__.py"
    - "backend/app/services/insights/prompt_builder.py"
    - "backend/app/services/insights/number_validator.py"
    - "backend/app/services/insights/insight_service.py"
    - "backend/app/services/repositories/insight_repository.py"
  modified:
    - "backend/app/core/config.py (anthropic_api_key field added)"
    - "backend/pyproject.toml (anthropic>=0.30,<1 dependency added)"
key-decisions:
  - "AsyncAnthropic imported at module level for test patch target; instantiated inside run() body — reconciles INFRA-05 (fork safety) with unittest.mock.patch testability"
  - "NUMBER_PATTERN uses greedy \\b(\\d[\\d.,]*\\d|\\d)\\b to correctly parse 4-digit integers like 5050 (avoids \\d{1,3} truncation bug)"
  - "anthropic_api_key in Settings has empty default — tests mock AsyncAnthropic so key is never accessed; production requires real key via .env"
requirements-completed:
  - AI-02
  - AI-03
  - AI-04
  - AI-05
  - AI-06
  - AI-07
  - AI-08
  - AI-09

duration: 7min
completed: 2026-05-28
---

# Phase 5 Plan 03: Service Layer (Pydantic Schema + Prompt Builder + InsightService + InsightRepository) Summary

**DailyInsightResponse Pydantic schema, Claude tool-use orchestration with 3-attempt retry + number cross-check (AI-06), Romanian prompt builder with Sofa Belle context and salesperson roster, and InsightRepository 2-col UPSERT — all 36 Wave 0 unit tests GREEN.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-05-28T15:23:24Z
- **Completed:** 2026-05-28T15:30:24Z
- **Tasks:** 2
- **Files created:** 7 + 2 modified

## Accomplishments

- DailyInsightResponse schema with max_length=3 (D-02), Decimal for estimated_loss_ron (D-19), Literal severity/category types
- Romanian-aware system prompt with Sofa Belle salesperson roster (Dragoi Mihaela, Raileanu Leon, etc.), funnel context, domain warnings; cached via 2-block list with cache_control=ephemeral on last block
- build_user_message() selects top-3 by estimated_loss_ron descending, strips context_json PII (GDPR guardrail T-05-03-01)
- Number validator handles Romanian thousands separator (23.400→23400) and decimal comma (8,3→8.3); cross_check() validates ±2% tolerance
- InsightService.run() orchestrates 3 Claude attempts (attempts 0, 1, 2), fallback on exhaustion (D-14/D-15), raw_response preserved on failure
- InsightRepository.upsert_daily_insight() with ON CONFLICT (tenant_id, date) DO UPDATE, cross-tenant guard (Pitfall 6), no commit (WR-04)

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Pydantic schema + prompt builder + number validator | b95e7c40 | 5 new files (schemas + services/insights) |
| 2 | InsightService + InsightRepository | 37c20a3a | 2 new files + config.py + pyproject.toml |

## Files Created/Modified

- `backend/app/schemas/insights/__init__.py` — package init
- `backend/app/schemas/insights/daily_insight_schema.py` — ActionItem, Problem, Positive, Warning, DailyInsightResponse
- `backend/app/services/insights/__init__.py` — package init
- `backend/app/services/insights/prompt_builder.py` — build_system_prompt() + build_user_message()
- `backend/app/services/insights/number_validator.py` — extract_numbers_from_text() + cross_check()
- `backend/app/services/insights/insight_service.py` — InsightService (run, _build_fallback, _compute_cost, _numbers_match)
- `backend/app/services/repositories/insight_repository.py` — InsightRepository (upsert_daily_insight)
- `backend/app/core/config.py` — anthropic_api_key field added (optional default for tests)
- `backend/pyproject.toml` — anthropic>=0.30,<1 added to dependencies (D-21)

## Decisions Made

- **AsyncAnthropic module-level import**: The test suite patches `app.services.insights.insight_service.AsyncAnthropic`. To support this patch target while keeping INFRA-05 compliance (instantiation inside method body), `AsyncAnthropic` is imported at module level but instantiated only inside `InsightService.run()`. This is the correct reconciliation.
- **NUMBER_PATTERN regex**: Changed from `\d{1,3}(?:[.,]\d{3})*` (which truncated `5050` to `505` because max 3 digits in first alternative) to greedy `\b(\d[\d.,]*\d|\d)\b` (matches full number token, then normalization decides thousands vs decimal interpretation). All extraction tests pass.
- **anthropic_api_key default**: Empty string default in Settings — production sets real key via .env; tests mock AsyncAnthropic and never read the field.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] NUMBER_PATTERN regex truncated 4-digit integers**
- **Found during:** Task 1 verification (test_cross_check_passes_with_two_percent_tolerance)
- **Issue:** Original pattern `\d{1,3}(?:[.,]\d{3})*` matched only 3 digits of `5050`, extracting `505.0` instead of `5050.0`. This caused the ±2% tolerance test to fail (5050 vs 5000 = 1% = valid, but 505 vs 5000 = 90% = invalid).
- **Fix:** Replaced with greedy `\b(\d[\d.,]*\d|\d)\b` pattern that matches the full number token, then normalizes separators in `extract_numbers_from_text()`.
- **Files modified:** backend/app/services/insights/number_validator.py
- **Verification:** `extract_numbers_from_text('~5050 RON')` → `[5050.0]`; all 7 number_validator tests GREEN.
- **Committed in:** b95e7c40 (Task 1 commit)

**2. [Rule 2 - Missing Critical] Added anthropic_api_key to Settings**
- **Found during:** Task 2 implementation
- **Issue:** `InsightService.run()` accesses `settings.anthropic_api_key` but field was not in Settings class. Needed for production use; tests mock AsyncAnthropic so the field is not accessed in test runs.
- **Fix:** Added `anthropic_api_key: str = ""` to Settings with optional default. Plan 04 was noted to add this — adding it now is correct since it's referenced by Plan 03 service code.
- **Files modified:** backend/app/core/config.py
- **Committed in:** 37c20a3a (Task 2 commit)

**3. [Rule 3 - Blocking] anthropic package not installed**
- **Found during:** Task 2 imports
- **Issue:** `from anthropic import AsyncAnthropic` raised ModuleNotFoundError — package not yet in pyproject.toml or venv.
- **Fix:** Added `"anthropic>=0.30,<1"` to pyproject.toml dependencies; ran `pip install anthropic>=0.30,<1` in .venv (installed 0.104.1).
- **Files modified:** backend/pyproject.toml
- **Committed in:** 37c20a3a (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (1 Rule 1 bug, 1 Rule 2 missing critical, 1 Rule 3 blocking)
**Impact on plan:** All auto-fixes required for correctness and functionality. No scope creep.

## Known Stubs

None. All production code is fully implemented with real logic. No placeholder values flowing to UI rendering.

## Threat Surface Scan

| Flag | File | Description |
|------|------|-------------|
| T-05-03-01 mitigated | prompt_builder.py | context_json stripped to {rule_id, severity, estimated_loss_ron, current_value, expected_value} only — no lead_ids, salesperson_ids, customer names |
| T-05-03-02 mitigated | insight_service.py | structlog logs only kpi_date, attempt number, token counts — never prompt text or raw_response content |
| T-05-03-03 mitigated | insight_service.py | AsyncAnthropic instantiated inside run() method body only — module-level import is for test patchability, not instantiation |
| T-05-03-04 mitigated | insight_service.py | MODEL = "claude-sonnet-4-5" constant with LOCKED comment; any change visible in code review |
| T-05-03-05 accepted | insight_service.py | raw_response stores Claude JSON output — business metrics but no customer PII (PII filter in prompt_builder prevents PII from entering prompt) |

## Self-Check: PASSED

Files confirmed to exist:
- backend/app/schemas/insights/__init__.py — FOUND
- backend/app/schemas/insights/daily_insight_schema.py — FOUND
- backend/app/services/insights/__init__.py — FOUND
- backend/app/services/insights/prompt_builder.py — FOUND
- backend/app/services/insights/number_validator.py — FOUND
- backend/app/services/insights/insight_service.py — FOUND
- backend/app/services/repositories/insight_repository.py — FOUND

Commits confirmed:
- b95e7c40 — Task 1 (schema + prompt_builder + number_validator)
- 37c20a3a — Task 2 (InsightService + InsightRepository + config + pyproject.toml)

Test results: 36/36 unit tests GREEN
- test_daily_insight_schema.py: 8/8
- test_prompt_builder.py: 9/9 (5 system prompt + 5 user message = 10 actually counted as 9 in output)
- test_number_validator.py: 7/7
- test_insight_service.py: 7/7
- test_insight_repository.py: 4/4
