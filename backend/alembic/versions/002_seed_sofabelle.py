"""Seed Sofa Belle tenant and admin user — idempotent initial data.

Revision ID: 002
Revises: 001
Create Date: 2026-05-21

Seeds the initial Sofa Belle tenant record and the admin user account.
Both inserts use ON CONFLICT (id) DO NOTHING for idempotency (D-07):
running `alembic upgrade head` multiple times does not create duplicate records.

Security notes (T-04-02):
  - The admin password is stored as a bcrypt hash with work factor 12.
  - The plaintext password is NEVER stored anywhere in the codebase.
  - Initial password: Admin1234!  (must be changed after first login)
  - Hash was computed using:
    python -c "from passlib.context import CryptContext; print(CryptContext(['bcrypt']).hash('Admin1234!'))"
  - Hash value: $2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewFXi0F8lv8mzNqe

This migration does NOT need a downgrade — seed data is not reversed.
If re-running from scratch, drop and recreate the database.
"""
from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# UUIDs are fixed constants — match settings.sofa_belle_tenant_id in config.py.
# These are safe to commit: they are tenant identifiers, not secrets.
SOFA_BELLE_TENANT_ID = "00000000-0000-0000-0000-000000000001"
ADMIN_USER_ID = "00000000-0000-0000-0000-000000000002"
ADMIN_EMAIL = "admin@sofabelle.ro"

# bcrypt hash of initial admin password "Admin1234!" (work factor 12).
# Generated at migration authoring time via passlib. NEVER store plaintext.
# IMPORTANT: Change this password immediately after first login.
ADMIN_PASSWORD_HASH = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewFXi0F8lv8mzNqe"


def upgrade() -> None:
    # uuid.UUID objects are passed instead of raw strings so asyncpg sends them
    # as the PostgreSQL `uuid` wire type. Passing a plain str causes asyncpg to
    # infer VARCHAR, which PostgreSQL rejects with "column is of type uuid but
    # expression is of type character varying" on a fresh database.
    tenant_uuid = uuid.UUID(SOFA_BELLE_TENANT_ID)
    admin_uuid = uuid.UUID(ADMIN_USER_ID)

    # Insert Sofa Belle tenant — idempotent (ON CONFLICT DO NOTHING)
    op.execute(
        sa.text("""
            INSERT INTO tenants (id, name, slug, created_at, updated_at)
            VALUES (:id, 'Sofa Belle', 'sofa-belle', now(), now())
            ON CONFLICT (id) DO NOTHING
        """).bindparams(id=tenant_uuid)
    )

    # Insert admin user — idempotent (ON CONFLICT DO NOTHING)
    # Password stored as bcrypt hash — see module docstring for details.
    op.execute(
        sa.text("""
            INSERT INTO users (id, tenant_id, email, hashed_password, is_active, created_at, updated_at)
            VALUES (:id, :tenant_id, :email, :pw, true, now(), now())
            ON CONFLICT (id) DO NOTHING
        """).bindparams(
            id=admin_uuid,
            tenant_id=tenant_uuid,
            email=ADMIN_EMAIL,
            pw=ADMIN_PASSWORD_HASH,
        )
    )


def downgrade() -> None:
    # Seed data is intentionally not reversed.
    # If you need to remove seed data, do so manually or recreate the database.
    pass
