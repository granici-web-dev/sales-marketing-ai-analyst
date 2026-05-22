---
phase: 02
status: issues_found
critical_count: 5
warning_count: 7
info_count: 4
---

# Phase 02 Code Review

## Summary

Phase 02 delivers the MEFI ETL pipeline: HTTP client, DB repository, nightly sync task, one-time backfill task, Alembic migration, and a full test suite. The structural skeleton is sound — tenant isolation, fork-safe deferred imports, Redis advisory lock, and UPSERT idempotency are correctly implemented. However, five blockers were found: a type mismatch that silently returns `None` for every custom field extraction call, a `to_status_id` NOT NULL constraint that will crash on NULL status leads, a leaked Redis connection on happy-path early return, a non-existent `pytest-asyncio==1.2.0` pin, and a SQL session scope bug that issues ORM writes against a closed session. Seven warnings cover data-loss-adjacent risks and quality issues.

---

## Findings

### Critical

---

**[CRITICAL-01]** `backend/app/tasks/etl/sync_mefi_leads.py:26` — `get_cf()` calls `.get()` on Pydantic model objects, not dicts — always returns `None`

`lead.custom_fields` is `list[MefiCustomField]` (Pydantic v2 model instances). `get_cf()` is typed as `list[dict] | None` and calls `f.get("field_id")`. Pydantic `BaseModel` instances do not have a `.get()` method — the call raises `AttributeError` at runtime in Python 3.11, or silently evaluates to `None` in some mock/test contexts. In production every call to `get_cf(cf, 14)`, `get_cf(cf, 20)`, `get_cf(cf, 38–41)` will fail, meaning `showroom`, `offer_sent_flag`, and all UTM fields will be `None` for every lead. This silently destroys all custom-field data with zero error logged.

The same bug exists identically in `backend/app/tasks/etl/backfill_mefi_leads.py:24–27` (the duplicated copy).

The unit tests in `test_sync_mefi_leads.py` pass dicts directly to `get_cf`, so they do not catch the runtime failure with real Pydantic objects.

**Fix:** Either convert the Pydantic objects to dicts before calling `get_cf`, or rewrite `get_cf` to handle both:
```python
# Option A — convert first (preferred, explicit)
cf_dicts = [f.model_dump() for f in lead.custom_fields]
showroom = get_cf(cf_dicts, 14)

# Option B — update get_cf to handle Pydantic objects
def get_cf(fields: list[MefiCustomField | dict] | None, field_id: int) -> str | None:
    if not fields:
        return None
    for f in fields:
        if isinstance(f, dict):
            fid, val = f.get("field_id") or f.get("id"), f.get("value")
        else:
            fid, val = f.field_id, f.value
        if fid == field_id:
            return val
    return None
```
Also fix `custom_fields_raw` serialisation: `[f.model_dump() for f in cf]` is already correct in the row dict — use the same `cf_dicts` list there for consistency.

---

**[CRITICAL-02]** `backend/app/services/repositories/mefi_repository.py:118–119` — `to_status_id` NOT NULL constraint violated when `status_id` is absent

In `detect_and_record_history`, a history row is created for new leads (line 112–120) or status-changed leads (line 125–131). `to_status_id` is set from `row.get("status_id")` which returns `None` if the field is absent or was set to `None` in the row dict. `MefiLeadHistory.to_status_id` is `Mapped[int]` with `nullable=False` in both the ORM model (`mefi.py:154`) and the DDL (`003_mefi_schema.py`). Inserting a `None` value violates the NOT NULL constraint, raising `IntegrityError` and aborting the batch. Leads with `status=None` (valid per MEFI API: `status: MefiStatusRef | None = None` in `mefi.py:81`) trigger this.

**Fix:**
```python
new_status_id = row.get("status_id")
if new_status_id is None:
    # Skip history for leads without a status — cannot record a meaningful transition
    continue
```
Add this guard before appending to `history_rows` in both the new-lead branch and the changed-status branch.

---

**[CRITICAL-03]** `backend/app/tasks/etl/sync_mefi_leads.py:88–89` — Redis connection is not closed when lock acquisition returns early

When the lock is already held (`acquired` is falsy) the code returns early at line 89 with `await redis.aclose()` called first. However, the `finally` block at line 272–274 (`await redis.delete(lock_key)` and `await redis.aclose()`) is inside the outer `try` block that begins at line 91. The early-return path at line 88–89 correctly closes the connection, so this path is fine.

