# Phase 6: Backend HTTP API - Research

**Researched:** 2026-05-28
**Domain:** FastAPI endpoint design, Pydantic response schemas, Redis rate limiting, read-only service layer
**Confidence:** HIGH

---

## User Constraints

No CONTEXT.md exists for Phase 6 yet — no prior discuss-phase session. All decisions below are derived from ROADMAP.md, REQUIREMENTS.md, and codebase archaeology.

---

## Summary

Phase 6 adds a thin FastAPI read layer on top of the already-complete data stack (Phases 1–5). All data is pre-computed in `daily_kpi`, `salesperson_daily_kpi`, `source_daily_kpi`, `detected_problems`, and `daily_insights`. The API tier is genuinely thin: routers call read-only service methods that query these tables, and all responses go through Pydantic schemas.

The existing codebase already has the full auth/tenancy/middleware/session pattern in place. The primary design work is defining six response schemas (Sales, Salespeople, Marketing, InsightToday, InsightHistorical, HealthData), three read-service classes, one rate-limited mutation endpoint (POST /insights/refresh), and the health/data endpoint that reads from sync_runs/pipeline_runs.

No new packages are needed. All dependencies (fastapi, sqlalchemy async, pydantic v2, redis, celery) are already installed and slopcheck-verified.

**Primary recommendation:** Follow the established `auth.py` / `health.py` router pattern exactly. Create three new router files (`dashboards.py`, `insights.py`), three read service classes (`DashboardReadService`, `InsightReadService`, `HealthReadService`), and six Pydantic response schemas. The rate-limit key for POST /insights/refresh is `rate_limit:refresh:{user_id}` in Redis with TTL=3600.

---

## Project Constraints (from CLAUDE.md)

- Async-first: all I/O via `async/await`, `httpx.AsyncClient`, SQLAlchemy 2.x async
- Type hints everywhere, Pydantic v2, `from __future__ import annotations` in every file
- Multi-tenancy: every DB query filtered by `tenant_id` — no exceptions
- No PII in logs (structlog JSON only)
- Claude API called ONLY from Celery tasks (AI-09): POST /insights/refresh MUST enqueue a Celery task, never call Claude directly
- No raw SQL without reason — SQLAlchemy ORM (but existing metric services use `text()` for complex aggregations; read-only aggregation queries in the API layer may also use ORM select statements)
- No `SELECT *` — name specific columns
- Revenue fields: NUMERIC(12,2) stored as Decimal, serialized as **decimal strings** in API responses (DATA-04)
- API layer: parse request → call service → return response; NO direct SQL in endpoint handlers
- Migraciones only through Alembic (Phase 6 adds no new tables — read-only against existing schema)

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Date-range param validation | API / Backend | — | FastAPI `Query()` with `date` type, validated before service call |
| Sales funnel data assembly | API / Backend (service) | — | Aggregates across daily_kpi + source_daily_kpi for date range |
| Salesperson leaderboard assembly | API / Backend (service) | — | Aggregates salesperson_daily_kpi for date range |
| Marketing data assembly | API / Backend (service) | — | Aggregates source_daily_kpi for date range |
| Insight payload read | API / Backend (service) | — | Direct read from daily_insights.payload_json |
| 404 on missing insight date | API / Backend | — | Service returns None → router raises HTTPException(404) |
| Refresh rate limiting | API / Backend (Redis) | — | Redis SET NX EX key per user, 3600s TTL |
| Refresh pipeline enqueue | API / Backend (Celery) | — | `.delay()` call on `sync_mefi_leads` → chain triggers |
| Data freshness stale flag | API / Backend (service) | — | Read last sync_runs row, compare now vs last completed_at |
| JWT auth enforcement | API / Backend (middleware) | — | Existing `StructlogContextMiddleware` sets tenant; auth guard needed per endpoint |
| Decimal serialization as string | API / Backend (Pydantic) | — | Custom Pydantic serializer on Decimal fields |
| OpenAPI schema correctness | API / Backend (FastAPI) | — | response_model= on every endpoint |

---

## Standard Stack

### Core (already installed)
| Library | Installed Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | 0.136.1 | HTTP router, OpenAPI generation, dependency injection | Project standard [VERIFIED: pyproject.toml] |
| sqlalchemy[asyncio] | 2.0.49 | Async ORM, select() builders | Project standard [VERIFIED: pyproject.toml] |
| pydantic v2 | 2.13.4 | Response schema validation, Decimal handling | Project standard [VERIFIED: pyproject.toml] |
| redis | 7.4.0 | Rate limit key storage (SET NX EX) | Already used for Celery broker [VERIFIED: pyproject.toml] |
| structlog | 25.5.0 | JSON structured logging | Project standard [VERIFIED: pyproject.toml] |
| celery | 5.6.3 | Task enqueueing for refresh endpoint | Already wired [VERIFIED: pyproject.toml] |

### No New Packages Required
Phase 6 uses only packages already in `pyproject.toml`. No installation step needed.

---

## Package Legitimacy Audit

Phase 6 installs **no new packages**. All packages are already installed and previously validated.

| Package | Registry | Age | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|
| fastapi | PyPI | 6+ yrs | [OK] | Approved — already installed |
| sqlalchemy | PyPI | 15+ yrs | [OK] | Approved — already installed |
| pydantic | PyPI | 8+ yrs | [OK] | Approved — already installed |
| redis | PyPI | 10+ yrs | [OK] | Approved — already installed |
| structlog | PyPI | 10+ yrs | [OK] | Approved — already installed |
| celery | PyPI | 13+ yrs | [OK] | Approved — already installed |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

---

## Architecture Patterns

