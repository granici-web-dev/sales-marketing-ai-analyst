# Technology Stack

**Project:** Sales & Marketing AI Analyst (Sofa Belle pilot)
**Researched:** 2026-05-19
**Mode:** Ecosystem (stack validation for greenfield)
**Overall confidence:** HIGH for backend; MEDIUM-HIGH for frontend (one significant flag on Tremor)

> This file VALIDATES the stack defined in `CLAUDE.md` and `docs/STACK.md`. It is **prescriptive** for versions to pin in `pyproject.toml` / `package.json` and surfaces gotchas the roadmap must address.

---

## TL;DR — What Changes vs. `docs/STACK.md`

| Decision in existing docs | Validation result | Action |
|---|---|---|
| Python 3.11+ | HIGH — keep as floor, but **target 3.12** in Docker (free-threaded GIL is 3.13t, not needed) | Pin Docker image to `python:3.12-slim` |
| FastAPI "latest" | HIGH — 0.136.x is current | Pin `fastapi>=0.136,<0.140` |
| SQLAlchemy 2.x | HIGH — 2.0.x line is the recommended async track | Pin `sqlalchemy[asyncio]>=2.0.40,<2.1` |
| `claude-sonnet-4-5` | **CHANGE** — `claude-sonnet-4-6` is the recommended migration target; `4-7` exists only as Opus | Already corrected in `PROJECT.md`. Use `claude-sonnet-4-6`. |
| Tremor (`@tremor/react`) | **FLAG** — npm package effectively maintenance-mode since Jan 2025 (v3.18.7). Tremor pivoted to "Tremor Raw" (copy-paste, like shadcn). | **Use shadcn/ui `chart` component (Recharts v3) instead**. See Frontend section. |
| Tailwind 3.x | **CHANGE** — Tailwind v4 (4.3.x) is stable, shadcn's `new-york-v4` registry targets it, and Next 16 supports it natively | Use Tailwind v4 from day 1 |
| Next.js 14 | **CHANGE** — Next.js 16 is the current LTS line (Next 14 is two majors behind, in security-fix mode) | Use Next.js 16. App Router patterns are unchanged. |
| React 18 | **CHANGE** — Next 16 ships with React 19 by default | Use React 19 |
| Flower (Celery monitor) | MEDIUM — last release Aug 2023; still works on Celery 5.6 but no recent updates | Keep for dev; consider Sentry Cron Monitors for prod |

The rest of the stack (Pydantic v2, asyncpg, httpx, structlog, ruff, mypy, Docker Compose) is **on the right path**. Specific version pins below.

---

## Recommended Stack — Backend

### Core (HIGH confidence)

| Package | Pin | Latest (2026-05) | Why |
|---|---|---|---|
| Python | `3.12` (Docker base) | 3.12.x stable | Mature, all libs support it, faster than 3.11. Skip 3.13 free-threaded (3.13t) — third-party C extensions still catching up. |
| `fastapi` | `>=0.136,<0.140` | 0.136.1 | Async, OpenAPI, Pydantic v2 native. 0.136 line is stable; bumps are weekly but non-breaking. |
| `uvicorn[standard]` | `>=0.47,<0.50` | 0.47.0 | ASGI server. `[standard]` pulls in `uvloop` + `httptools` for ~20% throughput gain. |
| `gunicorn` | `>=26,<27` | 26.0.0 | Production process manager wrapping uvicorn workers. Replaces `python -m uvicorn` in prod. |
| `pydantic` | `>=2.13,<3` | 2.13.4 | Validation, serialization. v2 is ~10× faster than v1. |
| `pydantic-settings` | `>=2.14,<3` | 2.14.1 | Typed config from `.env`. **Required** — do not use raw `os.getenv`. |
| `sqlalchemy[asyncio]` | `>=2.0.40,<2.1` | 2.0.49 | ORM. Stay on 2.0.x line — 2.1 is not released yet and the async ergonomics are mature on 2.0. |
| `alembic` | `>=1.18,<2` | 1.18.4 | Schema migrations. Configure with `script_location` and `target_metadata` only — no auto-execution in app code. |
| `asyncpg` | `>=0.31,<0.32` | 0.31.0 | Fastest async PG driver. Connect string: `postgresql+asyncpg://...`. |
| `psycopg[binary]` | `>=3.3,<4` (dev only) | 3.3.4 | Sync driver for Alembic migrations and one-off scripts. Use `psycopg` (v3), **not** `psycopg2-binary`. |
| `greenlet` | `>=3.5` (transitive) | 3.5.0 | Required by SQLAlchemy async — pin explicitly to avoid resolver surprises. |
| `httpx` | `>=0.28,<0.29` | 0.28.1 | Async HTTP. **Always** instantiate one shared `httpx.AsyncClient` per integration (not per request) — TCP pool reuse matters. |
| `structlog` | `>=25.5,<26` | 25.5.0 | JSON logging. Configure once at startup; bind `tenant_id` / `request_id` via contextvars. |

