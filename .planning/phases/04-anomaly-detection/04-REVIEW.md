---
phase: 04-anomaly-detection
reviewed: 2026-05-28T12:00:00Z
depth: standard
files_reviewed: 15
files_reviewed_list:
  - backend/alembic/versions/007_detected_problems.py
  - backend/app/models/__init__.py
  - backend/app/models/anomaly/__init__.py
  - backend/app/models/anomaly/detected_problem.py
  - backend/app/services/anomaly/__init__.py
  - backend/app/services/anomaly/anomaly_service.py
  - backend/app/services/repositories/anomaly_repository.py
  - backend/app/tasks/celery_app.py
  - backend/app/tasks/etl/detect_anomalies.py
  - backend/app/tasks/etl/sync_mefi_leads.py
  - backend/tests/factories/anomaly_factory.py
  - backend/tests/integration/test_detect_anomalies_task.py
  - backend/tests/unit/test_anomaly_repository.py
  - backend/tests/unit/test_anomaly_service.py
  - backend/tests/unit/test_sync_mefi_leads.py
findings:
  critical: 2
  warning: 5
  info: 2
  total: 9
status: fixed
fixed_at: 2026-05-28T14:00:00Z
---

# Phase 04: Code Review Report

**Reviewed:** 2026-05-28T12:00:00Z
**Depth:** standard
**Files Reviewed:** 15
**Status:** issues_found

## Summary

Reviewed the full Phase 4 anomaly detection implementation: Alembic migration 007, the `DetectedProblem` ORM model and package wiring, `AnomalyService` (5-rule engine + orchestrator), `AnomalyRepository` (UPSERT layer), the `detect_anomalies` Celery task, the extended `sync_mefi_leads` chain, and all unit/integration/factory test files.

Core mechanics are well-implemented: INFRA-05 deferred imports, NullPool per invocation, WR-04 single-commit-per-batch, Pitfall 5 three-column conflict target, and Pitfall 6 tenant_id guard are all present and correct. Two critical issues require fixes before this phase can ship:

1. Both integration tests that claim to verify junk-exclusion and UPSERT idempotency are **vacuously passing** — they seed test data on `date.today()` while the task under test queries for `date.today() - 1` (yesterday). No seeded data is ever found; assertions pass without exercising the actual code paths.
2. The `showroom_traffic_drop` rule's `context_json` diverges from the schema documented in the ORM model comment. The documented keys `actual_visits` and `expected_visits` are absent; the undocumented key `drop_pct` is present instead. Any Phase 5 AI Insights code that reads the documented schema will fail at runtime.

Five warnings cover: a missing tenant_id cross-check in the repository write path; a two-transaction race window that can leave `SyncRun` stuck in `"running"`; an asymmetric `avg_deal_size` extractor that uses "most-recent" not "average"; a stale SyncRun cleanup with no age guard that could corrupt a legitimately concurrent run; and a misleading D-11 docstring that overstates the scope of junk_ids propagation.

---

## Critical Issues

### CR-01: Integration tests are vacuously passing — seeded data uses wrong date

**File:** `backend/tests/integration/test_detect_anomalies_task.py:155-264`

**Issue:** Both `test_slow_first_touch_not_triggered_for_junk_leads` and `test_detected_problems_upsert_idempotent` seed test data using `kpi_date = date.today()` (line 157) and insert leads with `created_date_local = kpi_date` (i.e., today). The `detect_anomalies` task under test computes its own `kpi_date` as `datetime.now(BUCHAREST).date() - timedelta(days=1)` (yesterday). The task's `_get_junk_ids()` query includes `AND created_date_local = :kpi_date` (yesterday), and `_db_fetch_slow_leads()` similarly filters `AND created_date_local = :kpi_date` (yesterday). Since the seeded leads are on today's date, neither query finds them. The task runs with empty data, fires no anomalies, writes no `detected_problems` rows, and both assertions — `count == 0` (line 214) and `len(duplicates) == 0` (line 259) — pass trivially.

The junk-exclusion test (`ANOM-07`, `ROADMAP SC#6`) therefore provides **zero coverage** of the actual junk filtering code. A regression that removes junk exclusion entirely would not be caught.

