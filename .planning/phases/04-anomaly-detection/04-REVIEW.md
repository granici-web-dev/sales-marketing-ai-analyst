---
phase: 04-anomaly-detection
reviewed: 2026-05-28T00:00:00Z
depth: standard
files_reviewed: 15
files_reviewed_list:
  - backend/app/tasks/etl/detect_anomalies.py
  - backend/app/tasks/etl/sync_mefi_leads.py
  - backend/app/tasks/celery_app.py
  - backend/app/services/anomaly/anomaly_service.py
  - backend/app/services/anomaly/__init__.py
  - backend/app/services/repositories/anomaly_repository.py
  - backend/app/models/anomaly/detected_problem.py
  - backend/app/models/anomaly/__init__.py
  - backend/app/models/__init__.py
  - backend/alembic/versions/007_detected_problems.py
  - backend/tests/unit/test_anomaly_service.py
  - backend/tests/unit/test_anomaly_repository.py
  - backend/tests/unit/test_sync_mefi_leads.py
  - backend/tests/integration/test_detect_anomalies_task.py
  - backend/tests/factories/anomaly_factory.py
findings:
  critical: 3
  warning: 5
  info: 3
  total: 11
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-05-28T00:00:00Z
**Depth:** standard
**Files Reviewed:** 15
**Status:** issues_found

## Summary

Phase 4 implements a 5-rule anomaly detection engine on top of the Phase 3 metrics
layer. The overall structure is sound: INFRA-05 deferred imports, NullPool per
invocation, WR-04 single-commit pattern, and the 3-column UPSERT conflict target are
all present and correctly applied. However, three critical defects require remediation
before this code can be trusted in production:

1. The migration DDL is missing the `detected_at` column that the ORM model declares,
   causing runtime `UndefinedColumn` errors at every INSERT.
2. `_get_junk_ids()` has no date filter: it pulls **all** junk leads for the tenant
   across all time, making the junk-exclusion set grow unboundedly and causing
   slow-first-touch and stuck-offer anomalies to be silently suppressed for leads
   that were junk long ago but whose `external_id` was reused or is coincidentally
   the same as an active lead today.
3. In `sync_mefi_leads`, the `liveness_failed` early-return path leaks the Redis
   lock: it calls `task_engine.dispose()` but returns **without** deleting the lock
   key, leaving it held for 10 hours and blocking all subsequent sync attempts.

Five warnings cover a silent test assertion, stored PII in `context_json`, a
double-dispose on the engine, a float used inside a JSONB column that would be
reinterpreted by the AI insights layer, and the PIPE-03 guard condition that will
never fire in normal operation. Three info items cover minor quality concerns.

---

## Critical Issues

### CR-01: `detected_at` column missing from Alembic migration 007

**File:** `backend/alembic/versions/007_detected_problems.py:33-89`

**Issue:** The ORM model `DetectedProblem` declares a `detected_at` column
(`TIMESTAMPTZ NOT NULL` with `server_default="now()"`, line 91-93 of
`detected_problem.py`). Migration 007 creates the `detected_problems` table but
does **not** add this column. When the Celery task calls
`AnomalyRepository.upsert_detected_problem()`, SQLAlchemy's Core INSERT will include
`detected_at` from the model metadata — PostgreSQL will respond with
`UndefinedColumn: column "detected_at" of relation "detected_problems" does not
exist`, failing every anomaly write at runtime. The `downgrade()` path is also
inconsistent because the column is tracked in the ORM but not in the DDL.

**Fix:** Add the missing column to `upgrade()` in the migration:
```python
sa.Column(
    "detected_at",
    sa.TIMESTAMP(timezone=True),
    server_default=sa.text("now()"),
    nullable=False,
),
```
Insert it immediately after the `updated_at` block (before the `date` column) to
mirror the order in which `TenantScopedMixin` columns are typically added. No
`downgrade()` change is needed because `drop_table` handles the whole table.

---

### CR-02: `_get_junk_ids()` has no date filter — fetches all-time junk leads

**File:** `backend/app/services/anomaly/anomaly_service.py:114-120`