### Task Queue (HIGH confidence)

| Package | Pin | Latest | Why |
|---|---|---|---|
| `celery[redis]` | `>=5.6,<6` | 5.6.3 | Distributed task queue. The `[redis]` extra pulls in `redis-py` properly. |
| `redis` | `>=7.4,<8` | 7.4.0 | Both Celery broker AND general cache. Server version: 7.x (Docker `redis:7-alpine`). |
| `celery-redbeat` | `>=2.3,<3` | 2.3.3 | **Replace the default file-based Beat scheduler with RedBeat.** File-based Beat loses schedule state on restart and corrupts on concurrent writers. RedBeat stores schedule in Redis — survives restarts, supports multiple Beat instances safely. |
| `kombu` | (transitive) | 5.6.2 | Pulled by Celery; mention only because pinning Celery 5.6+ requires kombu 5.6+. |
| `flower` | `>=2.0,<3` (dev) | 2.0.1 (2023) | Monitoring UI. **Concern:** no release in 2.5 years. Works on Celery 5.6 but unmaintained. Keep for dev convenience; for prod observability rely on Sentry + Prometheus exporters instead. |

### AI (HIGH confidence)

| Package | Pin | Latest | Why |
|---|---|---|---|
| `anthropic` | `>=0.103,<0.110` | 0.103.0 | Official SDK with `AsyncAnthropic` client. Releases are frequent (~weekly); keep a wider upper bound. |
| Model alias | `claude-sonnet-4-6` | — | Confirmed via Context7 (Anthropic platform docs, 2026-05). Sonnet 4.6 is the recommended migration target from 4.5. Opus 4.7 is overkill and ~3× cost for this workload. |

### Security & Auth (HIGH confidence)

| Package | Pin | Latest | Why |
|---|---|---|---|
| `cryptography` | `>=48,<49` | 48.0.0 | For `Fernet` (encrypting external API credentials at rest, per `CLAUDE.md` rule 4). |
| `pyjwt[crypto]` | `>=2.10,<3` | 2.10.x | JWT for the basic auth requirement. **Do not use `python-jose`** — last meaningful release in 2025, fewer maintainers, weaker test coverage. |
| `bcrypt` | `>=5,<6` | 5.0.0 | Password hashing (if any local auth users exist). |
| `passlib` | **avoid** | 1.7.4 (2020!) | Last release 2020. Dead. Use `bcrypt` directly or `argon2-cffi`. |

### Resilience / Retry (NEW — not in `docs/STACK.md`)

| Package | Pin | Latest | Why |
|---|---|---|---|
| `tenacity` | `>=9.1,<10` | 9.1.4 | Retry decorator for **idempotent** operations inside Celery tasks (e.g. MEFI 5xx). Pairs well with structured logging. Prefer over `backoff` (which had a quiet 2022-onwards). |
| `httpx-retries` | `>=0.5,<1` (optional) | 0.5.0 | Drop-in `httpx` transport that adds retries with backoff. Use if you want declarative retries at the transport layer rather than per-call. |