The assertion query on line 207-210 also uses `kpi_date` (today) when checking `detected_problems.date`, while the task would write rows for yesterday — these would never match regardless of what the task does.

**Fix:** Seed data using yesterday's date to match what the task queries. The `kpi_date` local variable should mirror the task's date computation:

```python
from datetime import timedelta
from zoneinfo import ZoneInfo

BUCHAREST = ZoneInfo("Europe/Bucharest")
# Match the task's exact kpi_date computation (detect_anomalies.py line 106):
kpi_date = datetime.now(BUCHAREST).date() - timedelta(days=1)

# Then seed junk leads on kpi_date (not date.today()):
"yesterday": kpi_date,  # was: "yesterday": date.today()

# And assert for kpi_date (not date.today()):
{"tenant_id": TENANT_ID, "kpi_date": kpi_date}  # was: kpi_date = date.today()
```

For `test_detected_problems_upsert_idempotent`, also seed at least one anomaly-triggering condition (e.g., a slow lead) so that rows are actually written and duplicates can be detected.

---

### CR-02: `detect_showroom_traffic_drop` emits `context_json` with different keys than the documented schema

**File:** `backend/app/services/anomaly/anomaly_service.py:512-515`

**Issue:** The ORM model docstring (`detected_problem.py:83`) documents the `showroom_traffic_drop` context_json contract as:
```json
{"actual_visits": 2, "expected_visits": 5.4, "baseline_days": 30}
```
The actual implementation at lines 512–515 emits:
```python
"context_json": {
    "baseline_days": len(non_null_baseline),
    "drop_pct": float((baseline_rate - current_rate) / baseline_rate * 100),
}
```
The keys `actual_visits` and `expected_visits` are absent; the undocumented key `drop_pct` is present. Phase 5 AI Insights will read `context_json` using the schema as its data contract. Any Phase 5 code that accesses `context_json["actual_visits"]` or `context_json["expected_visits"]` will raise `KeyError` at runtime, or — if using `.get()` — will silently produce `None` values in the AI-generated Romanian-language report, yielding factually incorrect output without an error signal.

**Fix:** Update the model docstring to match the actual implementation, and ensure Phase 5 is written against the correct schema:

In `detected_problem.py` line 83, change:
```python
# showroom_traffic_drop:   {"actual_visits": 2, "expected_visits": 5.4, "baseline_days": 30}
```
to:
```python
# showroom_traffic_drop:   {"baseline_days": 30, "drop_pct": 37.5}
#   baseline_days: number of non-null conversion_l_to_v days in the 30-day window
#   drop_pct: percentage drop from baseline (e.g., 37.5 = 37.5% below baseline)
```
Verify before Phase 5 work begins that no existing Phase 5 scaffold references `actual_visits` or `expected_visits`.

---

## Warnings

### WR-01: `AnomalyRepository.upsert_detected_problem` does not verify `row["tenant_id"] == self._tenant_id`

**File:** `backend/app/services/repositories/anomaly_repository.py:55-59`

**Issue:** The repository correctly validates that `tenant_id` is present and not `None` (Pitfall 6 guard). It does **not** verify that `row["tenant_id"]` equals `self._tenant_id`. A caller passing a row dict containing a different `tenant_id` (e.g., due to a future code refactor that wires the wrong service-to-repository pair) would silently insert a cross-tenant row, bypassing the multi-tenancy isolation required by CLAUDE.md Core Principle #3. Core INSERT bypasses `with_loader_criteria`, so there is no ORM-level backstop after the repository.

In the current code, `AnomalyService` always sets `"tenant_id": self._tenant_id`, so there is no active exploit path. The gap is a missing defensive layer.

**Fix:**
```python
if row["tenant_id"] != self._tenant_id:
    raise ValueError(
        f"AnomalyRepository.upsert_detected_problem: cross-tenant write blocked — "
        f"row.tenant_id={row['tenant_id']!r} != repository.tenant_id={self._tenant_id!r}"
    )
```
Add this check immediately after the existing `None` check on line 55.