**Issue:** The query in `_get_junk_ids()` is:
```sql
SELECT external_id FROM v_mefi_leads_junk WHERE tenant_id = :tenant_id
```
There is no `AND created_date_local = :kpi_date` predicate. This means the set
returned includes every junk lead ever recorded for the tenant, not just those from
`kpi_date`. The set is then used to exclude leads from `detect_slow_first_touch()`
(line 314). Because `external_id` values are assigned by MEFI and are sequential
integers rendered as strings, if a junk lead ID from six months ago happens to share
a value with an active lead from yesterday, that active lead is silently excluded from
slow-first-touch analysis — a false negative. More practically, as junk accumulates
over months, the set grows to thousands of entries and the in-memory lookup slows.
The intent stated in the docstring (D-11, D-14) is to check yesterday's leads, so the
set should be scoped to `kpi_date`.

**Fix:**
```python
stmt = text(
    "SELECT external_id FROM v_mefi_leads_junk "
    "WHERE tenant_id = :tenant_id "
    "AND created_date_local = :kpi_date"
).bindparams(tenant_id=self._tenant_id, kpi_date=kpi_date)
```
The `kpi_date` parameter is already passed to `_get_junk_ids()` — it just is not
used in the SQL. The corresponding unit test (`test_junk_ids_computed_once`) mocks
`_get_junk_ids` entirely, so this defect would not be caught by existing tests.

---

### CR-03: Redis lock leaked when MEFI liveness check fails

**File:** `backend/app/tasks/etl/sync_mefi_leads.py:139-145`

**Issue:** When `client.health_check()` returns `False`, the code sets the SyncRun
to `failed`, calls `await task_engine.dispose()`, and then returns early:
```python
await task_engine.dispose()
return {"status": "failed", "reason": "liveness_failed"}
```
This early return exits the inner `try` block but **does not reach the outer
`finally` block** (line 305-308). The Redis lock key (`sync:mefi:{tenant_id}`) set
at line 108 is never deleted. The lock has a 10-hour TTL (`_LOCK_TTL = 36000`), so
for the next 10 hours no nightly sync will run for this tenant — it will silently
return `{"status": "noop", "reason": "lock_held"}` on every retry attempt. This is a
silent data-starvation bug that would go unnoticed until the next morning's metrics
are missing.

Note: the early `task_engine.dispose()` on line 144 is also redundant because the
outer `finally` on line 308 disposes the engine as well (double-dispose — see WR-03).

**Fix:** Remove the manual `await task_engine.dispose()` on line 144 (it's covered by
`finally`) and release the Redis lock before returning:
```python
if not alive:
    log.warning("mefi.liveness_failed")
    sync_run.status = "failed"
    sync_run.error_msg = "MEFI liveness check returned total=0"
    sync_run.completed_at = datetime.now(UTC)
    await session.commit()
    await redis.delete(lock_key)   # release the lock
    await redis.aclose()           # close Redis connection
    return {"status": "failed", "reason": "liveness_failed"}
```
Alternatively, restructure so the `liveness_failed` path falls through to the outer
`finally` (raise a sentinel exception handled locally).

---

## Warnings

### WR-01: `lead_ids` stored in `context_json` — potential PII per CLAUDE.md Principle #6

**File:** `backend/app/services/anomaly/anomaly_service.py:358, 435`

**Issue:** Both `detect_slow_first_touch()` (line 358) and `detect_stuck_offer()`
(line 435) write `"lead_ids": [lead["external_id"] for lead in qualifying]` into
`context_json`. CLAUDE.md Principle #6 states: "Never log: phone numbers, email,
names, transcript contents." The spec also says external_ids (MEFI numeric IDs) are
acceptable to store (T-04-02-01 says "external_ids only — no PII"). However, the
`_get_junk_ids()` and `_db_fetch_slow_leads()` queries select `external_id` which
in MEFI's system is the lead's numeric primary key, not a customer identifier. The
model docstring for `context_json` explicitly says external_ids are OK. This is not
a clear violation today, but MEFI external IDs are sequential integers — if a future
consumer maps them back to customer records (names, phones), these stored IDs become
a vector. The log-time comment at T-04-03-01 ("never log lead_ids") is inconsistently
applied: logs are safe, but persistence in JSONB is equally durable.

**Fix:** Evaluate with the business owner whether storing lead external_ids is
required for Phase 5 AI insights. If not, replace with aggregate counts only:
```python
# Instead of: "lead_ids": [lead["external_id"] for lead in qualifying],
"affected_count": count,
```
If lead_ids are required by Phase 5, document explicitly that they are MEFI-internal
integer IDs (not PII), add a note to CLAUDE.md under Principle #6, and ensure no
subsequent phase logs or exposes them.

