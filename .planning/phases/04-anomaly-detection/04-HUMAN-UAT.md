---
status: partial
phase: 04-anomaly-detection
source: [04-VERIFICATION.md]
started: 2026-05-28T13:44:52Z
updated: 2026-05-28T13:44:52Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Full database round-trip — detect_anomalies runs against real PostgreSQL
expected: SyncRun row written with status="success", detected_problems rows inserted without UndefinedColumn errors (confirmed that the detected_at column added in 04-05 exists in the live schema)
result: [pending]

### 2. ROADMAP SC#2 — business hours boundary for slow_first_touch
expected: A lead created outside business hours (before 09:00 or after 19:00 Europe/Bucharest) with no contact attempt for 5+ hours does NOT trigger the slow_first_touch rule. A lead created inside business hours with no contact for 5+ hours DOES trigger it.
result: [pending]

### 3. ROADMAP SC#6 — end-to-end junk lead exclusion after CR-02 date-scoping fix
expected: Junk leads (lifecycle='junk' AND created_date_local = kpi_date) are excluded from slow_first_touch context_json after the _get_junk_ids() date-scoping fix. Leads created on other dates do NOT appear in the junk exclusion set.
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
