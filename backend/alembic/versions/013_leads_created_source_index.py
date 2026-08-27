"""Индекс по клиенту и дате заведения заявки.

Оба маркетинговых запроса — «брак по источникам» и «всего по источникам» —
отбирают `raw_mefi_leads` по клиенту И по дате создания, а индекс до сих пор
был только по клиенту. Планировщик брал все заявки клиента за всё время и
выбрасывал лишние уже после чтения: на замере 40 000 прочитано, 31 704
выброшено (docs/QUERY-PLANS.md).

Полторы миллисекунды сами по себе не повод заводить индекс — у записи тоже
есть цена. Дело в форме: без него работа пропорциональна ВСЕМ заявкам клиента
за всё время, с ним — только запрошенному окну. У пилота с его 1 200 заявками
разницы нет вовсе; на 400 000 это 29 мс против 2.

Замер, по шесть прогонов, на 640 000 заявках:
    без индекса   2.72 · 2.77 · 2.84 · 2.94 · 3.01 · 3.08 мс
    с индексом    1.27 · 1.32 · 1.32 · 1.36 · 1.38 · 1.43 мс
Вес — 6.6 МБ на 640 000 строк, около 0.4 МБ на клиента.

CONCURRENTLY, потому что обычный CREATE INDEX держит запись в таблице всё
время постройки. Сегодня это миллисекунды и никого не задело бы, но выкладка
случается тогда же, когда таблица велика, и тогда на это время встаёт приём
из MEFI. Плата за CONCURRENTLY — миграция идёт вне транзакции: если постройка
сорвётся, в базе останется индекс с `indisvalid = false`. Он не используется
и не мешает; убрать вручную:

    DROP INDEX CONCURRENTLY ix_raw_mefi_leads_tenant_created_source;

Проверки на «индекс используется» здесь нет и быть не может: на тестовых
объёмах планировщик правильно предпочтёт последовательный проход, и такая
проверка была бы красной по верной причине. Это меряется на стенде —
`backend/scripts/load-fixture.sql`.

Revision ID: 013
Revises: 012
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision = "013"
down_revision = "012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "ix_raw_mefi_leads_tenant_created_source"


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {INDEX_NAME} "
            "ON raw_mefi_leads (tenant_id, created_at_source)"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {INDEX_NAME}")
