"""Застрявшие оферты: SQL проверяется базой, а не подменой.

Единственный тест на `get_stuck_offers` мокал `session.execute` и возвращал
готовые строки — он проверял разбор ответа и ничего не знал о самом запросе.
А запрос там непростой: часть условий приходит из вида `v_mefi_leads_active`,
часть дописана снаружи, и «дошёл до оферты» складывается из трёх источников —
текущего статуса, флага и истории переходов.

Поэтому здесь настоящая база и по одной заявке на каждую ветку. Тест написан
против существующего запроса и на нём же увиден зелёным — иначе он описывал бы
не поведение, а намерение (Requirements: SALE-07).
"""

from __future__ import annotations

import os
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "")
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        not _TEST_DB_URL,
        reason="Нужна TEST_DATABASE_URL (docker compose up -d)",
    ),
]

TENANT = UUID("00000000-0000-0000-0000-000000000001")
OTHER_TENANT = UUID("00000000-0000-0000-0000-0000000000ff")

# Статусы MEFI, зашитые в вид: 17 — визит, 3 — оферта, 1 — договор.
STATUS_VISIT, STATUS_OFFER, STATUS_CONTRACT, STATUS_NEW = 17, 3, 1, 5

NOW = datetime.now(UTC)


def _ago(days: int) -> datetime:
    return NOW - timedelta(days=days)


