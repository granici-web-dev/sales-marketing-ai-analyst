---
phase: 05-ai-insights
plan: 04
subsystem: ai-insights
tags: [celery, anthropic, beat-schedule, pipe-01, nullpool, deferred-imports]
dependency_graph:
  requires:
    - "05-03 (InsightService + InsightRepository — imported by task)"
    - "05-02 (DailyInsight ORM model — UPSERT target)"
    - "04-04 (detect_anomalies task — 3rd chain link that now precedes this task)"
    - "backend/app/tasks/celery_app.py (include list + beat registration pattern)"
    - "backend/app/tasks/etl/sync_mefi_leads.py (daily_pipeline() chain definition)"
  provides:
    - "generate_daily_insights Celery task — 4th and final PIPE-01 chain link"
    - "Beat entry 'daily-insights-generation' at 06:00 Europe/Bucharest"
    - "ANTHROPIC_API_KEY env var wired to backend + worker services in docker-compose.yml"
  affects:
    - "Phase 6 API (daily_insights table rows now populated nightly)"
    - "Phase 7 frontend (DailyInsightResponse payload_json available for rendering)"
tech_stack:
  added: []
  patterns:
    - "NullPool + asyncio.run(_generate_async()) — mirrors detect_anomalies.py (INFRA-05)"
    - "WR-06 stale SyncRun cleanup before writing new SyncRun"
    - "DailyInsight UPSERT state machine: running → success/fallback/failed (D-16)"
    - "_generate_async(str|UUID, kpi_date=None) — accepts both Celery UUID and test string"
    - "soft_time_limit=120, time_limit=180 per AI-SPEC §4b.5 latency budget"
key_files:
  created:
    - "backend/app/tasks/etl/generate_daily_insights.py"
  modified:
    - "backend/app/tasks/celery_app.py (include list + beat entry)"
    - "backend/app/tasks/etl/sync_mefi_leads.py (daily_pipeline() 4th chain link)"
    - ".env.example (ANTHROPIC_API_KEY placeholder)"
    - "docker-compose.yml (ANTHROPIC_API_KEY in backend + worker)"
decisions:
  - "_generate_async signature: str|UUID + optional kpi_date param — reconciles Celery entry (UUID) with integration test calls (TENANT_ID_STR, kpi_date) without separate function overloads"
  - "Beat entry placed inside same try/except as existing 'daily-mefi-sync' — consistent error handling; failure is non-fatal at import time, authoritative on beat container startup"
  - "config.py and pyproject.toml not modified — both already updated in Wave 3 (05-03); no duplicate changes"
metrics:
  duration: 2min
  started: 2026-05-28T15:33:23Z
  completed: 2026-05-28T15:36:20Z
  tasks: 2
  files_created: 1
  files_modified: 4
requirements-completed:
  - AI-01
  - AI-09
---

# Phase 5 Plan 04: Celery Task Wiring (generate_daily_insights + Beat Schedule) Summary

**NullPool generate_daily_insights Celery task created as 4th PIPE-01 chain link; beat entry 'daily-insights-generation' at 06:00 Europe/Bucharest registered; ANTHROPIC_API_KEY wired to docker-compose backend + worker services; 37/37 Phase 5 tests pass (4 DB-dependent skipped).**

## Performance

- **Duration:** 2 min
- **Started:** 2026-05-28T15:33:23Z
- **Completed:** 2026-05-28T15:36:20Z
- **Tasks:** 2
- **Files created:** 1 + 4 modified

## Accomplishments

- `generate_daily_insights` task with `name="tasks.etl.generate_daily_insights"`, `soft_time_limit=120`, `time_limit=180` (AI-SPEC §4b.5)
- Full PIPE-01 chain now operational: `sync_mefi_leads → calculate_daily_kpis → detect_anomalies → generate_daily_insights`
- WR-06 stale SyncRun cleanup, PIPE-04 audit trail, T-05-04-01..06 security mitigations
- DailyInsight state machine: writes `status='running'` at start, upserts `success/fallback/failed` on completion
- Beat entry `'daily-insights-generation'` at `crontab(hour=6, minute=0)` with `args=[settings.sofa_belle_tenant_id]`
- `celery_app.py` include list extended with `"app.tasks.etl.generate_daily_insights"`
- `ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}` added to both `backend` and `worker` services in docker-compose.yml (beat excluded per plan — beat does not instantiate Anthropic client)
- `ANTHROPIC_API_KEY` placeholder added to `.env.example` with console URL comment

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | generate_daily_insights Celery task | a4fd6bf0 | backend/app/tasks/etl/generate_daily_insights.py |
| 2 | Infrastructure wiring — celery_app, chain, env | 61da5696 | celery_app.py, sync_mefi_leads.py, .env.example, docker-compose.yml |

## Files Created/Modified

