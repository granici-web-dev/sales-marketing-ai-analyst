# Architecture Patterns — Sales & Marketing AI Analyst

**Domain:** B2B SaaS analytics platform (ETL + AI insights)
**Researched:** 2026-05-19
**Confidence:** HIGH (validated against Context7 docs for SQLAlchemy 2.x, Celery, Anthropic SDK, TanStack Query, PostgreSQL 17)
**Scope:** Validate the existing 3-layer architecture (`docs/ARCHITECTURE.md`, `SPEC.md` §4/§6/§7), surface implementation gaps, and recommend build order.

---

## 1. Validation of the 3-Layer DB Architecture

The proposed `raw → metrics → insights` separation is the standard "medallion" pattern (also called bronze/silver/gold in Databricks/lakehouse terminology). It is the correct choice here.

### Why it's correct for this domain

| Concern | How the 3 layers solve it |
|---|---|
| External APIs change schemas | `raw_*` keeps `raw_payload JSONB` — re-derive without re-syncing |
| Metric formulas evolve | Recompute `daily_kpi` from `raw_*` without touching source APIs |
| AI prompts iterate | Re-run `insights_generator` on stable `detected_problems` |
| Audit trail | `raw_*.synced_at`, `daily_kpi.calculated_at`, `daily_insights.generated_at` give per-layer provenance |
| Replay / backfill | Each layer can be rebuilt from the layer below it |

### Validated against industry patterns (HIGH confidence)

This matches what Fivetran/dbt/Airbyte ecosystems converged on:
- **Raw / bronze:** immutable copy of source
- **Conformed / silver:** business metrics, joinable, type-safe
- **Marts / gold:** denormalized, BI/AI-ready

The SPEC even adds a 4th layer (`detected_problems`) between metrics and insights — this is a smart addition. It deterministically translates numbers into "things worth talking about" *before* the LLM sees the data, which:
1. Keeps the LLM input small and structured (cheaper, more reliable)
2. Lets you A/B-test prompts on a stable set of inputs
3. Lets you debug "why did Claude say X?" — answer is in `detected_problems` row

### Gap: missing `staging` / `clean` layer between raw and metrics

**Issue:** Going straight from `mefi_leads.raw_payload` to `daily_kpi` couples KPI logic to MEFI's wire format. When you add a second tenant on a different CRM, or MEFI changes a field name, every `metrics_calc` query breaks.

**Recommendation:** Introduce a thin **conformed layer** as views (not tables — no extra storage):

```sql
-- Example: backend/alembic/versions/XXXX_conformed_views.py
CREATE VIEW v_leads AS
SELECT
    tenant_id,
    external_id AS lead_id,
    created_at_source AS created_at,
    -- normalize category to a stable enum
    CASE category
        WHEN 'mail_fb_ig' THEN 'social'
        WHEN 'telefon'    THEN 'phone'
        WHEN 'whatsapp'   THEN 'whatsapp'
        WHEN 'site'       THEN 'web'
        WHEN 'designer'   THEN 'designer'
        ELSE 'other'
    END AS source_category,
    salesperson_id,
    status
FROM mefi_leads;
```

All `services/metrics/*.py` queries SELECT from `v_*`, never from `mefi_*` directly. When you add `pipedrive_leads`, you add a `UNION ALL` branch in the view and metrics code does not change.

**Confidence:** HIGH — this is dbt's "staging models" pattern, and the SPEC's "MEFI-agnostic" goal (§5.7) cannot be met without it.

---

## 2. Critical Implementation Gaps

These are issues that will cause rework if not addressed during phase planning.

### Gap A: No idempotency key strategy documented

The SPEC says "Each Celery task is idempotent" but does not specify *how*. For ETL, the standard pattern is:

```python
# backend/app/tasks/etl/sync_mefi.py
@app.task(
    bind=True,
    autoretry_for=(httpx.HTTPError,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
    acks_late=True,        # only ack after success
    reject_on_worker_lost=True,
)
def sync_mefi_leads(self, tenant_id: str, since: str | None = None) -> dict:
    ...
```

Plus: every `raw_*` table already has `UNIQUE(tenant_id, external_id)` — so upserts must use `INSERT ... ON CONFLICT DO UPDATE`. SQLAlchemy 2.x: `pg_insert(...).on_conflict_do_update(...)`. Document this as a convention.

**Why it matters:** Without `acks_late + ON CONFLICT`, a worker crash mid-sync either loses data or creates duplicates that break unique constraints on retry.

