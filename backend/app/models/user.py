from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin


class User(Base, TenantScopedMixin):
    """User model — represents an authenticated user within a tenant.

    Inherits TenantScopedMixin which provides:
      - id: UUID primary key
      - tenant_id: UUID NOT NULL (enforced by with_loader_criteria in session.py)
      - created_at / updated_at: TIMESTAMPTZ

    Every query against this table automatically receives a tenant_id filter
    via the do_orm_execute event listener in session.py (INFRA-03, D-06).

    Passwords are stored as bcrypt hashes — never plaintext. The initial admin
    user is seeded via Alembic migration 002_seed_sofabelle.py.
    """

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    # Пользователь, пришедший из движка, пароля здесь не имеет и иметь не должен.
    hashed_password: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Тот же человек в движке. Связь по идентификатору, а не по почте: почта
    # меняется, и после смены пользователь оказался бы новым — без переписок,
    # без истории, с чужим ощущением, что кабинет всё забыл.
    engine_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, unique=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
