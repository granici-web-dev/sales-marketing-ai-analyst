---
status: partial
phase: 01-foundation
source: [01-VERIFICATION.md]
started: 2026-05-21T00:00:00Z
updated: 2026-05-21T00:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. `docker compose up -d` + healthz
expected: All 7 services start (postgres, redis, backend, worker, beat, flower, frontend); `curl http://localhost:8000/healthz` returns `{"status":"ok"}` within 30 seconds
result: [pending]

### 2. Login flow (browser)
expected: Navigate to http://localhost:3000 → redirected to /login; enter `admin@sofabelle.ro` / `Admin1234!` → redirected to dashboard with full sidebar shell visible
result: [pending]

### 3. Celery worker responding
expected: `docker compose exec worker celery -A app.tasks.celery_app inspect ping` returns pong
result: [pending]

### 4. RedBeat scheduler alive
expected: `docker compose exec redis redis-cli KEYS 'redbeat*'` returns non-empty list within 30s of `docker compose up -d`
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps
