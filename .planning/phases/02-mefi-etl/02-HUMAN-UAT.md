---
status: partial
phase: 02-mefi-etl
source: [02-VERIFICATION.md]
started: 2026-05-22T00:00:00Z
updated: 2026-05-22T00:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Alembic migration 003 applies cleanly to live PostgreSQL

Run `docker compose up -d` then `cd backend && alembic upgrade head`.
Verify: `raw_mefi_leads`, `mefi_lead_history`, `mefi_salespeople` tables exist; `v_mefi_leads_active` and `v_mefi_leads_junk` views exist; `tenants.funnel_config` seeded for slug='sofa-belle'.

expected: Migration applies without error; all tables and views created; funnel_config JSONB contains visit/offer/contract stages
result: [pending]

### 2. Integration tests pass with live DB

With `docker compose up -d` and `TEST_DATABASE_URL` set to the test DB:
`pytest tests/integration/test_mefi_etl.py -v`

expected: 5 integration tests pass — views exist, funnel columns present, local timestamp columns, UNIQUE constraint, funnel_config seeded
result: [pending]

### 3. RedBeat schedule entry persisted in Redis

With Redis running, import celery_app and verify:
`redis-cli keys "analyst:redbeat:*"` returns an entry for `daily-mefi-sync`.

expected: RedBeat entry visible in Redis with crontab(hour=4, minute=0) schedule
result: [pending]

### 4. End-to-end sync with MEFI API key

With `MEFI_API_KEY` set and Docker stack running, invoke:
`celery -A app.tasks.celery_app call tasks.etl.sync_mefi_leads --args='["00000000-0000-0000-0000-000000000001"]'`

expected: SyncRun row written to sync_runs (status=running → success); raw_mefi_leads populated; mefi_salespeople rows created; Redis lock acquired and released
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps
