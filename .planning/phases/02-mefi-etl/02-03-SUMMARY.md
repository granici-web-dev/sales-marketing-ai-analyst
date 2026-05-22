---
plan: 02-03
phase: 02-mefi-etl
status: complete
completed_at: 2026-05-22
self_check: PASSED
---

# Plan 02-03 Summary: MefiRepository + sync_mefi_leads Celery Task

## What Was Built

**Task 1 — MefiRepository** (`backend/app/services/repositories/mefi_repository.py`):
- `bulk_upsert_leads(rows)` — PostgreSQL INSERT ON CONFLICT DO UPDATE via `pg_insert`; validates tenant_id in every row dict (T-02-08 mitigation); UPSERT columns preserve immutable fields (external_id, created_at_source)
- `detect_and_record_history(incoming_rows)` — ORM SELECT of current status_id per external_id, returns history row dicts for new leads and status changes
- `insert_history_rows(history_rows)` — plain INSERT without ON CONFLICT (multiple history entries per lead are correct)
- `upsert_salespeople(pairs)` — INSERT ON CONFLICT DO NOTHING; is_active/showroom left NULL for manual admin setup (D-06)
- `get_lead_count_for_tenant()` — COUNT(*) for backfill trigger detection
- `get_last_sync_at()` — MAX(completed_at) from sync_runs WHERE status='success' for incremental date window

**Task 2 — sync_mefi_leads + celery wiring**:
- `sync_mefi_leads` Celery task: name `tasks.etl.sync_mefi_leads`; autoretry for `httpx.TimeoutException/NetworkError`; manual retry on `RateLimitError` with `retry_after` countdown (T-02-11 UUID validation at entry)
- `_sync_async` coroutine: all DB/HTTP imports deferred to function body (Pitfall 8 / INFRA-05 fork-safety)
- Redis lock: `sync:mefi:{tenant_id}` SET NX EX 36000; released in `finally` (T-02-09)
- SyncRun lifecycle: written at start (status=running), updated to success/failed on completion
- Liveness probe abort: `health_check()` → False → SyncRun(failed) → return
- Backfill trigger: `get_lead_count_for_tenant() == 0` → `backfill_mefi_leads.apply_async(queue="backfill")`
- Incremental date window: last_sync_at - 1 day (D-10 page-shift prevention); full history from 2025-01-01 on first sync
- Custom field extraction: `get_cf()` helper; showroom (cf-14), offer_sent_flag (cf-20), UTM (cf-38..41)
- PIPE-03: raises RuntimeError("No data for today") when total_synced==0 and date_from==date_to
- `daily_pipeline()` function for Phase 3 chain extension

**celery_app.py updates**:
- `include` extended to `["app.tasks", "app.tasks.etl"]`
- `task_routes` added: `{"tasks.etl.backfill_mefi_leads": {"queue": "backfill"}}`
- Redbeat beat schedule: `daily-mefi-sync` at crontab(hour=4, minute=0) Europe/Bucharest with `sofa_belle_tenant_id` arg

## Requirements Satisfied

MEFI-02 ✓, MEFI-03 ✓, MEFI-04 ✓, MEFI-06 ✓, MEFI-07 ✓, MEFI-08 ✓, MEFI-09 ✓, MEFI-11 ✓, DATA-02 ✓, PIPE-01 ✓, PIPE-02 ✓, PIPE-03 ✓

## Commits

- `d65df978` feat(02-03): add MefiRepository — bulk upsert, history detection, salesperson upsert
- `7b2a9ee4` feat(02-03): add sync_mefi_leads Celery task + ETL pipeline wiring

## Key Files Created/Modified

- `backend/app/services/repositories/__init__.py` (new)
- `backend/app/services/repositories/mefi_repository.py` (new)
- `backend/app/tasks/etl/__init__.py` (new)
- `backend/app/tasks/etl/sync_mefi_leads.py` (new)
- `backend/app/tasks/celery_app.py` (modified — include, task_routes, beat schedule)

## Self-Check

- [x] `sync_mefi_leads.name == "tasks.etl.sync_mefi_leads"` ✓
- [x] `task_routes` has `"tasks.etl.backfill_mefi_leads": {"queue": "backfill"}` ✓
- [x] `bulk_upsert_leads` uses `on_conflict_do_update` ✓
- [x] No module-level `app.db.session` imports in sync_mefi_leads.py ✓
- [x] `get_cf(None, 14)` returns None without raising ✓
- [x] Beat schedule entry registered in celery_app for 04:00 Europe/Bucharest ✓

## Deviations

- `redis` and `celery-redbeat` installed into venv (were in pyproject.toml but not yet installed)
- Beat schedule registered via try/except to be graceful when Redis is not running at import time
- Inline execution (no subagent) due to Bash permission block in worktree context