> **Don't add both** — pick `tenacity` for clarity (it's also useful outside HTTP, e.g. Redis lock acquisition). `httpx-retries` only if the codebase grows many one-off HTTP calls.

### Observability (NEW — partly in `docs/STACK.md`)

| Package | Pin | Latest | Why |
|---|---|---|---|
| `sentry-sdk[fastapi,celery,sqlalchemy]` | `>=2.60,<3` | 2.60.0 | Error tracking + performance traces. Extras auto-instrument framework + worker. |
| `prometheus-fastapi-instrumentator` | (optional) | — | Metrics endpoint for Prometheus scraping. Defer to Iteration 4. |

### Testing & Quality (HIGH confidence)

| Package | Pin | Latest | Why |
|---|---|---|---|
| `pytest` | `>=9,<10` | 9.0.3 | Test framework. v9 dropped Python 3.8 support, fine on 3.12. |
| `pytest-asyncio` | `>=1.3,<2` | 1.3.0 | Async test mode. Set `asyncio_mode = "auto"` in `pyproject.toml`. |
| `pytest-cov` | `>=7.1,<8` | 7.1.0 | Coverage reporting. Aim for 70%+ on services/, 50%+ overall. |
| `factory_boy` | `>=3.3,<4` | 3.3.3 | Test fixtures. |
| `freezegun` | `>=1.5,<2` | 1.5.5 | Time mocking for daily KPI tests. |
| `respx` | `>=0.21` | recent | **Add** — mock `httpx` calls in tests. Critical for testing MEFI/Meta/Google integrations without network. |
| `ruff` | `>=0.15,<0.20` | 0.15.13 | Linter + formatter. Replaces black, isort, flake8, pyupgrade. |
| `mypy` | `>=2.1,<3` | 2.1.0 | Type checker. v2 is significantly faster and stricter than v1. Configure with `strict = true` for `app/`. |
| `uv` | `>=0.11` | 0.11.15 | Package manager. ~10× faster than pip; locks via `uv.lock`. |
| `pre-commit` | `>=4.6,<5` | 4.6.0 | Hook runner. |
| `gitleaks` | (binary, pre-commit hook) | latest | Secret scanning. Required by `CLAUDE.md`. |

---

## Recommended Stack — Frontend

### Core (HIGH confidence, with one CHANGE from docs)

| Package | Pin | Latest (2026-05) | Why |
|---|---|---|---|
| `next` | `^16.2` | 16.2.6 | **Upgrade from Next 14 in `docs/STACK.md`.** Next 14 is in security-fix-only mode; Next 16 is the current LTS line. App Router code from a fresh Next 14 project carries over with minimal changes. Use the App Router — Pages Router is legacy. |
| `react` / `react-dom` | `^19.2` | 19.2.6 | Ships with Next 16. Server Components, Actions, `use()` API are all production-stable now. |
| `typescript` | `^6` | 6.0.3 | TS 6 is current; strict mode required. |
| `tailwindcss` | `^4.3` | 4.3.0 | **Upgrade from Tailwind 3.x in `docs/STACK.md`.** v4 has a new engine (Lightning CSS), no `tailwind.config.js` required (CSS-first config), faster builds. shadcn's `new-york-v4` registry targets v4. Next 16 supports v4 out of the box. |
| `shadcn` (CLI) | `^4.7` | 4.7.0 | Component installer. Use `npx shadcn@latest init --registry new-york-v4`. |

### Data & State (HIGH confidence)

| Package | Pin | Latest | Why |
|---|---|---|---|
| `@tanstack/react-query` | `^5.100` | 5.100.11 | Server state. Use `QueryClient` with `staleTime: 60_000` default for dashboard data (refetched daily). |
| `zustand` | `^5` | 5.0.13 | Client state (UI: filters, date range pickers, modal state). Lightweight, no Redux ceremony. |
| `next-intl` | `^4.12` | 4.12.0 | i18n. Required for Romanian primary / English fallback. App Router native, type-safe message keys. |