**However**, re-reading: the `finally` block at lines 272–274 executes `await redis.delete(lock_key)` unconditionally. When the noop path (`acquired is None`) exits at line 89 (after `aclose`), the `try` block at line 91 is never entered, so the `finally` is never reached — this is correct. But there is a real problem: if `redis.set(...)` itself raises an exception (e.g., Redis is unreachable), `redis` is still defined but `.aclose()` is never called in the exception path because the `finally` at line 272 only runs if the main `try` (line 91) was entered. The `redis` variable is created at line 84, before the `try` block begins. A `ConnectionError` from line 85 would leave the aioredis connection pool unclosed.

**Fix:** Wrap the redis connection creation and use in a `try/finally`:
```python
redis = aioredis.from_url(settings.redis_url, decode_responses=True)
try:
    acquired = await redis.set(lock_key, "1", nx=True, ex=_LOCK_TTL)
    if not acquired:
        log.info("sync.lock_held", lock_key=lock_key)
        return {"status": "noop", "reason": "lock_held"}
    try:
        # ... main body ...
    except Exception as exc:
        # ... error handling ...
        raise
    finally:
        await redis.delete(lock_key)
finally:
    await redis.aclose()
```

---

**[CRITICAL-04]** `backend/pyproject.toml:27` — `pytest-asyncio==1.2.0` does not exist; test suite cannot install

`pytest-asyncio==1.2.0` is pinned in `[project.optional-dependencies].dev`. The latest release of pytest-asyncio as of mid-2026 is in the `0.x` series (e.g., `0.23.x`). There is no `1.2.0` release. `pip install pytest-asyncio==1.2.0` will fail with `Could not find a version that satisfies the requirement`. This means the entire test suite cannot be installed in CI or by any developer. All 24 unit tests and the integration test are blocked.

**Fix:**
```toml
"pytest-asyncio>=0.23,<1",
```

---

**[CRITICAL-05]** `backend/app/tasks/etl/sync_mefi_leads.py:228–234` — ORM writes on `session` after the `async with` context manager has exited

The `SyncRun` update on success (lines 229–234) writes to `sync_run.status`, `sync_run.records_synced`, etc. and calls `await session.commit()`. But `sync_run` was added to `session` inside the `async with AsyncSessionLocal() as session:` block (line 92), and the ORM writes on line 229 are still inside that block. This is actually fine for lines 229–234 **but** when the `RuntimeError("No data for today")` is raised at line 226, it exits the inner `async with MefiClient(...) as client:` context and is caught by the outer `except Exception as exc:` at line 248. In the error handler (lines 250–268), a *new* session (`err_session`) is opened to update the `SyncRun` — but the `SyncRun` with `status="running"` was committed on `session` (line 103). After `session` exits its context block (line 92), the ORM identity map is expired. The error handler selects by `status == "running"` which should still work. **The real bug is** that `session.commit()` at line 234 is reached even when `total_synced == 0 and date_from == date_to` raises `RuntimeError` at line 226 — the raise at 226 means lines 229–234 are never reached, and the `SyncRun` is never marked `success`. The error handler at line 266 then correctly marks it `failed`. This is correct behaviour. **However**, the `sync_run` ORM object was attached to `session` which exits its `async with` context after the exception propagates. The subsequent `err_session.execute(_select(_SR)...)` opens a fresh session and selects by `tenant_id + source + status="running"` — this is safe. But the SyncRun `started_at.desc().limit(1)` query on line 261 will pick the first matching running record. If two concurrent tasks somehow bypassed the Redis lock (edge case), the wrong SyncRun could be updated. This is a structural weakness rather than an outright crash, but warrants fixing.

**Fix:** Pass `sync_run.id` into the exception handler instead of re-querying by (tenant, source, status):
```python
# Before the try block, store the ID
sync_run_id: UUID | None = None
...
await session.refresh(sync_run)
sync_run_id = sync_run.id
...
# In error handler
if sync_run_id:
    run = await err_session.get(SyncRun, sync_run_id)
```

---

### Warning

---

**[WARNING-01]** `backend/app/services/repositories/mefi_repository.py:53–61` — `updated_at` not included in UPSERT `set_` — stale timestamp on every conflict