---

### WR-02: `assert_called_once()` is a no-op — test silently passes regardless

**File:** `backend/tests/unit/test_anomaly_service.py:676`

**Issue:** The test `test_junk_ids_computed_once` uses:
```python
mock_get_junk_ids.assert_called_once(), (
    "_get_junk_ids must be called exactly once ..."
)
```
`Mock.assert_called_once()` does **not exist** on Python's `unittest.mock.Mock`
(it was a common typo for `assert_called_once_with()`; the method that exists is
`assert_called_once_with`). Calling a non-existent method on a `MagicMock` returns
another `MagicMock` — the expression evaluates to a tuple `(MagicMock(), str)` which
is truthy and is immediately discarded. The assertion **never runs**. If `run_all_rules`
were refactored to call `_get_junk_ids` twice, this test would still pass silently.

**Fix:**
```python
# Wrong — silently does nothing:
mock_get_junk_ids.assert_called_once(), ("message")

# Correct — use assert_called_once_with or check call_count:
assert mock_get_junk_ids.call_count == 1, (
    "_get_junk_ids must be called exactly once per run_all_rules() — "
    "not once per rule (D-11 efficiency requirement)"
)
```

---

### WR-03: Double engine dispose in `sync_mefi_leads` liveness-failed path

**File:** `backend/app/tasks/etl/sync_mefi_leads.py:144`

**Issue:** When the liveness check fails, line 144 calls `await task_engine.dispose()`
before returning. But the `liveness_failed` path is **inside** the `try` block
whose `finally` (line 305-308) also calls `await task_engine.dispose()`. Any early
return from within the `try` block still triggers `finally`, so the engine is
disposed twice. While SQLAlchemy's `NullPool.dispose()` is idempotent, this is
incorrect flow and masks the lock-leak bug described in CR-03. The explicit dispose
on line 144 is the leftover from a draft pattern that was superseded by the `finally`.

**Fix:** Remove line 144 (`await task_engine.dispose()`). The `finally` block covers
all exit paths after the lock has been acquired. The Redis lock release (CR-03) must
be added instead.

---

### WR-04: PIPE-03 guard condition `date_from == date_to` never fires in normal operation

**File:** `backend/app/tasks/etl/sync_mefi_leads.py:257`

**Issue:** The guard that raises `RuntimeError("No data for today — halting pipeline
chain")` requires both `total_synced == 0` AND `date_from == date_to`. `date_to` is
always `sync_start_at.date().isoformat()` (today). `date_from` equals `date_to` only
when `last_sync_at` is None (no prior sync), because in that case the code sets
`date_from = date(2025, 1, 1).isoformat()` — which is explicitly different from
`date_to`. When `last_sync_at` is set, `date_from = (last_sync_at.date() - timedelta(days=1)).isoformat()`.
For this guard to fire, the last sync must have been exactly yesterday at midnight
so that `date_from == date_to` AND no leads were modified in that window. In practice
this condition can never be true: when there's no prior sync, `date_from` is 2025-01-01.

The guard was probably intended to read `date_from == date_to` **or** just
`total_synced == 0`. The current logic makes the anomaly pipeline's no-data warning
a dead code path.

**Fix:** Decide on the correct condition. If the intent is "warn when there is no
data today at all," the condition should be:
```python
if total_synced == 0:
    log.warning("sync.no_data_today", date=date_to)
    raise RuntimeError("No data for today — halting pipeline chain")
```
If it should only warn when the window covers a single day, add the right date check,
but verify the `date_from` derivation path first.

---

### WR-05: `float` used for `junk_rate`, `drop_pct`, `win_rate` stored in `context_json`

**File:** `backend/app/services/anomaly/anomaly_service.py:512, 572-573, 661`

**Issue:** Three places convert `Decimal` values to `float` before storing in
`context_json` (a JSONB column):

- `"drop_pct": float((baseline_rate - current_rate) / baseline_rate * 100)` (line 512)
- `"win_rate": float(sp_rate)` and `"team_avg": float(team_avg)` (lines 572-573)
- `"junk_rate": float(junk_rate)` (line 661)

