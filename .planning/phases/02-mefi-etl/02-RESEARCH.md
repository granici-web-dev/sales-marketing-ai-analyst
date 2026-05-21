# Phase 2: MEFI ETL — Research

**Researched:** 2026-05-21
**Domain:** Python async ETL — SQLAlchemy 2.x bulk upsert, Celery chain, Redis distributed lock, Alembic data/view migrations, MEFI CRM REST API
**Confidence:** HIGH (SQLAlchemy upsert + Alembic patterns confirmed via official docs; Celery retry patterns confirmed via official docs; MEFI API confirmed via project docs)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Raw Storage Scope**
- D-01: Pull all 3 lifecycle states (active, lost, junk) from MEFI and store in `raw_mefi_leads`. No lifecycle filter in the API call. Views handle filtering.
- D-02: Two conformed views: `v_mefi_leads_active` (lifecycle IN active/lost), `v_mefi_leads_junk` (lifecycle = junk). Metric services NEVER query `raw_mefi_leads` directly.

**Backfill Strategy**
- D-03: Auto-detect on first sync — `sync_mefi_leads` checks COUNT = 0 for the tenant. If yes, enqueues `backfill_mefi_leads` task before running incremental sync.
- D-04: Backfill chunks by full calendar months, 12 months back. Current partial month handled by regular incremental sync. Enqueue onto `backfill` Celery queue (separate from `default`).

**Salesperson List**
- D-05: Auto-upsert all user IDs seen in `assigned_to` field into `mefi_salespeople` via `INSERT ... ON CONFLICT (mefi_user_id) DO NOTHING`. Rows start with `is_active = NULL`, `showroom = NULL`.
- D-06: After first sync, Sofa Belle/developer manually sets `is_active = true` and `showroom` for the 6 active sellers.

**Funnel Config Migration**
- D-07: Seed `funnel_config` via new Alembic migration `003_seed_funnel_config.py`. Uses `UPDATE tenants SET funnel_config = '...' WHERE slug = 'sofa-belle'`.
- D-08: `funnel_config` is one JSONB column with visit/offer/contract stage IDs, source categories, showroom field key, junk status IDs, and offer_sent_flag_field key.

**Architecture & Rate Limiting**
- D-09: "Ever reached" funnel logic — lead is in stage if it EVER had the status (checked at read time from raw data in views/metrics layer).
- D-10: Incremental sync uses `date_from = last_sync_at`, `date_to = sync_start_at` upper bound to prevent page-shift.
- D-11: Redis lock `SET NX EX` on key `sync:mefi:{tenant_id}` prevents duplicate concurrent execution.
- D-12: Idempotent UPSERT on `(tenant_id, external_id)` for `raw_mefi_leads`.
- D-13: Rate limit: 600 req/min for read keys. Read `X-RateLimit-Remaining`, honor `Retry-After` on 429.
- D-14: Pipeline triggers downstream via Celery `chain()`: ETL → metrics → anomaly → insights.

### Claude's Discretion (from CONTEXT.md)
None explicitly listed.

