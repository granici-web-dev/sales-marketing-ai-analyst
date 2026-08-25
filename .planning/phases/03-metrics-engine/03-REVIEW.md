---
phase: 03-metrics-engine
reviewed: 2026-05-27T00:00:00Z
depth: standard
files_reviewed: 25
files_reviewed_list:
  - backend/alembic/versions/004_metrics_schema.py
  - backend/app/models/__init__.py
  - backend/app/models/metrics/__init__.py
  - backend/app/models/metrics/daily_kpi.py
  - backend/app/models/metrics/salesperson_kpi.py
  - backend/app/models/metrics/source_kpi.py
  - backend/app/services/metrics/__init__.py
  - backend/app/services/metrics/business_hours.py
  - backend/app/services/metrics/daily_kpi_service.py
  - backend/app/services/metrics/salesperson_kpi_service.py
  - backend/app/services/metrics/source_kpi_service.py
  - backend/app/services/repositories/metrics_repository.py
  - backend/app/tasks/celery_app.py
  - backend/app/tasks/etl/calculate_daily_kpis.py
  - backend/app/tasks/etl/sync_mefi_leads.py
  - backend/tests/factories/metrics_factory.py
  - backend/tests/unit/test_business_hours.py
  - backend/tests/unit/test_calculate_daily_kpis.py
  - backend/tests/unit/test_daily_kpi_service.py
  - backend/tests/unit/test_metrics_models.py
  - backend/tests/unit/test_metrics_repository.py
  - backend/tests/unit/test_migration_004.py
  - backend/tests/unit/test_salesperson_kpi_service.py
  - backend/tests/unit/test_source_kpi_service.py
  - backend/tests/unit/test_sync_mefi_leads.py
findings:
  critical: 5
  warning: 7
  info: 3
  total: 15
status: issues_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-05-27T00:00:00Z
**Depth:** standard
**Files Reviewed:** 25
**Status:** issues_found

## Summary

Phase 3 delivers the metrics engine: three metric tables (`daily_kpi`, `salesperson_daily_kpi`, `source_daily_kpi`), a business-hours utility, three aggregation services, a repository write layer, a Celery task, and 91 tests. The structural decisions are sound — NullPool fork safety, UPSERT idempotency, Decimal arithmetic throughout, explicit tenant_id validation before Core INSERTs — and the code shows clear awareness of the documented pitfalls.

However, **five blockers were found**. The most severe is a systematic data-inflation bug that will produce incorrect KPI counts for any lead that has at least one history row (which in production will be most leads). Two additional blockers affect calculation correctness directly: `min()` raises `ValueError` instead of returning `None` when all history rows have `NULL` timestamps, and `alte_ids` from `funnel_config` is silently ignored in both aggregate services. Two further blockers are a potential infinite loop in the business-hours engine and a double-retry hazard in the KPI Celery task.

---

## Critical Issues

### CR-01: `v_mefi_leads_active` LEFT JOIN fans out leads — `COUNT(*)` inflates all KPI counts

**File:** `backend/alembic/versions/004_metrics_schema.py:155-159` and `backend/app/services/metrics/daily_kpi_service.py:162` and `backend/app/services/metrics/source_kpi_service.py:166` and `backend/app/services/metrics/salesperson_kpi_service.py:207`

**Issue:** The updated `v_mefi_leads_active` view (migration 004) performs a `LEFT JOIN mefi_lead_history h ON h.tenant_id = r.tenant_id AND h.lead_external_id = r.external_id` with **no `GROUP BY` and no `DISTINCT`**. A lead with N history rows therefore produces N rows in the view. The window functions (`BOOL_OR ... OVER (PARTITION BY r.tenant_id, r.external_id)`) correctly aggregate the boolean `reached_*` columns, but every downstream `COUNT(*)` counts N instead of 1 for each multi-history lead.

Concretely:
- `daily_kpi_service.py:162` — `COUNT(*) AS leads_total` is overcounted.
- All per-source counts in `source_kpi_service.py:166-169` — `COUNT(*) AS leads`, `COUNT(CASE WHEN reached_visit ...) AS visits`, etc. — are overcounted.
- `salesperson_kpi_service.py:207` — `leads = lead_result.all()` then `len(leads)` is overcounted, and `sum(1 for l in leads if l.reached_visit)` is overcounted.

In a production database where the average lead has 4 history entries, every metric will be inflated ~4×. This corrupts all conversion rates, revenue, and delta values stored in the three metric tables.