### System Architecture Diagram

```
HTTP Request (with Authorization: Bearer <jwt>)
        │
        ▼
StructlogContextMiddleware
  sets tenant_id ContextVar (hardcoded Sofa Belle UUID)
        │
        ▼
FastAPI Router (dashboards.py / insights.py)
  parses Query params (from_date, to_date)
  calls get_session() dependency
  calls get_current_user() dependency (JWT guard)
        │
        ▼
Read Service (DashboardReadService / InsightReadService / HealthReadService)
  runs ORM SELECT against pre-computed metric tables
  assembles response dict
        │
        ▼
Pydantic response_model validation
  Decimal → serialized as str
        │
        ▼
JSON response to client

POST /insights/refresh:
  check Redis key rate_limit:refresh:{user_id} via SET NX EX 3600
  if key exists → 429 with Retry-After header
  if key absent → celery_app.send_task("tasks.etl.sync_mefi_leads", args=[tenant_id]) → daily_pipeline chain
  return {pipeline_run_id: <uuid>}
```

### Recommended Project Structure (additions only)

```
backend/app/
├── api/v1/
│   ├── dashboards.py        # GET /dashboards/sales, /salespeople, /marketing
│   ├── insights.py          # GET /insights/today, /insights, POST /insights/refresh
│   └── router.py            # add dashboards + insights routers
├── schemas/
│   ├── dashboards/
│   │   ├── __init__.py
│   │   ├── sales.py         # SalesDashboardResponse
│   │   ├── salespeople.py   # SalespeopleDashboardResponse
│   │   └── marketing.py     # MarketingDashboardResponse
│   └── insights/
│       └── (daily_insight_schema.py already exists — add InsightListResponse)
├── services/
│   └── dashboards/
│       ├── __init__.py
│       ├── dashboard_read_service.py    # aggregation queries for 3 dashboards
│       └── health_read_service.py       # last_sync_at, stale flag
```

### Pattern 1: Thin FastAPI Router (existing pattern)
**What:** Router delegates to service; no business logic in handler
**When to use:** All Phase 6 endpoints — mirrors `auth.py` exactly

```python
# Source: backend/app/api/v1/auth.py (codebase pattern)
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.deps import get_session
from app.schemas.dashboards.sales import SalesDashboardResponse
from app.services.dashboards.dashboard_read_service import DashboardReadService
from app.core.security import get_current_user  # must be created in Phase 6

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/dashboards", tags=["dashboards"])


@router.get("/sales", response_model=SalesDashboardResponse)
async def get_sales_dashboard(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    session: AsyncSession = Depends(get_session),
    current_user: UserOut = Depends(get_current_user),
) -> SalesDashboardResponse:
    svc = DashboardReadService(session, current_user.tenant_id)
    data = await svc.get_sales_dashboard(from_date, to_date)
    return SalesDashboardResponse(**data)
```

### Pattern 2: JWT Auth Guard Dependency
**What:** FastAPI `Depends()` that validates the Bearer token and returns the current user
**When to use:** Every protected endpoint in Phase 6

```python
# Source: derived from existing app/core/security.py + app/api/v1/auth.py pattern
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.security import verify_token

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    payload = verify_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user_id = payload.get("sub")
    tenant_id = payload.get("tenant_id")
    # fetch user from DB to confirm is_active=True
    # return UserOut with id, tenant_id
```

**Critical note:** The existing `StructlogContextMiddleware` in `main.py` already sets tenant context from the hardcoded `settings.sofa_belle_tenant_id` — it does NOT read tenant from JWT yet (deferred to Iteration 4). The `get_current_user` dependency is needed only to (1) validate the JWT is valid, (2) get `user.id` for the rate-limit key, and (3) return 401 for unauthenticated requests. Tenant context is already set by middleware.

### Pattern 3: Decimal Serialization as String (DATA-04)
**What:** Pydantic v2 custom serializer to prevent float drift on monetary fields
**When to use:** All `Decimal` revenue/monetary fields in response schemas

```python
# Source: CLAUDE.md DATA-04, Pydantic v2 docs [ASSUMED - pattern based on Pydantic v2 docs]
from decimal import Decimal
from pydantic import BaseModel, field_serializer

class SalesDashboardResponse(BaseModel):
    revenue: Decimal | None

    @field_serializer("revenue")
    def serialize_revenue(self, v: Decimal | None) -> str | None:
        return str(v) if v is not None else None
```

Alternative: use `model_config = ConfigDict(json_encoders={Decimal: str})` — but `field_serializer` is the Pydantic v2 canonical approach and is field-specific. [ASSUMED: both approaches work in Pydantic v2 — verify in tests]

### Pattern 4: Redis Rate Limiting
**What:** `SET NX EX` atomic Redis check for POST /insights/refresh
**When to use:** Rate-limited mutation endpoint

```python
# Source: redis-py docs, existing redis usage in sync_mefi_leads.py [ASSUMED - pattern]
import redis.asyncio as aioredis
from app.core.config import settings

REFRESH_RATE_LIMIT_TTL = 3600  # 1 hour

async def check_refresh_rate_limit(user_id: str) -> tuple[bool, int]:
    """Returns (allowed, retry_after_seconds)."""
    r = aioredis.from_url(settings.redis_url)
    key = f"rate_limit:refresh:{user_id}"
    was_set = await r.set(key, "1", nx=True, ex=REFRESH_RATE_LIMIT_TTL)
    if was_set:
        return True, 0
    ttl = await r.ttl(key)
    return False, max(ttl, 0)
```

Note: The existing codebase uses `redis.asyncio as aioredis` already (in `sync_mefi_leads.py` for `SET NX EX` locks). [VERIFIED: codebase]

