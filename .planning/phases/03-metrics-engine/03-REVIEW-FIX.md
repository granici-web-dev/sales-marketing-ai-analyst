---
phase: 03-metrics-engine
fixed_at: 2026-05-27T00:00:00Z
review_path: .planning/phases/03-metrics-engine/03-REVIEW.md
iteration: 1
findings_in_scope: 12
fixed: 12
skipped: 0
status: all_fixed
---

# Phase 03: Code Review Fix Report

**Fixed at:** 2026-05-27T00:00:00Z
**Source review:** .planning/phases/03-metrics-engine/03-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 12 (CR-01 through CR-05, WR-01 through WR-07)
- Fixed: 12
- Skipped: 0

## Fixed Issues

### CR-01: Fix `v_mefi_leads_active` LEFT JOIN fan-out

**Files modified:** `backend/alembic/versions/004_metrics_schema.py`
**Commit:** c1bdace6
**Applied fix:** Replaced the flat `LEFT JOIN mefi_lead_history h ... OVER (PARTITION BY ...)` window-function approach with a pre-aggregated subquery `h_agg` that `GROUP BY tenant_id, lead_external_id` before joining. The original view emitted N rows per lead when the lead had N history rows, inflating all `COUNT(*)` KPI values. The new view emits exactly one row per lead. Updated module-level comments to accurately describe the `reached_visit` logic (addresses WR-02 as well — see below).

---

### CR-02: Fix `min()` on empty generator in `salesperson_kpi_service.py`

**Files modified:** `backend/app/services/metrics/salesperson_kpi_service.py`
**Commit:** c6728ef7
**Applied fix:** Replaced `min(row["changed_at"] for row in history_rows if ...)` (which raises `ValueError` on empty generator) with a two-step pattern: collect `valid_timestamps` list, check `if not valid_timestamps: return None`, then call `min(valid_timestamps)`. Removed the dead `if first_touch is None` guard that could never be reached.

---

### CR-03: Fix `alte_ids` never passed to SQL in daily_kpi_service and source_kpi_service

**Files modified:** `backend/app/services/metrics/daily_kpi_service.py`, `backend/app/services/metrics/source_kpi_service.py`
**Commit:** f0ad50d6
**Applied fix:** In `daily_kpi_service.py`, replaced the residual catch-all CASE expression for `leads_alte` with `COUNT(CASE WHEN v.source_id = ANY(:alte_ids) AND d.lead_external_id IS NULL THEN 1 END)` and added `alte_ids=alte_ids` to the `bindparams()` call. In `source_kpi_service.py`, added `WHEN v.source_id = ANY(:alte_ids) THEN 'alte'` before the `ELSE 'alte'` fallback in the CASE expression and added `alte_ids=alte_ids` to `bindparams()`. Custom `alte` source mappings from `funnel_config` are now correctly applied.

---

### CR-04: Fix infinite loop on empty `work_days` in `business_hours.py`

**Files modified:** `backend/app/services/metrics/business_hours.py`, `backend/app/services/metrics/salesperson_kpi_service.py`
**Commit (salesperson_kpi_service):** c6728ef7
**Commit (business_hours):** 411e373d
**Applied fix:** In `salesperson_kpi_service._get_business_hours`, added `if not work_days: raise ValueError("business_hours.days must not be empty")` after `work_days = list(bh["days"])`. The existing `except (KeyError, ValueError, AttributeError)` block catches this and falls back to the safe `[0, 1, 2, 3, 4, 5, 6]` default. In `business_hours.business_minutes_between`, added a defence-in-depth guard `if not work_days: return 0` before the main loop to protect any other callers of the function directly.

---

### CR-05: Remove manual `self.retry()` — let `autoretry_for` handle all retries

**Files modified:** `backend/app/tasks/etl/calculate_daily_kpis.py`
**Commit:** 2fb7592c
**Applied fix:** Removed the `try: return asyncio.run(...) except Exception as exc: raise self.retry(exc=exc) from exc` wrapper. The task body is now simply `return asyncio.run(_calc_async(UUID(tenant_id), calculation_date))`. The `autoretry_for=(Exception,)`, `max_retries=3`, and `default_retry_delay=60` decorator kwargs are unchanged.

---

### WR-01: Document `leads_google` data gap in `daily_kpi_service.py`