**Fix:** Either deduplicate inside the view using a lateral join or `DISTINCT ON`, or deduplicate in the CTE that wraps the view query.

Option A — fix the view to use a subquery that aggregates history before joining:
```sql
CREATE OR REPLACE VIEW v_mefi_leads_active AS
SELECT
    r.tenant_id, r.id, r.created_at, r.updated_at,
    r.external_id, r.status_id, r.status_name, r.source_id, r.source_name,
    r.lifecycle, r.assigned_to_id, r.assigned_to_name, r.estimated_value,
    r.priority, r.is_duplicate, r.created_at_source, r.last_contact_at,
    r.status_changed_at, r.showroom, r.offer_sent_flag,
    r.utm_source, r.utm_campaign, r.utm_content, r.utm_medium,
    r.custom_fields_raw, r.raw_payload, r.synced_at,
    r.created_at_source AT TIME ZONE 'Europe/Bucharest' AS created_at_local,
    r.status_changed_at AT TIME ZONE 'Europe/Bucharest' AS status_changed_at_local,
    (r.status_id IN (17, 3, 1) OR COALESCE(h_agg.reached_visit, FALSE)) AS reached_visit,
    (r.status_id IN (3, 1) OR r.offer_sent_flag = TRUE OR COALESCE(h_agg.reached_offer, FALSE)) AS reached_offer,
    (r.status_id = 1) AS reached_contract
FROM raw_mefi_leads r
LEFT JOIN (
    SELECT
        tenant_id,
        lead_external_id,
        BOOL_OR(to_status_id IN (17, 3, 1)) AS reached_visit,
        BOOL_OR(to_status_id IN (3, 1))     AS reached_offer
    FROM mefi_lead_history
    GROUP BY tenant_id, lead_external_id
) h_agg ON h_agg.tenant_id = r.tenant_id AND h_agg.lead_external_id = r.external_id
WHERE r.lifecycle IN ('active', 'lost')
```

This produces exactly one row per lead. Migration 005 must `CREATE OR REPLACE` the view with this DDL (and update the downgrade path accordingly).

---

### CR-02: `min()` on empty generator raises `ValueError` — masquerades as unexpected task failure

**File:** `backend/app/services/metrics/salesperson_kpi_service.py:101-105`

**Issue:** `_compute_time_to_first_touch` filters history rows by `changed_at is not None` before passing to `min()`:
```python
first_touch = min(
    row["changed_at"] for row in history_rows if row.get("changed_at") is not None
)
if first_touch is None:   # dead code — never reached
    return None
```
If `history_rows` is non-empty but every entry has `changed_at = None` (a plausible data-quality condition when the history row was written before a timestamp was available), the generator is empty and `min()` raises `ValueError: min() arg is an empty sequence`. The `if first_touch is None` guard is dead code — `min()` never returns `None`; it raises before reaching that line.

The exception propagates as an unhandled `ValueError` up through `compute_for_date`, fails the Celery task, and the SyncRun is marked `failed`. The tenant gets no salesperson KPIs for that day.

**Fix:**
```python
valid_timestamps = [
    row["changed_at"] for row in history_rows if row.get("changed_at") is not None
]
if not valid_timestamps:
    return None
first_touch = min(valid_timestamps)
```

---

### CR-03: `alte_ids` from `funnel_config` is fetched but never passed to the SQL query — custom `alte` mappings are silently ignored

**File:** `backend/app/services/metrics/daily_kpi_service.py:148` and `backend/app/services/metrics/source_kpi_service.py:131`

**Issue:** Both services read `alte_ids` from `funnel_config.source_categories`:
```python
alte_ids = source_categories.get("alte", [3, 4, 5, 7, 12, 13])
```
But `alte_ids` is **never referenced in the SQL query or `bindparams()` call** in either service. The SQL for the `alte` bucket is a residual catch-all: "any source_id not in the named sets AND not designer AND not google." This means:

1. If a tenant configures `alte_ids` to exclude source ID 5 (moving it to a named category), that configuration is ignored — source 5 still falls into `alte`.
2. If a future tenant has different `alte` source IDs in `funnel_config`, they are silently discarded.

In `daily_kpi_service.py`, `alte_ids` is computed on line 148 but not included in `bindparams()` at lines 183-190. In `source_kpi_service.py`, same issue at lines 131 and 173-180.

