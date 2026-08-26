"""Seed Sofa Belle tenant and admin user — idempotent initial data.

Revision ID: 002
Revises: 001
Create Date: 2026-05-21

Seeds the initial Sofa Belle tenant record and the admin user account.
Both inserts use ON CONFLICT (id) DO NOTHING for idempotency (D-07):
running `alembic upgrade head` multiple times does not create duplicate records.

О пароле (правка после прогона сканеров, миграция 011).

Здесь стоял bcrypt-хеш пароля «Admin1234!», а сам пароль — в этой самой
строке рядом с ним. То есть «плейнтекст нигде не хранится» было неправдой:
он хранился в двух видах сразу, в файле, который лежит в открытом репозитории.

Двери это не открывало: входа по паролю в кабинете нет вовсе — пользователь
приходит сессией движка, и такие пользователи заводятся с hashed_password
= NULL (см. app/services/auth/link.py). Проверять пароль в этом коде некому.
Но появится вход по паролю — и эта учётка примет общеизвестный пароль
молча, без единой новой строки в миграциях.

Поэтому сюда пишется «!» — значение, которое не является хешем ничего и
которому не соответствует ни один пароль: bcrypt на нём не совпадёт никогда.
На момент этой миграции колонка ещё NOT NULL (её отпускает 010), поэтому
NULL здесь написать нельзя. Миграция 011 доводит до NULL и вычищает старый
хеш из баз, где он уже успел записаться.

This migration does NOT need a downgrade — seed data is not reversed.
If re-running from scratch, drop and recreate the database.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic
revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# UUIDs are fixed constants — match settings.sofa_belle_tenant_id in config.py.
# These are safe to commit: they are tenant identifiers, not secrets.
SOFA_BELLE_TENANT_ID = "00000000-0000-0000-0000-000000000001"
ADMIN_USER_ID = "00000000-0000-0000-0000-000000000002"
ADMIN_EMAIL = "admin@sofabelle.ro"

# Запертая учётка: «!» не является bcrypt-хешем, и ни один пароль ему
# не соответствует. Колонка на этом шаге ещё NOT NULL — см. docstring.
LOCKED_PASSWORD = "!"


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
    # Пароля у учётки нет — см. docstring модуля.
    op.execute(
        sa.text("""
            INSERT INTO users (id, tenant_id, email, hashed_password, is_active, created_at, updated_at)
            VALUES (:id, :tenant_id, :email, :pw, true, now(), now())
            ON CONFLICT (id) DO NOTHING
        """).bindparams(
            id=admin_uuid,
            tenant_id=tenant_uuid,
            email=ADMIN_EMAIL,
            pw=LOCKED_PASSWORD,
        )
    )


def downgrade() -> None:
    # Seed data is intentionally not reversed.
    # If you need to remove seed data, do so manually or recreate the database.
    pass
