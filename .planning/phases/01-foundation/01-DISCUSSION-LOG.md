# Phase 1: Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-20
**Phase:** 1-Foundation
**Areas discussed:** JWT auth flow, Multi-tenancy seam, Docker service topology, Frontend scaffold depth

---

## JWT Auth Flow

### Q1: JWT storage location

| Option | Description | Selected |
|--------|-------------|----------|
| HttpOnly cookie | Backend sets Set-Cookie. Next.js middleware reads server-side. Best XSS protection. Requires SameSite + CORS setup. | ✓ |
| Authorization header (memory) | Token in React state / Zustand. Cleared on refresh unless paired with refresh flow. Simpler CORS. | |
| You decide | Claude chooses. | |

**User's choice:** HttpOnly cookie
**Notes:** Standard SSR approach; pairs well with Next.js middleware.

---

### Q2: Token refresh strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Interceptor-based refresh | API client catches 401, calls /auth/refresh, retries original request. Transparent to UI. Requires refresh_token cookie. | ✓ |
| Manual redirect to login on 401 | Simpler. Works for MVP — user logs in again. No refresh token needed. | |

**User's choice:** Interceptor-based refresh
**Notes:** Chosen for better UX; refresh token as HttpOnly cookie.

---

### Q3: Next.js route protection mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Next.js Middleware | middleware.ts reads JWT cookie, redirects to /login before rendering. Zero flash. | ✓ |
| Layout-level server check | Each protected layout reads cookie in Server Component and redirects. More granular. | |
| You decide | Standard Next.js 16 + App Router pattern. | |

**User's choice:** Next.js Middleware
**Notes:** Most robust approach for App Router.

---

### Q4: Auth endpoint response format

| Option | Description | Selected |
|--------|-------------|----------|
| JWT in body + Set-Cookie for refresh token | Access token (short-lived) in JSON body; refresh token in HttpOnly cookie. | ✓ |
| Both tokens in HttpOnly cookies | Access token cookie + refresh token cookie, both HttpOnly. No JS can touch either. | |

**User's choice:** JWT in body + Set-Cookie for refresh token
**Notes:** Access token in body for programmatic use; refresh token stays HttpOnly for security.

---

## Multi-Tenancy Seam

### Q1: How to set SQLAlchemy tenant context in Phase 1

| Option | Description | Selected |
|--------|-------------|----------|
| Hardcoded Sofa Belle UUID at startup | Constant set as app-wide context var. with_loader_criteria reads from it. One-line swap in Iteration 4. | ✓ |
| JWT carries tenant_id from day 1 | Auth middleware extracts tenant_id per-request. More correct long-term, more complex for Phase 1. | |

**User's choice:** Hardcoded Sofa Belle UUID at startup
**Notes:** Keeps Phase 1 simple. The seam architecture is correct; only the source of the UUID changes in Iteration 4.

---

### Q2: Tenant seam test enforcement

| Option | Description | Selected |
|--------|-------------|----------|
| Failing test required (SC#6 literal) | Test that proves session factory rejects queries without tenant context. Must pass before Phase 1 done. | ✓ |
| Seam present, test deferred | Wire up the code but write the isolation test in Phase 2. | |

**User's choice:** Failing test required (SC#6 literal)
**Notes:** Success criteria are literal requirements; the test is mandatory for Phase 1 completion.

---

### Q3: Initial tenant + user provisioning

| Option | Description | Selected |
|--------|-------------|----------|
| Alembic data migration | Idempotent INSERT runs at alembic upgrade head. No separate script. | ✓ |
| docker-compose entrypoint script | Shell script runs after migrations. Explicit but not in migration chain. | |
| Manual psql | One-time SQL snippet. Fragile for team. | |

**User's choice:** Alembic data migration
**Notes:** Best developer experience — everything in `alembic upgrade head`.

---

## Docker Service Topology

### Q1: Worker and beat container split

| Option | Description | Selected |
|--------|-------------|----------|
| Separate containers | backend, worker, beat as 3 distinct services. SC#4 requires independent worker inspection. | ✓ |
| Combined worker+beat | Celery runs --beat alongside worker. Simpler but harder to restart independently. | |

**User's choice:** Separate containers
**Notes:** Clear separation for debugging and future scaling; required by SC#4.

---

### Q2: Flower monitoring UI

| Option | Description | Selected |
|--------|-------------|----------|
| Include from Phase 1 | Lightweight container. Useful during Phase 2 MEFI ETL development. Port 5555. | ✓ |
| Defer to Phase 9 | Not needed until production. Keeps docker-compose.yml minimal. | |

**User's choice:** Include from Phase 1
**Notes:** Developer productivity benefit outweighs the minimal overhead.

---

### Q3: Health checks and dependency ordering

| Option | Description | Selected |
|--------|-------------|----------|
| depends_on with condition: service_healthy | Postgres and redis must be healthy before backend/worker/beat start. Matches SC#1 (30s startup). | ✓ |
| depends_on without health checks | Simpler. App code handles connection retry. | |

**User's choice:** depends_on with condition: service_healthy
**Notes:** Prevents startup race conditions; ensures clean first `docker compose up -d`.

---

## Frontend Scaffold Depth

### Q1: Scaffold scope

| Option | Description | Selected |
|--------|-------------|----------|
| Full shell layout | Scaffold sidebar + topbar + content area now. Phase 7 fills content. Saves Phase 7 layout restructuring. | ✓ |
| Minimal — login + placeholder dashboard | Just /login and /dashboard (blank). Phase 7 builds layout from scratch. | |

**User's choice:** Full shell layout
**Notes:** Investing in the shell now avoids Phase 7 having to restructure around an existing layout.

---

### Q2: Navigation items in Phase 1

| Option | Description | Selected |
|--------|-------------|----------|
| All 4 final nav items | Sales, Salespeople, Marketing, Insights as placeholder pages. | |
| Per SPEC.md §13.1 (8 items) | All 8 nav items from spec: Overview, Marketing, Sales, Salespeople, Insights, Chat, Integrations, Profile/Settings. | ✓ |

**User's choice:** Per SPEC.md §13.1 — all 8 navigation items
**Notes:** User specified the canonical nav order from SPEC.md v2.1 section 13.1. Chat is a Phase 8 placeholder. Integrations and Profile/Settings also included. Canonical order: Overview → Marketing → Sales → Salespeople → Insights → Chat → Integrations → Profile/Settings.

---

### Q3: i18n scope for Phase 1

| Option | Description | Selected |
|--------|-------------|----------|
| next-intl + Romanian strings for login + nav | next-intl configured with ro as default. Login page and sidebar labels translated. | ✓ |
| Infrastructure only, English strings | next-intl configured but English text. Romanian added in Phase 7. | |

**User's choice:** next-intl + Romanian strings for login + nav
**Notes:** Pattern established from Phase 1; Phase 7 adds page content strings without restructuring.

---

## Claude's Discretion

None — user made explicit choices for all presented options.

## Deferred Ideas

- Grafana + Prometheus monitoring → Phase 9
- Sentry error tracking → Phase 9
- GitHub Actions CI/CD → Phase 9
- Email digest → future iteration
- TimescaleDB → if needed at scale (not MVP)
- Full Romanian i18n of all UI strings → Phase 7