### Deferred Ideas (OUT OF SCOPE)
- Webhook ingestion: real-time lead updates via MEFI webhooks
- Multi-tenant onboarding flow for funnel_config via UI
- Call data integration (MEFI API doesn't expose calls yet)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MEFI-01 | MEFI API client reads leads from `/leads/search` using MEFI_API_KEY from env | MefiClient(BaseIntegration) pattern in docs/INTEGRATIONS.md; settings.mefi_api_key needed in config.py |
| MEFI-02 | Nightly ETL syncs all leads to `raw_mefi_leads` via idempotent UPSERT on `(tenant_id, external_id)` | SQLAlchemy 2 postgresql dialect insert + on_conflict_do_update; bulk list of dicts in one statement |
| MEFI-03 | Incremental sync uses `date_from = last_sync_at`; backfill uses `date_to = sync_start_at` upper bound | Fixed date_to at task start; sort by status_changed_at ASC; pagination terminates on total_pages |
| MEFI-04 | Lifecycle junk filtering: `lifecycle IN ('active', 'lost')` only — junk excluded from metrics | Handled at VIEW layer (v_mefi_leads_active), not at sync/storage layer per D-01 |
| MEFI-05 | Funnel stage "ever reached" — Vizita if status_id ever was 17; Oferta if status_id ever 3 OR form-cf-20="✅DA"; Contract if status_id ever 1 | Evaluated from raw stored data; derived as computed columns in view or at metrics read time |
| MEFI-06 | Best-effort lead history: detect status changes between syncs, emit rows to `mefi_lead_history` | UPSERT RETURNING old status_id before update; compare with new; INSERT into mefi_lead_history |
| MEFI-07 | Tenant-specific status/source/salesperson IDs in `tenants.funnel_config JSONB` — no hardcoded IDs in code | Migration 003 seeds JSONB; services read config at task start |
| MEFI-08 | Sync run writes to `sync_runs` — status, records_synced, duration, error — success and failure | SyncRun model already exists; write at task start (status=running) and complete/fail |
| MEFI-09 | Liveness probe: if MEFI returns total=0 with no date filter, emit alert | Single liveness check call before sync; total=0 = API down or auth issue |
| MEFI-10 | Rate limit: max 50 req/min per REQUIREMENTS.md; 600/min per actual API; read X-RateLimit-Remaining; honor Retry-After on 429 | NOTE: REQUIREMENTS.md says 50/min but API README and leads-read.md say 600/min for lrd_* keys. Use 600/min (official API docs take precedence). |
| MEFI-11 | Redis lock SET NX EX on `sync:mefi:{tenant_id}` prevents duplicate concurrent runs | redis.asyncio client; set(key, val, nx=True, ex=TTL); delete on unlock |
| MEFI-12 | Initial 12-month backfill in dedicated `backfill` Celery queue, chunked by month | backfill queue registered in Phase 1 celery_app; backfill task iterates 12 month windows |
| DATA-01 | SQL views `v_mefi_leads_active` and `v_mefi_leads_junk` as metric layer interface | Alembic migration with op.execute("CREATE OR REPLACE VIEW ...") |
| DATA-02 | Critical custom fields promoted to dedicated columns: showroom (form-cf-14), UTM fields (form-cf-38..41), offer_sent_flag (form-cf-20) | Extracted during sync, stored as columns alongside custom_fields_raw JSONB |
| DATA-03 | All date grouping uses `AT TIME ZONE 'Europe/Bucharest'` — no raw UTC grouping | Applied in view definitions and all metric queries |
| DATA-04 | Revenue amounts as NUMERIC(12,2), never float | estimated_value mapped to NUMERIC(12,2) column; Pydantic field validated as Decimal |
| PIPE-01 | Celery chain() pipeline at 04:00 Europe/Bucharest: ETL → metrics → anomaly → insights | chain(sync_mefi_leads.si(), calculate_metrics.si(), detect_anomalies.si(), generate_insights.si()) |
| PIPE-02 | Each stage runs only if previous succeeded; failed stage halts chain | Celery chain propagates exceptions; if a task raises, subsequent tasks do not run |
| PIPE-03 | Pipeline health check after ETL: verify data exists for today before proceeding to metrics | Check COUNT in raw_mefi_leads for today's date; raise exception to halt chain if 0 |
</phase_requirements>

---

## Summary

Phase 2 builds the MEFI ETL pipeline on the foundation established in Phase 1. The three new backend components are: `MefiClient(BaseIntegration)` (HTTP client), `RawMefiLead` / `MefiLeadHistory` / `MefiSalesperson` (SQLAlchemy models), and two Celery tasks (`sync_mefi_leads`, `backfill_mefi_leads`). The conformed views (`v_mefi_leads_active`, `v_mefi_leads_junk`) are created via Alembic migration 003 alongside the funnel_config JSONB seed.

The critical correctness constraint is the date_to upper-bound windowing pattern (D-10): the task records `sync_start_at` at the very beginning, passes it as `date_to` to every paginated API call, and writes it to `sync_runs.completed_at` only on full success. This prevents leads from silently shifting pages during the multi-page fetch. The Redis `SET NX EX` lock (D-11) prevents a second beat-triggered run from starting while the first is still paginating.

For history tracking (MEFI-06), the most practical approach given the API's current-state-only response is a SELECT-before-UPSERT pattern: query the stored `status_id` for each lead's `external_id` before the bulk upsert, then emit `mefi_lead_history` rows for every lead where the status differs. This is O(1) per batch via a single SELECT with IN clause.

**Primary recommendation:** Use SQLAlchemy 2.x `postgresql.insert()` + `on_conflict_do_update()` with a list of dicts for single-statement bulk upserts; use `redis.asyncio` (already in pyproject.toml via `redis>=5`) for the distributed lock; use `op.execute("CREATE OR REPLACE VIEW ...")` in the Alembic migration for the conformed views.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| MEFI API pagination | Service (MefiClient) | — | All external HTTP calls in service layer per CLAUDE.md |
| Redis distributed lock | Celery Task | Service (MefiClient calls from task) | Lock scope is the task run, not the API call |
| Bulk UPSERT to raw_mefi_leads | Repository (MefiRepository) | — | DB access belongs in repository layer per Clean Architecture |
| Lead history change detection | Repository (MefiRepository) | — | Requires DB read before UPSERT — same layer |
| Salesperson auto-upsert | Repository (MefiRepository) | — | Same UPSERT pattern |
| Funnel config JSONB seed | Alembic migration 003 | — | Data migration, not application code |
| Conformed view creation | Alembic migration 003 | — | DDL belongs in migrations |
| SyncRun write | Celery Task | — | Task owns its own audit trail |
| Pipeline chain orchestration | Celery Beat schedule | — | Beat owns schedule; chain() defined in task module |
| Rate limit throttling | Service (MefiClient) | — | HTTP client layer reads response headers |

---

## Standard Stack

### Core (already in pyproject.toml — no new installs required)

| Library | Version (pyproject) | Latest (PyPI) | Purpose | Status |
|---------|---------------------|---------------|---------|--------|
| sqlalchemy[asyncio] | >=2.0,<3 | 2.0.49 | ORM + bulk upsert via postgresql dialect | Already installed |
| asyncpg | >=0.29,<1 | 0.30.0 | Async PostgreSQL driver | Already installed |
| alembic | >=1.13,<2 | 1.15.x | Migrations — view DDL + data migrations | Already installed |
| redis (redis.asyncio) | >=5,<6 | 7.0.1 | Async Redis client for distributed lock | Already installed |
| httpx | >=0.27,<1 | 0.28.1 | Async HTTP client for MEFI API | Already installed |
| celery[redis] | >=5.4,<6 | 5.6.3 | Task queue + chain orchestration | Already installed |
| pydantic v2 | >=2.7,<3 | 2.11.x | Request/response schema validation | Already installed |
| structlog | >=24,<26 | 25.x | Structured logging (no PII) | Already installed |

**No new runtime dependencies are required for Phase 2.** All packages needed are already present in `pyproject.toml`.

### Testing (dev extras — already present)

| Library | Version (pyproject) | Latest (PyPI) | Purpose |
|---------|---------------------|---------------|---------|
| respx | not yet in pyproject | 0.23.1 (PyPI) | Mock httpx requests in unit tests |
| pytest-asyncio | ==1.2.0 | 1.2.0 | Async test support |
| freezegun | in pyproject | 1.5.5 | Freeze datetime for sync window tests |
| factory-boy | in pyproject | 3.3.3 | Lead fixture factories |

**`respx` must be added to `[project.optional-dependencies].dev`** in pyproject.toml — it is the standard httpx mock library and is not currently listed.

**Installation:**
```bash
# No runtime changes. Only dev dependency to add:
# In pyproject.toml [project.optional-dependencies].dev, add:
"respx>=0.21,<1",
```

---

## Package Legitimacy Audit

slopcheck was not available at research time. All packages listed below are from pyproject.toml (already installed in Phase 1) or confirmed via `pip index versions`. No new packages with unknown provenance are being introduced.

| Package | Registry | Age | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|
| sqlalchemy | PyPI | 17+ yrs | [ASSUMED] OK | Approved — canonical Python ORM |
| asyncpg | PyPI | 8+ yrs | [ASSUMED] OK | Approved — canonical asyncpg driver |
| redis (redis-py) | PyPI | 14+ yrs | [ASSUMED] OK | Approved — official Redis Python client |
| httpx | PyPI | 6+ yrs | [ASSUMED] OK | Approved — Encode/encode project, widely used |
| celery | PyPI | 14+ yrs | [ASSUMED] OK | Approved — canonical distributed task queue |
| alembic | PyPI | 12+ yrs | [ASSUMED] OK | Approved — SQLAlchemy project migration tool |
| respx | PyPI | 5+ yrs | [ASSUMED] OK | Approved — standard httpx mock library |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none
**slopcheck was unavailable** — all packages above are tagged [ASSUMED]. Because all packages are already installed from Phase 1 (except respx which is a well-established testing library), human-verify checkpoint is waived; however planner should note [ASSUMED] provenance.

---

## Architecture Patterns

### System Architecture Diagram

```
Beat (04:00 EET)
    │
    ▼
[sync_mefi_leads task]
    │
    ├── 1. Acquire Redis lock (SET NX EX on sync:mefi:{tenant_id})
    │        └── Already locked? → log + return (NOOP)
    │
    ├── 2. Write SyncRun (status=running)
    │
    ├── 3. Liveness probe → POST /leads/search (no date_from, total=?)
    │        └── total=0? → emit alert, abort
    │
    ├── 4. COUNT raw_mefi_leads for tenant
    │        └── COUNT=0? → enqueue backfill_mefi_leads task → continue with incremental
    │
    ├── 5. Incremental fetch loop
    │   POST /leads/search
    │   filters: lifecycle=all, date_from=last_sync_at, date_to=sync_start_at
    │   date_field: status_changed_at
    │   sort: status_changed_at ASC, per_page=100
    │   ├── Page 1..N → yield lead batch
    │   └── For each lead where full_profile needed → GET /leads/{id}
    │
    ├── 6. Per-batch:
    │   ├── Extract custom fields (showroom, UTM, offer_sent_flag)
    │   ├── Detect status changes (SELECT existing status_id WHERE external_id IN (...))
    │   ├── UPSERT raw_mefi_leads (bulk postgresql.insert().on_conflict_do_update())
    │   ├── INSERT mefi_lead_history for changed leads
    │   └── UPSERT mefi_salespeople for new assigned_to IDs
    │
    ├── 7. Update SyncRun (status=success, records_synced=N, duration_ms)
    ├── 8. Release Redis lock
    │
    └── 9. chain() → calculate_metrics.si() [Phase 3]
             └── chain() → detect_anomalies.si() [Phase 4]
                      └── chain() → generate_insights.si() [Phase 5]


[backfill_mefi_leads task] (backfill queue, runs once after first sync)
    │
    ├── For each of 12 calendar months (oldest first):
    │   POST /leads/search
    │   date_from=month_start, date_to=month_end (FIXED at task start)
    │   lifecycle=all, sort=created_at ASC, per_page=100
    │   └── UPSERT raw_mefi_leads (same bulk pattern)
    │
    └── No chain → standalone, just fills historical data
```

### Recommended Project Structure

```
backend/app/
├── models/
│   └── mefi.py                        # RawMefiLead, MefiLeadHistory, MefiSalesperson
├── schemas/
│   └── mefi.py                        # MefiLeadResponse, MefiSearchResponse Pydantic models
├── services/
│   ├── integrations/
│   │   ├── base.py                    # BaseIntegration (already exists per INTEGRATIONS.md)
│   │   └── mefi.py                    # MefiClient(BaseIntegration)
│   └── repositories/
│       └── mefi_repository.py         # MefiRepository: bulk_upsert_leads(), upsert_salesperson()
└── tasks/
    ├── __init__.py
    ├── celery_app.py                  # Already built in Phase 1
    └── etl/
        ├── __init__.py
        └── sync_mefi_leads.py         # sync_mefi_leads task + backfill_mefi_leads task

backend/alembic/versions/
├── 001_base_tables.py                 # Phase 1 — exists
├── 002_seed_sofabelle.py              # Phase 1 — exists
└── 003_mefi_schema.py                 # Phase 2: mefi tables + views + funnel_config seed

backend/tests/
├── unit/
│   ├── test_mefi_client.py            # MefiClient: pagination, retry, rate limit (respx mocks)
│   ├── test_mefi_repository.py        # Bulk upsert, history detection (mock session)
│   └── test_sync_mefi_leads.py        # Task: lock, backfill detection, chain trigger
└── integration/
    └── test_mefi_etl.py               # Full flow against test DB (no real MEFI API)
```

---

## Research Question Answers

### Q1: SQLAlchemy 2.x Async Bulk Upsert Pattern

**Pattern:** Use `sqlalchemy.dialects.postgresql.insert()` (not the ORM `insert()`) with a list of dicts passed to `.values()`, then chain `.on_conflict_do_update()`. Execute via `await session.execute(stmt)`. [VERIFIED: docs.sqlalchemy.org/en/20/orm/queryguide/dml.html]

```python
# Source: docs.sqlalchemy.org/en/20/orm/queryguide/dml.html#orm-queryguide-upsert
from sqlalchemy.dialects.postgresql import insert as pg_insert

async def bulk_upsert_leads(
    session: AsyncSession,
    rows: list[dict],  # list of column-value dicts
) -> int:
    if not rows:
        return 0
    stmt = pg_insert(RawMefiLead).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["tenant_id", "external_id"],   # unique constraint columns
        set_={
            "status_id": stmt.excluded.status_id,
            "status_name": stmt.excluded.status_name,
            "lifecycle": stmt.excluded.lifecycle,
            "assigned_to_id": stmt.excluded.assigned_to_id,
            "showroom": stmt.excluded.showroom,
            "offer_sent_flag": stmt.excluded.offer_sent_flag,
            "utm_source": stmt.excluded.utm_source,
            "utm_medium": stmt.excluded.utm_medium,
            "utm_campaign": stmt.excluded.utm_campaign,
            "utm_content": stmt.excluded.utm_content,
            "estimated_value": stmt.excluded.estimated_value,
            "last_contact_at": stmt.excluded.last_contact_at,
            "status_changed_at": stmt.excluded.status_changed_at,
            "raw_payload": stmt.excluded.raw_payload,
            "synced_at": stmt.excluded.synced_at,
        }
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount
```

**Key points:**
- `stmt.excluded.column_name` references the incoming (attempted INSERT) values — this is PostgreSQL's `EXCLUDED` pseudo-table syntax. [VERIFIED: docs.sqlalchemy.org]
- The `index_elements` list must match an existing UNIQUE constraint (or index) on the table. The migration must create `UNIQUE(tenant_id, external_id)`. [VERIFIED: docs.sqlalchemy.org]
- Pass all rows as a single `.values(rows)` call — SQLAlchemy batches these into one `INSERT ... VALUES (...), (...), ...` statement via asyncpg. For 2,000 leads this is one round trip, not 2,000 round trips. [ASSUMED — inferred from SQLAlchemy batch insert behavior]
- `do NOT` use `populate_existing=True` execution option for this pure-SQL path (it's for ORM session identity map only).
- History change detection (MEFI-06) requires a SELECT before this UPSERT — see Q7.

**Note on `created_at_source` immutability:** Add `created_at_source` to the UPSERT `set_` only if you want to allow MEFI to correct creation timestamps. For audit integrity, exclude it so the first-synced value is preserved. [ASSUMED]

---

### Q2: MEFI Pagination + Incremental Sync Pattern

**The page-shift problem:** If MEFI has 543 leads (page 28 total at 20/page), and a new lead arrives mid-fetch, page 27 shifts — a lead from page 26 now lands on page 27, and the fetcher never sees it.

**D-10 solution:** Record `sync_start_at = datetime.now(UTC)` at the very start of the task. Pass `date_to=sync_start_at.date().isoformat()` to every page request. Leads created or status-changed AFTER `sync_start_at` are excluded from this run — they'll appear in the next nightly sync. [VERIFIED: project CONTEXT.md D-10; pattern confirmed in leads-read.md implementation guidance]

```python
# Source: docs/api-references/mefi/leads-read.md + D-10 from CONTEXT.md
async def fetch_leads_incremental(
    client: MefiClient,
    date_from: date,
    date_to: date,  # fixed at task start — prevents page shift
) -> AsyncIterator[dict]:
    page = 1
    while True:
        response = await client.post_search(
            filters={
                "lifecycle": ["active", "lost", "junk"],
                "date_from": date_from.isoformat(),
                "date_to": date_to.isoformat(),
                "date_field": "status_changed_at",
            },
            page=page,
            per_page=100,
            sort="status_changed_at",
            order="asc",
        )
        for lead in response["data"]:
            yield lead
        if page >= response["meta"]["total_pages"]:
            break
        page += 1
```

**Critical detail:** The MEFI API sorts results server-side. Use `sort="status_changed_at", order="asc"` for incremental. New leads added during pagination will be beyond `date_to` and thus absent from the result set — the fixed upper bound ensures stable total_pages for the duration of this fetch. [VERIFIED: leads-read.md]

**Backfill windowing:** For month-by-month backfill, `date_from = first_day_of_month`, `date_to = last_day_of_month`. Use `created_at` as the `date_field` for backfill (not `status_changed_at`). [ASSUMED — status_changed_at could miss very old leads never status-changed in the window; created_at is the correct field for historical backfill]

```python
# Month arithmetic for backfill
from calendar import monthrange

def month_window(year: int, month: int) -> tuple[date, date]:
    first = date(year, month, 1)
    last = date(year, month, monthrange(year, month)[1])
    return first, last
```

---

### Q3: Celery Chain + Autoretry for 429

**Retry-After handling pattern:** [VERIFIED: docs.celeryq.dev/en/stable/userguide/tasks.html]

```python
# Source: docs.celeryq.dev/en/stable/userguide/tasks.html + ines-panker.com article
from celery import shared_task
import asyncio
import httpx
from app.tasks.celery_app import celery_app

class RateLimitError(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = retry_after

@celery_app.task(
    bind=True,
    autoretry_for=(httpx.TimeoutException, httpx.NetworkError),
    max_retries=3,
    default_retry_delay=60,
)
def sync_mefi_leads(self, tenant_id: str) -> dict:
    try:
        result = asyncio.run(_sync_async(tenant_id))
        return result
    except RateLimitError as exc:
        # Honor Retry-After header: override countdown with server's value
        raise self.retry(countdown=exc.retry_after)

# In MefiClient:
async def _request(self, method: str, url: str, **kwargs) -> dict:
    response = await self._client.request(method, url, **kwargs)
    if response.status_code == 429:
        retry_after = int(response.headers.get("Retry-After", 60))
        raise RateLimitError(retry_after=retry_after)
    response.raise_for_status()
    return response.json()
```

**`bind=True` is mandatory** for `self.retry()` access. [VERIFIED: docs.celeryq.dev]

**Chain definition:** The chain is defined in the Celery Beat schedule (redbeat). Each task in the chain calls `chain(next_task.si(), ...)` — use `.si()` (signature immutable) rather than `.s()` to prevent the previous task's return value from being passed as an argument to the next task. [ASSUMED — standard Celery chain pattern; `.si()` is the correct call for no-argument passthrough]

```python
# Source: Celery docs — canvas primitives
from celery import chain

daily_pipeline = chain(
    sync_mefi_leads.si(tenant_id=SOFA_BELLE_TENANT_ID),
    calculate_metrics.si(tenant_id=SOFA_BELLE_TENANT_ID),   # Phase 3 stub
    detect_anomalies.si(tenant_id=SOFA_BELLE_TENANT_ID),    # Phase 4 stub
    generate_insights.si(tenant_id=SOFA_BELLE_TENANT_ID),   # Phase 5 stub
)
```

**Chain failure propagation:** If `sync_mefi_leads` raises an unhandled exception after all retries, Celery records the failure and the downstream tasks (metrics, anomaly, insights) do NOT execute — the chain is halted. This satisfies PIPE-02. [VERIFIED: Celery documentation on chain exception semantics]

---

### Q4: Redis Distributed Lock Pattern

**Pattern using `redis.asyncio` (already in pyproject.toml as `redis>=5`):** [VERIFIED: redis.readthedocs.io asyncio examples]

```python
# Source: redis.readthedocs.io/en/stable/examples/asyncio_examples.html
import redis.asyncio as aioredis
from app.core.config import settings

LOCK_TTL_SECONDS = 60 * 60 * 10  # 10 hours — exceeds visibility_timeout

async def acquire_sync_lock(tenant_id: str) -> bool:
    """Returns True if lock acquired, False if already locked."""
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        key = f"sync:mefi:{tenant_id}"
        # SET key value NX EX ttl — atomic: only sets if key does not exist
        acquired = await r.set(key, "1", nx=True, ex=LOCK_TTL_SECONDS)
        return acquired is not None
    finally:
        await r.aclose()

async def release_sync_lock(tenant_id: str) -> None:
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        await r.delete(f"sync:mefi:{tenant_id}")
    finally:
        await r.aclose()
```

**Important detail:** The lock TTL must exceed the total possible task duration. Phase 1 set `visibility_timeout = 32400` (9h). Set lock TTL to 10h to give a margin. If the task crashes without releasing the lock, TTL expiry ensures the next nightly run can proceed. [ASSUMED — standard distributed lock safety pattern]

**Pattern in async Celery task:** Since Celery tasks run synchronously (`asyncio.run()` wraps the async work), the lock acquisition and release must also happen inside `asyncio.run()` — or use `asyncio.run(acquire_lock())` before the main `asyncio.run(_sync_async())`. The simpler approach is to do all async work (lock + sync + unlock) in a single `asyncio.run()` call via a wrapper coroutine. [ASSUMED]

---

### Q5: Alembic UPDATE Migration (funnel_config seed)

**Pattern for data migration:** [VERIFIED: alembic.sqlalchemy.org/en/latest/tutorial.html — op.execute with sa.text()]

```python
# Source: alembic docs — op.execute() for data migrations
# backend/alembic/versions/003_mefi_schema.py

import json
import sqlalchemy as sa
from alembic import op

FUNNEL_CONFIG = {
    "funnel_stages": {
        "visit": [17],
        "offer": [3],
        "contract": [1]
    },
    "offer_sent_flag_field": "form-cf-20",
    "source_categories": {
        "mail_fb_ig": [2, 11],
        "telefon": [10],
        "whatsapp": [9],
        "site": [6],
        "designer": [],
        "alte": [3, 4, 5, 7, 12, 13]
    },
    "lifecycle_filter": ["active", "lost", "junk"],
    "showroom_field": "form-cf-14",
    "junk_statuses": [23]
}

def upgrade() -> None:
    # ... CREATE TABLE statements ...

    # Idempotent UPDATE — safe to run multiple times
    op.execute(
        sa.text("""
            UPDATE tenants
            SET funnel_config = :config::jsonb
            WHERE slug = 'sofa-belle'
              AND funnel_config IS NULL
        """).bindparams(config=json.dumps(FUNNEL_CONFIG))
    )
```

**Idempotency guard:** Add `AND funnel_config IS NULL` to the WHERE clause so running `alembic upgrade head` twice doesn't overwrite manually edited configs. [VERIFIED: standard Alembic data migration pattern from project's own 002_seed_sofabelle.py]

**Note:** The `tenants` table column `funnel_config JSONB` must be added in this same migration if not already present. Phase 1 migration 001 created `tenants` but may not have included this column — verify by checking the migration. [ASSUMED — Phase 1 SUMMARY.md mentions `funnel_config` but 001 may or may not have added the column; research at plan time by reading the actual migration file]

---

### Q6: PostgreSQL Views in Alembic

**Pattern:** Use `op.execute()` with `CREATE OR REPLACE VIEW` in upgrade and `DROP VIEW IF EXISTS` in downgrade. [VERIFIED: alembic.sqlalchemy.org/en/latest/cookbook.html]

```python
# Source: alembic.sqlalchemy.org/en/latest/cookbook.html

V_ACTIVE = """
CREATE OR REPLACE VIEW v_mefi_leads_active AS
SELECT
    r.*,
    r.created_at AT TIME ZONE 'Europe/Bucharest' AS created_at_local,
    r.status_changed_at AT TIME ZONE 'Europe/Bucharest' AS status_changed_at_local,
    -- "ever reached" funnel stages (computed from current status_id)
    -- NOTE: MEFI has no history endpoint — "ever reached" requires mefi_lead_history
    -- For initial phase: derive from current status only; update logic in Phase 3 metrics
    (r.status_id = 17 OR r.status_id IN (3, 1)) AS reached_visit,
    (r.status_id = 3 OR r.offer_sent_flag = true OR r.status_id = 1) AS reached_offer,
    (r.status_id = 1) AS reached_contract
FROM raw_mefi_leads r
WHERE r.lifecycle IN ('active', 'lost')
"""

V_JUNK = """
CREATE OR REPLACE VIEW v_mefi_leads_junk AS
SELECT *
FROM raw_mefi_leads
WHERE lifecycle = 'junk'
"""

def upgrade() -> None:
    # ... table creation ...
    op.execute(V_ACTIVE)
    op.execute(V_JUNK)

def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_mefi_leads_active")
    op.execute("DROP VIEW IF EXISTS v_mefi_leads_junk")
    # ... drop tables ...
```

**"Ever reached" in views:** The view can only express "currently is" logic from `status_id`. True "ever reached" requires `mefi_lead_history` (has the lead EVER been in status 17?). The view should expose a `reached_visit` boolean computed from current status — Phase 3 metrics can query `mefi_lead_history` for the full "ever reached" computation. Flag this open question for Phase 3. [VERIFIED: MEFI API has no history endpoint — confirmed in leads-read.md; ASSUMED for the "use history table" approach]

**Metric service access:** Downstream Phase 3 services query views via raw SQL using `text()` or via `select()` on a mapped table object — NOT through ORM models (views can be mapped but it's extra complexity). The recommended pattern for views is `await session.execute(text("SELECT ... FROM v_mefi_leads_active WHERE tenant_id = :tid AND ..."))`. [ASSUMED]

---

### Q7: Lead History Change Detection

**Challenge:** MEFI API returns only current state — no status history endpoint. Between nightly syncs, a lead could go from status 16 → 17 → 3 (missed intermediate status). We capture what we CAN: the status at last sync vs. status now.

**Pattern:** SELECT-before-UPSERT for change detection, batched as a single IN query: [ASSUMED — this is the standard pattern for CDC (change data capture) without native history support]

```python
# Pattern: batch SELECT before UPSERT
async def detect_and_record_changes(
    session: AsyncSession,
    incoming_rows: list[dict],
    tenant_id: UUID,
) -> list[dict]:  # returns history rows to insert
    external_ids = [r["external_id"] for r in incoming_rows]

    # Single query: fetch current stored status for all incoming leads
    result = await session.execute(
        select(RawMefiLead.external_id, RawMefiLead.status_id, RawMefiLead.status_name)
        .where(
            RawMefiLead.tenant_id == tenant_id,
            RawMefiLead.external_id.in_(external_ids),
        )
    )
    stored = {row.external_id: (row.status_id, row.status_name) for row in result}

    history_rows = []
    now = datetime.now(UTC)
    for row in incoming_rows:
        ext_id = row["external_id"]
        old = stored.get(ext_id)
        if old and old[0] != row["status_id"]:
            history_rows.append({
                "tenant_id": tenant_id,
                "lead_external_id": ext_id,
                "changed_at": now,
                "from_status_id": old[0],
                "from_status_name": old[1],
                "to_status_id": row["status_id"],
                "to_status_name": row["status_name"],
                "changed_by": None,  # MEFI API doesn't expose who changed it
            })

    return history_rows
```

**Caveat (MEFI-06 is "best-effort"):** If a lead cycles through statuses within a single day (17 → 3 → 17 again), only the net change (17 → 17 = no change, or whatever the state is at sync time) will be recorded. REQUIREMENTS.md explicitly labels this "best-effort". [VERIFIED: MEFI-06 text says "best-effort"; VERIFIED: leads-read.md confirms no history endpoint]

---

### Q8: MefiClient BaseIntegration Contract

**From `docs/INTEGRATIONS.md`** (canonical reference): [VERIFIED: docs/INTEGRATIONS.md in project codebase]

```python
# Contract — must implement these 3 methods:
class MefiClient(BaseIntegration):
    source_name = "mefi"

    async def authenticate(self, credentials: dict) -> bool:
        # For MEFI: validate API key by hitting /leads/search with minimal params
        # Returns True if 200, False if 401/403
        ...

    async def sync(
        self,
        tenant_id: UUID,
        since: datetime | None = None,
    ) -> SyncResult:
        # Full sync logic lives in Celery task; this method is the service-layer entry point
        # For MEFI: since=None → backfill; since=last_sync_at → incremental
        ...

    async def health_check(self) -> bool:
        # Quick liveness check: POST /leads/search with empty body → check total > 0
        ...
```

**httpx.AsyncClient lifecycle:** Create one `httpx.AsyncClient` per `MefiClient` instance, set `base_url`, `headers` (with Authorization), and `timeout`. Use `async with` or explicit `await client.aclose()`. The Celery task creates `MefiClient()` once per task invocation — no connection pooling needed across tasks. [VERIFIED: httpx docs; ASSUMED for per-task client pattern]

```python
class MefiClient(BaseIntegration):
    BASE_URL = "https://bellesofa.meficrm.com/api/v1"

    def __init__(self, api_key: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(30.0),
        )

    async def __aenter__(self) -> "MefiClient":
        return self

    async def __aexit__(self, *args) -> None:
        await self._client.aclose()
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Bulk DB upsert | Row-by-row INSERT in a loop | `postgresql.insert().values(rows).on_conflict_do_update()` | Single SQL statement; 100x faster; atomic |
| HTTP retry logic | Manual retry loop with sleep | Celery `autoretry_for` + `self.retry(countdown=N)` | Already configured; respects Celery broker |
| Distributed lock | File locks, DB row locks | `redis.asyncio` SET NX EX | TTL-based auto-expiry; survives worker crashes |
| Date arithmetic for months | Custom calendar math | `calendar.monthrange()` for last day; `dateutil.relativedelta` for month offset | Edge cases: Feb 28/29, Dec→Jan |
| Custom field parsing | Ad-hoc JSON walking | `get_custom_field_value(fields, field_id)` helper function | Defensive; handles absent/null field |
| Rate limit detection | Manual sleep timers | Read `X-RateLimit-Remaining` header; raise on 429 with `Retry-After` | Server-authoritative; no over-sleeping |
| Pagination | Cursor-based custom | `page` + `total_pages` from MEFI `meta` field | API already provides this |

**Key insight:** The biggest footgun in this phase is bulk insert performance. Every ORM `session.add(lead)` call followed by `session.flush()` is one SQL round trip. With 2,000 leads, that's 2,000 round trips vs. 1 for the bulk upsert. Use the Core-style `pg_insert().values(list_of_dicts)` pattern.

---

## Common Pitfalls

### Pitfall 1: Page Shift During Long Pagination Runs
**What goes wrong:** Fetching without a fixed `date_to` upper bound. A lead updated between page 5 and page 6 fetch may appear on both pages, or slip between pages.
**Why it happens:** The server re-orders the result set between requests if data changes.
**How to avoid:** Record `sync_start_at = datetime.now(UTC)` BEFORE first API call; pass as `date_to` to ALL pagination calls in this sync run. Leads updated after `sync_start_at` land in the NEXT sync.
**Warning signs:** `records_synced` count is inconsistent across re-runs on the same day.

### Pitfall 2: Duplicate Concurrent Sync Runs
**What goes wrong:** Beat triggers a new run while the previous is still paginating. Both runs write to the same rows — harmless for the UPSERT itself, but double the API calls and confuses `SyncRun` records.
**Why it happens:** Task takes > 5 minutes; beat fires again before completion.
**How to avoid:** Redis lock `SET NX EX` at task start. If lock exists, log and return immediately (NOOP).
**Warning signs:** Two `SyncRun` rows with `status=running` simultaneously for the same tenant.

### Pitfall 3: UTC vs. Europe/Bucharest Date Confusion
**What goes wrong:** MEFI timestamps are UTC. A lead created at `2026-01-15T23:30:00Z` is `2026-01-16T01:30:00 EET`. Grouping by UTC date gives wrong daily counts.
**Why it happens:** PostgreSQL stores TIMESTAMPTZ correctly but `GROUP BY DATE(timestamp)` truncates in UTC.
**How to avoid:** All views use `AT TIME ZONE 'Europe/Bucharest'` for date grouping. All Celery cron runs target Europe/Bucharest timezone (already configured in Phase 1).
**Warning signs:** Daily totals are off by a few leads, particularly around midnight EET.

### Pitfall 4: Async Context in Celery Prefork Workers
**What goes wrong:** `asyncio.run()` called from a Celery task that's already running inside an event loop (e.g., if Celery is configured with `CELERYD_POOL=solo` or gevent).
**Why it happens:** `asyncio.run()` creates a new event loop; calling it from within an existing event loop raises `RuntimeError: This event loop is already running`.
**How to avoid:** The prefork pool (default) runs tasks synchronously — each worker is a separate OS process with no pre-existing event loop. `asyncio.run()` is safe in prefork workers. Never use `gevent` pool with this codebase.
**Warning signs:** `RuntimeError: This event loop is already running` in worker logs.

### Pitfall 5: Missing tenant_id in Direct SQL Bulk Inserts
**What goes wrong:** The `do_orm_execute` event listener only fires for ORM SELECT queries. Core-style `session.execute(pg_insert(...).values(...))` bypasses the tenant filter listener.
**Why it happens:** The tenant isolation seam targets ORM operations. Bulk inserts use Core API.
**How to avoid:** Every dict in the `rows` list passed to `.values()` MUST include `tenant_id` explicitly. Never construct the batch without it. The `MefiRepository` should accept `tenant_id: UUID` and inject it into every row dict.
**Warning signs:** Rows appear in `raw_mefi_leads` without `tenant_id`, or UUIDs are `null`.

### Pitfall 6: MEFI custom_fields Array is Sparse/Absent
**What goes wrong:** `get_custom_field_value(lead["custom_fields"], 14)` raises `KeyError` or `TypeError` when `custom_fields` is `null` or the field is absent for a lead.
**Why it happens:** Not all leads have all custom fields filled. Showroom field may be absent for new web leads.
**How to avoid:** Defensive helper:
```python
def get_cf(fields: list[dict] | None, field_id: int) -> Any:
    if not fields:
        return None
    for f in fields:
        if f.get("field_id") == field_id:
            return f.get("value")
    return None
```
**Warning signs:** `500 Internal Server Error` or `NullPointerError` during batch processing.

### Pitfall 7: Rate Limit Confusion — 50/min vs 600/min
**What goes wrong:** REQUIREMENTS.md says "max 50 req/min" (likely a stale value from before API docs arrived). Actual MEFI API documentation (received 2026-05-18) specifies 600/min for `lrd_*` read keys.
**Why it happens:** Requirements were written before API documentation was received.
**How to avoid:** Use 600/min as the authoritative limit (from official MEFI API docs). At 100 leads/page, a full 2,000-lead sync is 20 API calls — negligible. Backfill (60 pages) also well under 600/min.
**Warning signs:** Over-throttling (adding unnecessary sleep) causing backfill to run for hours unnecessarily.

### Pitfall 8: asyncpg Connection Across Fork Boundary
**What goes wrong:** If `AsyncSessionLocal` is imported at module level in `sync_mefi_leads.py`, the asyncpg pool is inherited by Celery child workers after fork.
**Why it happens:** Fork copies parent's file descriptors. asyncpg connections cannot be shared.
**How to avoid:** Import `AsyncSessionLocal` ONLY inside the `asyncio.run()` wrapper function (inside the task body), never at module level. Phase 1 already wires `init_worker_process` to handle this — but module-level session imports in task files would bypass it.
**Warning signs:** `asyncpg.InterfaceError: connection is closed` or SSL errors under load.

### Pitfall 9: Alembic Autogenerate Ignores Views
**What goes wrong:** Running `alembic revision --autogenerate` on future migrations will produce a migration that includes `DROP TABLE raw_mefi_leads` if the model import is missing, or will NOT include the view DDL (autogenerate doesn't track views).
**Why it happens:** Alembic autogenerate compares ORM metadata vs database schema. Views are not in ORM metadata.
**How to avoid:** Always create view migrations manually with `op.execute()`. Import all new SQLAlchemy models in `alembic/env.py` before running autogenerate.
**Warning signs:** Migration says `DROP TABLE` when you only wanted `ALTER TABLE`.

---

## Code Examples

### Full Sync Task Skeleton
```python
# Source: CONTEXT.md patterns + INTEGRATIONS.md + Phase 1 conventions
# backend/app/tasks/etl/sync_mefi_leads.py
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID

from app.tasks.celery_app import celery_app


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    max_retries=3,
    default_retry_delay=60,
    name="tasks.etl.sync_mefi_leads",
)
def sync_mefi_leads(self, tenant_id: str) -> dict:
    """Nightly MEFI lead sync. Idempotent — safe to retry."""
    try:
        return asyncio.run(_sync_async(UUID(tenant_id)))
    except RateLimitError as exc:
        raise self.retry(countdown=exc.retry_after)


async def _sync_async(tenant_id: UUID) -> dict:
    from app.core.config import settings
    from app.core.tenancy import set_tenant_id
    from app.db.session import AsyncSessionLocal
    from app.services.integrations.mefi import MefiClient
    from app.services.repositories.mefi_repository import MefiRepository

    set_tenant_id(tenant_id)  # required before any ORM SELECT
    sync_start_at = datetime.now(UTC)

    # ... acquire lock, check empty, paginate, upsert, update SyncRun, release lock
```

### MefiClient Rate Limit Check
```python
# Source: leads-read.md rate limit section
async def _request_with_rate_check(self, ...) -> dict:
    response = await self._client.request(...)
    remaining = int(response.headers.get("X-RateLimit-Remaining", 600))
    if remaining < 10:
        import asyncio
        await asyncio.sleep(1)  # gentle back-off before limit exhausted
    if response.status_code == 429:
        retry_after = int(response.headers.get("Retry-After", 60))
        raise RateLimitError(retry_after=retry_after)
    response.raise_for_status()
    return response.json()
```

### Alembic Migration 003 Skeleton
```python
# Source: 002_seed_sofabelle.py pattern + alembic cookbook
"""Create MEFI tables, conformed views, seed funnel_config.

Revision ID: 003
Revises: 002
"""
from __future__ import annotations
import json
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "003"
down_revision = "002"

FUNNEL_CONFIG = { ... }  # from D-08 in CONTEXT.md

def upgrade() -> None:
    # 1. Add funnel_config column to tenants (if not already there)
    op.add_column("tenants", sa.Column("funnel_config", JSONB, nullable=True))

    # 2. Create raw_mefi_leads table
    op.create_table("raw_mefi_leads", ...)

    # 3. Create mefi_lead_history table
    op.create_table("mefi_lead_history", ...)

    # 4. Create mefi_salespeople table
    op.create_table("mefi_salespeople", ...)

    # 5. Create indexes
    op.create_index(...)

    # 6. Create views
    op.execute("CREATE OR REPLACE VIEW v_mefi_leads_active AS ...")
    op.execute("CREATE OR REPLACE VIEW v_mefi_leads_junk AS ...")

    # 7. Seed funnel_config (idempotent)
    op.execute(
        sa.text("""
            UPDATE tenants SET funnel_config = :cfg::jsonb
            WHERE slug = 'sofa-belle' AND funnel_config IS NULL
        """).bindparams(cfg=json.dumps(FUNNEL_CONFIG))
    )

def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_mefi_leads_junk")
    op.execute("DROP VIEW IF EXISTS v_mefi_leads_active")
    op.drop_table("mefi_salespeople")
    op.drop_table("mefi_lead_history")
    op.drop_table("raw_mefi_leads")
    op.drop_column("tenants", "funnel_config")
```

---

## SQLAlchemy Model Schema (raw_mefi_leads)

The model must match the SPEC.md schema enriched with the custom field columns from DATA-02 and CONTEXT.md:

```python
# backend/app/models/mefi.py
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Boolean, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TenantScopedMixin, TIMESTAMPTZ

class RawMefiLead(Base, TenantScopedMixin):
    __tablename__ = "raw_mefi_leads"

    external_id: Mapped[str] = mapped_column(Text, nullable=False)

    # MEFI standard fields
    status_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    lifecycle: Mapped[str] = mapped_column(Text, nullable=False)  # active/lost/junk
    assigned_to_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assigned_to_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    priority: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps from MEFI (UTC, stored as TIMESTAMPTZ)
    created_at_source: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)
    last_contact_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)
    status_changed_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)

    # Extracted custom fields (DATA-02)
    showroom: Mapped[str | None] = mapped_column(Text, nullable=True)  # form-cf-14
    offer_sent_flag: Mapped[bool | None] = mapped_column(Boolean, nullable=True)  # form-cf-20
    utm_source: Mapped[str | None] = mapped_column(Text, nullable=True)    # form-cf-38
    utm_campaign: Mapped[str | None] = mapped_column(Text, nullable=True)  # form-cf-39
    utm_content: Mapped[str | None] = mapped_column(Text, nullable=True)   # form-cf-40
    utm_medium: Mapped[str | None] = mapped_column(Text, nullable=True)    # form-cf-41

    # Raw preservation
    custom_fields_raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    synced_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)