### Pattern 5: Date Range Aggregation Query
**What:** ORM aggregation across daily_kpi rows for a date range
**When to use:** Sales, Salespeople, Marketing dashboard endpoints

```python
# Source: DailyKpi ORM model (codebase) + SQLAlchemy 2.x select() [VERIFIED: codebase]
from sqlalchemy import select, func
from app.models.metrics.daily_kpi import DailyKpi

stmt = (
    select(
        func.sum(DailyKpi.leads_total).label("leads_total"),
        func.sum(DailyKpi.revenue).label("revenue"),
        func.sum(DailyKpi.contracts_count).label("contracts_count"),
    )
    .where(
        DailyKpi.tenant_id == self._tenant_id,
        DailyKpi.date >= from_date,
        DailyKpi.date <= to_date,
    )
)
```

### Pattern 6: Insight 404 Handling
**What:** Service returns None → router raises HTTPException(404)
**When to use:** GET /insights?date=YYYY-MM-DD

```python
# Source: CONVENTIONS.md error handling pattern + codebase
@router.get("/insights", response_model=InsightResponse)
async def get_insight_by_date(
    date: date = Query(...),
    ...
) -> InsightResponse:
    insight = await svc.get_insight_for_date(date)
    if insight is None:
        raise HTTPException(status_code=404, detail="No insight for this date")
    return insight
```

### Anti-Patterns to Avoid

- **Raw SQL in router handlers:** All SQL must be in service classes. API handlers call services, never `session.execute()` directly.
- **Calling Claude API in the refresh endpoint:** POST /insights/refresh enqueues a Celery task. It NEVER instantiates `AsyncAnthropic` or calls `client.messages.create()`. This is AI-09.
- **Float for Decimal fields:** Response schemas use `Decimal`, serialized as string. Never `float` in response bodies.
- **Missing tenant_id filter:** Even though `with_loader_criteria` enforces tenant isolation on ORM SELECT, the service must pass `tenant_id` to all queries. See existing metric services for the pattern.
- **Aggregation returning None for SUM when all values are NULL:** Use `COALESCE(SUM(col), 0)` or handle None in service layer for count fields.
- **date query param named `from`:** Python keyword — must use `alias="from"` in FastAPI `Query()` and a different Python variable name (e.g., `from_date`).

---

## Existing Codebase Patterns — Critical Reference

### Auth JWT pattern (already exists)
The `verify_token()` function in `app/core/security.py` decodes JWTs and returns the payload dict or None. The auth router (`api/v1/auth.py`) uses it. Phase 6 needs a `get_current_user` dependency that calls `verify_token()` on the Bearer token from `Authorization` header.

`app/core/security.py` exports:
- `verify_token(token: str) -> dict | None` — decodes JWT, returns payload or None on error

`app/schemas/auth.py` exports:
- `UserOut` with `id: UUID`, `email: str`, `is_active: bool`

No `get_current_user` dependency exists yet — must be created in Phase 6 in `app/core/security.py` or a new `app/api/deps.py`.

### Tenant middleware (already exists)
`StructlogContextMiddleware` in `main.py` calls `set_tenant_id(UUID(settings.sofa_belle_tenant_id))` on every HTTP request. This means the `with_loader_criteria` ORM tenant filter is already active for all HTTP handlers. Service classes must still pass `tenant_id` explicitly to all Core INSERT/UPDATE queries (the event listener only fires on ORM SELECT).

### Session dependency (already exists)
`app/db/deps.py::get_session()` yields `AsyncSession`. Use `Depends(get_session)` in all Phase 6 endpoints — identical to `auth.py`.

### Router registration (already exists)
`app/api/v1/router.py` imports routers and calls `api_router.include_router()`. Phase 6 adds two new include statements for `dashboards` and `insights` routers.

### Existing `/healthz` endpoint
`app/main.py` has `@app.get("/healthz")` returning `{"status": "ok"}` — this is the liveness check at the app level, not under `/api/v1/`. The new `GET /api/v1/health/data` (data freshness) will live under the `health` router prefix already registered in `router.py`.

The existing `health.py` router has `GET /health/live` (not `GET /healthz`). The ROADMAP success criterion says `GET /api/v1/healthz` — this is ambiguous. The root `/healthz` already exists in `main.py`. The Phase 6 endpoint should be `/api/v1/health/data` for data freshness; the `/healthz` liveness check at root already satisfies SC#6 first part.

---

## What Services Return — Data Inventory

### Daily KPI table columns (for Sales Dashboard aggregation)
From `DailyKpi` model:
- Lead counts: `leads_total`, `leads_mail_fb_ig`, `leads_telefon`, `leads_whatsapp`, `leads_site`, `leads_designer`, `leads_alte`
- Funnel: `visits_count` (nullable), `offers_count`, `contracts_count`
- Rates: `conversion_l_to_v`, `conversion_v_to_o`, `conversion_l_to_o`, `conversion_o_to_c`, `conversion_l_to_c`
- Revenue: `revenue` (NUMERIC(12,2)), `avg_deal_size`
- Deltas: `*_wow_delta`, `*_mom_delta` (8 metrics × 2 = 16 columns)

For a date range query, the API aggregates rows: `SUM()` for counts/revenue, `AVG()` or last-row for rates and deltas.

### Salesperson KPI table columns (for Salespeople Dashboard)
From `SalespersonDailyKpi` model:
- `salesperson_external_id`, `leads_assigned`, `leads_contacted`
- `avg_time_to_first_touch_minutes` (nullable — NULL when no history)
- `visits_conducted`, `offers_sent`, `deals_won`, `deals_lost`
- `revenue`, `conversion_l_to_v`, `conversion_v_to_o`, `conversion_o_to_c`, `conversion_l_to_c`
- `avg_deal_size`, `data_completeness_pct`

