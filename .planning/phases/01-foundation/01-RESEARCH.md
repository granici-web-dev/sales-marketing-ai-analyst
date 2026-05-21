# Phase 1: Foundation - Research

**Researched:** 2026-05-20
**Domain:** Full-stack infrastructure — Python/FastAPI + Celery + PostgreSQL + Next.js 16 App Router
**Confidence:** HIGH (core backend patterns), MEDIUM (Next.js 16 specifics, celery-redbeat wiring)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**JWT Auth Flow**
- D-01: JWT stored as HttpOnly cookie. Access token returned in JSON response body; refresh token set as HttpOnly `Set-Cookie`.
- D-02: Token refresh is interceptor-based — API client catches 401, calls `POST /api/v1/auth/refresh`, retries original request. Transparent to UI.
- D-03: Next.js route protection via `proxy.ts` — reads JWT access token cookie server-side, redirects to `/login` before rendering.
- D-04: `POST /api/v1/auth/login` → `{access_token, token_type}` JSON + `refresh_token` HttpOnly cookie. `POST /api/v1/auth/refresh` → validates refresh cookie, returns new access token + rotates refresh cookie.

**Multi-Tenancy Seam**
- D-05: SQLAlchemy tenant context via hardcoded Sofa Belle UUID in `contextvars.ContextVar`. `with_loader_criteria` reads from the context var.
- D-06: Phase 1 MUST include a failing test proving the SQLAlchemy session factory rejects a query when no tenant context is set.
- D-07: Initial Sofa Belle tenant + admin user via Alembic data migration — idempotent `INSERT ... ON CONFLICT DO NOTHING`.

**Docker Service Topology**
- D-08: 6 containers: `postgres`, `redis`, `backend` (FastAPI/uvicorn), `worker` (Celery), `beat` (celery-redbeat), `frontend` (Next.js dev). Worker and beat are separate containers.
- D-09: Flower on port 5555 from Phase 1.
- D-10: `depends_on` with `condition: service_healthy` — postgres and redis pass healthcheck before backend/worker/beat start.

**Frontend Scaffold**
- D-11: Full shell layout (sidebar + topbar + content) in Phase 1.
- D-12: All 8 nav items wired as placeholder routes: Overview → `/`, Marketing → `/marketing`, Sales → `/sales`, Salespeople → `/salespeople`, Insights → `/insights`, Chat → `/chat`, Integrations → `/integrations`, Profile/Settings → `/settings`.
- D-13: next-intl with Romanian (`ro`) as default locale from Phase 1. Login page + sidebar labels have Romanian strings.

### Claude's Discretion
None explicitly listed for Phase 1.

### Deferred Ideas (OUT OF SCOPE)
- Grafana + Prometheus monitoring (Phase 9)
- Sentry error tracking (Phase 9)
- GitHub Actions CI/CD (Phase 9)
- Email digest (future)
- TimescaleDB (deferred until needed)
- Full i18n translation of all UI strings (Phase 7 — Phase 1 covers login + nav only)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INFRA-01 | Docker Compose dev stack runs all services with a single command | Docker Compose healthcheck patterns; 6-service topology confirmed |
| INFRA-02 | PostgreSQL schema uses TIMESTAMPTZ and tenant_id on every table | SQLAlchemy 2.x Mapped[] syntax; Base model with TIMESTAMPTZ |
| INFRA-03 | SQLAlchemy async session factory with `with_loader_criteria` tenant isolation seam | do_orm_execute event + contextvars pattern documented |
| INFRA-04 | Celery + celery-redbeat with Europe/Bucharest timezone and visibility timeout ≥ 8h | redbeat 2.3.3 config keys confirmed; broker_transport_options for visibility |
| INFRA-05 | Per-worker async SQLAlchemy engine via `worker_process_init` signal | worker_process_init fires in each child after fork; engine.dispose() + recreate pattern |
| INFRA-06 | structlog JSON logging with tenant_id, task_id — no PII | contextvars integration, merge_contextvars processor chain confirmed |
| AUTH-01 | User can log in with email and password | PyJWT 2.12.1 + bcrypt; FastAPI Depends pattern |
| AUTH-02 | Session persists across refresh via JWT HttpOnly cookie | Set-Cookie pattern confirmed; access token in body, refresh in cookie |
| AUTH-03 | All dashboard routes require auth; unauthenticated → redirect to login | proxy.ts (Next.js 16 rename from middleware.ts) + jose for JWT verify |
| UI-01 | All UI text defaults to Romanian; English secondary (via next-intl) | next-intl 4.12.0 + Next.js 16 proxy.ts; getRequestConfig + NextIntlClientProvider |
| PIPE-04 | `pipeline_runs` table created (Phase 1 creates table; Phase 2 writes to it) | Alembic migration with TIMESTAMPTZ, tenant_id NOT NULL |
</phase_requirements>

---

## Summary

Phase 1 builds a greenfield monorepo from scratch. The backend is Python 3.11 + FastAPI + SQLAlchemy 2.x async + Celery 5.x with celery-redbeat as the distributed beat scheduler stored in Redis. The frontend is Next.js 16.2 with React 19.2, Tailwind v4.3, and shadcn/ui. There is no existing code to reuse.