**Fix — daily_kpi_service.py:** Add `:alte_ids` to the SQL and bindparams:
```python
# In the SQL CASE expression, replace the residual ELSE with explicit alte check:
COUNT(CASE WHEN v.source_id = ANY(:alte_ids) AND d.lead_external_id IS NULL THEN 1 END) AS leads_alte,
# ...
).bindparams(
    tid=str(self._tenant_id),
    kpi_date=kpi_date,
    mail_fb_ig_ids=mail_fb_ig_ids,
    telefon_ids=telefon_ids,
    whatsapp_ids=whatsapp_ids,
    site_ids=site_ids,
    alte_ids=alte_ids,   # ← add this
)
```
Apply the same fix in `source_kpi_service.py`.

---

### CR-04: Empty `work_days` list causes infinite loop in `_next_open` — Celery worker hangs permanently

**File:** `backend/app/services/metrics/business_hours.py:45-58` and `backend/app/services/metrics/salesperson_kpi_service.py:158-167`

**Issue:** `_next_open` loops indefinitely when `work_days` is empty:
```python
while True:
    if candidate_date.weekday() in work_days:  # always False when work_days = []
        return open_dt
    candidate_date += timedelta(days=1)        # advances forever
```
`SalespersonKpiService._get_business_hours` falls back to the default `[0,1,2,3,4,5,6]` on `KeyError`, `ValueError`, or `AttributeError`, but a valid `funnel_config` with `"days": []` (an empty list — syntactically correct JSON) passes through the `try` block at line 160 without error, setting `work_days = []`. Any salesperson with an active lead triggers `business_minutes_between` → `_next_open` → infinite loop. The Celery worker process hangs until killed by the OS or visibility timeout (9 hours), during which it processes no other tasks.

**Fix — validate `work_days` after parsing:**
```python
work_days = list(bh["days"])
if not work_days:
    raise ValueError("business_hours.days must not be empty")
```
The `except (KeyError, ValueError, AttributeError)` block at line 162 will catch the `ValueError` and fall back to the safe default.

Additionally, add the same guard inside `business_minutes_between` as a defence-in-depth:
```python
if not work_days:
    return 0   # or raise ValueError — but do not loop
```

---

### CR-05: Double-retry hazard — `calculate_daily_kpis` manual `self.retry()` conflicts with `autoretry_for=(Exception,)`

**File:** `backend/app/tasks/etl/calculate_daily_kpis.py:39-67`

**Issue:** The task declares `autoretry_for=(Exception,)` (line 41) which automatically retries on any exception. The task body also has an explicit manual retry:
```python
try:
    return asyncio.run(_calc_async(UUID(tenant_id), calculation_date))
except Exception as exc:
    raise self.retry(exc=exc) from exc
```
When `asyncio.run()` raises, the `except` block calls `self.retry(exc=exc)`, which raises `celery.exceptions.Retry`. Celery processes this and schedules the retry. However when `max_retries` (3) is exhausted, `self.retry()` re-raises the **original exception** (not `Retry`). The `autoretry_for` wrapper, which wraps the entire `run()` function, then sees that `Exception` and **schedules an additional retry sequence** (up to another 3 retries), effectively allowing up to 6 retries instead of 3. This doubles the retry budget and can leave stale `SyncRun(status="running")` rows in the database for each spurious retry.

**Fix:** Remove the manual try/except. `autoretry_for=(Exception,)` handles all retries automatically:
```python
@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    max_retries=3,
    default_retry_delay=60,
    name="tasks.etl.calculate_daily_kpis",
)
def calculate_daily_kpis(
    self,
    tenant_id: str,
    calculation_date: str | None = None,
) -> dict:
    return asyncio.run(_calc_async(UUID(tenant_id), calculation_date))
```
The `UUID(tenant_id)` call will raise `ValueError` for malformed input, which `autoretry_for=(Exception,)` will retry — which is the intended behavior per the docstring.

---

## Warnings

### WR-01: `leads_google` computed but discarded — `daily_kpi` table has no column for it, causing silent data gap

**File:** `backend/app/services/metrics/daily_kpi_service.py:163,199`

**Issue:** `leads_google` is computed by the SQL query (line 163) and extracted into a Python variable (line 199), but is **never included in `row_dict`** returned to `MetricsRepository.upsert_daily_kpi()`. The `DailyKpi` model and migration 004 have no `leads_google` column. Google lead counts exist in `source_daily_kpi` (where `source='google'`) but not in the aggregate `daily_kpi` table. Additionally, `leads_total` counts all leads including Google, while `leads_mail_fb_ig + leads_telefon + leads_whatsapp + leads_site + leads_designer + leads_alte` does not. Any dashboard or analysis expecting `sum(leads_by_category) == leads_total` will see a systematic discrepancy.

