"""Вид отдаёт время последнего перехода — чтобы историю читали один раз.

Запрос застрявших оферт читал `mefi_lead_history` дважды: один раз внутри
вида, где она сворачивается ради `reached_offer`, второй — внешним
соединением ради `MAX(changed_at)`. Одни и те же строки, два прохода;
на замере это 83 % всех прочитанных страниц запроса и 112 мс из 115,
которые экран продаж проводит в базе (docs/QUERY-PLANS.md).

Свернуть это в сервисе было бы дешевле — без миграции, — но тогда пришлось
бы вынести туда `IN (3, 1)`: определение «дошёл до оферты» живёт в этом виде
и только в нём. Второе место для той же константы дороже одной миграции,
тем более что воронка у клиента настраиваемая (`tenants.funnel_config`).

Поэтому `MAX(changed_at)` считается там же, где уже считаются `BOOL_OR` —
свёртка истории и так идёт, лишняя агрегатная функция в ней бесплатна.

Столбец добавляется В КОНЕЦ: `CREATE OR REPLACE VIEW` умеет дописывать
столбцы, но не переставлять и не удалять. Порядок остальных не тронут.

Revision ID: 012
Revises: 011
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision = "012"
down_revision = "011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Точная копия вида из 004 плюс один столбец в конце и один агрегат в свёртке.
# Копией, а не правкой на месте: `CREATE OR REPLACE VIEW` требует запрос
# целиком, а вид, собранный из кусков, невозможно прочитать глазами.
V_MEFI_LEADS_ACTIVE_V012 = """
CREATE OR REPLACE VIEW v_mefi_leads_active AS
SELECT
    r.tenant_id, r.id, r.created_at, r.updated_at,
    r.external_id, r.status_id, r.status_name, r.source_id, r.source_name,
    r.lifecycle, r.assigned_to_id, r.assigned_to_name, r.estimated_value,
    r.priority, r.is_duplicate, r.created_at_source, r.last_contact_at,
    r.status_changed_at, r.showroom, r.offer_sent_flag,
    r.utm_source, r.utm_campaign, r.utm_content, r.utm_medium,
    r.custom_fields_raw, r.raw_payload, r.synced_at,
    r.created_at_source AT TIME ZONE 'Europe/Bucharest' AS created_at_local,
    r.status_changed_at AT TIME ZONE 'Europe/Bucharest' AS status_changed_at_local,
    (r.status_id IN (17, 3, 1) OR COALESCE(h_agg.reached_visit, FALSE)) AS reached_visit,
    (r.status_id IN (3, 1) OR r.offer_sent_flag = TRUE OR COALESCE(h_agg.reached_offer, FALSE)) AS reached_offer,
    (r.status_id = 1) AS reached_contract,
    -- NULL означает «переходов не было вовсе», а не «был сегодня»: заявка
    -- без единой записи в истории застряла сильнее прочих, и ноль сказал бы
    -- ровно обратное.
    h_agg.last_changed_at AS last_history_change_at
FROM raw_mefi_leads r
LEFT JOIN (
    SELECT
        tenant_id,
        lead_external_id,
        -- Visit: current status IN (17,3,1) OR ever reached any visit-or-later stage (status 17, 3, or 1) in history
        BOOL_OR(to_status_id IN (17, 3, 1)) AS reached_visit,
        BOOL_OR(to_status_id IN (3, 1))     AS reached_offer,
        MAX(changed_at)                     AS last_changed_at
    FROM mefi_lead_history
    GROUP BY tenant_id, lead_external_id
) h_agg ON h_agg.tenant_id = r.tenant_id AND h_agg.lead_external_id = r.external_id
WHERE r.lifecycle IN ('active', 'lost')
"""

# Точная копия вида из 004 — для отката.
V_MEFI_LEADS_ACTIVE_V004 = """
CREATE OR REPLACE VIEW v_mefi_leads_active AS
SELECT
    r.tenant_id, r.id, r.created_at, r.updated_at,
    r.external_id, r.status_id, r.status_name, r.source_id, r.source_name,
    r.lifecycle, r.assigned_to_id, r.assigned_to_name, r.estimated_value,
    r.priority, r.is_duplicate, r.created_at_source, r.last_contact_at,
    r.status_changed_at, r.showroom, r.offer_sent_flag,
    r.utm_source, r.utm_campaign, r.utm_content, r.utm_medium,
    r.custom_fields_raw, r.raw_payload, r.synced_at,
    r.created_at_source AT TIME ZONE 'Europe/Bucharest' AS created_at_local,
    r.status_changed_at AT TIME ZONE 'Europe/Bucharest' AS status_changed_at_local,
    (r.status_id IN (17, 3, 1) OR COALESCE(h_agg.reached_visit, FALSE)) AS reached_visit,
    (r.status_id IN (3, 1) OR r.offer_sent_flag = TRUE OR COALESCE(h_agg.reached_offer, FALSE)) AS reached_offer,
    (r.status_id = 1) AS reached_contract
FROM raw_mefi_leads r
LEFT JOIN (
    SELECT
        tenant_id,
        lead_external_id,
        BOOL_OR(to_status_id IN (17, 3, 1)) AS reached_visit,
        BOOL_OR(to_status_id IN (3, 1))     AS reached_offer
    FROM mefi_lead_history
    GROUP BY tenant_id, lead_external_id
) h_agg ON h_agg.tenant_id = r.tenant_id AND h_agg.lead_external_id = r.external_id
WHERE r.lifecycle IN ('active', 'lost')
"""


def upgrade() -> None:
    op.execute(V_MEFI_LEADS_ACTIVE_V012)


def downgrade() -> None:
    # Убрать столбец через CREATE OR REPLACE нельзя — только пересоздав вид.
    op.execute("DROP VIEW v_mefi_leads_active")
    op.execute(V_MEFI_LEADS_ACTIVE_V004)
