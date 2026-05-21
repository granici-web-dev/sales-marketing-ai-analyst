from __future__ import annotations

"""
INFRA-02 schema inspection tests.

Verifies that all tenant-scoped tables have:
- tenant_id column with nullable=False
- created_at column with TIMESTAMPTZ type

These tests run against the SQLAlchemy model definitions (no DB required).
They will fail with ImportError until implementation plans complete — expected.
"""

import pytest
from sqlalchemy.dialects.postgresql import TIMESTAMPTZ

# Skipped until implementation exists — imports are stubs only
pytestmark = pytest.mark.skip(reason="Stubs — implementation pending (Wave 0 gate)")

try:
    from app.db.base import Base, TenantScopedMixin
except ImportError:
    Base = None  # type: ignore[assignment]
    TenantScopedMixin = None  # type: ignore[assignment]

try:
    from app.models.user import User
except ImportError:
    User = None  # type: ignore[assignment]

try:
    from app.models.pipeline import SyncRun, PipelineRun
except ImportError:
    SyncRun = None  # type: ignore[assignment]
    PipelineRun = None  # type: ignore[assignment]

try:
    from app.models.tenant import Tenant
except ImportError:
    Tenant = None  # type: ignore[assignment]


def test_tenant_id_not_null() -> None:
    """INFRA-02: users.tenant_id must be NOT NULL.

    Inspects the SQLAlchemy model directly without a DB connection.
    Requirement: tenant_id column is non-nullable on all tenant-scoped tables.
    """
    if User is None:
        pytest.fail("app.models.user.User not importable — implementation pending")

    column = User.__table__.columns["tenant_id"]
    assert column.nullable is False, (
        f"users.tenant_id must be NOT NULL (nullable=False), got nullable={column.nullable}"
    )


def test_created_at_is_timestamptz() -> None:
    """INFRA-02: users.created_at must use TIMESTAMPTZ (not TIMESTAMP).

    PostgreSQL TIMESTAMP without timezone is ambiguous for international deployments.
    TIMESTAMPTZ stores UTC and displays in session timezone.
    """
    if User is None:
        pytest.fail("app.models.user.User not importable — implementation pending")

    column = User.__table__.columns["created_at"]
    assert isinstance(column.type, TIMESTAMPTZ), (
        f"users.created_at must be TIMESTAMPTZ, got {type(column.type).__name__}"
    )


def test_pipeline_run_has_tenant_id() -> None:
    """INFRA-02 + PIPE-04: pipeline_runs table must have tenant_id column.

    Required for multi-tenancy schema compliance (even though enforcement is
    deferred to Iteration 4 per CONTEXT.md).
    """
    if PipelineRun is None:
        pytest.fail("app.models.pipeline.PipelineRun not importable — implementation pending")

    assert "tenant_id" in PipelineRun.__table__.columns, (
        "pipeline_runs table must have a tenant_id column (INFRA-02)"
    )


def test_sync_run_has_tenant_id() -> None:
    """INFRA-02: sync_runs table must have tenant_id column.

    Required for multi-tenancy schema compliance.
    """
    if SyncRun is None:
        pytest.fail("app.models.pipeline.SyncRun not importable — implementation pending")

    assert "tenant_id" in SyncRun.__table__.columns, (
        "sync_runs table must have a tenant_id column (INFRA-02)"
    )


def test_tenant_model_has_no_tenant_id() -> None:
    """INFRA-02: tenants table must NOT have a tenant_id column.

    Per CLAUDE.md: 'Every table except `tenants`, `admin_users`' requires tenant_id.
    The tenants table is the root — it cannot reference itself.
    """
    if Tenant is None:
        pytest.fail("app.models.tenant.Tenant not importable — implementation pending")

    assert "tenant_id" not in Tenant.__table__.columns, (
        "tenants table must NOT have a tenant_id column (it IS the tenant root, "
        "per CLAUDE.md exception for tenants table)"
    )
