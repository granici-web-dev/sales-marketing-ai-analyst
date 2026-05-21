# Phase 1: Foundation - Context

**Gathered:** 2026-05-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Working development environment where all infrastructure pieces (web, worker, scheduler, database, cache, frontend) start with one command, and a user can log in to a protected route.

This phase produces: Docker Compose stack, FastAPI async skeleton, Celery+celery-redbeat, Next.js 16 scaffold with full sidebar shell, JWT auth with HttpOnly cookie, next-intl i18n, SQLAlchemy multi-tenancy seam, and base Alembic migrations.

**Does NOT include:** any MEFI data, metrics, or dashboard content (those are Phases 2–7).

</domain>

<decisions>
## Implementation Decisions

### JWT Auth Flow

- **D-01:** JWT stored as HttpOnly cookie. Access token returned in JSON response body for programmatic use; refresh token set as HttpOnly `Set-Cookie`. Next.js interceptor reads the access token from the cookie header.
- **D-02:** Token refresh is interceptor-based — API client catches 401, calls `POST /api/v1/auth/refresh` (refresh token sent automatically via cookie), retries the original request. Transparent to the UI.
- **D-03:** Next.js route protection via `proxy.ts` — reads JWT access token cookie server-side, redirects to `/login` before any rendering. No flash of protected content.
  > **Technical amendment (approved):** Original decision said `middleware.ts`, but Next.js 16 introduced a breaking rename: `middleware.ts` → `proxy.ts` and `export function middleware` → `export function proxy`. The implementation correctly uses `proxy.ts` per RESEARCH.md findings. The `edge` runtime is not supported; `proxy.ts` runs on `nodejs`. This is a framework-mandated change, not a scope change.
- **D-04:** Auth endpoints: `POST /api/v1/auth/login` → returns `{access_token, token_type}` in JSON body + sets `refresh_token` HttpOnly cookie. `POST /api/v1/auth/refresh` → validates refresh cookie, returns new access token + rotates refresh cookie.

### Multi-Tenancy Seam

- **D-05:** SQLAlchemy tenant context set via a **hardcoded Sofa Belle UUID** stored as a Python `contextvars.ContextVar`. The `StructlogContextMiddleware.__call__` (per-request ASGI middleware) sets this on every request before dispatching — NOT in the lifespan event (ContextVars set in lifespan do not propagate to HTTP request coroutines). The `with_loader_criteria` seam reads from the context var. One-line swap in Iteration 4 when JWT carries `tenant_id`.
- **D-06:** Phase 1 **must include a failing test** that proves the SQLAlchemy session factory rejects a query when no tenant context is set — matches SC#6 exactly. This test is a required deliverable, not optional.
- **D-07:** Initial Sofa Belle tenant + admin user provisioned via **Alembic data migration** — idempotent `INSERT ... ON CONFLICT DO NOTHING`. Runs automatically at `alembic upgrade head`. No separate seed script required.

### Docker Service Topology

- **D-08:** Docker Compose runs **6 backend services** as separate containers: `postgres`, `redis`, `backend` (FastAPI/uvicorn), `worker` (Celery), `beat` (celery-redbeat), `frontend` (Next.js dev server). Worker and beat are separate — never combined.
- **D-09:** **Flower** included from Phase 1 on port 5555 — useful for debugging Celery tasks during Phase 2 MEFI ETL development.
- **D-10:** `depends_on` with `condition: service_healthy` — postgres and redis must pass healthcheck before backend/worker/beat start. Prevents race conditions on first `docker compose up -d`.

### Frontend Scaffold

- **D-11:** **Full shell layout scaffolded in Phase 1** — sidebar + topbar + main content area as a shared layout. Phase 7 fills the page content; the layout skeleton is ready from Phase 1.
- **D-12:** All 8 navigation items from **SPEC.md §13.1** wired as placeholder routes with active links and "În curând" (Coming soon) placeholder content:
  - 🏠 Overview → `/`
  - 📈 Marketing → `/marketing`
  - 💼 Sales → `/sales`
  - 👥 Salespeople → `/salespeople`
  - 💡 Insights → `/insights`
  - 💬 Chat → `/chat` (Phase 8 placeholder)
  - ⚙️ Integrations → `/integrations`
  - 👤 Profile/Settings → `/settings`
