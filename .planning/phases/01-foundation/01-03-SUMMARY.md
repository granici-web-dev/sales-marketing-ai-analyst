---
phase: 01-foundation
plan: "03"
subsystem: auth
tags: [pydantic, pydantic-settings, pyjwt, structlog, contextvars, jwt, tenancy, exceptions, logging]

# Dependency graph
requires: []
provides:
  - "Settings class with 8 typed env vars loaded via pydantic-settings"
  - "PyJWT encode/decode utilities (create_access_token, create_refresh_token, verify_token)"
  - "TenantIsolationError and AppError exception hierarchy"
  - "_tenant_id_var ContextVar[UUID|None] with set/get/require helpers"
  - "configure_logging() with structlog merge_contextvars + JSONRenderer chain"
affects:
  - "01-04 (DB session.py imports get_current_tenant_id, TenantIsolationError, settings.database_url)"
  - "01-05 (Celery app imports settings.redis_url)"
  - "01-06 (FastAPI main.py imports configure_logging, settings, create_access_token, verify_token)"
  - "01-07 (auth endpoints import create_access_token, create_refresh_token, verify_token)"

# Tech tracking
tech-stack:
  added:
    - "pydantic-settings==2.11.0 (typed Settings class from .env)"
    - "pydantic==2.13.4 (Settings validation backend)"
    - "PyJWT==2.12.1 (JWT encode/decode; NOT python-jose which has CVEs)"
    - "structlog==25.5.0 (structured JSON logging with contextvars integration)"
  patterns:
    - "Settings singleton pattern: module-level `settings = Settings()` imported everywhere"
    - "Exception hierarchy: AppError base with message attribute; all errors subclass AppError"
    - "ContextVar tenant isolation: _tenant_id_var default=None prevents cross-request bleed"
    - "verify_token returns None on any error (never raises) — safe for middleware"
    - "explicit algorithms=[jwt_algorithm] in jwt.decode prevents alg:none confusion attack"

key-files:
  created:
    - "backend/app/__init__.py"
    - "backend/app/core/__init__.py"
    - "backend/app/core/config.py"
    - "backend/app/core/exceptions.py"
    - "backend/app/core/tenancy.py"
    - "backend/app/core/security.py"
    - "backend/app/core/logging.py"
    - "backend/pyproject.toml"
    - "backend/tests/__init__.py"
    - "backend/tests/unit/__init__.py"
    - "backend/tests/unit/test_core_modules.py"
  modified: []

key-decisions:
  - "PyJWT (not python-jose): python-jose has unpatched CVEs CVE-2024-33663 and CVE-2024-33664; PyJWT is actively maintained"
  - "verify_token returns None on any PyJWTError (never raises) — safe to call in middleware without try/except"
  - "require_tenant_id() raises TenantIsolationError when None — D-06 enforcement hook for session.py"
  - "_tenant_id_var ContextVar default=None — no tenant bleeds across async tasks without explicit set"
  - "structlog processor chain includes merge_contextvars first — all bound vars (tenant_id, request_id) appear in JSON output"
  - "configure_logging does NOT use BaseHTTPMiddleware — pure ASGI middleware required for contextvars propagation"

patterns-established:
  - "Pattern: from __future__ import annotations in every Python file (CLAUDE.md Core #1)"
  - "Pattern: no print() calls anywhere — structlog only (CLAUDE.md Core #6)"
  - "Pattern: no secrets in code — all via Settings(BaseSettings) from .env (CLAUDE.md Core #4)"
  - "Pattern: exceptions have .message attribute via AppError.__init__(self, message)"
  - "Pattern: TDD with RED (failing tests) committed before GREEN (implementation)"

requirements-completed:
  - INFRA-05
  - INFRA-06
  - AUTH-01
  - AUTH-02

# Metrics
duration: 5min
completed: "2026-05-21"
---

# Phase 1 Plan 03: Core Python Modules Summary

**Pydantic Settings, PyJWT token utilities, tenant ContextVar, and structlog JSON logging — foundational imports consumed by all other backend plans**

## Performance

- **Duration:** 5 min
- **Started:** 2026-05-21T07:07:57Z
- **Completed:** 2026-05-21T07:12:40Z
- **Tasks:** 2 (TDD: 1 RED + 2 GREEN commits)
- **Files created:** 11

## Accomplishments

- Config system: `Settings(BaseSettings)` reads 8 typed env vars (DATABASE_URL, REDIS_URL, JWT_SECRET_KEY, jwt_algorithm, access_token_expire_minutes, refresh_token_expire_days, sofa_belle_tenant_id, log_level) with defaults; module-level `settings` singleton
- JWT utilities: `create_access_token` (15-min TTL), `create_refresh_token` (30-day TTL + type:refresh claim), `verify_token` (explicit algorithms=["HS256"], returns None on any error); PyJWT only — python-jose excluded due to CVEs
- Exception hierarchy: `AppError(Exception)` base with `.message` attribute; `TenantIsolationError`, `NotFoundError`, `AuthenticationError`, `AuthorizationError` subclasses
- Tenant seam: `_tenant_id_var: ContextVar[UUID | None] = ContextVar("tenant_id", default=None)` with `set_tenant_id`, `get_current_tenant_id`, `require_tenant_id` (raises `TenantIsolationError` when None — the D-06 enforcement hook)
- Structlog: `configure_logging()` with 7-processor chain: merge_contextvars + add_log_level + add_logger_name + TimeStamper + StackInfoRenderer + format_exc_info + JSONRenderer