CLAUDE.md prohibits float for monetary values (D-19). While `drop_pct`, `win_rate`,
and `junk_rate` are percentages (not currency), the same precision concern applies
when the Phase 5 AI Insights layer reads these values back from JSONB as Python
`float` and performs arithmetic on them. `Decimal("0.1") + Decimal("0.2")` is exact;
`float(0.1) + float(0.2)` is not. For `junk_rate` in particular, storing
`float(8/30)` = `0.26666666666666666` instead of `Decimal("0.2667")` is inconsistent
with the `current_value` column which stores the rate as `NUMERIC(12,4)`.

**Fix:** Store ratios as strings or use Python's `json`-safe representation of
Decimal (PostgreSQL JSONB accepts numeric literals with full precision):
```python
# Instead of float():
"drop_pct": str(round((baseline_rate - current_rate) / baseline_rate * 100, 4)),
"win_rate": str(sp_rate),
"junk_rate": str(junk_rate),
```
Or accept float only for display fields (`drop_pct`, `win_rate`) while keeping
`junk_rate` as Decimal-string since it feeds D-08 loss calculation downstream.

---

## Info

### IN-01: `context_json` key name inconsistency: `"count"` vs `"junk_count"`

**File:** `backend/app/services/anomaly/anomaly_service.py:659` vs
`backend/app/models/anomaly/detected_problem.py:85`

**Issue:** The model docstring documents the `junk_lead_quality` context as
`{"junk_count": 45, "total_leads": 150, "junk_rate": 0.30}`, but the service
emits `{"count": junk_count, "total": total_leads, "junk_rate": ...}`. The keys
`count` vs `junk_count` and `total` vs `total_leads` differ. Any Phase 5 consumer
reading `context_json["junk_count"]` will get a `KeyError` if it trusts the model
docstring as the schema contract.

**Fix:** Align the service with the documented contract. Either update the docstring
or the service dict:
```python
"context_json": {
    "junk_count": junk_count,   # was "count"
    "total_leads": total_leads, # was "total"
    "junk_rate": float(junk_rate),
},
```

---

### IN-02: `services/anomaly/__init__.py` breaks the deferred-import pattern

**File:** `backend/app/services/anomaly/__init__.py:3`

**Issue:** The package `__init__.py` imports `AnomalyService` at module load time:
```python
from app.services.anomaly.anomaly_service import AnomalyService
```
The INFRA-05 pattern requires all `app.services.*` imports to be deferred to inside
the async coroutine body so they are not executed before Celery forks worker processes.
`detect_anomalies.py` correctly does its import inside `_detect_async()` at line 91.
However, if any module imports from `app.services.anomaly` (the package), the
`__init__.py` runs at that point and transitively imports `AnomalyService`, which
imports `sqlalchemy.ext.asyncio` and `structlog` at module level. For the current
codebase this is safe because `detect_anomalies.py` imports from the full path
`app.services.anomaly.anomaly_service` (bypassing `__init__.py`), but this is
fragile — any future developer importing `from app.services.anomaly import
AnomalyService` (the documented public API) will break fork safety.

**Fix:** Remove the module-level import from `__init__.py` or make it lazy:
```python
# Option A: Remove __init__.py content entirely — callers import the full path
# Option B: lazy __init__.py:
def __getattr__(name: str):
    if name == "AnomalyService":
        from app.services.anomaly.anomaly_service import AnomalyService
        return AnomalyService
    raise AttributeError(name)
```

---

### IN-03: Integration test seeds leads using `kpi_date = date.today()` (not yesterday)

**File:** `backend/tests/integration/test_detect_anomalies_task.py:158, 176`

**Issue:** In `test_slow_first_touch_not_triggered_for_junk_leads`, the test seeds
raw_mefi_leads with `"yesterday": kpi_date` where `kpi_date = date.today()`. The
field name `yesterday` is passed to the INSERT but the value is today's date (not
yesterday). The `detect_anomalies` task checks for `kpi_date = yesterday` (D-14).
The seeded leads would be for the wrong date, meaning the test could pass vacuously
(no leads on yesterday's date at all, so no anomaly fires regardless of junk
filtering). The variable name `kpi_date = date.today()` is also confusing — the
task computes `kpi_date = datetime.now(BUCHAREST).date() - timedelta(days=1)`.

**Fix:**
```python
from datetime import timedelta
from zoneinfo import ZoneInfo
BUCHAREST = ZoneInfo("Europe/Bucharest")
kpi_date = datetime.now(BUCHAREST).date() - timedelta(days=1)  # match task logic
```
And use `kpi_date` consistently in both the seed INSERT and the assertion SELECT.

---

_Reviewed: 2026-05-28T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