---

### WR-02: Two-commit transaction window leaves `SyncRun` stuck in `"running"` if second commit fails

**File:** `backend/app/tasks/etl/detect_anomalies.py:147-159`

**Issue:** The task performs two separate `session.commit()` calls within the same session:
1. **Line 151:** commits all `detected_problems` upsert rows.
2. **Line 159:** commits the `SyncRun.status = "success"` update.

If the process is killed, the DB connection drops, or a transient error occurs between these two commits, all `detected_problems` rows are durably persisted but the `SyncRun` row remains in `"running"` state. On the next retry, the WR-06 stale-cleanup UPDATE marks the orphaned `SyncRun` as `"failed"` — so the audit trail records a "failed" run for a task that actually completed all its data work. Monitoring and alerting may trigger a false incident.

**Fix:** Merge both writes into a single atomic commit:
```python
# Step 4+5: upsert results AND update SyncRun in one atomic transaction
for problem in problems:
    await repo.upsert_detected_problem(problem)

elapsed_ms = int((datetime.now(UTC) - detect_start_at).total_seconds() * 1000)
sync_run.status = "success"
sync_run.records_synced = len(problems)
sync_run.duration_ms = elapsed_ms
sync_run.completed_at = datetime.now(UTC)
await session.commit()  # single atomic commit covers both upserts and SyncRun update
```

---

### WR-03: `_extract_avg_deal_size` takes the first non-None value, not the average — asymmetric with `_extract_close_rate`

**File:** `backend/app/services/anomaly/anomaly_service.py:93-102`

**Issue:** The method is named `_extract_avg_deal_size` and the parameter is `baseline_rows` (implying a window of data), but the implementation takes the **first non-None `avg_deal_size`** from the list (line 99). Because `_db_fetch_trailing_metrics` orders rows by `date DESC`, the first value is the most-recent day's `avg_deal_size`. If deal size has been volatile (e.g., a discounted campaign), all loss estimates for `slow_first_touch`, `stuck_offer`, `underperforming_salesperson`, and `junk_lead_quality` will use an unrepresentative single-day value rather than a trailing average, potentially under- or over-stating financial risk.

The companion `_extract_close_rate` correctly averages all non-None values. The asymmetry is undocumented and surprising to readers.

**Fix (option A — average, consistent with `_extract_close_rate`):**
```python
def _extract_avg_deal_size(self, baseline_rows: list[dict]) -> Decimal:
    values = [
        Decimal(str(row["avg_deal_size"]))
        for row in baseline_rows
        if row.get("avg_deal_size") is not None
    ]
    if values:
        return sum(values, Decimal("0")) / Decimal(str(len(values)))
    return AVG_DEAL_SIZE_FALLBACK
```

**Fix (option B — document the intent explicitly):** If "most-recent day" is intentional, rename the method to `_extract_latest_deal_size` and update the docstring to explain why a trailing average is not used.

---

### WR-04: Stale SyncRun cleanup marks ALL running rows failed without an age threshold — unsafe under concurrent execution

**File:** `backend/app/tasks/etl/detect_anomalies.py:118-127`

**Issue:** The WR-06 cleanup UPDATE marks **any** `SyncRun(source="anomaly", status="running")` for the tenant as `"failed"`, with no minimum age guard:
```python
_update(SyncRun)
.where(
    SyncRun.tenant_id == tenant_id,
    SyncRun.source == "anomaly",
    SyncRun.status == "running",  # no age filter
)
```
If two Celery workers legitimately process the same tenant concurrently (e.g., a manual re-run initiated while the scheduled run is mid-flight), the second worker's startup UPDATE marks the first worker's active `SyncRun` as `"failed"`. The first worker then reaches its success-commit path and finds its in-memory `sync_run` object (already committed as `"failed"` by the second worker) being updated to `"success"`, causing the audit trail to show `"success"` for a run that was partially aborted by the competing UPDATE.