### Charts — **MAJOR CHANGE from `docs/STACK.md`** (HIGH confidence flag)

**Recommendation:** Use **shadcn/ui `chart` component (Recharts v3 under the hood)**, NOT `@tremor/react`.

**Evidence for the change:**
- `@tremor/react` last npm release: **v3.18.7 on 2025-01-13** — 16 months stale as of research date.
- Tremor's v4 was published as `4.0.0-beta-tremor-v4.x` in Dec 2024 and abandoned.
- The Tremor team pivoted to "Tremor Raw" — copy-paste Tailwind+Radix components (same pattern as shadcn/ui). The `tremor-raw` repo last push was Jan 2025; only 3 stars; effectively superseded.
- The main `tremorlabs/tremor` repo (the design-system-with-blocks) was last pushed Oct 2025 but has not shipped a new npm package.
- Meanwhile, **shadcn/ui added a first-class `chart` component** built on Recharts v3 with `ChartContainer`, `ChartTooltipContent`, `ChartLegendContent`, `ChartConfig` — covering bar, line, area, pie, radar, radial, and interactive charts. Actively maintained, matches Tailwind v4, owns the code (per shadcn philosophy).

**Stack for charts:**

| Package | Pin | Latest | Why |
|---|---|---|---|
| `recharts` | `^3.8` | 3.8.1 | Chart engine. shadcn `chart` component wraps Recharts. |
| `shadcn` chart component | (copy-pasted via CLI) | — | `npx shadcn@latest add chart` |
| `date-fns` | `^4.2` | 4.2.1 | Date manipulation for chart axes and KPI windows. |

If a chart type is missing (e.g. funnel), drop down to raw Recharts or `@nivo/funnel` (well-maintained). **Do not** install `@tremor/react`.

### Forms (HIGH confidence)

| Package | Pin | Latest | Why |
|---|---|---|---|
| `react-hook-form` | `^7.76` | 7.76.0 | Form state, performant. |
| `zod` | `^4.4` | 4.4.3 | Schema validation, integrates via `@hookform/resolvers/zod`. v4 unified `z.string()` → `z.string()` API; small migration if porting v3 code. |
| `@hookform/resolvers` | latest | — | Glue between RHF and Zod. |

### Testing (HIGH confidence)

| Package | Pin | Latest | Why |
|---|---|---|---|
| `vitest` | `^4.1` | 4.1.6 | Fast Vite-native test runner. v4 is current line. |
| `@testing-library/react` | latest | — | Component testing. |
| `playwright` | `^1.60` | 1.60.0 | E2E. Defer until Iteration 1 ships a real dashboard. |

### Code Quality

| Package | Pin | Latest | Why |
|---|---|---|---|
| `eslint` | `^10` (via Next 16 config) | 10.4.0 | Linter. Next 16 ships its own ESLint config. |
| `prettier` | `^3.8` | 3.8.3 | Formatter. |

### Package Manager

| Tool | Why |
|---|---|
| `pnpm` | Already in `docs/STACK.md`. Stay with it — faster than npm, less disk than yarn, content-addressed store works well in Docker layers. |

---

## Database

| Tool | Version | Why |
|---|---|---|
| PostgreSQL | **16** (Docker `postgres:16-alpine`) | Mature, JSONB, partial indexes, generated columns. v17 is out but no compelling feature for this workload yet. |
| Redis | **7** (Docker `redis:7-alpine`) | Celery broker + RedBeat schedule store + general cache. v8 exists but Celery's redis-py compat is best validated on 7.x. |
| pgvector | **NOT NEEDED** in MVP1-3 | Spec doesn't require embeddings/RAG. AI insights are generated from structured KPI data, not from semantic retrieval over a doc corpus. Add only if/when "explain why this lead stalled" requires similarity search. |
| TimescaleDB | **NOT NEEDED** in MVP1-3 | Daily KPI rollups in Postgres handle the volume (single tenant, ~hundreds of leads/month). Re-evaluate at 10+ tenants. |

