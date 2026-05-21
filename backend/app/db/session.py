from __future__ import annotations

import asyncio

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, with_loader_criteria

from app.core.config import settings
from app.core.tenancy import get_current_tenant_id
from app.db.base import TenantScopedMixin


def _create_engine():
    """Create a new SQLAlchemy async engine from settings.

    Extracted as a callable function so init_worker_process() can create
    a fresh engine per Celery child process after fork (INFRA-05).
    Pool settings follow RESEARCH.md recommendations for PostgreSQL.
    """
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        echo=False,
    )


def _create_session_factory(eng):
    """Create a new async session factory bound to the given engine.

    Extracted as a callable function so init_worker_process() can rebind
    the factory to the fresh per-worker engine (INFRA-05, Pattern 4).
    expire_on_commit=False avoids lazy-load errors after session.commit()
    in async contexts.
    """
    return async_sessionmaker(eng, expire_on_commit=False, class_=AsyncSession)


# Module-level engine and session factory.
# WARNING: Do NOT share these across fork boundaries — Celery's prefork pool
# will call init_worker_process() in each child to dispose and recreate these.
engine = _create_engine()
AsyncSessionLocal = _create_session_factory(engine)


@event.listens_for(Session, "do_orm_execute")
def _add_tenant_filter(execute_state) -> None:  # type: ignore[no-untyped-def]
    """Tenant isolation seam — the most security-critical code in Phase 1.

    Intercepts every ORM SELECT and injects a tenant_id WHERE clause via
    with_loader_criteria. This implements INFRA-03 and D-06 (SC#6):

    - Checks execute_state.is_select to skip INSERT/UPDATE/DELETE.
    - Checks is_column_load / is_relationship_load to skip internal ORM loads
      that are already tenant-scoped by their parent query.
    - If no tenant context is set (ContextVar is None), raises TenantIsolationError
      immediately — no query reaches the database.
    - Uses TenantScopedMixin (NOT Base) as the criteria target:
        * Tenant model inherits Base + TimestampMixin only (not TenantScopedMixin)
        * Applying criteria to Base would try cls.tenant_id on Tenant → AttributeError
        * Using TenantScopedMixin excludes Tenant from filtering automatically
    - include_aliases=True ensures joined-load aliases also carry the tenant filter
      (T-04-05 mitigation).

    Threat model coverage:
      T-04-01: Information Disclosure — tenant data leak via missing filter.
      T-04-03: Tampering — criteria applied to Tenant model (excluded via mixin).
      T-04-05: EoP — joined-load aliases also filtered via include_aliases=True.
    """
    if (
        execute_state.is_select
        and not execute_state.is_column_load
        and not execute_state.is_relationship_load
    ):
        tenant_id = get_current_tenant_id()
        if tenant_id is None:
            from app.core.exceptions import TenantIsolationError

            raise TenantIsolationError("No tenant context set — refusing query")
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                TenantScopedMixin,
                lambda cls: cls.tenant_id == tenant_id,
                include_aliases=True,
            )
        )


def init_worker_process(**kwargs) -> None:  # type: ignore[no-untyped-def]
    """Dispose parent engine and create a fresh one in each Celery worker process.

    INFRA-05 / Pattern 4: SQLAlchemy asyncpg connections must not cross fork
    boundaries. This function is wired to the Celery `worker_process_init`
    signal in app/tasks/celery_app.py. It fires in each child after the
    prefork pool creates it.

    Uses sys.modules[__name__] to reassign module-level attributes without
    the `global` keyword — required for Python module attribute reassignment
    from within a function scope.
    """
    import sys

    mod = sys.modules[__name__]
    asyncio.run(mod.engine.dispose())
    mod.engine = _create_engine()
    mod.AsyncSessionLocal = _create_session_factory(mod.engine)
