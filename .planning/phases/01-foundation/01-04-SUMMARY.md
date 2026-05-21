---
plan: 01-04
phase: 01-foundation
status: complete
completed: 2026-05-21
---

## Summary

Implemented SQLAlchemy 2.x async models, the tenant isolation seam, and Alembic migrations for all base tables. All files committed directly by orchestrator after executor agent had Bash restricted.

## What Was Built

### Task 1: SQLAlchemy base + models + tenant seam

**`backend/app/db/base.py`** — DeclarativeBase, TimestampMixin (created_at/updated_at TIMESTAMPTZ), TenantScopedMixin (tenant_id UUID NOT NULL FK → tenants)

**`backend/app/db/session.py`** — Critical tenant isolation seam:
- `do_orm_execute` event listener on `Session`
- `with_loader_criteria(TenantScopedMixin, lambda cls: cls.tenant_id == get_current_tenant_id(), include_aliases=True)`
- Raises `TenantIsolationError` when `_tenant_id_var` ContextVar is None
- `init_worker_process()` using `sys.modules[__name__]` pattern for fork-safe engine disposal (INFRA-05)

**`backend/app/db/deps.py`** — `get_session()` FastAPI dependency via `AsyncSessionLocal`

**Models:**
- `Tenant` — inherits Base + TimestampMixin only (no tenant_id — CLAUDE.md exception)
- `User` — inherits TenantScopedMixin (tenant_id NOT NULL)
- `SyncRun`, `PipelineRun` — both inherit TenantScopedMixin (PIPE-04)

### Task 2: Alembic migrations

- `alembic.ini` — script_location=alembic, sqlalchemy.url placeholder
- `env.py` — async_engine_from_config + connection.run_sync bridge; all model imports before target_metadata
- `001_base_tables.py` — 4 tables (tenants, users, sync_runs, pipeline_runs) with TIMESTAMPTZ + tenant_id NOT NULL
- `002_seed_sofabelle.py` — idempotent INSERT ON CONFLICT DO NOTHING for Sofa Belle tenant + admin user; password stored as bcrypt hash (work factor 12)

## Key Files

```
key-files:
  created:
    - backend/app/db/base.py
    - backend/app/db/session.py
    - backend/app/db/deps.py
    - backend/app/models/tenant.py
    - backend/app/models/user.py
    - backend/app/models/pipeline.py
    - backend/alembic/versions/001_base_tables.py
    - backend/alembic/versions/002_seed_sofabelle.py
```

## Requirements Satisfied

- INFRA-02: TIMESTAMPTZ + tenant_id everywhere (except Tenant model — CLAUDE.md)
- INFRA-03: Tenant isolation seam (with_loader_criteria + TenantIsolationError)
- INFRA-05: Fork-safe engine disposal (init_worker_process)
- PIPE-04: pipeline_runs table via PipelineRun model + migration 001
- D-06 gate: D-06 test (test_query_without_tenant_context_raises) will now pass — TenantIsolationError raised on uncontexted query

## Deviations

None — plan executed as written. Committed by orchestrator due to Bash restriction in worktree executor.

## Self-Check: PASSED