For range query: SUM counts, AVG rates and TTFT.

**salesperson_name lookup:** `salesperson_external_id` is a TEXT field (the MEFI external ID integer). Phase 6 needs to join or lookup `mefi_salespeople.name` to return human-readable names. [VERIFIED: codebase — MefiSalesperson model has `name` field]

### Source KPI table columns (for Marketing Dashboard)
From `SourceDailyKpi` model:
- `source` (TEXT category name), `leads`, `visits`, `offers`, `deals_won`
- `ad_spend` (NULL — Iteration 2), `cpl`, `cac`, `roas` (all NULL)
- `revenue`, `conversion_rate`

For range query: SUM leads/visits/offers/deals_won per source category.

**Junk % by source:** NOT in source_daily_kpi. Junk leads are excluded from v_mefi_leads_active. The junk % by source requires querying `raw_mefi_leads` for junk lifecycle leads grouped by source_id. This is a new query the service must run. [VERIFIED: codebase — confirmed junk leads in raw_mefi_leads with lifecycle='junk', excluded from all KPI tables]

**Site conversion approximation:** MARK-02 says "leads from site / sessions approximation from MEFI". Since GA4 is not connected in Iteration 1, the site conversion is `source_daily_kpi WHERE source='site' conversion_rate` — the leads-to-deals rate for the site source. No session data available. [VERIFIED: codebase/REQUIREMENTS.md]

### DailyInsight (for Insights endpoints)
From `DailyInsight` model:
- `date`, `status` (running|success|failed|fallback), `payload_json` (JSONB — DailyInsightResponse dict)
- `generated_at`, `input_tokens`, `output_tokens`, `cost_usd`

`payload_json` contains the full `DailyInsightResponse` dict. The API returns this JSON directly after schema validation.

**Fallback response (INSI-05):** When `status='failed'`, the service returns the payload_json (which contains the algorithmic fallback from `_build_fallback()`) plus a `generation_failed: true` flag in the response.

### SyncRun / PipelineRun (for Health endpoint)
From `SyncRun` model:
- `source`, `status`, `records_synced`, `duration_ms`, `started_at`, `completed_at`

For `/health/data`: query `sync_runs WHERE source='mefi' ORDER BY started_at DESC LIMIT 1` → `last_sync_at = completed_at`, `stale = (now - last_sync_at > 26h)`.

`PipelineRun.stage` and `PipelineRun.status` for `last_pipeline_status`.

---

## Response Schema Design

### SalesDashboardResponse
```
{
  "period": {"from": "2026-05-01", "to": "2026-05-19"},
  "funnel": {
    "leads": 217,
    "visits": 62,        # nullable — KI-03
    "offers": 87,
    "contracts": 12
  },
  "conversion_rates": {
    "l_to_v": "0.2857",        # Decimal as string
    "v_to_o": "1.4032",
    "l_to_o": "0.4009",
    "o_to_c": "0.1379",
    "l_to_c": "0.0553",
    "l_to_v_wow_delta": "-0.0500",   # nullable
    "l_to_c_wow_delta": "0.1000",
    # ... all 10 rate × delta pairs
  },
  "kpi_cards": {
    "leads_total": 217,
    "visits_count": 62,
    "offers_count": 87,
    "contracts_count": 12,
    "revenue": "102000.00",          # Decimal as string
    "avg_deal_size": "8500.00",
    "revenue_wow_delta": "0.0500",
    "leads_total_wow_delta": "-0.0300"
  },
  "source_breakdown": [
    {"source": "showroom", "leads": 62, "conversion_rate": "0.19"},
    {"source": "mail", "leads": 55, ...},
    ...
  ],
  "revenue_series": [
    {"date": "2026-05-01", "revenue": "5000.00"},
    ...
  ]
}
```

### SalespeopleDashboardResponse
```
{
  "period": {"from": ..., "to": ...},
  "salespeople": [
    {
      "external_id": "7",
      "name": "Raileanu Leon",
      "leads_assigned": 45,
      "visits_conducted": 12,
      "offers_sent": 20,
      "deals_won": 8,
      "revenue": "72000.00",
      "win_rate": "0.1778",
      "avg_time_to_first_touch_minutes": 142,   # nullable
      "data_completeness_pct": "88.89"
    },
    ...
  ]
}
```

### MarketingDashboardResponse
```
{
  "period": {"from": ..., "to": ...},
  "lead_volume_by_source": [
    {"source": "showroom", "leads": 360, "series": [{"date": ..., "leads": N}, ...]},
    ...
  ],
  "site_conversion_rate": "0.0645",   # site leads → deals
  "junk_by_source": [
    {"source": "telefon", "junk_count": 12, "total_leads": 90, "junk_pct": "0.1333"},
    ...
  ],
  "ad_spend": null,    # explicit null — MARK-03
  "cpl": null,
  "cac": null,
  "roas": null
}
```

### InsightTodayResponse / InsightResponse
```
{
  "date": "2026-05-27",
  "status": "success",
  "generation_failed": false,
  "generated_at": "2026-05-28T06:07:23Z",
  "payload": { ...DailyInsightResponse... }
}
```

### HealthDataResponse
```
{
  "last_sync_at": "2026-05-28T03:47:12Z",   # nullable
  "last_pipeline_status": "success",          # nullable
  "stale": false
}
```