**Fix:** Either add a `leads_google` column to `DailyKpi` (migration 005) and include it in `row_dict`, or explicitly document that `leads_total` includes Google and the named columns do not, and adjust the comment on line 163 to avoid confusion.

---

### WR-02: `reached_visit` history check is broader than the comment states — inflates visit conversion rate

**File:** `backend/alembic/versions/004_metrics_schema.py:134-139`

**Issue:** The comment reads: "Visit: current status IN (17,3,1) OR ever had status 17 in history." However, the SQL history check is:
```sql
BOOL_OR(h.to_status_id IN (17, 3, 1)) OVER (PARTITION BY r.tenant_id, r.external_id)
```
This marks `reached_visit = TRUE` for any lead that ever had status 3 (Offer) or status 1 (Contract) in its history — even if it **never** had status 17 (Showroom Visit). A lead that went directly from "new" to "offer" (skipping the showroom) will have `reached_visit = TRUE`, inflating the visit count and artificially increasing the visit-to-offer conversion rate (which becomes 100% for such leads).

This may be intentional product logic (progressive funnels imply earlier stages), but the comment misleads future maintainers. If it is intentional, remove "ever had status 17" from the comment and replace it with "ever had any visit-or-beyond status (17, 3, or 1) in history." If it is unintentional, change `IN (17, 3, 1)` to `= 17`.

**Fix (comment correction for intentional behavior):**
```sql
-- Visit: current status IN (17,3,1) OR ever reached any visit-or-later stage (status 17, 3, or 1) in history
```

**Fix (if behavior is unintentional):**
```sql
BOOL_OR(h.to_status_id = 17) OVER (PARTITION BY r.tenant_id, r.external_id)
```

---

### WR-03: `leads_contacted` references `history_by_lead` defined in a sibling `if` block — fragile variable scope

**File:** `backend/app/services/metrics/salesperson_kpi_service.py:287-295`

**Issue:** `history_by_lead` is defined inside the first `if leads_assigned > 0:` block (line 244). The `leads_contacted` computation references it in a second, separate `if leads_assigned > 0:` block (line 287). If `leads_assigned > 0`, `history_by_lead` IS defined, so this works. But the `else` branch at line 293-294 redundantly reassigns `history_by_lead = {}` — this is dead code when `leads_assigned == 0`, because in that case the first `if` block was skipped and `history_by_lead` was never defined; fortunately, the else branch defines it before use.

The fragility is that a future refactor could break the invariant by changing the first `if` block without updating the second. The variable exists in an implicit scoping relationship that is not documented.

**Fix:** Consolidate both `if leads_assigned > 0` blocks into a single block, or initialize `history_by_lead = {}` unconditionally before the first block.

---

### WR-04: Per-row `commit()` in `upsert_daily_kpi` and singular upsert methods breaks atomicity with the task's own session operations

**File:** `backend/app/services/repositories/metrics_repository.py:65,98,173`

**Issue:** `upsert_daily_kpi()`, `upsert_salesperson_kpi()`, and `upsert_source_kpi()` each call `await self._session.commit()` internally. The batch methods (`upsert_salesperson_kpis`, `upsert_source_kpis`) correctly commit once after the loop. But the task in `calculate_daily_kpis.py` also calls `await session.commit()` after all three upsert operations (line 167). The net result is that each metric table is written and committed independently. A failure between `upsert_daily_kpi` and `upsert_salesperson_kpis` leaves `daily_kpi` with new data but `salesperson_daily_kpi` and `source_daily_kpi` with stale data, and `SyncRun` still at `status="running"`. On retry, UPSERT idempotency corrects this, but the window between partial writes and the error handler is a data-consistency gap for any reads that happen during that window.

**Fix:** Move `commit()` out of the individual repository methods and into the task (or a unit-of-work context manager), so the three metric tables plus the SyncRun status update are committed atomically.

---

### WR-05: `_compute_time_to_first_touch` is declared `async` but contains no `await` — misleads callers

**File:** `backend/app/services/metrics/salesperson_kpi_service.py:70-121`

**Issue:** `_compute_time_to_first_touch` is declared `async def` but performs only synchronous computation (no `await` anywhere in the function body; the deferred import of `business_minutes_between` is also synchronous). It is `await`-ed at the call site (line 257), which works, but the `async` declaration adds overhead (coroutine object creation and scheduling) and misleads future maintainers into thinking DB or I/O calls happen inside.

