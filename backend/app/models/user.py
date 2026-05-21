from __future__ import annotations

from sqlalchemy import Boolean, Text
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
    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