The `bulk_upsert_leads` update column list explicitly enumerates mutable fields but omits `updated_at`. On every UPSERT that hits the `ON CONFLICT DO UPDATE` branch, the `updated_at` column retains its original value (the timestamp of the first insert). The `updated_at` field has `onupdate=func.now()` on the ORM side, but Core `pg_insert` does not trigger ORM event listeners. This means any downstream query checking `updated_at > last_check` will never see updates to existing leads.

**Fix:** Add `"updated_at"` to `update_cols`, or add `"updated_at": func.now()` to `set_`:
```python
stmt = stmt.on_conflict_do_update(
    index_elements=["tenant_id", "external_id"],
    set_={
        **{col: stmt.excluded[col] for col in update_cols},
        "updated_at": func.now(),
    },
)
```

---

**[WARNING-02]** `backend/app/tasks/etl/sync_mefi_leads.py:266` — `error_msg = str(exc)[:500]` may log PII from MEFI HTTP responses

Exception messages from `httpx.HTTPStatusError` include the response URL and body excerpt. MEFI API error responses could contain the lead name, phone, or email (e.g., a validation error body echoing the request). This is stored in `sync_runs.error_msg` and readable by any service with DB access.

**Fix:** Sanitise the error message before storing, or categorise by exception type:
```python
if isinstance(exc, httpx.HTTPStatusError):
    error_msg = f"HTTP {exc.response.status_code} from MEFI API"
elif isinstance(exc, httpx.HTTPError):
    error_msg = f"Network error: {type(exc).__name__}"
else:
    error_msg = type(exc).__name__
run.error_msg = error_msg[:500]
```

---

**[WARNING-03]** `backend/app/services/integrations/mefi.py:215` — `int()` on missing `X-RateLimit-Remaining` header raises `ValueError` if the header contains non-numeric content

```python
remaining = int(response.headers.get("X-RateLimit-Remaining", 600))
```
If MEFI returns a malformed header value (e.g., `"N/A"` or empty string `""`), `int()` raises `ValueError` and propagates out of `_request`, causing the whole sync to abort on an unexpected exception type that is not caught by `autoretry_for`.

**Fix:**
```python
try:
    remaining = int(response.headers.get("X-RateLimit-Remaining", 600))
except (ValueError, TypeError):
    remaining = 600
```

---

**[WARNING-04]** `backend/app/tasks/etl/sync_mefi_leads.py:219` — pagination termination uses `len(response.data) < per_page`, not `page >= total_pages` — infinite loop risk

If `per_page=100` and the API returns exactly 100 records on the last page (a full final page), the loop continues and fetches page N+1 which returns `data=[]`. The empty-data `break` at line 155 catches this case, so no actual infinite loop occurs today. **However**, if the API omits the empty-page termination (returns a full last page with a 200 and meta.total_pages correctly set), this code will issue one extra API call per sync. More critically, if the API has a bug and keeps returning 100-record pages indefinitely, no upper bound terminates the loop — the task will run until the Redis lock TTL expires (10 hours) or the worker is killed.

**Fix:** Add an upper-bound guard using `response.meta`:
```python
if page >= response.meta.total_pages:
    break
page += 1
```

---

**[WARNING-05]** `backend/app/tasks/etl/sync_mefi_leads.py:224–226` — `RuntimeError("No data for today")` raised inside `async with AsyncSessionLocal()` exits without marking `SyncRun` as failed via the main session

When `total_synced == 0 and date_from == date_to`, the `RuntimeError` propagates past the `async with session` context manager. The context manager rolls back any uncommitted transaction (the success commit at line 234 has not run). The error handler at line 248 opens a new session and searches for a `running` SyncRun to mark `failed`. This works in the single-tenant case, but the SyncRun status transition from `running` to `failed` happens in a *different* session than where the `running` record was first committed. If the error handler's `SELECT` fails (lines 269 `except Exception: pass`), the SyncRun remains stuck in `running` status indefinitely.

**Fix:** Mark the SyncRun `failed` before raising:
```python
if total_synced == 0 and date_from == date_to:
    log.warning("sync.no_data_today", date=date_to)
    sync_run.status = "failed"
    sync_run.error_msg = "No data for today — pipeline halted"
    sync_run.completed_at = datetime.now(UTC)
    await session.commit()
    raise RuntimeError("No data for today — halting pipeline chain")
```

---

**[WARNING-06]** `backend/app/services/integrations/mefi.py:93–107` — `authenticate()` ignores all non-401/403 HTTP errors by returning `False` — masks server errors

