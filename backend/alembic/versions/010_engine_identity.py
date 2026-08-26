"""Личность приезжает из движка.

Аналитик держал свою таблицу пользователей и свой пароль. Пока он был
единственным кабинетом, это было нормально; в портале, где семь агентов и
одна учётная запись Davoq, вторая пара «логин-пароль» — это вторая дверь
в один дом, и клиент вправе спросить, зачем их две.

Личность теперь удостоверяет движок. Здесь появляются две привязки к нему
и снимается требование пароля.

── Почему привязка, а не общий идентификатор ──

Заманчиво было бы взять UUID арендатора из движка и записать его в
`tenants.id` аналитика. Так делать нельзя: на этот идентификатор ссылается
каждая тенантная таблица, и смена ключа переписала бы всю базу ради
стройности. Отдельная колонка стоит одного индекса и не трогает ни строки.

── Почему пароль становится необязательным, а не удаляется ──

Пользователь, пришедший из движка, пароля здесь не имеет и иметь не должен.
Но удалять колонку рано: пока привязка не проставлена ни одному арендатору,
старый вход остаётся единственным способом войти. Колонка уйдёт вместе с ним.

Revision ID: 010
Revises: 009
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Арендатор движка ↔ арендатор аналитика. UNIQUE обязателен: два арендатора
    # аналитика на одного клиента движка означали бы, что вход отдаёт данные
    # по жребию.
    op.add_column(
        "tenants",
        sa.Column("engine_tenant_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_unique_constraint("uq_tenants_engine_tenant_id", "tenants", ["engine_tenant_id"])

    op.add_column(
        "users",
        sa.Column("engine_user_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_unique_constraint("uq_users_engine_user_id", "users", ["engine_user_id"])

    # Пользователь из движка пароля здесь не имеет.
    op.alter_column("users", "hashed_password", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    # Обратно пароль обязательным сделать нельзя, пока есть строки без него:
    # ALTER упадёт, и это правильно — молча выдумать им пароль хуже.
    op.drop_constraint("uq_users_engine_user_id", "users", type_="unique")
    op.drop_column("users", "engine_user_id")
    op.drop_constraint("uq_tenants_engine_tenant_id", "tenants", type_="unique")
    op.drop_column("tenants", "engine_tenant_id")