### Gap B: Async/sync boundary — current spec is wrong on a critical point

`docs/ARCHITECTURE.md` says:
> "Sync: only inside Celery tasks (Celery 5.x not fully async)"
> "In Celery tasks use `asyncio.run()` for calling async code"

**This works but has a fork-safety hazard** that the docs do not flag.

From SQLAlchemy 2.x docs (Context7, HIGH confidence):
> "It is critical that pooled connections are not shared with a forked process when using a connection pool or an Engine created via `create_engine()`. TCP connections are represented as file descriptors, and sharing them across process boundaries can lead to concurrent access issues."

Celery's default `prefork` worker model forks worker processes. If the async engine is created at module import (i.e., before fork), every worker inherits the same TCP file descriptors → deadlocks under load.

**Required pattern (HIGH confidence):**

```python
# backend/app/tasks/celery_app.py
from celery import Celery
from celery.signals import worker_process_init

app = Celery(...)

@worker_process_init.connect
def init_worker(**kwargs):
    """Re-create async engine per forked worker process."""
    from app.db.session import init_async_engine
    init_async_engine()
```

```python
# backend/app/db/session.py
_engine: AsyncEngine | None = None

def init_async_engine() -> None:
    global _engine
    _engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)

def get_async_engine() -> AsyncEngine:
    if _engine is None:
        init_async_engine()
    return _engine
```

```python
# backend/app/tasks/_helpers.py
import asyncio
from contextlib import asynccontextmanager

def run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Should not happen in prefork worker, but guard anyway
            raise RuntimeError("nested event loop")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)
```

```python
# backend/app/tasks/etl/sync_mefi.py
@app.task(bind=True, ...)
def sync_mefi_leads(self, tenant_id: str) -> dict:
    return run_async(_sync_mefi_leads(tenant_id))

async def _sync_mefi_leads(tenant_id: str) -> dict:
    async with AsyncSessionLocal() as session:
        ...
```

**Alternative considered:** `celery -P gevent` or `celery -P eventlet`. Not recommended — monkey-patching breaks asyncpg and creates subtle bugs. Stick with default prefork + per-worker engine + `asyncio.new_event_loop()` per task.

### Gap C: Celery Beat single-point-of-failure not addressed

`docker-compose.yml` will run one `beat` container. If beat dies between 03:00 and 06:00, the entire day's pipeline silently doesn't run. Mitigations:

1. Use `celery-redbeat` (Redis-backed scheduler with leader election) — survives container restart
2. Add a healthcheck task: every minute beat enqueues a `heartbeat` task, a separate watchdog (e.g. uptime-kuma or a cron on host) alerts if no heartbeat in last 5 min
3. After each pipeline stage, write `pipeline_runs(date, stage, status)` row — the morning insights query verifies "did metrics_calc actually run for today?"

Document this as a known operational risk for Phase 1, fix in production-hardening phase.

### Gap D: Pipeline orchestration — chain vs independent schedules

SPEC schedules four cron jobs at 03:00, 04:00, 05:00, 06:00 with 1-hour gaps. Problems:

1. **MEFI sync running > 1 hour** (full backfill of 12 months for Sofa Belle) → metrics_calc runs against incomplete data
2. **No back-pressure** — if metrics_calc fails, anomaly_detection still runs at 05:00 against stale data
3. **No re-trigger primitive** — manual re-run requires running each stage by hand

**Recommended pattern (HIGH confidence — Celery docs):**

```python
# backend/app/tasks/daily_pipeline.py
from celery import chain

@app.task
def run_daily_pipeline(tenant_id: str, target_date: str):
    pipeline = chain(
        sync_all_sources.si(tenant_id, target_date),
        calculate_metrics.si(tenant_id, target_date),
        detect_anomalies.si(tenant_id, target_date),
        generate_insights.si(tenant_id, target_date),
    )
    return pipeline.apply_async()
```

Then schedule ONE cron at 03:00 that calls `run_daily_pipeline.delay(...)`. Each stage runs only after the previous succeeds, automatic retry per stage, single re-trigger primitive for the entire pipeline.

The 04:00/05:00/06:00 timestamps in the SPEC become **soft SLAs**, not cron triggers. This is the standard Celery pattern for multi-stage data pipelines.

### Gap E: Tenancy enforcement deferred — but schema choices already lock it in

`PROJECT.md` explicitly defers tenancy enforcement to Iteration 4. That's a reasonable speed/quality tradeoff. But:

- ✅ Every table has `tenant_id` — keeps the door open
- ⚠️ No `tenant_id` index on `daily_insights` or `detected_problems` — add now (cheap)
- ⚠️ The SQLAlchemy "global filter via event listener" pattern in §13 has a subtle bug: it does not catch raw SQL or `session.execute(text(...))`. Need RLS at PostgreSQL level for defense in depth.

**Recommendation for Iteration 4:** Use **PostgreSQL Row Level Security (RLS)** as the enforcement primitive, with SQLAlchemy event listeners as the "make it ergonomic" layer. RLS is enforced at the database, so even a SQL injection or raw query cannot escape it.

```sql
ALTER TABLE mefi_leads ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON mefi_leads
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid);
```

Then per-request middleware: `SET LOCAL app.current_tenant_id = '<from JWT>'`.

Document this decision now even though implementation is deferred — it influences whether `tenant_id` is `NOT NULL` (must be, for RLS).

### Gap F: Frontend — Server Components, Client Components, and TanStack Query boundary

Next.js 14 App Router introduces a hard divide that the docs do not address: **TanStack Query is client-only**. Tremor charts run client-side too. So the pattern (HIGH confidence from TanStack docs):

```tsx
// app/(dashboard)/sales/page.tsx — Server Component (default)
import { dehydrate, HydrationBoundary } from '@tanstack/react-query'
import { getQueryClient } from '@/lib/query-client'
import { salesOverviewQuery } from '@/lib/queries/sales'
import { SalesDashboard } from '@/components/dashboards/sales-dashboard'

export default async function Page() {
  const queryClient = getQueryClient()
  void queryClient.prefetchQuery(salesOverviewQuery({ from: '...', to: '...' }))

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <SalesDashboard />  {/* 'use client' inside */}
    </HydrationBoundary>
  )
}
```

```tsx
// components/dashboards/sales-dashboard.tsx
'use client'
import { useQuery } from '@tanstack/react-query'
import { Card, Title, BarChart } from '@tremor/react'
import { salesOverviewQuery } from '@/lib/queries/sales'

export function SalesDashboard() {
  const { data } = useQuery(salesOverviewQuery({ from: '...', to: '...' }))
  return <Card><Title>Vânzări</Title><BarChart data={data.funnel} /></Card>
}
```

**Why this matters for build order:** if Phase 6 (frontend) starts without this structure decided, you will refactor every page. Lock it in as the first frontend PR.

---

## 3. Validation of the Daily Pipeline (03/04/05/06)

| Stage | Soft SLA | Validated against industry pattern? |
|---|---|---|
| ETL @ 03:00 | < 1h | ✅ Standard "after-midnight EU traffic" window — Meta/Google Ads daily aggregates are stable by ~02:00 UTC = 04:00 EEST. **Run at 04:00 instead** to ensure ad data is final |
| Metrics @ 04:00 | < 15min | ✅ Pure SQL on `raw_*` — should be seconds for Sofa Belle volume (~hundreds of leads/month) |
| Anomaly @ 05:00 | < 5min | ✅ Algorithmic rules over `daily_kpi` rows — trivial work |
| Insights @ 06:00 | < 2min | ✅ One Claude API call per tenant, ~30s round-trip |
| Email @ 07:00 | < 1min | ⚠️ Skip in Iteration 1 per `PROJECT.md` |

**Recommended adjustment:** Shift ETL to **04:00 EEST** (= 02:00 UTC) for Iteration 2 when Meta/Google Ads come in. Daily aggregates from ad platforms are not finalized until the source timezone's day rollover + processing lag. Hardcoding 03:00 now is fine for Iteration 1 (MEFI only — operates in Romania timezone), but document the constraint.

**The pipeline as designed will work.** The bigger risk is operational (Gap C above) not timing.

---

## 4. Anthropic Structured Output Pattern (HIGH confidence)

The SPEC says "Claude returns JSON, we parse it." The current SDK (Anthropic Python SDK, verified via Context7 2026-05) has a first-class API for this: **`client.messages.parse()` with `output_format=PydanticModel`**.

### Recommended pattern