### RefreshResponse
```
{
  "pipeline_run_id": "00000000-0000-0000-0000-000000000001",
  "enqueued_at": "2026-05-28T12:00:00Z"
}
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JWT validation | Custom token parser | `verify_token()` in `app/core/security.py` | Already exists, tested |
| Redis rate limit | Custom TTL tracking | `redis.asyncio` `SET NX EX` | Atomic, single-instruction |
| Date range param parsing | Manual string → date | FastAPI `Query(date)` type | FastAPI handles ISO-8601 parsing |
| Decimal serialization | Float coercion | Pydantic v2 `field_serializer` | Precision guaranteed |
| Tenant isolation | Per-query WHERE | `with_loader_criteria` seam (already wired) | Never bypass existing seam |
| Task enqueueing | Direct Celery import + chain construction | `celery_app.send_task("tasks.etl.sync_mefi_leads", args=[tenant_id])` | Existing chain wires downstream tasks |

**Key insight:** The entire pipeline chain (sync → kpis → anomaly → insights) is triggered by sending the `sync_mefi_leads` task. The chain is already defined in `daily_pipeline()` in `sync_mefi_leads.py`. The refresh endpoint should call `daily_pipeline(tenant_id).delay()` or `celery_app.send_task("tasks.etl.sync_mefi_leads", args=[str(tenant_id)])` — the chain propagates automatically.

---

## Common Pitfalls

### Pitfall 1: `from` as Python Query Parameter Name
**What goes wrong:** `from` is a Python keyword — `def endpoint(from: date = Query(...))` is a syntax error.
**Why it happens:** The URL spec uses `?from=YYYY-MM-DD` but Python can't use `from` as a variable name.
**How to avoid:** Use `from_date: date = Query(..., alias="from")` and `to_date: date = Query(..., alias="to")`.
**Warning signs:** `SyntaxError` in router file at import.

### Pitfall 2: SUM() returns NULL when all values are NULL
**What goes wrong:** `func.sum(DailyKpi.visits_count)` returns `None` when all `visits_count` rows are NULL (KI-03 — visits_count is nullable in migration 006).
**Why it happens:** PostgreSQL SUM() of all NULLs is NULL, not 0.
**How to avoid:** Use `func.coalesce(func.sum(col), 0)` for count aggregations. Keep NULL for rates/revenue (NULL means "no data", not "zero"). visits_count should remain nullable in responses.
**Warning signs:** TypeError when converting None to int in response schema.

### Pitfall 3: Decimal → float coercion in JSON serialization
**What goes wrong:** Pydantic serializes `Decimal("85000.00")` as `85000.0` (float) by default, losing string precision signal.
**Why it happens:** Default JSON encoder converts Decimal to float.
**How to avoid:** Add `@field_serializer` for every Decimal field in response schemas, or set `model_config = ConfigDict(json_encoders={Decimal: str})`. Test that response JSON contains `"85000.00"` (string), not `85000.0` (float).
**Warning signs:** Frontend receives number type for revenue field instead of string.

### Pitfall 4: Rate limit Redis connection not closed
**What goes wrong:** Async Redis connections leak if not explicitly closed after rate-limit check.
**Why it happens:** `aioredis.from_url()` creates a new connection pool on each call.
**How to avoid:** Use `async with aioredis.from_url(...) as r:` or reuse an existing Redis client. Alternatively, create the Redis client as a FastAPI dependency with proper cleanup.
**Warning signs:** "Too many open connections" errors under load.

### Pitfall 5: `with_loader_criteria` fires only on ORM SELECT, not Core INSERT
**What goes wrong:** Believing the tenant isolation seam covers all queries. Core text() queries and pg_insert() bypass it.
**Why it happens:** `do_orm_execute` event only intercepts ORM SELECT statements.
**How to avoid:** Phase 6 is read-only — no INSERT/UPDATE needed. All reads via ORM select() are covered. Service methods must still pass `tenant_id` explicitly to `text()` queries (e.g., junk-by-source query against raw_mefi_leads).
**Warning signs:** Data returned without tenant filtering for text() queries.

### Pitfall 6: Insight today vs yesterday
**What goes wrong:** GET /insights/today returns None if insights have not run for today yet (pipeline runs at 06:00 for yesterday's data).
**Why it happens:** `generate_daily_insights` generates insights for `yesterday` (kpi_date = today - 1 day), so on any given calendar day "today's insight" is for yesterday's data.
**How to avoid:** `GET /insights/today` should query `daily_insights WHERE date = yesterday` (Bucharest today - 1 day). The endpoint name is UI-facing ("today's report"), not a literal date query.
**Warning signs:** Always returning 404 for /insights/today.

### Pitfall 7: Salesperson name lookup — join required
**What goes wrong:** `salesperson_daily_kpi.salesperson_external_id` is a TEXT string (the MEFI integer ID). The response needs human-readable names.
**Why it happens:** KPI tables store external IDs for efficient joins, not names.
**How to avoid:** JOIN `salesperson_daily_kpi` with `mefi_salespeople` on `(tenant_id, external_id = salesperson_external_id)` to get `mefi_salespeople.name`. This join is within the same DB, not an external API call.
**Warning signs:** Response shows `"name": "7"` instead of `"name": "Raileanu Leon"`.

### Pitfall 8: Pipeline refresh — chain vs standalone task
**What goes wrong:** Calling `generate_daily_insights.delay(tenant_id)` triggers only the insights step, not the full sync→kpis→anomaly→insights chain.
**Why it happens:** The chain `daily_pipeline()` is defined in `sync_mefi_leads.py` and must be called to wire the full chain.
**How to avoid:** Import and call `daily_pipeline(tenant_id).delay()` from `sync_mefi_leads` module, or use `celery_app.send_task("tasks.etl.sync_mefi_leads", args=[str(tenant_id)])` which is the first link of the chain. The chain propagation happens inside each task via `.si()` callbacks. [VERIFIED: codebase — daily_pipeline() in sync_mefi_leads.py wires the chain]

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Tremor charts | shadcn/ui chart (Recharts v3) | Phase 1 decision | No @tremor/react imports anywhere |
| Per-table Python date groups | AT TIME ZONE 'Europe/Bucharest' in SQL | Phase 2/3 | All KPI dates are Bucharest-local |
| Float revenue | Decimal (NUMERIC(12,2)) | Phase 3 | DATA-04: serialize as string |
| Inline Celery task logic | Deferred imports + NullPool pattern | Phase 3+ | INFRA-05 fork-safe pattern |

**Deprecated/outdated:**
- `@tremor/react`: forbidden per CLAUDE.md + Phase 1 decision (shadcn/ui chart instead)
- Sync DB queries in HTTP handlers: forbidden per CLAUDE.md Principle #5

---

## Environment Availability

Phase 6 is pure code/config — no new external service dependencies. All services already running:

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PostgreSQL | All read queries | ✓ | 16 (Docker) | — |
| Redis | Rate limiting | ✓ | 7 (Docker) | — |
| Celery worker | Refresh enqueue | ✓ | 5.6.3 | — |
| FastAPI | HTTP layer | ✓ | 0.136.1 | — |

**Missing dependencies with no fallback:** None.

---

## Validation Architecture

nyquist_validation is enabled (not set to false in config.json).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio |
| Config file | `backend/pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `cd backend && pytest tests/unit/test_dashboard_read_service.py tests/unit/test_insight_read_service.py -x` |
| Full suite command | `cd backend && pytest --cov=app --cov-report=term-missing` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SALE-01..07 | Sales dashboard data assembly | unit | `pytest tests/unit/test_dashboard_read_service.py::test_get_sales_dashboard_*` | ❌ Wave 0 |
| SALES-01..04 | Salespeople dashboard + name join | unit | `pytest tests/unit/test_dashboard_read_service.py::test_get_salespeople_dashboard_*` | ❌ Wave 0 |
| MARK-01..04 | Marketing dashboard + junk % | unit | `pytest tests/unit/test_dashboard_read_service.py::test_get_marketing_dashboard_*` | ❌ Wave 0 |
| INSI-01,02 | Insight read (today + by date) | unit | `pytest tests/unit/test_insight_read_service.py::test_get_insight_*` | ❌ Wave 0 |
| INSI-03 | Refresh rate limit (allow + 429) | unit | `pytest tests/unit/test_insights_router.py::test_refresh_*` | ❌ Wave 0 |
| INSI-05 | Fallback response when status=failed | unit | `pytest tests/unit/test_insight_read_service.py::test_get_insight_fallback*` | ❌ Wave 0 |
| INSI-06 | generated_at + freshness in response | unit | `pytest tests/unit/test_insight_read_service.py::test_insight_has_freshness` | ❌ Wave 0 |
| UI-06 | /health/data stale flag logic | unit | `pytest tests/unit/test_health_read_service.py::test_stale_flag*` | ❌ Wave 0 |
| PIPE-04 | pipeline_runs read in health endpoint | unit | `pytest tests/unit/test_health_read_service.py::test_last_pipeline_status*` | ❌ Wave 0 |
| DATA-04 | Decimal serialized as string in response | unit | `pytest tests/unit/test_dashboard_schemas.py::test_decimal_*` | ❌ Wave 0 |
| AUTH-03 | Unauthenticated → 401 | integration | `pytest tests/integration/test_api_auth.py::test_*_requires_auth` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && pytest tests/unit/test_dashboard_read_service.py tests/unit/test_insight_read_service.py tests/unit/test_health_read_service.py -x`
- **Per wave merge:** `cd backend && pytest --cov=app --cov-report=term-missing`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_dashboard_read_service.py` — RED stubs for SALE-01..07, SALES-01..04, MARK-01..04
- [ ] `tests/unit/test_insight_read_service.py` — RED stubs for INSI-01..06
- [ ] `tests/unit/test_health_read_service.py` — RED stubs for UI-06, PIPE-04
- [ ] `tests/unit/test_dashboard_schemas.py` — RED stubs for DATA-04 decimal serialization
- [ ] `tests/unit/test_insights_router.py` — RED stubs for INSI-03 rate limit (allow + 429)
- [ ] `tests/factories/dashboard_factory.py` — factory-boy factories for daily_kpi, salesperson, source rows
- [ ] `tests/integration/test_api_auth.py` — integration tests for 401 on unauthenticated requests

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | JWT Bearer via `verify_token()` dependency on all endpoints |
| V3 Session Management | no | Stateless JWT; no server-side session |
| V4 Access Control | yes | Single tenant (hardcoded); authenticated user can only see their tenant's data |
| V5 Input Validation | yes | Pydantic v2 schema on all query params and response models |
| V6 Cryptography | no | JWT signing already in Phase 1; no new crypto in Phase 6 |

