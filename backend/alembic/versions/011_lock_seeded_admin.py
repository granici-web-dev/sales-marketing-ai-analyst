"""Убрать пароль у засеянной учётки администратора.

Миграция 002 заводила `admin@sofabelle.ro` с bcrypt-хешем пароля
«Admin1234!», а сам пароль стоял в комментарии рядом. Нашли сканеры
(semgrep detected-bcrypt-hash), причём в открытом репозитории, то есть
хеш и пароль к нему видны всем и останутся в истории навсегда.

Входа по паролю в кабинете нет: пользователь приходит сессией движка,
и такие пользователи заводятся с hashed_password = NULL. Проверять
пароль в этом коде некому, поэтому дверь эта не открывала. Опасность
отложенная: появится вход по паролю — и учётка примет общеизвестный
пароль молча, без единой новой строки в миграциях. Такие сюрпризы
находят не тогда, когда их ищут.

Здесь пароль снимается. Условие в WHERE узкое намеренно: если кто-то
успел поставить учётке настоящий хеш, миграция его не тронет — она
чистит ровно два известных значения, старый хеш и «!» из правленной 002.

Revision ID: 011
Revises: 010
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa

from alembic import op

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None

ADMIN_USER_ID = "00000000-0000-0000-0000-000000000002"

# Хеш из прежней 002. Он и так лежит в истории репозитория; смысл не в том,
# чтобы его спрятать, а в том, чтобы найти строку, которая ему равна.
# Сканер находит его здесь и прав по форме: это действительно хеш пароля
# в коде. Подавлено, потому что миграция, которая убирает утёкший хеш,
# обязана его назвать — иначе она не найдёт, что убирать.
# nosemgrep: generic.secrets.security.detected-bcrypt-hash.detected-bcrypt-hash
LEAKED_HASH = "$2b$12$NiZht6VcY7E5p2r0aMRtW.ODg6uvd/PvEC78f71SuXbqggJW319vy"
LOCKED_PASSWORD = "!"


def upgrade() -> None:
    # uuid.UUID, а не строка: asyncpg выводит для строки тип VARCHAR, и
    # postgres отказывается сравнивать его с колонкой uuid. Та же грабля
    # описана в 002 — здесь она наступила на прогоне на чистой базе.
    op.execute(
        sa.text("""
            UPDATE users
               SET hashed_password = NULL, updated_at = now()
             WHERE id = :id
               AND hashed_password IN (:leaked, :locked)
        """).bindparams(id=uuid.UUID(ADMIN_USER_ID), leaked=LEAKED_HASH, locked=LOCKED_PASSWORD)
    )


def downgrade() -> None:
    # Обратного хода нет намеренно: «вернуть общеизвестный пароль» — не та
    # операция, которую стоит делать одной командой.
    pass