**Files modified:** `backend/app/services/metrics/daily_kpi_service.py`
**Commit:** f0ad50d6
**Applied fix:** Added a SQL comment on the `leads_google` CASE column explaining the data gap: Google leads are not stored in `daily_kpi` (no column), appear only in `source_daily_kpi`, and `leads_total` includes Google leads causing `sum(per-category) != leads_total`. Removed the unused Python variable `leads_google = int(agg.leads_google) ...` extraction to prevent ruff/mypy unused-variable warnings.

---

### WR-02: Fix or clarify `reached_visit` history check comment in migration 004

**Files modified:** `backend/alembic/versions/004_metrics_schema.py`
**Commit:** c1bdace6 (addressed as part of CR-01 fix)
**Applied fix:** Updated the view DDL comments to accurately describe the intentional progressive-funnel behavior: `-- Visit: current status IN (17,3,1) OR ever reached any visit-or-later stage (status 17, 3, or 1) in history`. Also updated the module-level comment block to say "ever reached visit-or-later stage (17, 3, or 1) in history" instead of "ever had status 17 in history". The `BOOL_OR(to_status_id IN (17, 3, 1))` behavior is intentional product logic and the comment now accurately describes it.

---

### WR-03: Fix fragile `history_by_lead` variable scope in `salesperson_kpi_service.py`

**Files modified:** `backend/app/services/metrics/salesperson_kpi_service.py`
**Commit:** c6728ef7
**Applied fix:** Added `history_by_lead: dict[str, list[dict]] = {}` unconditionally before the first `if leads_assigned > 0:` block. Removed the duplicate `history_by_lead: dict[str, list[dict]] = {}` declaration inside the `if leads_assigned > 0:` block (kept only the population loop). Removed the redundant `history_by_lead = {}` assignment from the `else` branch (the variable is now always pre-initialized).

---

### WR-04: Fix per-row commits breaking atomicity in `metrics_repository.py`

**Files modified:** `backend/app/services/repositories/metrics_repository.py`, `backend/tests/unit/test_metrics_repository.py`
**Commit (repository):** 3a551164
**Commit (tests):** b508c91a
**Applied fix:** Removed `await self._session.commit()` from `upsert_daily_kpi()`, `upsert_salesperson_kpi()`, and `upsert_source_kpi()`. The batch methods `upsert_salesperson_kpis` and `upsert_source_kpis` retain their end-of-loop commits per the fix specification. The task's final `session.commit()` (step 5) commits the SyncRun status update. Updated `test_metrics_repository.py` to assert `commit.assert_not_called()` instead of `commit.assert_called_once()` for the singular upsert methods.

---

### WR-05: Remove spurious `async` from `_compute_time_to_first_touch`

**Files modified:** `backend/app/services/metrics/salesperson_kpi_service.py`, `backend/tests/unit/test_salesperson_kpi_service.py`
**Commit (service):** c6728ef7
**Commit (tests):** b508c91a
**Applied fix:** Changed `async def _compute_time_to_first_touch(...)` to `def _compute_time_to_first_touch(...)`. Removed `await` from the call site. Updated the two tests that called `await service._compute_time_to_first_touch(...)` to call it without `await` and removed `@pytest.mark.asyncio` from those test functions.

---

### WR-06: Prevent orphaned `SyncRun(status="running")` rows on retry

**Files modified:** `backend/app/tasks/etl/calculate_daily_kpis.py`
**Commit:** 2fb7592c
**Applied fix:** Before creating a new `SyncRun(status="running")`, added an `UPDATE SyncRun SET status="failed", completed_at=... WHERE tenant_id=... AND source="metrics" AND status="running"` + `session.flush()` to mark any stale running records as failed. This prevents accumulation of permanently-stuck "running" rows when retries create multiple SyncRun entries but the error handler only updates the latest one.

---

### WR-07: Verify task route key matches registered task names

**Files modified:** `backend/app/tasks/celery_app.py`
**Commit:** d632269d
**Applied fix:** Added a comment to the `task_routes` dict explaining the naming convention requirement: route keys must match the explicit `name=` kwarg in `@celery_app.task` decorators. Verified that all three tasks (`sync_mefi_leads`, `backfill_mefi_leads`, `calculate_daily_kpis`) already declare `name="tasks.etl.*"` matching the route key pattern — no code changes needed beyond documentation.

---

_Fixed: 2026-05-27T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