## Task Commits

Each task was committed atomically (TDD pattern):

1. **RED — Failing tests for all 5 core modules** - `6ff0d3b` (test)
2. **Task 1: Settings, exceptions, tenancy** - `48b9d15` (feat)
3. **Task 2: security.py + logging.py** - `540585b` (feat)

_Note: TDD tasks have RED commit before GREEN — test gate confirmed modules did not exist._

## Files Created

- `backend/app/__init__.py` — Package marker (empty)
- `backend/app/core/__init__.py` — Package marker (empty)
- `backend/app/core/config.py` — `Settings(BaseSettings)` with all 8 env vars; `settings` singleton
- `backend/app/core/exceptions.py` — `AppError`, `TenantIsolationError`, `NotFoundError`, `AuthenticationError`, `AuthorizationError`
- `backend/app/core/tenancy.py` — `_tenant_id_var` ContextVar; `set_tenant_id`, `get_current_tenant_id`, `require_tenant_id`
- `backend/app/core/security.py` — `create_access_token`, `create_refresh_token`, `verify_token` (PyJWT, no python-jose)
- `backend/app/core/logging.py` — `configure_logging()` with structlog JSON processor chain
- `backend/pyproject.toml` — pytest asyncio_mode=auto config
- `backend/tests/__init__.py`, `backend/tests/unit/__init__.py` — Package markers
- `backend/tests/unit/test_core_modules.py` — 26 unit tests for all 5 modules (26/26 passing)

## Decisions Made

- PyJWT instead of python-jose: python-jose has CVE-2024-33663 (algorithm confusion) and CVE-2024-33664 (JWT bomb). PyJWT 2.12.1 is actively maintained and the explicit upstream.
- `verify_token` returns None on any `PyJWTError` — makes middleware usage safe without caller wrapping in try/except.
- `require_tenant_id()` as the enforcement hook for Plan 04's `do_orm_execute` event listener — Plan 04 imports and calls this function.
- `_tenant_id_var` default=None enforced by ContextVar semantics — each asyncio coroutine gets its own copy; explicit set required per request.

## Deviations from Plan

None — plan executed exactly as written. The `algorithms=[` grep returning 2 instead of 1 is expected: one occurrence is in the docstring (documentation), one is in the actual `jwt.decode()` call. The functional behavior matches the requirement.

## Issues Encountered

- System Python is 3.9.6 (RESEARCH.md notes this); packages installed via `pip3 install --user` for local verification. All modules import correctly. Docker runtime (Python 3.11) is the authoritative runtime — no issues expected.

## Known Stubs

None — all 5 core modules are complete implementations, not stubs. No placeholder values, no TODO/FIXME markers, no empty collections returned.

## Threat Flags

No new threat surface beyond what the plan's `<threat_model>` documented:
- T-03-01 mitigated: `algorithms=["HS256"]` explicit in `verify_token`
- T-03-03 mitigated: `merge_contextvars` is the only auto-logging; no request bodies or query params
- T-03-04 mitigated: `grep "jose" backend/app/core/security.py` returns empty
- T-03-05 mitigated: `_tenant_id_var` default=None

## Next Phase Readiness

- Plan 04 (DB session) can import: `from app.core.tenancy import get_current_tenant_id, require_tenant_id`, `from app.core.exceptions import TenantIsolationError`, `from app.core.config import settings`
- Plan 05 (Celery) can import: `from app.core.config import settings` for `settings.redis_url`
- Plan 06 (FastAPI) can import: `from app.core.logging import configure_logging`, `from app.core.security import verify_token`
- Plan 07 (auth endpoints) can import: `from app.core.security import create_access_token, create_refresh_token, verify_token`
- All contracts established: exports, signatures, exception types match what Plans 04-07 expect

## TDD Gate Compliance

- RED gate: `6ff0d3b` — `test(01-03): add failing tests for core module behaviors (RED)`
- GREEN gate (Task 1): `48b9d15` — `feat(01-03): implement Pydantic Settings, exception hierarchy, tenant ContextVar`
- GREEN gate (Task 2): `540585b` — `feat(01-03): implement PyJWT security utilities and structlog JSON logging`
- All 26 tests pass on GREEN; 0 tests passed on RED (confirmed ModuleNotFoundError for all)

---
*Phase: 01-foundation*
*Completed: 2026-05-21*