@pytest.fixture
async def session():
    """Свой движок на каждый тест, как в `test_mefi_etl.py`.

    Общая фикстура `db_session` здесь не годится: conftest забрал фабрику
    сессий по значению при импорте и не видит, как её пересоздают под каждый
    тест. Второй тест подряд получает соединение с уже закрытого цикла
    событий и падает не проверкой, а установкой. NullPool ничего между
    тестами не держит.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.core.tenancy import set_tenant_id

    set_tenant_id(TENANT)
    engine = create_async_engine(_TEST_DB_URL, poolclass=NullPool)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        try:
            yield s
        finally:
            await s.rollback()
    await engine.dispose()


@pytest.fixture
async def seeded(session):
    """Заявки по одной на ветку. Откатывается вместе с сессией теста."""
    db_session = session

    await db_session.execute(
        text(
            "INSERT INTO tenants (id, name, slug, created_at, updated_at) "
            "VALUES (:id, 'Другой', 'other-tenant', now(), now()) "
            "ON CONFLICT (id) DO NOTHING"
        ),
        {"id": OTHER_TENANT},
    )
    for tenant in (TENANT, OTHER_TENANT):
        await db_session.execute(
            text(
                "INSERT INTO mefi_salespeople (id, tenant_id, created_at, updated_at, "
                "external_id, name) VALUES (:id, :t, now(), now(), 7, 'Продавец Семь') "
                "ON CONFLICT (tenant_id, external_id) DO NOTHING"
            ),
            {"id": uuid4(), "t": tenant},
        )

    async def lead(
        external_id: str,
        *,
        status_id: int,
        lifecycle: str = "active",
        offer_sent: bool = False,
        assigned_to: int | None = 7,
        tenant: UUID = TENANT,
    ) -> None:
        await db_session.execute(
            text(
                "INSERT INTO raw_mefi_leads (id, tenant_id, created_at, updated_at, "
                "external_id, status_id, lifecycle, offer_sent_flag, assigned_to_id, "
                "created_at_source) VALUES (:id, :t, now(), now(), :eid, :st, :lc, :flag, "
                ":who, :src)"
            ),
            {
                "id": uuid4(),
                "t": tenant,
                "eid": external_id,
                "st": status_id,
                "lc": lifecycle,
                "flag": offer_sent,
                "who": assigned_to,
                "src": _ago(60),
            },
        )

    async def history(
        external_id: str, to_status: int, days_ago: int, tenant: UUID = TENANT
    ) -> None:
        await db_session.execute(
            text(
                "INSERT INTO mefi_lead_history (id, tenant_id, created_at, updated_at, "
                "lead_external_id, to_status_id, changed_at) "
                "VALUES (:id, :t, now(), now(), :eid, :st, :at)"
            ),
            {"id": uuid4(), "t": tenant, "eid": external_id, "st": to_status, "at": _ago(days_ago)},
        )

    # ── попадают в список ────────────────────────────────────────────────────
    # оферта по текущему статусу, тишина 30 дней
    await lead("by-status", status_id=STATUS_OFFER)
    await history("by-status", STATUS_OFFER, 30)
    # оферта по флагу, тишина 20 дней
    await lead("by-flag", status_id=STATUS_NEW, offer_sent=True)
    await history("by-flag", STATUS_NEW, 20)
    # оферта ТОЛЬКО по истории — та самая ветка, ради которой вид сворачивает
    # историю; текущий статус про оферту не знает
    await lead("by-history", status_id=STATUS_NEW)
    await history("by-history", STATUS_OFFER, 40)
    # оферта есть, истории нет вовсе: days_stuck неизвестен, но заявка висит
    await lead("no-history", status_id=STATUS_OFFER)
    # проигранная заявка — вид пропускает 'active' и 'lost'
    await lead("lost-one", status_id=STATUS_CONTRACT, lifecycle="lost")
    await history("lost-one", STATUS_CONTRACT, 25)
    # продавец не найден: имя должно приехать пустым, а заявка — приехать
    await lead("no-seller", status_id=STATUS_OFFER, assigned_to=999)
    await history("no-seller", STATUS_OFFER, 22)

    # ── не попадают ──────────────────────────────────────────────────────────
    # шевелилась три дня назад
    await lead("recent", status_id=STATUS_OFFER)
    await history("recent", STATUS_OFFER, 3)
    # до оферты не дошла ни по статусу, ни по флагу, ни по истории
    await lead("no-offer", status_id=STATUS_NEW)
    await history("no-offer", STATUS_VISIT, 40)
    # брак: вид его не показывает
    await lead("junk-one", status_id=STATUS_OFFER, lifecycle="junk")
    await history("junk-one", STATUS_OFFER, 40)
    # чужой клиент
    await lead("alien", status_id=STATUS_OFFER, tenant=OTHER_TENANT)
    await history("alien", STATUS_OFFER, 40, tenant=OTHER_TENANT)

    await db_session.flush()
    return db_session


async def _stuck(session) -> list[dict]:
    from app.services.dashboards.dashboard_read_service import DashboardReadService

    service = DashboardReadService(session, TENANT)
    return await service.get_stuck_offers(date.today() - timedelta(days=89), date.today())


async def test_returns_exactly_the_stuck_ones(seeded) -> None:
    """Список — ровно шесть заявок; всё, что шевелилось, не дошло, брак и чужое — мимо."""
    rows = await _stuck(seeded)
    assert {r["external_id"] for r in rows} == {
        "by-status",
        "by-flag",
        "by-history",
        "no-history",
        "lost-one",
        "no-seller",
    }


async def test_days_stuck_counts_from_last_change(seeded) -> None:
    """Счёт идёт от последнего перехода, а не от заведения заявки."""
    by_id = {r["external_id"]: r for r in await _stuck(seeded)}
    assert by_id["by-history"]["days_stuck"] == 40
    assert by_id["by-status"]["days_stuck"] == 30
    assert by_id["by-flag"]["days_stuck"] == 20


async def test_no_history_means_unknown_not_zero(seeded) -> None:
    """Без истории срок неизвестен. Ноль означал бы «шевелилась сегодня»."""
    by_id = {r["external_id"]: r for r in await _stuck(seeded)}
    assert by_id["no-history"]["days_stuck"] is None


async def test_ordered_by_days_stuck_desc(seeded) -> None:
    """Сначала самые застоявшиеся; неизвестный срок — в конце."""
    known = [r["days_stuck"] for r in await _stuck(seeded) if r["days_stuck"] is not None]
    assert known == sorted(known, reverse=True)


async def test_salesperson_name_resolved_and_missing(seeded) -> None:
    """Имя подставляется по assigned_to_id; несуществующий продавец даёт пустое."""
    by_id = {r["external_id"]: r for r in await _stuck(seeded)}
    assert by_id["by-status"]["salesperson_name"] == "Продавец Семь"
    assert by_id["no-seller"]["salesperson_name"] is None