```python
# backend/app/services/insights/schemas.py
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Literal

Severity = Literal["high", "medium", "low"]
Category = Literal["marketing", "sales", "team", "funnel"]

class Action(BaseModel):
    order: int = Field(ge=1, le=10)
    description: str
    owner: str
    deadline: str  # ISO date
    expected_outcome: str

class Problem(BaseModel):
    id: str
    severity: Severity
    category: Category
    title: str
    description: str
    estimated_loss_ron: float = Field(ge=0)
    actions: list[Action] = Field(min_length=1, max_length=5)

class Positive(BaseModel):
    title: str
    description: str
    recommendation: str

class Warning(BaseModel):
    title: str
    description: str

class DailyInsightResponse(BaseModel):
    summary: str
    problems: list[Problem] = Field(max_length=3)  # SPEC: max 3 high priority
    positives: list[Positive] = Field(default_factory=list)
    warnings: list[Warning] = Field(default_factory=list)
    weekly_action_plan: list[str] = Field(min_length=3, max_length=10)
```

```python
# backend/app/services/insights/claude_client.py
from anthropic import AsyncAnthropic
from app.services.insights.schemas import DailyInsightResponse

client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

async def generate_insight(
    tenant_context: dict,
    detected_problems: list[dict],
    metrics: dict,
) -> tuple[DailyInsightResponse, int]:  # parsed + tokens_used
    user_prompt = build_user_prompt(tenant_context, detected_problems, metrics)

    parsed = await client.messages.parse(
        model="claude-sonnet-4-5",
        max_tokens=4096,
        system=ROMANIAN_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
        output_format=DailyInsightResponse,
    )

    return parsed.parsed_output, parsed.usage.input_tokens + parsed.usage.output_tokens
```

**Why this beats hand-rolled JSON parsing:**

1. Anthropic SDK generates a JSON Schema from the Pydantic model and sends it to Claude as a constraint
2. Response is guaranteed schema-valid (no `try/except json.JSONDecodeError` needed)
3. Pydantic validates ranges (`ge=0`, `max_length=3`) — Claude can't hallucinate 50 problems
4. Type-safe end-to-end into the DB write

**Pitfall to avoid:** Do not use `tool_use` for this. Tool use is for "Claude calls your function." For "Claude returns structured data," `messages.parse()` is the modern, simpler primitive.

**Fallback for older SDK:** if `messages.parse()` not available, use `tool_choice={"type": "tool", "name": "submit_insight"}` with a tool whose `input_schema` is the JSON schema. Same effect, more boilerplate.

### Prompt structure for cheap, deterministic insights

```python
# backend/app/services/insights/prompt_builder.py
def build_user_prompt(ctx: dict, problems: list, metrics: dict) -> str:
    return f"""
DATE TENANT:
{json.dumps(ctx, indent=2, ensure_ascii=False)}

METRICI PERIOADĂ (ultimele 7 zile vs 7 zile anterioare):
{json.dumps(metrics, indent=2, ensure_ascii=False)}

PROBLEME DETECTATE ALGORITMIC (top 10 după severitate):
{json.dumps(problems[:10], indent=2, ensure_ascii=False)}

Formulează un raport conform schemei JSON. Maximum 3 probleme high-priority.
"""
```

Pre-truncating `problems` to top-10 in Python (not asking Claude to filter 50) keeps input tokens predictable (~$0.05/insight as SPEC estimates).

---

## 5. PostgreSQL Time-Series Patterns for `daily_kpi`

### Decision: do NOT partition `daily_kpi` in Iteration 1

The SPEC mentions "TimescaleDB extension (optional)." Concrete recommendation: **skip it for Iteration 1, revisit at 50+ tenants**.

**Math (HIGH confidence):**
- `daily_kpi`: 1 row per tenant per day = 365 rows/tenant/year
- `salesperson_daily_kpi`: 6 salespeople × 365 = 2,190 rows/tenant/year
- `source_daily_kpi`: ~10 sources × 365 = 3,650 rows/tenant/year

At 100 tenants over 3 years: ~620k rows. **Trivial for PostgreSQL with a B-tree index.** Partitioning adds operational complexity for zero query benefit at this scale.

### Indexes that ARE required (Iteration 1)

The SPEC already has:
```sql
CREATE INDEX ON daily_kpi (tenant_id, date DESC);
```

This is correct and sufficient. The leading `tenant_id` + descending `date` matches every dashboard query pattern (`WHERE tenant_id = ? AND date BETWEEN ? AND ? ORDER BY date DESC`).

**Add these for `raw_*` tables (HIGH confidence — query patterns from §11):**

```sql
-- Drill-down queries: "show me all leads from Facebook last week"
CREATE INDEX ON mefi_leads (tenant_id, source, created_at_source DESC);

-- Salesperson dashboard: "all deals closed by X last quarter"
CREATE INDEX ON mefi_deals (tenant_id, salesperson_id, closed_at_source DESC);

-- Anomaly rule "stuck offers": offers in status='sent' with no recent activity
CREATE INDEX ON mefi_offers (tenant_id, status, sent_at_source DESC)
    WHERE status = 'sent';  -- partial index, small and hot
```

