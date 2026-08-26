from __future__ import annotations

from contextvars import ContextVar
from uuid import UUID

from app.core.exceptions import TenantIsolationError

# ContextVar default=None ensures no tenant bleeds across async tasks or requests.
# Each asyncio coroutine gets its own copy of the context — ContextVar semantics
# guarantee isolation without explicit cleanup between requests.
_tenant_id_var: ContextVar[UUID | None] = ContextVar("tenant_id", default=None)


def set_tenant_id(tenant_id: UUID) -> None:
    """Set the current tenant ID in the async context.

    Called by FastAPI middleware (StructlogContextMiddleware) at the start
    of every request. In MVP1-3, this is always the hardcoded Sofa Belle UUID;
    in Iteration 4, it will be extracted from the JWT tenant_id claim.
    """
    _tenant_id_var.set(tenant_id)


def get_current_tenant_id() -> UUID | None:
    """Return the current tenant ID from the async context, or None if not set."""
    return _tenant_id_var.get()


def require_tenant_id() -> UUID:
    """Return the current tenant ID or raise TenantIsolationError if not set.

    Used by the SQLAlchemy do_orm_execute event listener (session.py) to
    enforce the multi-tenancy seam — any ORM SELECT without a tenant context
    is rejected before touching the database.

    Raises:
        TenantIsolationError: When no tenant context is set in the current
            async task / request context.
    """
    tenant_id = get_current_tenant_id()
    if tenant_id is None:
        raise TenantIsolationError("No tenant context set — refusing query")
    return tenant_id