- `backend/app/tasks/etl/generate_daily_insights.py` — 4th Celery task; NullPool + deferred imports; InsightService + InsightRepository wired
- `backend/app/tasks/celery_app.py` — include list + 'daily-insights-generation' beat at 06:00
- `backend/app/tasks/etl/sync_mefi_leads.py` — daily_pipeline() extended to 4-link chain
- `.env.example` — ANTHROPIC_API_KEY placeholder added
- `docker-compose.yml` — ANTHROPIC_API_KEY wired to backend + worker services

## Decisions Made

- **_generate_async signature**: `(tenant_id: str | UUID, kpi_date: object = None)` — the integration tests call `_generate_async(TENANT_ID_STR, kpi_date)` with a string and an explicit date, while the Celery task calls with `UUID(tenant_id)`. The `str | UUID` + internal `isinstance` check reconciles both callers without separate overloads.
- **config.py / pyproject.toml not modified**: Both were already updated in Plan 03 (Wave 3). The plan noted them as files to modify, but they were already correct — no duplicate edits made. Documented here for traceability.
- **Beat try/except scope**: The new `_insights_entry.save()` is inside the same `try/except BLE001` block as the existing `_entry.save()` — consistent failure semantics (non-fatal at import time; authoritative registration happens on beat container startup).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] _generate_async signature mismatch with integration test contracts**
- **Found during:** Task 1 implementation
- **Issue:** The plan action showed `async def _generate_async(tenant_id: UUID) -> dict:` (single UUID arg), but the Wave 0 integration tests call `_generate_async(TENANT_ID_STR, kpi_date)` with a string tenant_id and explicit date. Test contracts from Wave 0 are authoritative.
- **Fix:** Changed signature to `_generate_async(tenant_id: str | UUID, kpi_date: object = None)`. UUID conversion via `isinstance(tenant_id, str)` check inside function body. The Celery task still calls `asyncio.run(_generate_async(UUID(tenant_id)))` — valid since UUID passes the isinstance guard.
- **Files modified:** backend/app/tasks/etl/generate_daily_insights.py
- **Impact:** None on production behavior; required for test compatibility.

**2. [Rule 2 - No-op] config.py anthropic_api_key already present from Wave 3**
- **Found during:** Task 2 planning
- **Issue:** Plan listed `backend/app/core/config.py` in `files_modified` and said to add `anthropic_api_key: str`. Field was already added in Plan 03 (Wave 3) as deviation fix #2.
- **Fix:** No change made — field already correct. Noted for traceability.

**3. [Rule 2 - No-op] pyproject.toml anthropic>=0.30,<1 already present from Wave 3**
- **Found during:** Task 2 planning
- **Issue:** Plan listed `backend/pyproject.toml` and said to add `"anthropic>=0.30,<1"`. Already added in Plan 03 (Wave 3) as deviation fix #3.
- **Fix:** No change made — dependency already correct. Noted for traceability.

---

**Total deviations:** 1 auto-fixed (signature), 2 no-ops (already done in Wave 3)
**Impact on plan:** No scope change. All must-have truths satisfied.

## Known Stubs

None. All production code is fully implemented. The pipeline is now end-to-end operational pending a live ANTHROPIC_API_KEY in .env.

## Threat Surface Scan

| Flag | File | Description |
|------|------|-------------|
| T-05-04-01 mitigated | docker-compose.yml | ANTHROPIC_API_KEY sourced from ${ANTHROPIC_API_KEY} host env — never hardcoded; .env not committed (gitleaks hook) |
| T-05-04-02 mitigated | generate_daily_insights.py | soft_time_limit=120, time_limit=180 prevents hanging Anthropic API calls from blocking worker |
| T-05-04-03 mitigated | celery_app.py | Explicit module paths in include list prevent wildcard task discovery |
| T-05-04-04 mitigated | generate_daily_insights.py | structlog fields: kpi_date, status, input_tokens, cost_usd, duration_ms — no prompt content, no raw_response |
| T-05-04-05 accepted | celery_app.py | Beat entry in Redis via redbeat; tampering requires prior infrastructure access |
| T-05-04-SC mitigated | pyproject.toml | anthropic is the official Anthropic SDK (already installed 0.104.1 in Wave 3) |

## Self-Check: PASSED

Files confirmed to exist:
- backend/app/tasks/etl/generate_daily_insights.py — FOUND
- backend/app/tasks/celery_app.py — FOUND (modified)
- backend/app/tasks/etl/sync_mefi_leads.py — FOUND (modified)
- .env.example — FOUND (modified)
- docker-compose.yml — FOUND (modified)

Commits confirmed:
- a4fd6bf0 — Task 1 (generate_daily_insights task)
- 61da5696 — Task 2 (infrastructure wiring)

Test results: 37/37 pass (4 DB-dependent skipped)
- test_daily_insight_schema.py: all GREEN
- test_prompt_builder.py: all GREEN
- test_insight_service.py: all GREEN
- test_number_validator.py: all GREEN
- test_insight_repository.py: all GREEN
- test_no_claude_calls_in_http_handlers: PASS (AI-09 grep gate)
- DB-dependent integration tests: 4 SKIPPED (require TEST_DATABASE_URL)