### When to consider partitioning (future)

| Trigger | Action |
|---|---|
| `mefi_leads` > 10M rows | RANGE partition by `created_at_source` (monthly) |
| Single tenant > 100M lead history rows | LIST partition by `tenant_id` |
| Cold data > 90 days never queried | Partition + move old partitions to slower tablespace |

**BRIN index is not the right tool here.** BRIN is for append-only tables where the indexed column correlates with physical order. `daily_kpi` is small enough that B-tree wins on every dimension (lookup, range scan, index size). BRIN becomes interesting at 100M+ rows with strictly time-ordered inserts — not our case.

### Materialized views: skip for now

Dashboard queries against `daily_kpi` will be fast enough (single-digit ms) that materialized views add maintenance burden without benefit. Revisit if dashboard p95 > 500ms.

---

## 6. Component Architecture

### Component Boundaries

```
┌──────────────────────────────────────────────────────────────────┐
│  Frontend (Next.js 14)                                            │
│                                                                   │
│  Server Components (RSC)         Client Components ('use client') │
│  ─────────────────────          ──────────────────────────────── │
│  • Layout / routing              • TanStack Query hooks           │
│  • Auth check (JWT verify)       • Tremor charts                  │
│  • Prefetch via QueryClient      • Form interactions              │
│  • i18n provider (next-intl)     • Date range picker              │
│                                                                   │
└──────────────────────────────────┬───────────────────────────────┘
                                   │ HTTPS JSON (no SSR proxy needed)
                                   ▼
┌──────────────────────────────────────────────────────────────────┐
│  Backend HTTP (FastAPI, async)                                    │
│                                                                   │
│  api/v1/auth.py        api/v1/dashboards.py     api/v1/insights.py│
│       │                       │                        │          │
│       ▼                       ▼                        ▼          │
│  services/auth/        services/metrics/        services/insights/│
│  (JWT, password)       (query daily_kpi)        (read daily_insight)│
│       │                       │                        │          │
│       └───────────────────────┴────────────────────────┘          │
│                               │                                   │
│                               ▼                                   │
└──────────────────────────────────┬───────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────┐
│  PostgreSQL 16                                                    │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ tenants, users, integrations          (admin)              │  │
│  ├────────────────────────────────────────────────────────────┤  │
│  │ raw_* tables  +  raw_payload JSONB    (immutable copy)     │  │
│  ├────────────────────────────────────────────────────────────┤  │
│  │ v_leads, v_visits, ...                (conformed views)    │  │
│  ├────────────────────────────────────────────────────────────┤  │
│  │ daily_kpi, salesperson_daily_kpi, source_daily_kpi         │  │
│  ├────────────────────────────────────────────────────────────┤  │
│  │ detected_problems, daily_insights      (AI layer)          │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
└──────────────────────────────────▲───────────────────────────────┘
                                   │ asyncpg via SQLAlchemy 2.x
                                   │
┌──────────────────────────────────┴───────────────────────────────┐
│  Background Workers (Celery, prefork)                             │
│                                                                   │
│  Celery Beat (scheduler) ──► triggers daily pipeline @ 04:00 EEST│
│                                                                   │
│  Pipeline chain (per tenant):                                     │
│    sync_all_sources ─► calc_metrics ─► detect_anomalies          │
│                                              │                    │
│                                              ▼                    │
│                                       generate_insights ─► Claude │
│                                                                   │
│  Each task:                                                       │
│    • own asyncpg engine (per-worker, post-fork init)              │
│    • run_async() wraps async logic                                │
│    • idempotent (UNIQUE + ON CONFLICT, acks_late)                 │
└──────────────────────────────────────────────────────────────────┘
```

### Communication Rules

| From | To | Via | Notes |
|---|---|---|---|
| Frontend | Backend HTTP | HTTPS REST | TanStack Query manages cache; no GraphQL |
| Backend HTTP | PostgreSQL | asyncpg | Read-only for dashboards; never call external APIs |
| Backend HTTP | Celery | `task.delay()` for manual sync trigger | Returns task_id, frontend polls `/api/v1/tasks/{id}` |
| Celery Beat | Celery Worker | Redis broker | `chain()` for daily pipeline |
| Celery Worker | External APIs | httpx.AsyncClient | Only from tasks, never from HTTP handlers |
| Celery Worker | PostgreSQL | asyncpg (per-worker engine) | Upsert with ON CONFLICT |
| Celery Worker | Claude API | anthropic AsyncAnthropic | Only from `insights_generator` task |