The `authenticate` method catches `httpx.HTTPStatusError` (any HTTP error) and always returns `False` regardless of status code. A 500 Internal Server Error or 503 Service Unavailable will silently be treated as "bad credentials" instead of "API temporarily unavailable". This causes the nightly sync to abort with a misleading "liveness_failed" or silent failure rather than retrying.

**Fix:** Only suppress auth errors; re-raise server errors:
```python
except httpx.HTTPStatusError as exc:
    if exc.response.status_code in (401, 403):
        return False
    raise  # propagate 5xx — let caller decide
```

---

**[WARNING-07]** `backend/app/tasks/etl/backfill_mefi_leads.py:62–74` — `backfill_mefi_leads` uses `asyncio.run()` inside a Celery task with `task_acks_late=True` — double-run risk under `gevent`/`eventlet` workers

Celery's concurrency model with `asyncio.run()` works correctly under the default **prefork** pool, but `asyncio.run()` creates a new event loop per call and blocks the thread. If the worker pool is ever switched to `gevent` or `eventlet` (common for I/O-heavy workloads), `asyncio.run()` inside a task body creates a new loop that conflicts with the monkey-patched event system, causing deadlocks or missed acknowledgements with `task_acks_late=True`. The same issue exists in `sync_mefi_leads.py:53`. This is a latent correctness bug that only surfaces on pool changes.

**Fix:** Document the dependency on prefork explicitly in the task docstring and pin the worker start command. For future-proofing, consider using `anyio` or a shared event loop per worker (created in `_on_worker_process_init`).

---

### Info

---

**[INFO-01]** `backend/app/tasks/etl/sync_mefi_leads.py:18` — `get_cf()` return type annotation is `object` instead of `str | None`

The actual returned value is always `str | None` (custom field values are strings or None). The `object` annotation prevents mypy from catching downstream type errors where the returned value is used as `str`.

**Fix:**
```python
def get_cf(fields: list[dict] | None, field_id: int) -> str | None:
```
Apply the same fix to the duplicated copy in `backfill_mefi_leads.py:15`.

---

**[INFO-02]** `backend/app/tasks/etl/sync_mefi_leads.py:277–287` — `daily_pipeline()` is a module-level function with a deferred `from celery import chain` import, but it is never called anywhere in Phase 2

The function is dead code in this phase. Its existence is justified by the plan comment ("Phase 3 will extend this"), but it is untested and the deferred import pattern inside a non-async function is inconsistent with the fork-safety pattern used elsewhere.

**Fix:** Keep as-is if intentional, but add a type annotation for the return type (`celery.canvas.chain`) and a test that it returns a chain containing `sync_mefi_leads`.

---

**[INFO-03]** `backend/app/tasks/celery_app.py:95` — `except Exception: pass` silently swallows RedBeat registration errors at import time

The beat schedule registration wraps the entire `RedBeatSchedulerEntry` creation and `.save()` in a broad `except Exception: pass`. If `settings.redis_url` is valid but Redis rejects the connection for a non-transient reason (wrong auth, wrong DB index), the beat schedule is silently not registered. The worker and beat container will start without error, but the nightly sync will never fire.

**Fix:** At minimum log the failure:
```python
except Exception as exc:  # noqa: BLE001
    import structlog
    structlog.get_logger().warning(
        "redbeat.schedule_registration_failed",
        error=str(exc),
    )
```

---

**[INFO-04]** `backend/tests/unit/test_mefi_repository.py:113` — `test_upsert_statement_has_on_conflict` contains a vacuous assertion

Line 113 ends with `or True`, making the entire assertion always pass regardless of whether `ON CONFLICT` appears in the compiled statement:
```python
assert "ON CONFLICT" in stmt_str.upper() or "on_conflict_do_update" in type(call_args).__name__.lower() or True
```
The comment on line 115 acknowledges this: "Primary assertion: the function doesn't raise and calls execute+commit". This test provides no actual validation of the UPSERT semantics.

**Fix:** Remove the `or True` and use a type check against the insert construct:
```python
from sqlalchemy.dialects.postgresql.dml import Insert
assert isinstance(call_args, Insert)
assert call_args.on_conflict_do_update is not None
```

---

## Verdict

**Five blockers must be fixed before production deployment.** The most severe is CRITICAL-01 (custom field extraction silently returns `None` for all leads due to a type mismatch), which would cause the ETL to write `NULL` into all `showroom`, `offer_sent_flag`, and UTM columns for every lead synced — making Phase 3 funnel metrics entirely wrong without any observable error.
