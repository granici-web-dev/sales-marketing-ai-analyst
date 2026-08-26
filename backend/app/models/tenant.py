from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Tenant(Base, TimestampMixin):
    """The Tenant model — represents a client organisation in the multi-tenant system.

    Intentionally does NOT inherit TenantScopedMixin and therefore has NO
    tenant_id column. The Tenant record IS the tenant; applying a tenant_id
    filter to it would be circular.

    CLAUDE.md Core Principle #3 exception: `tenants` and `admin_users` tables
    are the only tables permitted to omit `tenant_id`.

    The `with_loader_criteria` seam in session.py uses `TenantScopedMixin`
    (not Base) as the target, so queries against this table are never filtered
    and never trigger TenantIsolationError.
    """

    __tablename__ = "tenants"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    # Тот же клиент в движке. NULL — аналитик этому клиенту ещё не подключён,
    # и вход через движок для него закрыт: пускать в чужие данные по совпадению
    # почты нельзя, а другого признака у нас нет.
    engine_tenant_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, unique=True
    )