**The hard rule:** FastAPI endpoints touch *only* PostgreSQL. Everything that crosses the network boundary goes through Celery + DB as buffer.

---

## 7. Data Flow

### Read path (user opens dashboard)

```
User opens /sales
  → Next.js Server Component prefetches /api/v1/dashboards/sales?from=...&to=...
    → FastAPI handler validates JWT, extracts tenant_id
      → services/metrics/sales.py SELECTs from daily_kpi WHERE tenant_id=? AND date BETWEEN ? AND ?
        → returns DTO (Pydantic schema)
  → HydrationBoundary serializes to client
  → Client Component renders Tremor charts from already-hydrated data
  → useQuery keeps data fresh (staleTime: 5 min — insights only change daily)
```

**Latency target:** < 200ms server-side. Pure SQL against indexed `daily_kpi`, single tenant, < 1000 rows.

### Write path (nightly pipeline)

```
04:00 EEST  Celery Beat fires `run_daily_pipeline(tenant_id, '2026-05-19')`
            └─► chain:
                ├─► sync_all_sources(tenant_id, date)
                │     └─► for each integration:
                │           ├─► sync_mefi_leads (httpx → MEFI API)
                │           ├─► sync_mefi_deals
                │           └─► ... (Meta/Google/TikTok in Iteration 2+)
                │         └─► INSERT INTO mefi_* ... ON CONFLICT DO UPDATE
                ├─► calculate_metrics(tenant_id, date)
                │     └─► INSERT INTO daily_kpi SELECT ... FROM v_leads JOIN v_deals ...
                ├─► detect_anomalies(tenant_id, date)
                │     └─► run 12 rule functions, INSERT INTO detected_problems
                └─► generate_insights(tenant_id, date)
                      └─► load context + problems + metrics
                      └─► await client.messages.parse(...)
                      └─► INSERT INTO daily_insights
```

**Failure semantics:** chain stops at first failed stage. Failed stage retries with exponential backoff (max 5). After 5 failures, alert fires (Sentry). Subsequent stages do not run — protects from generating insights on stale data.

### Refresh path (user clicks "Refresh insights")

```
POST /api/v1/insights/refresh
  → handler: rate-limit check (Redis: 1 req/hour/tenant)
  → handler: enqueue generate_insights.delay(tenant_id, today)
  → handler: returns 202 Accepted with task_id
  → frontend polls GET /api/v1/tasks/{id} every 2s
  → when complete, invalidates React Query cache for ['insights', today]
```

Manual refresh skips ETL/metrics/anomaly stages — works on existing `detected_problems`. This is correct: ad data does not change intraday.

---

## 8. Suggested Build Order

Given the architecture above, here's the dependency-driven phase ordering:

### Phase A: Foundation (no business logic)

1. **Docker Compose stack** — PostgreSQL 16, Redis 7, FastAPI placeholder, Next.js placeholder, Celery worker, Celery Beat
2. **Backend skeleton** — FastAPI app factory, async SQLAlchemy session, Alembic init, structlog config, Pydantic Settings
3. **Celery skeleton** — `celery_app.py`, `worker_process_init` signal for per-worker engine, `run_async()` helper, one `ping` task to validate the async/sync boundary works
4. **Frontend skeleton** — Next.js 14 App Router, TailwindCSS, shadcn init, TanStack Query provider, `getQueryClient()` per-request helper, next-intl with ro/en locales
5. **Auth** — `POST /auth/login`, JWT middleware, protected route group in Next.js

**Quality gate:** can log in, can `celery -A app.tasks.celery_app inspect ping`, can SELECT 1 from FastAPI handler.

### Phase B: MEFI ETL (highest-risk integration first)

6. **MEFI client** — `BaseIntegration` ABC, `MefiClient(httpx.AsyncClient)`, auth, pagination
7. **Raw layer** — Alembic migrations for `mefi_leads`, `mefi_lead_history`, `mefi_visits`, `mefi_offers`, `mefi_deals`, `mefi_calls`, `mefi_salespeople` (all from §5 of SPEC, with indexes from this doc §5)
8. **Conformed views** — `v_leads`, `v_visits`, `v_offers`, `v_deals` as Alembic migration
9. **Sync tasks** — one Celery task per entity, all with `acks_late`, `autoretry_for=httpx.HTTPError`, upsert via `pg_insert().on_conflict_do_update()`
10. **Pipeline chain** — `daily_pipeline.py` with chain primitive, Celery Beat schedule at 04:00 EEST
11. **`pipeline_runs` table** — append per-stage status row, enables "did today's pipeline succeed?" query

