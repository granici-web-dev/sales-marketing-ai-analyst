from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# SQLAlchemy uses TIMESTAMP(timezone=True) to map to PostgreSQL TIMESTAMPTZ.
# The 'TIMESTAMPTZ' SQL alias is not a Python class in the dialect module.
TIMESTAMPTZ = DateTime(timezone=True)


class Base(DeclarativeBase):
    """Declarative base for all SQLAlchemy models.

    All models must inherit from this class. Models that are tenant-scoped
    (every table except `tenants` and `admin_users`) must also inherit
    TenantScopedMixin, which is the target of `with_loader_criteria` in session.py.
    """


class TimestampMixin:
    """Adds created_at and updated_at columns with TIMESTAMPTZ type.

    INFRA-02 requirement: all tables must use TIMESTAMPTZ (not TIMESTAMP)
    to avoid timezone ambiguity. server_default=func.now() sets the column
    value at the DB level, ensuring correct timezone handling regardless of
    application timezone.
    """

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class TenantScopedMixin(TimestampMixin):
    """Mixin for all tenant-scoped tables (every table except `tenants`).

    Inheriting this mixin adds:
      - id: UUID primary key (auto-generated)
      - tenant_id: UUID NOT NULL (foreign key enforced at migration level)
      - created_at / updated_at: TIMESTAMPTZ via TimestampMixin

    The `with_loader_criteria` in session.py targets THIS mixin (not Base),
    so the Tenant model (which inherits only Base + TimestampMixin) is
    excluded from automatic tenant filtering — avoiding AttributeError on
    queries against the `tenants` table.

    CLAUDE.md Core Principle #3: EVERY query to tenant-scoped tables must
    filter by tenant_id. This mixin is the structural enforcement point.
    """

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
