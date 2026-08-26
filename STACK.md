# STACK.md

Reverse-engineered from manifests and source on **2026-08-25**
(`/rigorous document`). Versions are quoted exactly as pinned.

---

## Backend

| Concern | Choice | Pin |
|---|---|---|
| Language | Python | `>=3.11` (ruff target `py311`) |
| HTTP framework | FastAPI | `>=0.111,<1` |
| ASGI server | uvicorn[standard] | `>=0.29,<1` |
| ORM / query layer | SQLAlchemy 2 (async) | `>=2.0,<3` |
| Driver | asyncpg | `>=0.29,<1` |
| Migrations | Alembic | `>=1.13,<2` |
| Validation | Pydantic 2 + pydantic-settings | `>=2.7,<3` / `>=2.3,<3` |
| Background work | Celery[redis] | `>=5.4,<6` |
| Scheduler | celery-redbeat | `>=2.2,<3` |
| Cache / broker | Redis | `>=5,<6` |
| Logging | structlog | `>=24,<26` |
| LLM | anthropic | `>=0.30,<1` |
| Auth | PyJWT + bcrypt | `>=2.8,<3` / `>=4.0` |
| HTTP client | httpx | `>=0.27,<1` |
| Lint | ruff, line-length 100 | — |
| Tests | pytest + pytest-asyncio (`asyncio_mode = auto`) | `>=0.21,<1` |

## Frontend

| Concern | Choice | Pin |
|---|---|---|
| Framework | Next.js (App Router) | `16.2.6` exact |
| Runtime | React | `^19.2.0` |
| Language | TypeScript, `strict: true` | `^6.0.3` |
| Styling | Tailwind CSS v4 + `@tailwindcss/postcss` | `^4.3.0` |
| Components | Radix primitives, shadcn-style local components | `^1.4.3` |
| Charts | Recharts | `^3.8.0` |
| Server state | TanStack Query | `5.100.11` exact |
| Client state | zustand | `5.0.13` exact |
| Forms | react-hook-form + zod + @hookform/resolvers | `7.76.0` / `4.4.3` |
| i18n | next-intl | `4.12.0` exact |
| Tokens | jose | `6.2.3` exact |
| Tests | vitest + Testing Library + jsdom | `^4.1.7` |
| Package manager | pnpm | `10.34.5` via `packageManager` |

## Infrastructure

Docker Compose with seven services: postgres, redis, backend, worker, beat,
flower, frontend. `docker-compose.prod.yml` is a thin override that drops
`--reload` and the source bind mounts; it is explicitly a skeleton.

---

## Decisions

**celery-redbeat instead of Celery's default Beat scheduler.** The default keeps
its schedule in a local file, which does not survive a container restart and
cannot be shared between replicas. redbeat keeps it in Redis, which is already a
dependency.

**One `chain()` for the daily pipeline, not four independent cron jobs.**
`sync_mefi_leads → calculate_daily_kpis → detect_anomalies →
generate_daily_insights`, every step `.si()` (immutable). A failure halts the
chain instead of computing insights over metrics that were never refreshed. The
immutability matters: a mutable signature would make Celery prepend the previous
step's return value, and every task in this chain takes `tenant_id` first.

**Raw `text()` for analytics, ORM for entities.** 41 raw-SQL sites, all in
metric and dashboard services. Window functions and multi-CTE funnel queries do
not read better through the ORM. Entity access (users, conversations, messages)
stays on the ORM.

**Engine created per worker process, never before the fork.** asyncpg sockets
cannot cross a `fork()`. `app.db.session` is imported *inside* the
`worker_process_init` handler, and the handler disposes the inherited pool and
rebuilds the engine plus session factory. `AsyncSessionLocal` is therefore
rebound at runtime: resolve it through the module, never `from … import`.

**Anthropic client instantiated inside request scope, never at module level.**
Same fork-safety reason, plus test patchability. `AsyncAnthropic` is imported at
module level so tests can patch it, but constructed inside the handler body.

**Streaming chat is a documented exception to the batch-only LLM rule.** Every
other Claude call is a batch job in a worker. `/chat` uses FastAPI
`StreamingResponse` with the async client and tool use, and reuses the Phase 6
metric services as tool backends rather than issuing its own SQL.

**"Ever reached" funnel semantics.** A lead counts as having reached a stage if
it ever passed through it, derived in a SQL view from current status plus
transition history — not "currently in". A lead that moved on has still visited.

**Single-tenant with the multi-tenant seam built in.** `tenant_id` is on every
table, `TenantScopedMixin` is the target of a `with_loader_criteria` filter, and
the current tenant lives in a `ContextVar`. Today that ContextVar is set to a
hardcoded UUID at startup; Iteration 4 sets it from the JWT. The seam exists so
the change is one line rather than a rewrite.

---

## Anti-choices

**No CI.** There is no `.github/workflows`, no `.gitlab-ci.yml`, nothing.
The 511-test suite runs only when someone runs it. Not a decision so much as an
absence — Phase 9 is where it lands.

**No Tremor.** Replaced by shadcn's chart wrapper over Recharts v3 during Phase
7. The shadcn components are vendored locally rather than installed, because the
CLI was unavailable.

**No call transcription.** Explicitly out of scope; the client's telephony
vendor does it. This product is about the whole funnel, not conversations.

**No dashboard parity with MEFI BI.** The CRM already shows raw numbers. This
product interprets them; duplicating the charts would be the wrong product.

**No revenue from MEFI.** Not a preference — `estimated_value` is NULL for all
1 238 leads, verified against the live API on 2026-08-25. Revenue, CAC and ROAS
come from a monthly spreadsheet import, and per-source revenue is therefore
unobtainable in principle.

**No `git`-tracked package store.** `frontend/.pnpm-store` was 98 % of tracked
files until it was cut from history on 2026-08-25; it is now ignored.