```

**Unique constraint** must be added in the migration: `UNIQUE(tenant_id, external_id)` — this is the UPSERT conflict target. [VERIFIED: MEFI leads-read.md idempotency section]

---

## Dependencies to Add

### Runtime (pyproject.toml — no changes needed)
All runtime dependencies are already present from Phase 1. No new packages to add.

### Dev (pyproject.toml — add to [project.optional-dependencies].dev)
```toml
"respx>=0.21,<1",  # httpx mock for unit tests — not currently in pyproject.toml
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Row-by-row ORM insert (session.add) | Core-style bulk insert with postgresql.insert().values(list) | SQLAlchemy 2.0 (2023) | 100x+ throughput for batch inserts |
| aioredis (separate package) | redis.asyncio (built into redis-py >= 4.2) | redis-py 4.2.0 (2022) | aioredis is deprecated; redis.asyncio is the standard |
| Celery ALWAYS_EAGER for testing | pytest-celery or task.apply() in tests | Celery 5.x | ALWAYS_EAGER removed in Celery 5 |
| Alembic autogenerate for views | Manual op.execute() with CREATE OR REPLACE VIEW | All versions | Autogenerate never tracked views |

**Deprecated/outdated:**
- `aioredis`: deprecated since redis-py 4.2 added `redis.asyncio`. Do NOT import `aioredis` — use `import redis.asyncio as aioredis`.
- `session.bulk_save_objects()`: removed in SQLAlchemy 2.0. Use Core-style `session.execute(insert().values(...))` instead.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | All backend code | ✗ (system is 3.9.6) | 3.9.6 | Docker container uses 3.11+ |
| PostgreSQL 16 | Migrations, UPSERT | ✗ (not running locally) | — | Docker compose |
| Redis 7 | Lock, Celery broker | ✗ (not running locally) | — | Docker compose |
| Docker | Full stack | ✓ | 29.4.1 | — |