### Known Threat Patterns for FastAPI REST

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Missing auth on dashboard endpoints | Spoofing / Info Disclosure | `Depends(get_current_user)` on all endpoints; 401 if token invalid |
| Date range parameter injection | Tampering | FastAPI `date` type rejects non-ISO-8601 input automatically |
| Rate limit bypass by rotating user | Spoofing | Rate limit key = `user_id` from JWT (not IP); valid JWT required |
| Claude called from HTTP handler | Tampering / DoS | AI-09 enforcement: refresh endpoint enqueues Celery task only |
| Decimal → float in JSON losing precision | Tampering | `field_serializer` on every Decimal field; test with assertion `isinstance(json_value, str)` |
| Cross-tenant data exposure | Info Disclosure | `with_loader_criteria` seam active; service passes `tenant_id` to text() queries |

---

## Phase Requirements

<phase_requirements>

| ID | Description | Research Support |
|----|-------------|------------------|
| SALE-01 | Funnel visualization (Lead→Vizita→Oferta→Contract) stage counts for date range | `DailyKpi.leads_total`, `.visits_count`, `.offers_count`, `.contracts_count` — SUM over date range |
| SALE-02 | L→V, V→O, L→O, O→C, L→C conversion rates with WoW/MoM deltas | 5 rate columns + 10 delta columns in `DailyKpi`; for range: return last-day or weighted avg |
| SALE-03 | KPI cards: leads, visits, offers, contracts, revenue (Încasări) with deltas | SUM counts, last delta columns; revenue as Decimal string |
| SALE-04 | Lead volume breakdown by source as chart + table | `SourceDailyKpi` SUM per source category over date range |
| SALE-05 | Revenue trend over time (line chart) | `DailyKpi.revenue` per date for selected range — return time series array |
| SALE-06 | Date range switching: 7d, 30d, 90d, custom | API accepts `from` + `to` query params; preset logic is frontend concern |
| SALE-07 | Stuck offers widget: count and list of offers >14 days no activity | Query `v_mefi_leads_active` for `reached_offer=true` leads with last `mefi_lead_history` entry >14 days ago |
| SALES-01 | Leaderboard: all salespeople with leads/visits/offers/contracts/revenue/win-rate | `SalespersonDailyKpi` SUM per salesperson + join to `mefi_salespeople.name` |
| SALES-02 | Time-to-first-touch per salesperson (target <4h), highlighted when breached | `avg_time_to_first_touch_minutes` from SalespersonDailyKpi; >240min = breach |
| SALES-03 | Per-salesperson funnel for date range | SUM `leads_assigned`, `visits_conducted`, `offers_sent`, `deals_won` per salesperson |
| SALES-04 | `data_completeness_pct` per salesperson | `SalespersonDailyKpi.data_completeness_pct` — AVG over range or last available |
| MARK-01 | Lead volume by source over time (line chart) | `SourceDailyKpi` per source per date — return time series per source |
| MARK-02 | Site conversion rate (leads from site / sessions approximation) | `SourceDailyKpi WHERE source='site' conversion_rate` — only leads-to-deals available (no GA4) |
| MARK-03 | Placeholder sections for CPL/CAC/ROAS — "Coming in next update" | Return explicit `null` for `ad_spend`, `cpl`, `cac`, `roas` fields |
| MARK-04 | Junk lead % by source | New query: `raw_mefi_leads` grouped by `source_id` WHERE `lifecycle='junk'`, joined to total count by source |
| INSI-01 | Today's AI insights: top-3 problems with all fields | `DailyInsight WHERE date = yesterday` → return `payload_json` as `DailyInsightResponse` |
| INSI-02 | Historical insights by date | `DailyInsight WHERE date = ?` → 404 if absent |
| INSI-03 | Manual refresh: rate-limited 1/hr, returns pipeline_run_id | Redis SET NX EX 3600; enqueue `daily_pipeline(tenant_id).delay()`; return task_id |
| INSI-04 | Each problem links to triggering metric (source traceability) | `Problem.id = rule_id` already in DailyInsightResponse; include in API response |
| INSI-05 | Generation failure → algorithmic fallback + notice flag | `DailyInsight.status='failed'` → return payload_json (fallback) + `generation_failed: true` |
| INSI-06 | generated_at + data freshness status | Return `DailyInsight.generated_at` + `stale` flag from last sync_runs |
| UI-06 | Data freshness banner: last_sync_at > 26h or sync failed | `GET /health/data` returns `last_sync_at`, `last_pipeline_status`, `stale: bool` |
| PIPE-04 | pipeline_runs read for health endpoint | `PipelineRun` ORDER BY started_at DESC LIMIT 1 for last_pipeline_status |