**Quality gate:** trigger `run_daily_pipeline.delay(tenant_id, today)` manually, see all 4 stages succeed (insights is a stub), verify row in `pipeline_runs`.

### Phase C: Metrics engine

12. **Daily KPI aggregator** — `services/metrics/daily.py` writes one row per `(tenant_id, date)` from views
13. **Salesperson KPI aggregator**
14. **Source KPI aggregator**
15. **Unit tests** — known-input/known-output for every formula (especially conversion rates with zero divisors)

**Quality gate:** load fixture of 1 month of fake MEFI data, run `calculate_metrics`, verify `daily_kpi.conversion_l_to_v` etc. match hand-computed values.

### Phase D: Anomaly detection

16. **Rules engine** — `services/anomaly_detection/rules.py` with one function per rule from SPEC §9
17. **Detector task** — loads metrics, runs rules, writes `detected_problems`
18. **Test fixtures** — synthetic `daily_kpi` rows that trigger each rule

**Quality gate:** synthetic "CPL doubled" data → produces `detected_problems` row with rule_id='cpl_increase'.

### Phase E: AI insights

19. **Pydantic schemas** — `DailyInsightResponse`, `Problem`, `Action` etc. from §4 of this doc
20. **Prompt builder** — Romanian system prompt, structured user prompt
21. **Claude client** — `messages.parse()` with `output_format=DailyInsightResponse`
22. **Insights task** — wire into pipeline chain
23. **Token & cost logging** — persist `tokens_used`, `llm_model` to `daily_insights`

**Quality gate:** end-to-end test with VCR-recorded Claude response → `daily_insights` row written.

### Phase F: Backend HTTP API for dashboards

24. **Dashboard endpoints** — `/dashboards/overview`, `/sales`, `/marketing`, `/salespeople`, `/salespeople/{id}` — all are pure read-from-`daily_kpi` queries
25. **Insights endpoints** — `/insights/today`, `/insights/by-date/{date}`, `/insights/refresh` (rate-limited)
26. **OpenAPI** — auto-generated from FastAPI; frontend uses `openapi-typescript` to generate TS types

**Quality gate:** Postman/HTTPie can hit every endpoint with seeded data, returns valid JSON matching OpenAPI schema.

### Phase G: Frontend dashboards

27. **API client** — `lib/api.ts` typed wrapper around fetch
28. **Query factories** — `lib/queries/{sales,marketing,salespeople,insights}.ts` with `queryOptions()` for type-safe prefetch + useQuery
29. **Pages** — Server Component prefetches, Client Component renders, in this order:
    - Overview (uses 6 KPI cards from daily_kpi — simplest)
    - Sales (funnel chart — most data)
    - Salespeople (table + detail page)
    - Marketing (placeholder for Iteration 2 channels)
    - **Insights** ⭐ (the headline feature — leave for last because design matters most)
30. **i18n** — `messages/ro.json`, `messages/en.json`, use `next-intl` `useTranslations()`

**Quality gate:** click through every page, no console errors, Romanian text everywhere, Tremor charts render seeded data.

### Phase H: Polish & ship

31. **E2E tests** — Playwright happy path
32. **Sentry** — backend + frontend
33. **Healthchecks** — `/healthz` + Celery heartbeat task
34. **Deploy** — Hetzner/Unihost, Caddy with Let's Encrypt
35. **Demo to Sofa Belle** — collect feedback

### Build-order rationale

- **Foundation first** because every subsequent phase depends on it
- **MEFI ETL before metrics** because metrics need data
- **Metrics before anomaly** because anomaly needs metrics
- **Anomaly before AI** because AI consumes `detected_problems`
- **Backend API before frontend** because frontend consumes API
- **Insights page last in frontend** because it is the highest-design-stakes page and benefits from feedback from the other pages first

---

## 9. Anti-Patterns to Avoid

### Anti-pattern: HTTP handler calling Claude or external APIs directly
**Why bad:** 30s latency, no retry, no rate limit protection, no idempotency.
**Instead:** Always enqueue Celery task, return 202 Accepted with task_id.

### Anti-pattern: Single-engine global for both web and worker
**Why bad:** asyncpg connections shared across forked Celery workers → deadlocks.
**Instead:** Per-worker engine init in `worker_process_init` signal.