---

## Infrastructure

### Development

| Tool | Why |
|---|---|
| Docker Compose v2 | Multi-service local dev. Services: `postgres`, `redis`, `backend`, `worker`, `beat`, `flower`, `frontend`. |
| `uv` | Python package manager. |
| `pnpm` | Node package manager. |

### Production

| Tool | Why |
|---|---|
| Hetzner (EU) | Already chosen; good price/perf, GDPR-friendly. |
| Caddy | Auto SSL, simpler config than nginx for the use case. |
| Docker Compose | Single-host orchestration. Premature to introduce K8s. |
| Sentry | Errors + cron monitors. **Use the Cron Monitors feature** to alert if the 03:00 MEFI sync or 06:00 insights task fails to start. |

### CI/CD

| Tool | Why |
|---|---|
| GitHub Actions | Standard. |
| GitHub Container Registry | Push backend + frontend images here. |

---

## Critical Stack Combination Gotchas

These are the issues most likely to cost the project days if not anticipated. Each is HIGH confidence (verified against Context7/official docs).

### 1. SQLAlchemy async + Celery sync boundary

Celery workers run sync by default. `AsyncSession` cannot be awaited from a sync Celery task without bridging.

**Two valid approaches — pick ONE and stick to it:**

**Option A (recommended): `asyncio.run()` per task.**

```python
@celery_app.task(bind=True)
def sync_mefi_leads(self, tenant_id: int) -> None:
    asyncio.run(_sync_mefi_leads_async(tenant_id))

async def _sync_mefi_leads_async(tenant_id: int) -> None:
    async with AsyncSessionLocal() as session:
        ...
```

Pros: clear sync/async boundary, each task gets a fresh event loop, simple.
Cons: small overhead spinning up the loop per task (~1ms — negligible vs network I/O).

**Option B: dedicated async worker pool (`celery -P gevent`)** — adds operational complexity; **not recommended** for this project.

**What NOT to do:** call `loop.run_until_complete()` against a long-lived event loop in the worker — leads to "Event loop is closed" errors when Celery retries the task.

### 2. Celery Beat schedule durability

The default `PersistentScheduler` writes to a local `celerybeat-schedule.db` file. Problems:
- Lost on container restart unless mounted as a volume.
- Corrupted if two Beat processes ever run simultaneously.
- No way to safely add/remove schedules at runtime.

**Fix:** Use **`celery-redbeat`** from day one. Set `beat_scheduler = "redbeat.RedBeatScheduler"`. Schedules live in Redis. Multiple Beat processes coordinate via Redis lock. Schedule changes propagate immediately.

### 3. asyncpg + pgbouncer (future risk)

If/when the project deploys behind pgbouncer in **transaction pooling mode**, `asyncpg` will break on prepared statements (which it uses by default). Fix: pass `statement_cache_size=0` in the `create_async_engine` `connect_args`. Not an MVP1 concern (no pgbouncer), but document it now to avoid surprises in Iteration 4.

### 4. Pydantic v2 settings + secrets

`pydantic-settings` reads `.env` but does **not** automatically encrypt anything. Per `CLAUDE.md` rule 4, API credentials stored in the DB must be Fernet-encrypted before insert and decrypted on read. Centralise this in a `SecretsService` — do **not** decrypt in models or routers.

### 5. Next 16 + Tailwind v4 + shadcn

The shadcn registry has **two variants**: `new-york` (Tailwind 3) and `new-york-v4` (Tailwind 4). Initialise with `npx shadcn@latest init --registry new-york-v4` or you'll mix component versions. Same applies to `add` commands.

### 6. httpx connection pool lifetime

Creating a new `httpx.AsyncClient()` per request defeats TCP pooling and triples MEFI sync latency. **Pattern:** one shared client per integration class, instantiated in `BaseIntegration.__init__`, closed in a FastAPI `lifespan` handler (for the API process) and in a Celery `worker_shutdown` signal handler (for workers).

### 7. structlog + Celery worker context