</phase_requirements>

---

## Open Questions (RESOLVED)

1. **Revenue series granularity for date ranges**
   - What we know: `DailyKpi.revenue` is per-day. For a 30d range, return 30 data points.
   - What's unclear: For 90d or custom ranges, does the frontend need daily granularity or weekly aggregation?
   - Recommendation: Always return daily granularity. Frontend decides grouping. [ASSUMED]
   - **RESOLVED:** Always daily granularity — one row per day. The frontend handles grouping/display. Locked user decision.

2. **Salesperson name lookup performance**
   - What we know: `mefi_salespeople` table has 6 rows (Sofa Belle). JOIN is trivial at this scale.
   - What's unclear: At Iteration 4 scale with many tenants, N+1 risk.
   - Recommendation: JOIN in SQL for Phase 6. No optimization needed for 6-row table.
   - **RESOLVED:** JOIN in SQL (same as recommendation). 6-row table; no optimization concern for Iteration 1.

3. **Junk by source query — which table?**
   - What we know: `raw_mefi_leads` has all leads including `lifecycle='junk'` and `source_id`.
   - What's unclear: Should we use `raw_mefi_leads` directly or a new view? CLAUDE.md says metric services never query `raw_mefi_*` directly — but this is the API layer, not a metric service, and there's no pre-computed junk-by-source table.
   - Recommendation: Create a junk-by-source query in `DashboardReadService.get_marketing_dashboard()` that queries `raw_mefi_leads WHERE lifecycle='junk'` grouped by source_id. Document the exception in code comments.
   - **RESOLVED:** Query `raw_mefi_leads` directly in `DashboardReadService`. This is a confirmed documented exception to the no-raw-table rule: no pre-computed junk-by-source table exists and this is read-only aggregation in the API (not metric) service layer. Comment the exception in code.