- **D-13:** **next-intl configured with Romanian (`ro`) as default locale** from Phase 1. Login page and sidebar labels have Romanian translation strings. Translation file pattern established so Phase 7 adds strings without restructuring.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — Full requirement list; Phase 1 covers INFRA-01..06, AUTH-01..03, UI-01, PIPE-04
- `.planning/ROADMAP.md` — Phase 1 success criteria (6 items, SC#1–SC#6) — all must be verifiable

### Architecture & Stack
- `docs/ARCHITECTURE.md` — High-level system architecture, async/sync boundary, layer responsibilities
- `docs/STACK.md` — Technology choices and versions; note: STATE.md overrides some entries (see below)
- `docs/CONVENTIONS.md` — Code style, naming conventions, commit format — mandatory reading before writing any code

### Stack Overrides (from project initialization — take precedence over docs/STACK.md)
- **Frontend:** Next.js 16.2, React 19.2, Tailwind v4.3, shadcn/ui + Recharts v3 (Tremor removed)
- **Scheduler:** celery-redbeat (not Celery Beat default file scheduler)
- **Pipeline:** Celery `chain()` for daily pipeline (not 4 independent cron jobs)
- **AI model:** claude-sonnet-4-5 (per SPEC.md — used for both Phase 5 insights and Phase 8 chat)
- Source: `.planning/STATE.md` key decisions section

### UI Structure
- `SPEC.md §13.1` — Sidebar navigation structure (8 nav items, canonical order)
- `SPEC.md §13.10` — i18n requirements (ro primary, en secondary)

### Database Schema Reference
- `SPEC.md §7` — Full PostgreSQL schema (tables, columns, types, indexes)
- Phase 1 creates base tables: `tenants`, `users`, `sync_runs`, `pipeline_runs` with `tenant_id NOT NULL`, `TIMESTAMPTZ` columns

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — this is the first phase, no existing code.

### Established Patterns
- None — this phase establishes the patterns. See `docs/CONVENTIONS.md` for required conventions.
- Clean Architecture layers to establish: `api/` → `services/` → `db/` (repositories) — no SQL in API layer, no HTTP in DB layer.

### Integration Points
- This phase creates all integration points for future phases:
  - `app/db/session.py` — SQLAlchemy async session factory (tenant context var lives here)
  - `app/tasks/celery_app.py` — Celery app definition (all future tasks import from here)
  - `app/core/security.py` — JWT encode/decode utilities (Phase 2+ auth middleware reads from here)
  - `frontend/proxy.ts` — Route protection (all protected routes flow through here; Next.js 16 rename from middleware.ts)
  - `frontend/messages/ro.json` + `en.json` — i18n message files (all Phase 7 strings added here)

</code_context>

<specifics>
## Specific Ideas

- SPEC.md §13.1 nav order is **canonical** — sidebar must match: Overview → Marketing → Sales → Salespeople → Insights → Chat → Integrations → Profile/Settings.
- The `pipeline_runs` table (PIPE-04) must be created in Phase 1 even though no pipeline runs yet — it's used by the dashboard health endpoint and needed in Phase 2.
- The tenant context var enforcement test (D-06) should test the SQLAlchemy `with_loader_criteria` hook directly, not just an endpoint — proves the DB layer rejects without context, not just that auth middleware redirects.

</specifics>

<deferred>
## Deferred Ideas

- Grafana + Prometheus monitoring — Phase 9 (Polish & Deploy)
- Sentry error tracking — Phase 9
- GitHub Actions CI/CD — Phase 9
- Email digest — future iteration (out of v1 scope)
- TimescaleDB — deferred until we need time-series at scale (not needed for MVP)
- Full i18n translation of all UI strings — Phase 7 (Phase 1 covers login + nav only)

</deferred>

---

*Phase: 1-Foundation*
*Context gathered: 2026-05-20*