Celery workers reset contextvars between tasks. Bind `tenant_id`, `task_id`, `task_name` at the start of every task using a custom Celery signal (`task_prerun`). Otherwise logs from inside tasks lose tenant context.

### 8. Tremor abandonment is a load-bearing risk in `docs/STACK.md`

This is the #1 outdated decision in the existing docs. If the team blindly installs `@tremor/react`, they get a 16-month-stale package with peer-dep warnings against React 19 / Next 16 / Tailwind 4. **Roadmap must explicitly call out shadcn `chart` as the chart layer**, ideally in Iteration 0 (foundation).

---

## Installation — Reference Commands

### Backend bootstrap

```bash
cd backend
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e ".[dev]"
```

`pyproject.toml` dependencies block (target):

```toml
[project]
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.136,<0.140",
    "uvicorn[standard]>=0.47,<0.50",
    "gunicorn>=26,<27",
    "pydantic>=2.13,<3",
    "pydantic-settings>=2.14,<3",
    "sqlalchemy[asyncio]>=2.0.40,<2.1",
    "alembic>=1.18,<2",
    "asyncpg>=0.31,<0.32",
    "psycopg[binary]>=3.3,<4",
    "greenlet>=3.5",
    "httpx>=0.28,<0.29",
    "structlog>=25.5,<26",
    "celery[redis]>=5.6,<6",
    "redis>=7.4,<8",
    "celery-redbeat>=2.3,<3",
    "anthropic>=0.103,<0.110",
    "cryptography>=48,<49",
    "pyjwt[crypto]>=2.10,<3",
    "bcrypt>=5,<6",
    "tenacity>=9.1,<10",
    "sentry-sdk[fastapi,celery,sqlalchemy]>=2.60,<3",
]

[project.optional-dependencies]
dev = [
    "pytest>=9,<10",
    "pytest-asyncio>=1.3,<2",
    "pytest-cov>=7.1,<8",
    "factory_boy>=3.3,<4",
    "freezegun>=1.5,<2",
    "respx>=0.21",
    "ruff>=0.15,<0.20",
    "mypy>=2.1,<3",
    "pre-commit>=4.6,<5",
    "flower>=2.0,<3",
]
```

### Frontend bootstrap

```bash
cd frontend
pnpm create next-app@16 . --typescript --tailwind --app --eslint --src-dir
pnpm add @tanstack/react-query@^5.100 zustand@^5 next-intl@^4.12 \
        react-hook-form@^7.76 zod@^4.4 @hookform/resolvers \
        recharts@^3.8 date-fns@^4.2
pnpm add -D vitest@^4.1 @testing-library/react @testing-library/jest-dom \
            playwright@^1.60 prettier@^3.8

# shadcn (Tailwind v4 registry)
npx shadcn@latest init --registry new-york-v4
npx shadcn@latest add button card chart input form select dialog table tabs
```

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|---|---|---|---|
| Charts | shadcn/ui `chart` (Recharts v3) | `@tremor/react` | Abandoned npm package, 16 months stale, peer-dep issues with React 19 |
| Charts | shadcn/ui `chart` (Recharts v3) | `@nivo/*` | Heavier (~120kB extra), overkill for KPI dashboards. Acceptable as a fallback for funnel charts only. |
| Task queue | Celery 5.6 + RedBeat | `arq` (async-native) | `arq` is simpler and async-native (no sync boundary issue), but smaller ecosystem, no Flower equivalent, no proven track record at SaaS scale. Keep Celery. |
| HTTP retries | `tenacity` | `backoff` | `backoff` last shipped Oct 2022. `tenacity` is actively maintained. |
| HTTP retries | `tenacity` | `httpx-retries` | OK to use, but `tenacity` is more flexible (covers Redis ops, Anthropic calls, etc.) |
| JWT | `pyjwt[crypto]` | `python-jose` | Smaller maintainer base, slower release cadence. |
| Password hashing | `bcrypt` direct | `passlib` | passlib unmaintained since 2020. |
| PG sync driver | `psycopg` v3 | `psycopg2-binary` | psycopg2 is in maintenance mode. v3 is the active line and has better type stubs. |
| Settings | `pydantic-settings` v2 | `dynaconf` | Pydantic-native, fewer deps, type-safe by default. |
| Frontend tests | Vitest 4 | Jest | Vitest is faster, native to Vite ecosystem, better TS support. |
| Date library | `date-fns` v4 | Day.js | Both fine; `date-fns` integrates more naturally with chart formatters. |
| State (server) | TanStack Query | SWR | Both excellent; TanStack has richer mutation API for the few write paths (e.g. "mark insight as actioned"). |
| State (client) | Zustand | Redux Toolkit | Zustand has 10% of the boilerplate for a dashboard this size. |
| Logging | structlog | loguru | structlog has better Celery + FastAPI integration patterns and predictable JSON output. |