4. **POST /insights/refresh — should it trigger full pipeline or insights-only?**
   - What we know: ROADMAP SC#5 says "enqueues a pipeline run". The chain is sync→kpis→anomaly→insights. Triggering sync on manual refresh would re-pull from MEFI (correct if data is stale).
   - What's unclear: Should "refresh" mean "regenerate insights from existing data" or "full pipeline re-run"?
   - Recommendation: Trigger `generate_daily_insights.si(tenant_id).delay()` directly (insights-only) rather than the full pipeline chain. This matches "refresh the insights page" semantics. The full pipeline runs on schedule. [ASSUMED — confirm with user if needed]
   - **RESOLVED:** Trigger full `daily_pipeline(tenant_id_str).delay()` chain — the complete sync→kpis→anomaly→insights sequence. Locked decision per ROADMAP SC#5 and user confirmation. The partial insights-only path is superseded.

5. **`pipeline_run_id` in refresh response**
   - What we know: The refresh endpoint should return a `pipeline_run_id`. Celery tasks return `AsyncResult.id` (the task ID). There is no row created in `pipeline_runs` at enqueue time — it's created when the task runs.
   - What's unclear: Should the response contain the Celery task ID or a pre-created `pipeline_runs.id`?
   - Recommendation: Return the Celery `task_id` (str UUID) as `pipeline_run_id`. The client can use it to poll if a polling endpoint is added later. [ASSUMED]
   - **RESOLVED:** Return Celery task ID string as `pipeline_run_id` — i.e. `task.id` from the `AsyncResult` returned by `.delay()`. No pre-created DB row needed.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `GET /insights/today` queries daily_insights for yesterday (Bucharest - 1 day) | Insight today vs yesterday pitfall | If wrong: endpoint always returns 404 |
| A2 | POST /insights/refresh triggers `generate_daily_insights` only, not full pipeline | Open Questions #4 | If wrong: full MEFI sync triggered on every manual refresh |
| A3 | Celery task ID returned as `pipeline_run_id` in refresh response | Open Questions #5 | If wrong: need to pre-create pipeline_runs row |
| A4 | Daily revenue series uses daily granularity for all date ranges | Open Questions #1 | If wrong: need backend aggregation by week |
| A5 | Pydantic v2 `field_serializer` is the correct approach for Decimal→str | Code Examples | If wrong: use json_encoders instead |
| A6 | Junk-by-source query reads `raw_mefi_leads` directly (exception to no-raw-table rule) | Open Questions #3 | If wrong: need new DB view or junk column in source_kpi |

---

## Sources

### Primary (HIGH confidence)
- Codebase: `backend/app/api/v1/auth.py` — router pattern, JWT usage [VERIFIED: codebase]
- Codebase: `backend/app/core/security.py` — `verify_token()` API [VERIFIED: codebase]
- Codebase: `backend/app/core/tenancy.py` — tenant isolation seam [VERIFIED: codebase]
- Codebase: `backend/app/db/deps.py` — `get_session()` dependency [VERIFIED: codebase]
- Codebase: `backend/app/main.py` — `StructlogContextMiddleware` tenant setup [VERIFIED: codebase]
- Codebase: `backend/app/models/metrics/daily_kpi.py` — all columns for Sales dashboard [VERIFIED: codebase]
- Codebase: `backend/app/models/metrics/salesperson_kpi.py` — all columns for Salespeople [VERIFIED: codebase]
- Codebase: `backend/app/models/metrics/source_kpi.py` — all columns for Marketing [VERIFIED: codebase]
- Codebase: `backend/app/models/insights/daily_insight.py` — insight table schema [VERIFIED: codebase]
- Codebase: `backend/app/models/pipeline.py` — SyncRun + PipelineRun models [VERIFIED: codebase]
- Codebase: `backend/app/schemas/insights/daily_insight_schema.py` — DailyInsightResponse [VERIFIED: codebase]
- Codebase: `backend/app/tasks/etl/sync_mefi_leads.py` — daily_pipeline chain [VERIFIED: codebase]
- Codebase: `backend/app/tasks/etl/generate_daily_insights.py` — task name for enqueueing [VERIFIED: codebase]
- Codebase: `backend/pyproject.toml` — installed packages and versions [VERIFIED: codebase]
- slopcheck: all 7 core packages verified [OK] [VERIFIED: slopcheck v0.6.1]

### Secondary (MEDIUM confidence)
- FastAPI docs pattern: `Query(alias="from")` for reserved Python keywords [CITED: fastapi.tiangolo.com]
- Pydantic v2 `field_serializer` for Decimal→str [ASSUMED: based on Pydantic v2 training knowledge]

### Tertiary (LOW confidence)
- Rate limit key design `rate_limit:refresh:{user_id}` — standard pattern [ASSUMED]
- POST /insights/refresh returns Celery task_id as pipeline_run_id [ASSUMED]

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages already installed and verified in codebase
- Architecture: HIGH — codebase patterns fully inspected; no new patterns needed
- Response schemas: MEDIUM — designed from model inspection; exact field names subject to planner refinement
- Rate limiting: MEDIUM — pattern from existing sync_mefi_leads.py Redis lock usage
- Pitfalls: HIGH — all derived from direct codebase inspection of existing patterns and model nullability

**Research date:** 2026-05-28
**Valid until:** 2026-06-28 (stable stack; no fast-moving dependencies)