### Anti-pattern: `Session.execute(text("SELECT * FROM mefi_leads"))`
**Why bad:** Bypasses ORM tenant filter (when implemented in Iteration 4), `SELECT *` breaks on schema changes.
**Instead:** Always go through ORM models, name columns explicitly.

### Anti-pattern: Parsing Claude output with `json.loads(response.content[0].text)`
**Why bad:** Claude can return prose around the JSON, schema drift, no validation.
**Instead:** `messages.parse(output_format=PydanticModel)` — schema-constrained at the SDK layer.

### Anti-pattern: Recomputing metrics on-demand inside dashboard endpoints
**Why bad:** SPEC's principle: "BD as buffer between external APIs and UI." Same applies to expensive aggregations.
**Instead:** All aggregation happens in `calculate_metrics` Celery task, dashboards SELECT from precomputed rows.

### Anti-pattern: Storing JWT in localStorage
**Why bad:** XSS-exfiltratable.
**Instead:** httpOnly cookie set by `/auth/login`, sent automatically by Next.js fetch.

### Anti-pattern: Treating the 4 daily cron schedules as independent
**Why bad:** If 03:00 ETL fails or runs long, 04:00 metrics runs on incomplete data, etc.
**Instead:** Single 04:00 cron, Celery `chain()` enforces ordering and stops on failure.

---

## 10. Scalability Considerations

| Concern | At 1 tenant (Sofa Belle) | At 10 tenants | At 100 tenants |
|---|---|---|---|
| `daily_kpi` rows | 365/year | 3.6k/year | 36k/year — still trivial |
| `mefi_leads` rows | ~5k/year | ~50k | ~500k — index sufficient, no partition |
| Celery pipeline duration | < 5min total | < 30min if serialized, < 5min if per-tenant queue | Sharded queues per tenant tier |
| Claude API spend | ~$1.50/month | ~$15/month | ~$150/month |
| Claude API rate limit | none | none | possible 50 req/min cap → stagger schedules |
| PostgreSQL size | < 100 MB | < 1 GB | ~10 GB — single instance fine |
| Redis | tiny | tiny | tiny (just broker + rate limit) |

**Conclusion:** the architecture as designed scales to 100 tenants on a single-VM deployment (Hetzner CX31 or similar). No fundamental rework needed until ~500 tenants.

**First scale bottleneck to watch (HIGH confidence):** Celery worker concurrency under serialized ETL. Solution: per-tenant queue routing, separate worker per queue, scale horizontally.

---

## 11. Open Questions for Subsequent Research

| Question | Why it matters | When to resolve |
|---|---|---|
| MEFI API rate limits | Determines whether ETL needs throttle | Phase B, after MEFI docs received |
| MEFI pagination model (cursor vs offset) | Affects sync task structure | Phase B |
| MEFI webhooks availability | If yes, switch from nightly poll to event-driven | Phase B+ |
| Claude API tier limits | 50 req/min default may force stagger at 100 tenants | Phase E |
| Sofa Belle's actual data volume | Validates "small" assumption — could change indexing | Phase B, after first full sync |
| Whether `funnel_config JSONB` per tenant is needed in MVP1 | SPEC has it; for single tenant might be over-engineering | Phase A — decide whether to skip column initially |

---

## Sources

| Source | Used for | Confidence |
|---|---|---|
| Context7 `/websites/celeryq_dev_en_stable` | Celery chain pattern, periodic tasks, timezone, prefork worker | HIGH |
| Context7 `/websites/sqlalchemy_en_20` | AsyncSession, run_sync, fork-safety warning, asyncpg cleanup | HIGH |
| Context7 `/anthropics/anthropic-sdk-python` | `messages.parse()` with Pydantic output_format | HIGH |
| Context7 `/websites/tanstack_query_v5` | Next.js App Router prefetch + HydrationBoundary pattern | HIGH |
| Context7 `/websites/postgresql_current` | BRIN index, date_bin, partitioning guidance | HIGH |
| Context7 `/tremorlabs/tremor` | Verified Tremor still current and Tailwind-based | MEDIUM (small snippet sample) |
| Project SPEC.md §4, §6, §7, §10 | Existing architecture intent | HIGH (project source of truth) |
| Project docs/ARCHITECTURE.md | Layer breakdown, daily cycle, async/sync note | HIGH |
| Project PROJECT.md | Iteration scope, deferred items, key decisions | HIGH |