The most technically novel piece is the SQLAlchemy `with_loader_criteria` tenant isolation seam — it must intercept every ORM SELECT via the `do_orm_execute` event listener and inject a tenant filter from a `ContextVar`. The required failing test (D-06, SC#6) proves the seam is wired before any data-fetching code is written.

Next.js 16 introduced a **breaking rename**: `middleware.ts` → `proxy.ts` and `export function middleware` → `export function proxy`. This affects how route protection and next-intl are wired. The `edge` runtime is NOT supported in `proxy.ts`; it runs on `nodejs`. For JWT verification inside proxy.ts, use the `jose` library (works with Node.js runtime), not the Python-land python-jose.

**Primary recommendation:** Build backend in strict Clean Architecture layers (api → services → db/repositories), wire tenant isolation before writing any query, establish all integration points (session.py, celery_app.py, security.py, proxy.ts, messages/ro.json) so Phase 2+ can add code without restructuring.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| JWT token generation / validation | API / Backend | — | Tokens signed server-side; backend owns secret |
| HttpOnly cookie setting | API / Backend | — | `response.set_cookie()` in FastAPI response; browser cannot set HttpOnly |
| Route protection (redirect to /login) | Frontend Server (proxy.ts) | API / Backend | proxy.ts intercepts before rendering; backend re-validates on every API call |
| Tenant context injection | API / Backend (middleware) | DB Layer | FastAPI dependency sets ContextVar before any DB call |
| JWT verification in proxy.ts | Frontend Server | — | jose library in Node.js runtime |
| Celery task scheduling | CDN / Static infra | — | celery-redbeat stores schedule in Redis; beat container owns trigger |
| SQLAlchemy tenant isolation | Database / Storage | — | do_orm_execute event listener lives in session.py |
| i18n / locale negotiation | Frontend Server (proxy.ts) | — | next-intl routing uses proxy.ts for locale detection |
| structlog context binding | API / Backend | Worker layer | bind_contextvars in FastAPI middleware + Celery task preamble |
| Base table creation | Database / Storage | — | Alembic migrations; no manual DDL |

---

## Standard Stack

### Backend Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | 0.128.8 | Async HTTP framework | Auto-OpenAPI, Pydantic v2 native, async Depends |
| sqlalchemy | 2.0.49 | Async ORM | `with_loader_criteria`, `async_sessionmaker`, Mapped[] syntax |
| asyncpg | 0.31.0 | PostgreSQL async driver | Fastest Python async PG driver |
| alembic | 1.16.5 | Database migrations | Standard for SQLAlchemy; async env.py pattern |
| pydantic | 2.13.4 | Models and settings | Type-safe DTO + settings; v2 required by CLAUDE.md |
| pydantic-settings | 2.11.0 | Typed config from .env | Mandatory per CLAUDE.md (no secrets in code) |
| uvicorn | 0.39.0 | ASGI server | Standard with FastAPI |
| celery | 5.6.3 | Task queue | Distributed, mature; Celery 5.x is Python 3.11 native |
| celery-redbeat | 2.3.3 | Redis-backed beat scheduler | Stores schedule in Redis (survives restart); replaces default file scheduler |
| PyJWT | 2.12.1 | JWT encode/decode | Replaces python-jose (CVE-2024-33663/33664); actively maintained |
| bcrypt | 5.0.0 | Password hashing | Industry standard; passlib wraps it |
| passlib | 1.7.4 | Password hashing abstraction | FastAPI security standard; bcrypt backend |
| python-multipart | 0.0.20 | Form parsing (login form) | Required by FastAPI for form data |
| structlog | 25.5.0 | Structured JSON logging | contextvars integration; JSON renderer |
| httpx | 0.28.1 | Async HTTP client | Required by CLAUDE.md; ETL integration (Phase 2+) |
| cryptography | 48.0.0 | Fernet encryption | Encrypting API credentials in DB (Phase 2+, but install now) |

[VERIFIED: PyPI registry] — all packages confirmed via `pip3 index versions`

### Backend Testing

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | latest | Test runner | All tests |
| pytest-asyncio | 1.2.0 | Async test fixtures | Required for async SQLAlchemy session fixtures |
| pytest-cov | 7.1.0 | Coverage reporting | CI gate (≥70% on business logic) |
| factory-boy | 3.3.3 | Test data factories | Generates Tenant, User fixtures |
| freezegun | 1.5.5 | Time mocking | Tests involving `datetime.utcnow()` |

[VERIFIED: PyPI registry]

### Frontend Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| next | 16.2.6 | App Router framework | Locked by CONTEXT.md |
| react | 19.2 | UI library | Bundled with Next.js 16 |
| typescript | 6.0.3 | Type safety | Strict mode required |
| tailwindcss | 4.3.0 | Utility CSS | Locked by CONTEXT.md |
| shadcn (CLI) | 4.7.0 | Component CLI | `npx shadcn@latest init` |
| next-intl | 4.12.0 | i18n routing | Locked — ro default locale |
| jose | 6.2.3 | JWT verify in proxy.ts | Works in Node.js runtime (edge NOT supported in proxy.ts) |
| @tanstack/react-query | 5.100.11 | Server state / caching | Standard for data fetching |
| zustand | 5.0.13 | Client state | Lightweight; login state, locale toggle |
| zod | 4.4.3 | Schema validation | Login form validation |
| react-hook-form | 7.76.0 | Form management | Login form |

[VERIFIED: npm registry] — all packages confirmed via `npm view`

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PyJWT | python-jose | python-jose has unpatched CVEs (2024); PyJWT is its upstream; do NOT use python-jose |
| celery-redbeat | Celery Beat (file) | File scheduler loses state on restart; redbeat stores in Redis — resilient |
| pytest-asyncio 1.2.0 | 0.23.x | 1.x is stable release; new loop_scope parameter replaces deprecated asyncio_mode |
| bcrypt+passlib | argon2-cffi | argon2 is more modern but passlib with bcrypt is the FastAPI canonical tutorial path |

**Installation (backend):**
```bash
uv pip install fastapi==0.128.8 sqlalchemy==2.0.49 asyncpg==0.31.0 alembic==1.16.5 \
  pydantic==2.13.4 pydantic-settings==2.11.0 uvicorn==0.39.0 \
  celery==5.6.3 celery-redbeat==2.3.3 redis \
  PyJWT==2.12.1 bcrypt==5.0.0 passlib==1.7.4 python-multipart==0.0.20 \
  structlog==25.5.0 httpx==0.28.1 cryptography==48.0.0 \
  pytest pytest-asyncio==1.2.0 pytest-cov==7.1.0 factory-boy==3.3.3 freezegun==1.5.5
```

**Installation (frontend):**
```bash
pnpm dlx shadcn@latest init   # after create-next-app
pnpm add next-intl jose @tanstack/react-query zustand zod react-hook-form
```

---

## Package Legitimacy Audit

> slopcheck was not available at research time. All packages are verified against their authoritative source (PyPI / npm registry) and official documentation. Packages are tagged [VERIFIED: PyPI registry] or [VERIFIED: npm registry] rather than [ASSUMED] because they are confirmed via official registries AND are well-known packages present in official framework documentation.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| fastapi | PyPI | 7 yrs | 50M+/mo | github.com/tiangolo/fastapi | n/a | Approved |
| sqlalchemy | PyPI | 18 yrs | 200M+/mo | github.com/sqlalchemy/sqlalchemy | n/a | Approved |
| asyncpg | PyPI | 8 yrs | 50M+/mo | github.com/MagicStack/asyncpg | n/a | Approved |
| alembic | PyPI | 14 yrs | 80M+/mo | github.com/sqlalchemy/alembic | n/a | Approved |
| celery | PyPI | 15 yrs | 100M+/mo | github.com/celery/celery | n/a | Approved |
| celery-redbeat | PyPI | 8 yrs | ~2M/mo | github.com/sibson/redbeat | n/a | Approved |
| PyJWT | PyPI | 13 yrs | 200M+/mo | github.com/jpadilla/pyjwt | n/a | Approved |
| structlog | PyPI | 11 yrs | 30M+/mo | github.com/hynek/structlog | n/a | Approved |
| pydantic | PyPI | 8 yrs | 400M+/mo | github.com/pydantic/pydantic | n/a | Approved |
| pydantic-settings | PyPI | 5 yrs | 100M+/mo | github.com/pydantic/pydantic-settings | n/a | Approved |
| next | npm | 13 yrs | 100M+/wk | github.com/vercel/next.js | n/a | Approved |
| next-intl | npm | 5 yrs | 5M+/wk | github.com/amannn/next-intl | n/a | Approved |
| jose | npm | 12 yrs | 50M+/wk | github.com/panva/jose | n/a | Approved |
| @tanstack/react-query | npm | 3 yrs | 20M+/wk | github.com/TanStack/query | n/a | Approved |
| tailwindcss | npm | 7 yrs | 100M+/wk | github.com/tailwindlabs/tailwindcss | n/a | Approved |
| shadcn CLI | npm | 1 yr | 5M+/wk | github.com/shadcn-ui/ui | n/a | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*Note: `python-jose` is explicitly excluded — two unpatched CVEs (CVE-2024-33663, CVE-2024-33664). Use `PyJWT` instead.*

---

## Architecture Patterns

### System Architecture Diagram

```
Browser
  │
  │  GET /dashboard (or any protected route)
  ▼
Next.js proxy.ts (Node.js runtime)
  │  1. Read access_token cookie
  │  2. jose.jwtVerify(token, secret)
  │  3. If invalid → redirect to /login
  │  4. If valid → pass through + set locale headers
  ▼
Next.js Server Components / Pages
  │  5. Render with next-intl (ro locale)
  │  6. Client components fetch data via TanStack Query
  ▼
FastAPI Backend (port 8000)
  │  7. Auth middleware reads cookie, sets tenant ContextVar
  │  8. SQLAlchemy do_orm_execute injects tenant_id filter
  │  9. Returns JSON
  ▼
PostgreSQL (port 5432)
  │
  ├── tenants
  ├── users
  ├── sync_runs
  └── pipeline_runs

Redis (port 6379)
  ├── Celery broker (task queues)
  └── celery-redbeat schedule keys (redbeat::*)

Celery Worker
  │  worker_process_init → dispose + recreate SQLAlchemy engine
  └── tasks run asyncio.run(async_fn())

Celery Beat (celery-redbeat)
  └── reads schedule from Redis, enqueues tasks

Flower (port 5555)
  └── monitors worker + beat
```

### Recommended Project Structure

```
backend/
├── pyproject.toml              # uv managed; defines [dev] extras for test tools
├── alembic.ini
├── alembic/
│   ├── env.py                  # async_engine_from_config + connection.run_sync
│   └── versions/
│       ├── 001_base_tables.py  # tenants, users, sync_runs, pipeline_runs
│       └── 002_seed_sofabelle.py  # INSERT ... ON CONFLICT DO NOTHING
└── app/
    ├── main.py                 # FastAPI app, lifespan, routers, CORS
    ├── core/
    │   ├── config.py           # pydantic-settings Settings class
    │   ├── security.py         # PyJWT encode/decode, bcrypt verify
    │   ├── tenancy.py          # ContextVar[UUID | None], get_current_tenant_id()
    │   └── exceptions.py       # AppError, NotFoundError, TenantIsolationError
    ├── db/
    │   ├── base.py             # DeclarativeBase, TimestampMixin
    │   ├── session.py          # create_async_engine, async_sessionmaker,
    │   │                       # do_orm_execute event → with_loader_criteria
    │   └── deps.py             # get_session() FastAPI dependency
    ├── models/
    │   ├── tenant.py           # Tenant model
    │   ├── user.py             # User model
    │   └── pipeline.py         # SyncRun, PipelineRun models
    ├── schemas/
    │   ├── auth.py             # LoginRequest, TokenResponse, UserOut
    │   └── health.py           # HealthResponse
    ├── services/
    │   └── auth_service.py     # authenticate_user(), create_tokens()
    ├── api/
    │   └── v1/
    │       ├── router.py       # APIRouter aggregation
    │       ├── auth.py         # /auth/login, /auth/refresh, /auth/logout
    │       └── health.py       # /healthz
    └── tasks/
        └── celery_app.py       # Celery app instance + redbeat config

frontend/
├── package.json
├── next.config.ts              # withNextIntl(config)
├── components.json             # shadcn/ui config
├── proxy.ts                    # Auth + i18n routing (NOT middleware.ts)
├── messages/
│   ├── ro.json                 # Romanian strings (login, nav labels)
│   └── en.json                 # English strings
└── src/
    ├── i18n/
    │   ├── routing.ts          # defineRouting({ locales: ['ro','en'], defaultLocale: 'ro' })
    │   └── request.ts          # getRequestConfig → returns { locale, messages }
    └── app/
        ├── layout.tsx          # NextIntlClientProvider wrapper
        ├── (auth)/
        │   └── login/
        │       └── page.tsx
        └── (dashboard)/
            ├── layout.tsx      # Sidebar + topbar shell
            ├── page.tsx        # Overview placeholder
            ├── marketing/page.tsx
            ├── sales/page.tsx
            ├── salespeople/page.tsx
            ├── insights/page.tsx
            ├── chat/page.tsx
            ├── integrations/page.tsx
            └── settings/page.tsx
```

### Pattern 1: SQLAlchemy Async + Tenant Isolation via `with_loader_criteria`

**What:** Every ORM SELECT automatically gains a `WHERE tenant_id = :current_tenant_id` clause through the `do_orm_execute` event listener. The current tenant UUID comes from a `ContextVar` set by FastAPI middleware before any service call.

**When to use:** All ORM queries against tenant-scoped tables (every table except `tenants`).

```python
# Source: SQLAlchemy 2.0 docs — ORM Events + with_loader_criteria
# app/core/tenancy.py
from __future__ import annotations
from contextvars import ContextVar
from uuid import UUID

_tenant_id_var: ContextVar[UUID | None] = ContextVar("tenant_id", default=None)

def set_tenant_id(tenant_id: UUID) -> None:
    _tenant_id_var.set(tenant_id)

def get_current_tenant_id() -> UUID | None:
    return _tenant_id_var.get()
```

```python
# app/db/session.py
from __future__ import annotations
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import with_loader_criteria
from app.core.tenancy import get_current_tenant_id
from app.db.base import Base

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# Register on the sync Session class (not the async wrapper)
from sqlalchemy.orm import Session

@event.listens_for(Session, "do_orm_execute")
def _add_tenant_filter(execute_state: any) -> None:
    tenant_id = get_current_tenant_id()
    if (
        execute_state.is_select
        and not execute_state.is_column_load
        and not execute_state.is_relationship_load
    ):
        if tenant_id is None:
            from app.core.exceptions import TenantIsolationError
            raise TenantIsolationError("No tenant context set — refusing query")
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                Base,
                lambda cls: cls.tenant_id == tenant_id,
                include_aliases=True,
            )
        )
```

**D-06 failing test pattern:**

```python
# tests/test_tenant_isolation.py
import pytest
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.core.exceptions import TenantIsolationError
from app.core.tenancy import _tenant_id_var

@pytest.mark.asyncio
async def test_query_without_tenant_context_raises():
    """SC#6: DB layer rejects queries when no tenant context is set."""
    # Ensure no tenant is set
    _tenant_id_var.set(None)
    async with AsyncSessionLocal() as session:
        with pytest.raises(TenantIsolationError):
            await session.execute(select(User))
```

### Pattern 2: Alembic Async env.py

**What:** Alembic runs synchronously but asyncpg is async-only. Bridge via `async_engine_from_config` + `connection.run_sync`.

```python
# alembic/env.py
from __future__ import annotations
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

config = context.config
fileConfig(config.config_file_name)

# MUST import all models before target_metadata is set — else autogenerate is blind
from app.db.base import Base
import app.models.tenant  # noqa: F401
import app.models.user    # noqa: F401
import app.models.pipeline  # noqa: F401

target_metadata = Base.metadata

def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations():
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

def run_migrations_online():
    asyncio.run(run_async_migrations())

run_migrations_online()
```

**Data migration pattern (Alembic — D-07):**

```python
# alembic/versions/002_seed_sofabelle.py
from alembic import op
import sqlalchemy as sa
from uuid import UUID

SOFA_BELLE_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
ADMIN_USER_ID = UUID("00000000-0000-0000-0000-000000000002")

def upgrade():
    op.execute(
        sa.text("""
            INSERT INTO tenants (id, name, slug, created_at)
            VALUES (:id, 'Sofa Belle', 'sofa-belle', now())
            ON CONFLICT (id) DO NOTHING
        """).bindparams(id=str(SOFA_BELLE_TENANT_ID))
    )
    # bcrypt hash must be pre-computed and hardcoded here
    op.execute(
        sa.text("""
            INSERT INTO users (id, tenant_id, email, hashed_password, is_active, created_at)
            VALUES (:id, :tenant_id, 'admin@sofabelle.ro', :pw, true, now())
            ON CONFLICT (id) DO NOTHING
        """).bindparams(
            id=str(ADMIN_USER_ID),
            tenant_id=str(SOFA_BELLE_TENANT_ID),
            pw="$2b$12$...",  # bcrypt hash of initial password
        )
    )

def downgrade():
    pass  # seed data is not reversed
```

### Pattern 3: celery-redbeat Configuration

**What:** celery-redbeat stores the beat schedule in Redis, surviving worker restarts. `RedBeatScheduler` replaces the default file-based scheduler.

```python
# app/tasks/celery_app.py
from __future__ import annotations
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "sales_analyst",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks"],
)

celery_app.conf.update(
    # Timezone
    timezone="Europe/Bucharest",
    enable_utc=True,

    # Redbeat scheduler
    beat_scheduler="redbeat.RedBeatScheduler",
    redbeat_redis_url=settings.redis_url,
    redbeat_lock_timeout=60 * 60 * 9,  # 9 hours > 8h requirement (INFRA-04)
    redbeat_key_prefix="analyst:redbeat",

    # Visibility timeout: must exceed the longest task runtime
    # (Phase 2 ETL could take hours for backfill)
    broker_transport_options={
        "visibility_timeout": 60 * 60 * 9,  # 9 hours
    },

    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Worker reliability
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
)
```

**Key config note:** `broker_transport_options["visibility_timeout"]` must be ≥ the longest expected task runtime. If a task runs longer than `visibility_timeout`, Redis re-enqueues it, causing duplicates. 9 hours covers all ETL scenarios in later phases.

### Pattern 4: Per-Worker Engine Initialization (INFRA-05)

**What:** SQLAlchemy connections must not cross fork boundaries. `worker_process_init` fires in each child after the prefork pool creates it. Dispose the parent's engine and create a fresh one.

```python
# app/tasks/celery_app.py (continued)
from celery.signals import worker_process_init
from app.db import session as db_session

@worker_process_init.connect
def init_worker_process(**kwargs):
    """Create a fresh SQLAlchemy engine per Celery worker process (fork-safe)."""
    import asyncio
    asyncio.run(db_session.engine.dispose())
    # Recreate engine for this process
    db_session.engine = db_session._create_engine()
    db_session.AsyncSessionLocal = db_session._create_session_factory(db_session.engine)
```

**Async in Celery tasks:** Celery 5.x tasks are synchronous. Call async functions with `asyncio.run()`:

```python
@celery_app.task
def some_task() -> None:
    asyncio.run(_async_impl())

async def _async_impl() -> None:
    async with AsyncSessionLocal() as session:
        # do async work
        ...
```

### Pattern 5: FastAPI JWT HttpOnly Cookie Auth (D-01 to D-04)

```python
# app/api/v1/auth.py
from __future__ import annotations
from fastapi import APIRouter, Response, HTTPException, Cookie
from app.core.security import create_access_token, create_refresh_token, verify_token
from app.schemas.auth import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])

ACCESS_TOKEN_EXPIRE_MIN = 15
REFRESH_TOKEN_EXPIRE_DAYS = 30
COOKIE_NAME = "refresh_token"

@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, response: Response):
    user = await authenticate_user(body.email, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token({"sub": str(user.id), "tenant_id": str(user.tenant_id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})

    # Refresh token as HttpOnly cookie (D-01, D-04)
    response.set_cookie(
        key=COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=True,       # HTTPS in prod; False in dev behind HTTP
        samesite="lax",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path="/api/v1/auth/refresh",  # Scope cookie to refresh endpoint only
    )
    # Access token in JSON body (D-01)
    return TokenResponse(access_token=access_token, token_type="bearer")


@router.post("/refresh", response_model=TokenResponse)
async def refresh(response: Response, refresh_token: str | None = Cookie(default=None)):
    if refresh_token is None:
        raise HTTPException(status_code=401, detail="No refresh token")
    payload = verify_token(refresh_token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    new_access_token = create_access_token({"sub": payload["sub"]})
    new_refresh_token = create_refresh_token({"sub": payload["sub"]})  # rotate
    response.set_cookie(
        key=COOKIE_NAME,
        value=new_refresh_token,
        httponly=True, secure=True, samesite="lax",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path="/api/v1/auth/refresh",
    )
    return TokenResponse(access_token=new_access_token, token_type="bearer")
```

### Pattern 6: Next.js 16 proxy.ts — Auth + next-intl

**Critical:** In Next.js 16, `middleware.ts` is renamed to `proxy.ts` and `export function middleware` becomes `export function proxy`. The `edge` runtime is NOT supported — proxy.ts runs on `nodejs`. [VERIFIED: nextjs.org/docs/app/guides/upgrading/version-16]

```typescript
// proxy.ts  (NOT middleware.ts — this is the Next.js 16 rename)
import createMiddleware from "next-intl/middleware";
import { type NextRequest, NextResponse } from "next/server";
import { jwtVerify } from "jose";
import { routing } from "./src/i18n/routing";

const handleI18nRouting = createMiddleware(routing);

const PUBLIC_PATHS = ["/login", "/api/v1/auth"];

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Skip auth check for public paths and static assets
  const isPublic = PUBLIC_PATHS.some((p) => pathname.startsWith(p));
  if (isPublic) {
    return handleI18nRouting(request);
  }

  const accessToken = request.cookies.get("access_token")?.value;
  if (!accessToken) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  try {
    const secret = new TextEncoder().encode(process.env.JWT_SECRET_KEY!);
    await jwtVerify(accessToken, secret);
  } catch {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  return handleI18nRouting(request);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
```

**next-intl setup for Next.js 16 (three required pieces):**

```typescript
// src/i18n/routing.ts
import { defineRouting } from "next-intl/routing";

export const routing = defineRouting({
  locales: ["ro", "en"],
  defaultLocale: "ro",
  localePrefix: "never",  // URLs without /ro/ prefix (e.g., /sales not /ro/sales)
});
```

```typescript
// src/i18n/request.ts
import { getRequestConfig } from "next-intl/server";
import { routing } from "./routing";

export default getRequestConfig(async ({ requestLocale }) => {
  let locale = await requestLocale;
  if (!locale || !routing.locales.includes(locale as any)) {
    locale = routing.defaultLocale;
  }
  return {
    locale,  // REQUIRED in next-intl v4 — must be returned
    messages: (await import(`../../messages/${locale}.json`)).default,
  };
});
```

```typescript
// app/layout.tsx
import { NextIntlClientProvider } from "next-intl";  // REQUIRED in next-intl v4

export default async function RootLayout({ children }) {
  return (
    <html>
      <body>
        <NextIntlClientProvider>{children}</NextIntlClientProvider>
      </body>
    </html>
  );
}
```

### Pattern 7: structlog JSON Logging (INFRA-06)

```python
# app/core/logging.py
from __future__ import annotations
import structlog
import logging

def configure_logging(log_level: str = "INFO") -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,         # Inject tenant_id, task_id
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(level=log_level)
```

**FastAPI middleware for context binding:**

```python
# app/main.py
from fastapi import FastAPI, Request
from structlog.contextvars import clear_contextvars, bind_contextvars
import uuid

@app.middleware("http")
async def structlog_context_middleware(request: Request, call_next):
    clear_contextvars()
    bind_contextvars(request_id=str(uuid.uuid4()), path=request.url.path)
    # tenant_id bound AFTER auth middleware sets it in ContextVar
    response = await call_next(request)
    return response
```

**IMPORTANT:** Use a pure ASGI middleware (not `@app.middleware("http")` BaseHTTPMiddleware) to ensure contextvars propagate correctly. `BaseHTTPMiddleware` runs the endpoint in a task group copy of the context. [CITED: structlog.org/en/latest/contextvars.html]

### Pattern 8: Docker Compose with Healthchecks (D-10)

```yaml
# docker-compose.yml (key services)
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: analyst
      POSTGRES_USER: analyst
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -d analyst -U analyst"]
      interval: 5s
      timeout: 5s
      retries: 10
      start_period: 10s

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10

  backend:
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  worker:
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: celery -A app.tasks.celery_app worker --loglevel=info

  beat:
    depends_on:
      redis:
        condition: service_healthy
    command: celery -A app.tasks.celery_app beat -S redbeat.RedBeatScheduler --loglevel=info

  flower:
    ports:
      - "5555:5555"
    command: celery -A app.tasks.celery_app flower
    depends_on:
      redis:
        condition: service_healthy
```

### Anti-Patterns to Avoid

- **`python-jose` usage:** Has CVEs 2024-33663 and 2024-33664. Use `PyJWT` only.
- **`middleware.ts` filename:** In Next.js 16, this is now `proxy.ts`. Using `middleware.ts` will silently fail.
- **Edge runtime in proxy.ts:** The `edge` runtime is NOT supported for proxy in Next.js 16. `jose` must be used (not `jsonwebtoken` which requires Node.js APIs not in edge).
- **Forgetting `locale` return in `getRequestConfig`:** In next-intl v4, `locale` MUST be returned from `getRequestConfig`. Without it, "Unable to find next-intl locale" error appears even after correct proxy.ts rename.
- **`BaseHTTPMiddleware` for structlog:** Creates a copy of the async context, so `bind_contextvars` calls in endpoints don't propagate back to the middleware. Use pure ASGI middleware instead.
- **Async engine shared across fork:** Do not let the parent's asyncpg connection pool survive into child worker processes. Always `engine.dispose()` in `worker_process_init`.
- **Missing `import app.models.*` in alembic/env.py:** If model files are not imported before `target_metadata = Base.metadata`, Alembic autogenerate produces empty migration files.
- **`with_loader_criteria` on `Base` class without `include_aliases=True`:** Without `include_aliases=True`, the criteria won't apply to joined-load aliases, silently missing tenant filter on related objects.
- **Combining worker and beat in one container:** D-08 is explicit: beat must be a separate container. Running `celery -A app beat -A app worker` in one process is a deprecated pattern that causes race conditions.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JWT encode/decode | Custom token logic | `PyJWT` | Handles exp, iat, claims validation; timing-safe |
| Password hashing | `hashlib.sha256(password)` | `passlib[bcrypt]` | bcrypt is designed for passwords (work factor); SHA256 is not |
| Alembic async bridge | Custom asyncio migration runner | `async_engine_from_config` + `connection.run_sync` | Alembic's official supported pattern |
| Celery beat storage | Cron file + custom parser | `celery-redbeat` | Redis persistence, HA-ready, no file state |
| i18n routing | Custom locale URL rewriting | `next-intl` | Handles locale detection, message loading, SSR/CSR sync |
| JSON structured logging | `print(json.dumps(...))` | `structlog` with `merge_contextvars` | Thread-safe, async-safe contextvars; automatic proc chain |
| DB healthcheck in Docker | Custom wait-for script | `pg_isready` in healthcheck | Native, no extra dependencies, correct semantics |

**Key insight:** The tenant isolation seam is the one place that MUST be hand-built (there's no library that does this for SQLAlchemy the way the project needs it), but it's small — 15 lines in `session.py` and 3 lines in `tenancy.py`.

---

## Common Pitfalls

### Pitfall 1: Next.js 16 proxy.ts rename breaks silently

**What goes wrong:** Developers place auth/i18n logic in `middleware.ts` — Next.js 16 ignores it completely. No error is shown. All routes appear public.
**Why it happens:** Next.js 16 renamed the convention from `middleware` to `proxy`. Old filename is silently ignored.
**How to avoid:** Create `proxy.ts` with `export function proxy(...)`. Use the codemod: `npx @next/codemod@canary middleware-to-proxy`.
**Warning signs:** Routes that should redirect to login are accessible without a token.

### Pitfall 2: next-intl v4 "Unable to find locale" error

**What goes wrong:** `getRequestConfig` does not return `locale` field — results in runtime error in all pages.
**Why it happens:** next-intl v4 made `locale` mandatory in the return object of `getRequestConfig`.
**How to avoid:** Always return `{ locale, messages }` from `getRequestConfig`. The `locale` value must be a string from your `routing.locales` list.
**Warning signs:** `Error: Unable to find next-intl locale` in server logs.

### Pitfall 3: `with_loader_criteria` applies to `Base` but excludes the `Tenant` model itself

**What goes wrong:** Filtering on `Base` also tries to apply `tenant_id` to the `Tenant` model, which has no `tenant_id` column (it IS the tenant).
**Why it happens:** `with_loader_criteria(Base, ...)` applies to all subclasses of `Base`, including `Tenant`.
**How to avoid:** Add a class-level check: `lambda cls: cls.tenant_id == tenant_id if hasattr(cls, 'tenant_id') else True`. Or create a `TenantScopedBase` mixin and apply criteria only to that.
**Warning signs:** Queries against `tenants` table raise `AttributeError: 'Tenant' object has no attribute 'tenant_id'`.

### Pitfall 4: asyncpg fork-safety — parent engine leaks into workers

**What goes wrong:** Celery prefork workers inherit the parent's asyncpg connection pool. Shared file descriptors cause `PostgreSQL SSL connection has been closed unexpectedly` or data corruption.
**Why it happens:** Python `fork()` copies all file descriptors, including open database connections.
**How to avoid:** Always call `engine.dispose()` then recreate the engine in `worker_process_init`. Never open any database connection before the Celery worker pool is initialized.
**Warning signs:** Intermittent `asyncpg.InterfaceError` in worker logs; tasks failing only under concurrent load.

### Pitfall 5: structlog `bind_contextvars` not visible in `BaseHTTPMiddleware`

**What goes wrong:** `tenant_id` bound in auth middleware is not visible in the structlog output of that same request.
**Why it happens:** `BaseHTTPMiddleware` wraps the endpoint in a new asyncio task group, which copies the context. Changes to contextvars in the endpoint don't propagate back to the middleware's `finally` block.
**How to avoid:** Use pure ASGI middleware (a class implementing `__call__(scope, receive, send)`) instead of `@app.middleware("http")` for anything that reads contextvars in the `finally` block.
**Warning signs:** `tenant_id` shows as empty/None in log output even though auth middleware set it.

### Pitfall 6: Alembic autogenerate produces empty migration

**What goes wrong:** Running `alembic revision --autogenerate` produces a migration file with empty `upgrade()` and `downgrade()` bodies — no tables are detected.
**Why it happens:** `target_metadata = Base.metadata` is set before models are imported, so `Base.metadata` is empty.
**How to avoid:** Import ALL model modules before `target_metadata = Base.metadata` in `alembic/env.py`. This is easy to miss when models are in subdirectories.
**Warning signs:** Empty migration files despite schema changes.

### Pitfall 7: `redbeat_lock_timeout` too short — duplicate beat tasks

**What goes wrong:** celery-redbeat fires the same scheduled task twice within the same run window.
**Why it happens:** Default `redbeat_lock_timeout` is 1500 seconds (25 minutes). If a task takes longer or the beat process restarts, the lock expires and a second beat instance acquires it.
**How to avoid:** Set `redbeat_lock_timeout` ≥ the longest possible task runtime + loop interval. 9 hours is safe for this project.
**Warning signs:** Two entries for the same pipeline run in `pipeline_runs`; logs show task started twice.

---

## Code Examples

### SQLAlchemy Base Model (INFRA-02)

```python
# app/db/base.py
from __future__ import annotations
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, TIMESTAMPTZ

class Base(DeclarativeBase):
    pass

class TimestampMixin:
    """Adds created_at and updated_at with TIMESTAMPTZ (INFRA-02 requirement)."""
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=func.now(), onupdate=func.now(), nullable=False
    )

class TenantScopedMixin(TimestampMixin):
    """Every table except tenants inherits this — enforces INFRA-02 tenant_id."""
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
```

### FastAPI App Lifespan + Settings

```python
# app/core/config.py
from __future__ import annotations
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str
    redis_url: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    # Hardcoded for MVP (D-05) — replaced by JWT claim in Iteration 4
    sofa_belle_tenant_id: str = "00000000-0000-0000-0000-000000000001"

settings = Settings()
```

### PyJWT Security Utilities

```python
# app/core/security.py
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import UUID
import jwt
from jwt.exceptions import PyJWTError
from app.core.config import settings

def create_access_token(data: dict) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({**data, "exp": expire}, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

def create_refresh_token(data: dict) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    return jwt.encode({**data, "exp": expire, "type": "refresh"}, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

def verify_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except PyJWTError:
        return None
```

### Frontend messages/ro.json (baseline for Phase 1)

```json
{
  "auth": {
    "login": "Autentificare",
    "email": "Email",
    "password": "Parolă",
    "loginButton": "Intră în cont",
    "invalidCredentials": "Email sau parolă incorectă"
  },
  "nav": {
    "overview": "Prezentare generală",
    "marketing": "Marketing",
    "sales": "Vânzări",
    "salespeople": "Agenți de vânzări",
    "insights": "Analize AI",
    "chat": "Chat AI",
    "integrations": "Integrări",
    "settings": "Setări"
  },
  "placeholder": {
    "comingSoon": "În curând"
  }
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `middleware.ts` + `export function middleware` | `proxy.ts` + `export function proxy` | Next.js 16 (2025) | All auth/i18n middleware must be in proxy.ts |
| `python-jose` for JWT | `PyJWT` | 2024 (CVEs disclosed) | python-jose has unpatched vulnerabilities |
| Celery Beat file scheduler | `celery-redbeat` | Project decision | Beat schedule survives restarts |
| Next.js 14 App Router | Next.js 16.2 (Turbopack default, React 19.2) | 2025 | `params`/`searchParams` are Promises (async); `synchronous access removed` |
| `Optional[T]` type hints | `T \| None` syntax | Python 3.10+ | Use union syntax throughout |
| `next-intl` v3 (optional `NextIntlClientProvider`) | v4 (required `NextIntlClientProvider` + mandatory `locale` in return) | next-intl 4.0 | Breaks without explicit provider and locale return |
| `experimental.turbopack` config | `turbopack` top-level config | Next.js 16 | Move out of `experimental` |

**Deprecated/outdated:**
- `python-jose`: Do not use — CVE-2024-33663, CVE-2024-33664. Use PyJWT.
- `middleware.ts` in Next.js 16: Silent no-op. Renamed to `proxy.ts`.
- Synchronous `params`/`searchParams` access in Next.js layouts/pages: Removed in Next.js 16 — must use `await props.params`.
- `next lint` CLI command: Removed in Next.js 16. Use ESLint CLI directly.
- `serverRuntimeConfig` / `publicRuntimeConfig`: Removed in Next.js 16. Use env vars.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The access token should also be stored as a cookie (not just in memory) for proxy.ts to read it | Pattern 6 — proxy.ts | If the access token is only returned in JSON body, proxy.ts cannot read it from `request.cookies` — middleware would need to parse the Authorization header instead |
| A2 | `localePrefix: "never"` is appropriate — URLs like `/sales` instead of `/ro/sales` | next-intl routing config | If locale-prefixed URLs are required (SEO or multi-region), routing.ts must change to `"as-needed"` or `"always"` |
| A3 | `sofa_belle_tenant_id` UUID is a hardcoded constant from startup (not per-request) | D-05 implementation | If multiple test tenants are ever needed before Iteration 4, the ContextVar pattern requires extension |

**If this table is empty for non-A items:** All structural claims were verified via official docs or registries.

---

## Open Questions (RESOLVED)

1. **Access token storage in browser**
   - What we know: D-01 says access token is returned in JSON body. D-03 says proxy.ts reads it from cookie.
   - What's unclear: Is the frontend supposed to store the access token in a cookie itself (after receiving it in JSON body), or in memory only? If memory-only, proxy.ts cannot read it server-side.
   - Recommendation: Store access token in a non-HttpOnly cookie (JavaScript can write it; proxy.ts can read it). The security tradeoff is acceptable because the refresh token (HttpOnly) is the sensitive long-lived credential. Confirm with user or implement as non-HttpOnly `access_token` cookie set by frontend after successful login.
   - **RESOLVED:** Access token written to a non-HttpOnly cookie (`access_token`) by the frontend after login, so `proxy.ts` can read it server-side for route protection. Refresh token is HttpOnly. Login page sets `document.cookie = "access_token=" + result.access_token + "; path=/; SameSite=Lax"` after successful POST /api/v1/auth/login.

2. **`bcrypt` hash in seed migration**
   - What we know: D-07 seeds admin user via Alembic data migration.
   - What's unclear: The initial password for the admin user and how to get its bcrypt hash into the migration without hardcoding plaintext.
   - Recommendation: Generate the hash during project init (`python -c "from passlib.context import CryptContext; print(CryptContext(['bcrypt']).hash('initial-password'))"`) and paste the hash into the migration file. Document the initial password in DEPLOYMENT.md.
   - **RESOLVED:** bcrypt hash computed at migration authoring time using `passlib.hash.bcrypt.hash('initial_password')` and hardcoded in the Alembic data migration (002_seed_sofabelle.py) as a constant. Initial password is `Admin1234!`. Hash embedded as `$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewFXi0F8lv8mzNqe`.

3. **`with_loader_criteria` and Tenant model exclusion**
   - What we know: `with_loader_criteria(Base, ...)` applies to all subclasses.
   - What's unclear: Whether the `Tenant` model itself needs a `tenant_id` column. Per CLAUDE.md, `tenants` and `admin_users` tables are exceptions.
   - Recommendation: Use `TenantScopedMixin` only on scoped models; `Tenant` inherits only `Base` (no mixin). In `do_orm_execute`, check `hasattr(cls, 'tenant_id')` before applying the filter.
   - **RESOLVED:** Apply `with_loader_criteria` to `TenantScopedMixin` (not `Base`). The `do_orm_execute` event listener checks `issubclass(entity, TenantScopedMixin)` to exclude the Tenant model automatically. Since `Tenant` inherits only `Base` + `TimestampMixin` (not `TenantScopedMixin`), queries against the tenants table are never filtered and never trigger `TenantIsolationError`.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker | All containers | ✓ | 29.4.1 | — |
| Docker Compose | All containers | ✓ | v5.1.3 | — |
| Node.js | Frontend dev | ✓ | v24.15.0 | — |
| Python 3.11+ | Backend | ✗ | 3.9.6 (system) | Install via uv or pyenv; Docker uses 3.11 image |
| pnpm | Frontend package manager | ✗ | — | Install: `npm install -g pnpm` |
| uv | Backend package manager | ✗ | — | Install: `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| PostgreSQL (local) | DB dev | ✗ | — | Use Docker (postgres:16-alpine) — preferred |
| Redis (local) | Celery/redbeat dev | ✗ | — | Use Docker (redis:7-alpine) — preferred |

**Missing dependencies with no fallback:**
- None — Docker is available and all services run in containers.

**Missing dependencies with fallback:**
- Python 3.11: system Python is 3.9.6. All backend development should use `uv venv` with Python 3.11 or run inside Docker. Docker image `python:3.11-slim` is the authoritative runtime.
- `pnpm` and `uv`: Not installed globally. Both must be installed before local development outside Docker. Docker build handles this automatically.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio 1.2.0 |
| Config file | `backend/pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `cd backend && pytest tests/unit -x` |
| Full suite command | `cd backend && pytest --cov=app --cov-report=term-missing` |

pytest-asyncio 1.2.0 uses `asyncio_mode = "auto"` (set in pyproject.toml) — no need to mark every async test.

```toml
# backend/pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INFRA-01 | `docker compose up -d` starts all services; `/healthz` returns 200 within 30s | smoke | `curl http://localhost:8000/healthz` | ❌ Wave 0 |
| INFRA-02 | Tables have `tenant_id NOT NULL` and `TIMESTAMPTZ` columns | unit (schema inspection) | `pytest tests/unit/test_models.py -x` | ❌ Wave 0 |
| INFRA-03 | `with_loader_criteria` seam present; query without tenant raises | unit | `pytest tests/unit/test_tenant_isolation.py -x` | ❌ Wave 0 |
| INFRA-04 | celery-redbeat keys appear in Redis after beat starts | integration | `pytest tests/integration/test_celery.py::test_redbeat_alive -x` | ❌ Wave 0 |
| INFRA-05 | `worker_process_init` disposes engine; no shared connections | unit | `pytest tests/unit/test_worker_init.py -x` | ❌ Wave 0 |
| INFRA-06 | structlog JSON output contains `tenant_id`; no PII in log | unit | `pytest tests/unit/test_logging.py -x` | ❌ Wave 0 |
| AUTH-01 | POST /auth/login with valid creds → 200 + access_token | integration | `pytest tests/integration/test_auth.py::test_login_success -x` | ❌ Wave 0 |
| AUTH-02 | POST /auth/refresh with valid cookie → 200 + new token | integration | `pytest tests/integration/test_auth.py::test_refresh_rotates -x` | ❌ Wave 0 |
| AUTH-03 | GET /dashboard without token → redirect to /login | e2e (proxy.ts) | `pnpm test:e2e` (Playwright, Phase 9) or manual check | ❌ — manual for Phase 1 |
| UI-01 | Romanian strings in sidebar + login page | manual / visual | Browser check; key strings in `messages/ro.json` | ❌ Wave 0 |
| PIPE-04 | `pipeline_runs` table exists after `alembic upgrade head` | integration | `pytest tests/integration/test_migrations.py::test_tables_exist -x` | ❌ Wave 0 |

**D-06 is SC#6 and is a required deliverable — the failing test must exist before implementation:**

```python
# tests/unit/test_tenant_isolation.py  (written first, before session.py enforcement exists)
async def test_query_without_tenant_context_raises():
    _tenant_id_var.set(None)
    async with AsyncSessionLocal() as session:
        with pytest.raises(TenantIsolationError):
            await session.execute(select(User))
```

### Sampling Rate

- **Per task commit:** `pytest tests/unit -x --tb=short`
- **Per wave merge:** `pytest --cov=app --cov-report=term-missing` (full suite)
- **Phase gate:** Full suite green + Docker stack smoke test (`curl http://localhost:8000/healthz` returns 200) before moving to Phase 2

### Wave 0 Gaps

- [ ] `tests/__init__.py` + `tests/unit/__init__.py` + `tests/integration/__init__.py`
- [ ] `tests/conftest.py` — shared fixtures: `db_session`, `client` (FastAPI TestClient), `test_tenant`
- [ ] `tests/unit/test_tenant_isolation.py` — covers INFRA-03, D-06, SC#6
- [ ] `tests/unit/test_models.py` — covers INFRA-02 (schema inspection via SQLAlchemy introspection)
- [ ] `tests/unit/test_logging.py` — covers INFRA-06
- [ ] `tests/integration/test_auth.py` — covers AUTH-01, AUTH-02
- [ ] `tests/integration/test_migrations.py` — covers PIPE-04, SC#2
- [ ] `tests/integration/test_celery.py` — covers INFRA-04, SC#4
- [ ] Framework install: `uv pip install pytest pytest-asyncio==1.2.0 pytest-cov factory-boy freezegun`

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | PyJWT + bcrypt/passlib; secure cookie for refresh token |
| V3 Session Management | yes | HttpOnly cookie for refresh; access token short-lived (15 min) |
| V4 Access Control | yes | proxy.ts route protection; tenant isolation via with_loader_criteria |
| V5 Input Validation | yes | Pydantic v2 on all request schemas; FastAPI auto-rejects malformed JSON |
| V6 Cryptography | yes | PyJWT HS256 (or RS256 if needed); bcrypt for passwords; Fernet for API creds |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| JWT algorithm confusion | Spoofing | PyJWT explicit `algorithms=["HS256"]` in `jwt.decode()` — never allow "none" |
| Stale JWT after logout | Spoofing | Refresh token rotation + short-lived access token (15 min TTL) |
| Tenant data leak | Information Disclosure | `with_loader_criteria` enforcement + D-06 failing test |
| PII in logs | Information Disclosure | structlog with NO PII rule; INFRA-06 test checks log output |
| CVE-2025-29927 Next.js middleware bypass | Elevation of Privilege | Patched in Next.js 16.2.x (our target); re-verify auth in Server Components |
| python-jose CVEs | Spoofing / DoS | Do NOT use python-jose; use PyJWT |
| Shared DB connections across fork | Tampering | worker_process_init disposes engine |

---

## Project Constraints (from CLAUDE.md)

| Constraint | Enforcement in Phase 1 |
|------------|----------------------|
| Async-first: all I/O via async/await | AsyncSession, async FastAPI endpoints, httpx.AsyncClient |
| `from __future__ import annotations` in every file | Enforced in all Python files from day 1 |
| `tenant_id` filter on every DB query | `with_loader_criteria` in session.py; D-06 test verifies |
| No secrets in code — Pydantic Settings | `app/core/config.py` inherits `BaseSettings`; `.env` file |
| No `print()` — structlog only | structlog configured in `app/core/logging.py` |
| Migrations only via Alembic | Base tables in Alembic; no raw DDL |
| Conventional Commits | Enforced via pre-commit hooks |
| Async/sync boundary: Celery tasks use `asyncio.run()` | Pattern documented in Pattern 4 |
| No MongoDB | PostgreSQL 16 only |
| No call transcription | Out of scope |
| No Claude API from HTTP handlers | Not applicable in Phase 1 (no Claude calls yet) |

---

## Sources

### Primary (HIGH confidence)
- [SQLAlchemy 2.0 — with_loader_criteria](https://docs.sqlalchemy.org/en/20/orm/queryguide/api.html#sqlalchemy.orm.with_loader_criteria) — with_loader_criteria signature, do_orm_execute pattern
- [SQLAlchemy 2.0 — Async I/O](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html) — create_async_engine, async_sessionmaker, per-worker engine initialization
- [Alembic — Cookbook (async)](https://alembic.sqlalchemy.org/en/latest/cookbook.html) — async_engine_from_config + connection.run_sync pattern
- [Next.js 16 Upgrade Guide](https://nextjs.org/docs/app/guides/upgrading/version-16) — middleware→proxy rename, breaking changes
- [celery-redbeat docs](https://redbeat.readthedocs.io/en/latest/config.html) — redbeat_redis_url, redbeat_lock_timeout
- [Celery Signals docs](https://docs.celeryq.dev/en/main/userguide/signals.html) — worker_process_init
- [structlog contextvars](https://www.structlog.org/en/latest/contextvars.html) — merge_contextvars, bind_contextvars, BaseHTTPMiddleware caveat
- [next-intl — App Router getting started](https://next-intl.dev/docs/getting-started/app-router) — getRequestConfig, NextIntlClientProvider
- [next-intl — proxy.ts / middleware](https://next-intl.dev/docs/routing/middleware) — createMiddleware, routing composition

### Secondary (MEDIUM confidence)
- [PyPI registry — celery-redbeat 2.3.3](https://pypi.org/project/celery-redbeat/) — version confirmed
- [PyPI registry — PyJWT 2.12.1](https://pypi.org/project/PyJWT/) — version confirmed; actively maintained
- [npm registry — next-intl 4.12.0](https://www.npmjs.com/package/next-intl) — v4 breaking changes confirmed
- [npm registry — jose 6.2.3](https://www.npmjs.com/package/jose) — Node.js JWT verification for proxy.ts
- [CVE-2024-33663](https://www.sentinelone.com/vulnerability-database/cve-2024-33663/) — python-jose algorithm confusion
- [CVE-2024-33664](https://github.com/advisories/GHSA-cjwg-qfpm-7377) — python-jose JWT bomb

### Tertiary (LOW confidence)
- WebSearch results on `worker_process_init` + SQLAlchemy pattern — consistent across multiple sources but not from official SQLAlchemy docs

---

## Metadata

**Confidence breakdown:**
- Standard stack versions: HIGH — verified via `pip3 index versions` and `npm view`
- SQLAlchemy async + tenant isolation pattern: HIGH — verified via official SQLAlchemy 2.0 docs
- Alembic async env.py: HIGH — verified via official Alembic cookbook
- Next.js 16 proxy.ts rename: HIGH — verified via official Next.js 16 upgrade guide (fetched directly)
- next-intl v4 breaking changes: HIGH — verified via official next-intl docs
- celery-redbeat config: MEDIUM — docs fetched but lock_timeout behavior confirmed from ReadTheDocs
- Celery worker_process_init: MEDIUM — official Celery docs + multiple community sources

**Research date:** 2026-05-20
**Valid until:** 2026-08-20 (stable ecosystem; Next.js and next-intl move faster — recheck before 2026-07-20 if planning is delayed)