**Fix:** Add a minimum-staleness guard so only genuinely stale rows are cleaned up:
```python
from datetime import timedelta

await session.execute(
    _update(SyncRun)
    .where(
        SyncRun.tenant_id == tenant_id,
        SyncRun.source == "anomaly",
        SyncRun.status == "running",
        SyncRun.started_at < datetime.now(UTC) - timedelta(minutes=30),
    )
    .values(status="failed", completed_at=datetime.now(UTC))
)
```
30 minutes is a safe threshold; the normal detect_anomalies task completes in seconds to low minutes.

---

### WR-05: D-11 docstring claims `junk_ids` is "passed to all non-junk rules" but only `detect_slow_first_touch` receives it

**File:** `backend/app/services/anomaly/anomaly_service.py:9, 62, 688`

**Issue:** The module-level docstring (line 9), class docstring (line 62), and `run_all_rules` inline comment (line 688) all state that `junk_ids` is "computed ONCE and passed to all non-junk rules." In the actual `run_all_rules` implementation (lines 694-710), only `detect_slow_first_touch` receives the `junk_ids` argument. `detect_stuck_offer` and `detect_underperforming_salesperson` do not accept or use it. This is functionally acceptable because `v_mefi_leads_active` already excludes `lifecycle='junk'` at the DB view level. However, the false documentation will mislead future maintainers who might add a new rule and assume junk exclusion is applied at the Python layer for all rules — causing them to omit it for new rules.

**Fix:** Update all three docstring locations to accurately reflect the design:
```python
# D-11: compute junk IDs ONCE and pass to detect_slow_first_touch (the only rule
# that processes leads not pre-filtered by v_mefi_leads_active).
# Other rules query v_mefi_leads_active which already excludes lifecycle='junk' at DB level.
```

---

## Info

### IN-01: `sync_mefi_leads` double engine dispose in `liveness_failed` path

**File:** `backend/app/tasks/etl/sync_mefi_leads.py:144`

**Issue:** The `liveness_failed` early-return path (inside the outer `try` block starting line 120) calls `await task_engine.dispose()` explicitly at line 144 before `return`. Python's `finally` clause still executes even when a `return` is reached inside `try`, so the outer `finally` (line 305-308) also calls `await task_engine.dispose()`. The engine is disposed twice. `NullPool.dispose()` is idempotent so this causes no runtime error, but it is unnecessary code noise and may mask future changes to the `finally` structure.

**Fix:** Remove the explicit `await task_engine.dispose()` on line 144. The `finally` block covers all exit paths after the lock has been acquired:
```python
if not alive:
    log.warning("mefi.liveness_failed")
    sync_run.status = "failed"
    sync_run.error_msg = "MEFI liveness check returned total=0"
    sync_run.completed_at = datetime.now(UTC)
    await session.commit()
    # No manual dispose — finally handles it
    return {"status": "failed", "reason": "liveness_failed"}
```

---

### IN-02: `showroom_traffic_drop` sets `estimated_loss_ron = Decimal("0")` — will suppress the rule in Phase 5 priority ranking

**File:** `backend/app/services/anomaly/anomaly_service.py:494`

**Issue:** The D-05 formula (module docstring line 25) specifies a lost-opportunity calculation for trend rules. The `detect_showroom_traffic_drop` implementation sets `estimated_loss_ron = Decimal("0")` with the comment "visits data not available per-day." Phase 5 AI Insights will likely use `estimated_loss_ron` to rank anomaly severity and decide which problems to feature in the daily report. A zero loss estimate for a 37%-drop in showroom traffic will place this anomaly below all other rules in priority order, potentially omitting it from the top-3 insights despite being a high-impact signal for Sofa Belle.

**Fix:** Either implement a conservative proxy estimate using available data (similar to the `underperforming_salesperson` proxy on line 569):
```python
# D-05 conservative proxy: estimated_leads_missed × avg_deal_size × close_rate
leads_missed = baseline_rate * Decimal("10")  # approximate: needs leads_total for kpi_date
estimated_loss = leads_missed * avg_deal_size * close_rate
```
Or, if a meaningful estimate is not possible, document the limitation explicitly in the Phase 5 AI prompt so the model can acknowledge the missing data rather than silently de-prioritizing the rule.

---

_Reviewed: 2026-05-28T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