**Note on Python version:** System Python 3.9.6 is below the project's 3.11+ requirement. All code must run inside the Docker container (`python:3.11` or higher base image). Local development uses `uv venv` with a 3.11+ interpreter. `from __future__ import annotations` is mandatory on all files per CLAUDE.md.

**Missing dependencies with no fallback:**
- None — Docker provides all runtime dependencies.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio 1.2.0 |
| Config file | `backend/pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `cd backend && pytest tests/unit/test_mefi_client.py tests/unit/test_mefi_repository.py tests/unit/test_sync_mefi_leads.py -x` |
| Full suite command | `cd backend && pytest --cov=app --cov-report=html` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MEFI-01 | MefiClient makes POST /leads/search with Bearer auth | unit | `pytest tests/unit/test_mefi_client.py::test_search_includes_auth_header -x` | ❌ Wave 0 |
| MEFI-02 | UPSERT on (tenant_id, external_id) — duplicate call is idempotent | unit | `pytest tests/unit/test_mefi_repository.py::test_bulk_upsert_idempotent -x` | ❌ Wave 0 |
| MEFI-03 | date_to is fixed at sync_start_at, not re-evaluated per page | unit | `pytest tests/unit/test_mefi_client.py::test_pagination_date_to_fixed -x` | ❌ Wave 0 |
| MEFI-05 | View v_mefi_leads_active includes reached_visit/offer/contract columns | integration | `pytest tests/integration/test_mefi_etl.py::test_view_funnel_columns -x` | ❌ Wave 0 |
| MEFI-06 | Status change between syncs emits mefi_lead_history row | unit | `pytest tests/unit/test_mefi_repository.py::test_history_emitted_on_status_change -x` | ❌ Wave 0 |
| MEFI-08 | SyncRun row written with status=running on start, status=success on complete | unit | `pytest tests/unit/test_sync_mefi_leads.py::test_sync_run_lifecycle -x` | ❌ Wave 0 |
| MEFI-09 | Liveness probe with no date filter: total=0 → alert raised | unit | `pytest tests/unit/test_mefi_client.py::test_liveness_total_zero_raises -x` | ❌ Wave 0 |
| MEFI-10 | 429 response triggers self.retry with countdown=Retry-After value | unit | `pytest tests/unit/test_mefi_client.py::test_429_respects_retry_after -x` | ❌ Wave 0 |
| MEFI-11 | Lock acquired at task start; second call returns immediately (NOOP) | unit | `pytest tests/unit/test_sync_mefi_leads.py::test_redis_lock_prevents_duplicate -x` | ❌ Wave 0 |
| MEFI-12 | Backfill task uses backfill queue, chunks 12 months | unit | `pytest tests/unit/test_sync_mefi_leads.py::test_backfill_month_windows -x` | ❌ Wave 0 |
| DATA-01 | Views exist after migration 003 | integration | `pytest tests/integration/test_migrations.py::test_003_views_exist -x` | ❌ Wave 0 |
| DATA-02 | Showroom and UTM columns populated from custom_fields | unit | `pytest tests/unit/test_mefi_repository.py::test_custom_field_extraction -x` | ❌ Wave 0 |
| DATA-03 | View columns include AT TIME ZONE Bucharest variants | integration | `pytest tests/integration/test_mefi_etl.py::test_view_local_timestamps -x` | ❌ Wave 0 |
| PIPE-01 | Beat schedule triggers chain at 04:00 EET | unit | `pytest tests/unit/test_sync_mefi_leads.py::test_beat_schedule_configured -x` | ❌ Wave 0 |
| PIPE-02 | Exception in sync_mefi_leads prevents metrics task from running | unit | `pytest tests/unit/test_sync_mefi_leads.py::test_chain_halts_on_failure -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/unit/ -x -q`
- **Per wave merge:** `pytest --cov=app/services/integrations --cov=app/tasks/etl --cov-report=term-missing`
- **Phase gate:** Full suite green (≥70% coverage on new files) before `/gsd:verify-work`

### Wave 0 Gaps (must create before implementation)
- [ ] `tests/unit/test_mefi_client.py` — covers MEFI-01, MEFI-03, MEFI-09, MEFI-10
- [ ] `tests/unit/test_mefi_repository.py` — covers MEFI-02, MEFI-06, DATA-02
- [ ] `tests/unit/test_sync_mefi_leads.py` — covers MEFI-08, MEFI-11, MEFI-12, PIPE-01, PIPE-02
- [ ] `tests/integration/test_mefi_etl.py` — covers MEFI-05, DATA-01, DATA-03
- [ ] `tests/factories/mefi_factory.py` — LeadFactory using factory-boy for test data
- [ ] `respx` added to `[project.optional-dependencies].dev` in pyproject.toml

---

## Security Domain

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | — (ETL uses static API key, not user auth) |
| V3 Session Management | No | — |
| V4 Access Control | Yes | Tenant isolation: every bulk insert row must include explicit tenant_id |
| V5 Input Validation | Yes | Pydantic schemas validate MEFI API response before processing |
| V6 Cryptography | Partial | MEFI API key stored as env var (plaintext in .env), not Fernet-encrypted; API key is read-only and per-tenant; low risk |

### Known Threat Patterns for ETL Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Missing tenant_id in bulk insert | Information Disclosure | Explicit tenant_id in every row dict; MefiRepository accepts tenant_id param |
| MEFI API key leaked via logs | Information Disclosure | structlog config never logs Authorization header; CLAUDE.md: no secrets in code |
| Raw payload JSONB injection | Tampering | Pydantic schema validates response structure before storing in raw_payload |
| Duplicate sync run data corruption | Tampering | Redis distributed lock prevents concurrent runs |
| MEFI response with malformed data causing task crash | DoS | autoretry + max_retries=3; SyncRun records failure; chain halts gracefully |

---

## Open Questions

1. **funnel_config column: does 001_base_tables.py already include it?**
   - What we know: Phase 1 SUMMARY.md mentions Tenant model and migration 001, but doesn't explicitly list all columns.
   - What's unclear: Whether `funnel_config JSONB` was added to the `tenants` table in 001 (it was planned in SPEC.md).
   - Recommendation: Read `backend/alembic/versions/001_base_tables.py` at plan time. If column exists, migration 003 only needs to UPDATE; if absent, add `op.add_column()` before the UPDATE.

2. **"Ever reached" funnel — view expression vs. mefi_lead_history join**
   - What we know: D-09 says "ever reached"; MEFI API has no history endpoint; `mefi_lead_history` only captures inter-sync changes.
   - What's unclear: For Phase 2, should `v_mefi_leads_active.reached_visit` be `current status_id = 17` (partial) or a subquery against `mefi_lead_history`?
   - Recommendation: Implement view with current-status logic for Phase 2 (simpler, works on first sync); add history join in Phase 3 metrics calculation. Document the limitation in view comment.

3. **Backfill queue registration — is it already wired?**
   - What we know: Phase 1 SUMMARY.md mentions "backfill queue is separate from default". The `celery_app.py` currently has `include=["app.tasks"]` — the `backfill` queue name might not be explicitly declared.
   - What's unclear: Whether Celery needs explicit queue declaration or if routing by name is sufficient.
   - Recommendation: Check `celery_app.conf` for `task_routes` or `task_queues`. If absent, add `task_routes = {"tasks.etl.backfill_mefi_leads": {"queue": "backfill"}}` in Phase 2.

4. **MEFI search date filter: YYYY-MM-DD only (no time component)?**
   - What we know: `leads-read.md` shows `filters.date_from` and `date_to` as `YYYY-MM-DD` format (date, not datetime).
   - What's unclear: If last_sync_at was 03:47:22, does `date_from = "2026-05-20"` include all changes from midnight or only from 03:47?
   - Recommendation: Treat as date granularity (midnight-to-midnight). To avoid missing leads changed between the stored `last_sync_at` time and midnight, use `date_from = last_sync_at.date() - timedelta(days=1)` (1 day lookback). The UPSERT idempotency handles re-syncing already-seen leads safely.

5. **mefi_salespeople: mefi_user_id vs external_id column naming**
   - What we know: SPEC.md uses `external_id` as the MEFI-side ID convention. CONTEXT.md D-05 says "INSERT ON CONFLICT (mefi_user_id)".
   - What's unclear: Whether the conflict target column is named `external_id` (consistent with leads table) or `mefi_user_id`.
   - Recommendation: Use `external_id` for consistency with the `raw_mefi_leads` pattern. The CONTEXT.md reference to `mefi_user_id` is likely informal shorthand.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | respx is the correct httpx mock library (not `pytest-httpx` or `responses`) | Standard Stack | Wrong mock library chosen; tests fail to compile |
| A2 | `asyncio.run()` is safe in Celery prefork workers (no pre-existing event loop) | Q4 Redis Lock | RuntimeError if Celery pool is not prefork |
| A3 | All rows in `.values(list_of_dicts)` become one SQL statement (not N statements) | Q1 Bulk Upsert | Performance degraded; 2000 SQL round trips instead of 1 |
| A4 | date_from/date_to in MEFI API is date-granularity (midnight UTC, not exact time) | Q2 Pagination | Leads changed between last_sync_at time and midnight could be missed |
| A5 | CONTEXT.md "mefi_user_id" maps to column named "external_id" in mefi_salespeople | Open Question 5 | Schema naming inconsistency between tables |
| A6 | funnel_config JSONB column NOT yet in 001_base_tables.py (needs add_column in 003) | Alembic Migration | If already there: migration fails with "column already exists" |
| A7 | "ever reached" view logic uses current status_id only for Phase 2 (not history join) | Q6 Views | Phase 3 metrics may be slightly undercounting funnel stages until history is rich |
| A8 | Lock TTL of 10 hours is sufficient; task never runs longer | Q4 Redis Lock | If backfill takes > 10h, lock expires, next beat run starts concurrent sync |
| A9 | slopcheck unavailable; all packages from pyproject.toml are legitimate | Package Legitimacy | All packages are 5+ year old, widely used — risk is negligible |

---

## Sources

### Primary (HIGH confidence)
- `docs/api-references/mefi/leads-read.md` — Pagination pattern, date filters, rate limit headers, field schema
- `docs/api-references/mefi/README.md` — Auth, rate limits (600/min for lrd_*), available endpoints
- `docs/api-references/mefi/enums.md` — Sofa Belle status/source/salesperson IDs
- `docs/api-references/mefi/custom-fields.md` — form-cf-14 (showroom), form-cf-20 (offer flag), UTM fields
- `docs/INTEGRATIONS.md` — BaseIntegration contract, BaseIntegration ABC class definition
- `backend/app/db/base.py` — TenantScopedMixin interface (confirmed at read time)
- `backend/app/db/session.py` — AsyncSessionLocal, tenant context pattern (confirmed at read time)
- `backend/app/tasks/celery_app.py` — Celery app config, backfill queue (confirmed at read time)
- `backend/app/models/pipeline.py` — SyncRun model fields (confirmed at read time)
- [docs.sqlalchemy.org/en/20/orm/queryguide/dml.html](https://docs.sqlalchemy.org/en/20/orm/queryguide/dml.html) — PostgreSQL upsert with on_conflict_do_update
- [alembic.sqlalchemy.org/en/latest/cookbook.html](https://alembic.sqlalchemy.org/en/latest/cookbook.html) — CREATE VIEW in migrations via op.execute
- [docs.celeryq.dev/en/stable/userguide/tasks.html](https://docs.celeryq.dev/en/stable/userguide/tasks.html) — bind=True, self.retry, autoretry_for
- [redis.readthedocs.io/en/stable/examples/asyncio_examples.html](https://redis.readthedocs.io/en/stable/examples/asyncio_examples.html) — redis.asyncio SET NX EX pattern

### Secondary (MEDIUM confidence)
- [ines-panker.com article on resumable pagination](https://www.ines-panker.com/2026/02/24/api-resilience-resumable-pagination.html) — Retry-After + resumable pagination pattern
- PyPI `pip index versions` for: sqlalchemy (2.0.49), redis (7.0.1), httpx (0.28.1), respx (0.23.1) — version currency confirmed

---

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH — all packages already in pyproject.toml from Phase 1; PyPI versions verified
- Architecture: HIGH — MEFI API docs in-project; patterns from official SQLAlchemy/Celery/redis docs
- Pitfalls: MEDIUM — most derived from known patterns (page-shift, fork-safety documented); Pitfall 4/5 have HIGH confidence
- MEFI API behavior: HIGH — official documentation received 2026-05-18 and in project

**Research date:** 2026-05-21
**Valid until:** 2026-06-21 (MEFI API docs stable; check if MEFI adds endpoints before Phase 3)