**Fix:** Change to `def _compute_time_to_first_touch(...)` (synchronous) and call it without `await`:
```python
ttft = self._compute_time_to_first_touch(
    str(l.lead_external_id),
    lead_history,
    lead_created_at=l.created_at_source,
    open_time=open_time,
    close_time=close_time,
    work_days=work_days,
    tz=tz,
)
```

---

### WR-06: Orphaned `SyncRun(status="running")` rows accumulate on repeated retries

**File:** `backend/app/tasks/etl/calculate_daily_kpis.py:127-135`

**Issue:** Each invocation of `calculate_daily_kpis` (including every retry) unconditionally creates and commits a new `SyncRun(status="running")` row at Step 1 (line 127-134). With `max_retries=3` (potentially up to 6 per CR-05), a single failing invocation creates 4–7 `SyncRun` rows. The error handler uses `LIMIT 1 ORDER BY started_at DESC` to find the latest one, so older ones are never updated and remain permanently `status="running"`. Any audit dashboard querying `SyncRun WHERE status='running'` will accumulate noise over time.

**Fix:** Before creating a new `SyncRun`, check whether an existing `running` record exists for this `(tenant_id, source)` pair and reuse it instead of creating a duplicate, or mark previous `running` rows as `failed` before creating the new one.

---

### WR-07: Task route key in `celery_app.conf` uses module-dotted name that doesn't match registered task name

**File:** `backend/app/tasks/celery_app.py:77-79`

**Issue:**
```python
task_routes={
    "tasks.etl.backfill_mefi_leads": {"queue": "backfill"},
},
```
The registered task name (per the `name=` kwarg in the `@celery_app.task` decorator) is `"tasks.etl.backfill_mefi_leads"`. The test at `test_sync_mefi_leads.py:125-126` asserts this key exists and passes. However, this naming convention (`tasks.etl.*` not `app.tasks.etl.*`) is inconsistent with the `include` list at lines 28-33 which uses `app.tasks.etl.*` module paths. If Celery's task autodiscovery uses the module path as the default name for any task that doesn't declare an explicit `name=`, those tasks would be routed using `app.tasks.etl.*` names and the routing rule would silently not apply. Verify that all tasks in `app.tasks.etl` declare explicit `name="tasks.etl.*"` and that the route key matches.

---

## Info

### IN-01: `alte_ids` unused variable in both services should be removed to prevent confusion

**File:** `backend/app/services/metrics/daily_kpi_service.py:148` and `backend/app/services/metrics/source_kpi_service.py:131`

**Issue:** Even after fixing CR-03 (passing `alte_ids` to the SQL), if the residual catch-all approach is kept intentionally (i.e., `alte` is defined as "everything else"), then `alte_ids` should be removed from both services. Currently it is read from `funnel_config` and silently discarded, which misleads future developers into thinking the config drives the `alte` bucket.

**Fix:** Either use `alte_ids` in the SQL (CR-03 fix) or remove the variable entirely and add a comment explaining that `alte` is a residual category.

---

### IN-02: Two test functions in `test_migration_004.py` have `self=None` parameter — anti-pattern

**File:** `backend/tests/unit/test_migration_004.py:184,221`

**Issue:**
```python
def test_business_hours_patch_dict(self=None) -> None:
def test_replaces_v_mefi_leads_active_with_history_join(self=None) -> None:
```
Module-level pytest functions should not declare `self`. pytest calls them with no arguments; `self=None` works accidentally because the default satisfies the parameter, but it confuses type checkers (mypy would flag this) and suggests the functions were intended to be class methods that were accidentally promoted to module level. The mypy strict mode required by CLAUDE.md will flag these.

**Fix:** Remove `self=None` from both function signatures:
```python
def test_business_hours_patch_dict() -> None:
def test_replaces_v_mefi_leads_active_with_history_join() -> None:
```

---

### IN-03: `avg_time_to_first_touch_minutes` averaging uses integer truncation

**File:** `backend/app/services/metrics/salesperson_kpi_service.py:270`

**Issue:**
```python
ttft_minutes = int(sum(ttft_values) / len(ttft_values))
```
`sum(ttft_values)` is `int`, `len(ttft_values)` is `int`, so the division is float division in Python 3, then truncated by `int()`. For example, if three leads have TTFT of 10, 10, 11 minutes, the average is 10.33... truncated to 10. The model stores `Integer`, so some loss of precision is unavoidable, but using `round()` instead of `int()` would give a less biased estimate.

**Fix:**
```python
ttft_minutes = round(sum(ttft_values) / len(ttft_values))
```

---

_Reviewed: 2026-05-27T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