---

## Confidence Assessment per Decision

| Decision | Confidence | Source |
|---|---|---|
| Python 3.12 floor | HIGH | PyPI release data, ecosystem support |
| FastAPI 0.136+ | HIGH | PyPI + Context7 docs |
| SQLAlchemy 2.0 async + asyncpg | HIGH | Context7 official docs |
| Celery 5.6 + RedBeat | HIGH | Celery docs (Context7), redbeat changelog |
| `claude-sonnet-4-6` model | HIGH | Anthropic platform docs via Context7 (verified 2026-05-19) |
| Replace Tremor → shadcn chart | HIGH | npm registry data (last release date), shadcn docs (Context7) |
| Tailwind v4 + Next 16 + React 19 | HIGH | npm registry data, Next 16 release notes |
| `pyjwt` over `python-jose` | MEDIUM | Release cadence comparison; both work technically |
| `psycopg` v3 over psycopg2 | HIGH | Official psycopg docs |
| `tenacity` over `backoff` | HIGH | Last-release dates |
| Skip pgvector/TimescaleDB for MVP | HIGH | Project scope (single tenant, hundreds of leads) |
| Async/Celery bridging via `asyncio.run` | HIGH | SQLAlchemy docs (Context7) + Celery docs |

---

## What This Implies for the Roadmap

1. **Iteration 0 (foundation) must explicitly:**
   - Pin Python 3.12 in Docker.
   - Configure Celery to use `redbeat.RedBeatScheduler` (not default file scheduler).
   - Initialise shadcn with the `new-york-v4` registry.
   - Reject any PR that adds `@tremor/react` or `passlib` or `python-jose`.
   - Establish the `asyncio.run()` Celery task pattern as the convention.

2. **A "stack hygiene" task should be revisited at every iteration boundary:**
   - Bump FastAPI, Pydantic, anthropic SDK (weekly releases).
   - Re-check Tremor status — if Tremor v4 finally ships and stabilises, reconsider.
   - Re-check Claude model deprecations (Sonnet 4.0 / Opus 4 are already deprecation-scheduled for late 2026).

3. **Iteration 4 (multi-tenancy) prerequisites already in stack:**
   - SQLAlchemy event listeners exist for global query filters.
   - structlog contextvars enable per-tenant log binding.
   - No stack change needed — only application-layer code.

---

## Sources

- Anthropic platform docs (model IDs) — via Context7 `/websites/platform_claude_en`, accessed 2026-05-19
- FastAPI docs — via Context7 `/fastapi/fastapi`
- SQLAlchemy 2.0 async docs — via Context7 `/websites/sqlalchemy_en_20`
- Celery docs (Beat scheduler) — via Context7 `/websites/celeryq_dev_en_stable`
- shadcn/ui chart component — via Context7 `/websites/ui_shadcn`
- Tremor status — npm registry `@tremor/react` (last release 2025-01-13), GitHub `tremorlabs/tremor` (last push 2025-10-10, no release)
- All version numbers — PyPI JSON API and npm registry, queried 2026-05-19
- Next.js release notes — GitHub `vercel/next.js` releases API
