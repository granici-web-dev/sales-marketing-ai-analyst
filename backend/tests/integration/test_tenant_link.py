"""Привязка клиента: реестр и команда.

Раньше привязка была строкой UPDATE в комментарии. У комментария нет ни отказа,
ни предупреждения — поэтому проверяется здесь прежде всего то, чего команда НЕ
делает: не привязывает одного арендатора движка к двум клиентам и не
переставляет готовую привязку молча. И то и другое отправило бы человека,
который войдёт следующим, в чужие данные.
"""

from __future__ import annotations

import os
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.cli.main import main
from app.services.tenants import directory
from app.services.tenants.directory import (
    AlreadyLinkedError,
    EngineTenantTakenError,
    TenantNotFoundError,
)

_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _TEST_DB_URL, reason="нужен TEST_DATABASE_URL"),
]


@pytest.fixture
async def conn():
    """Соединение в транзакции, которая всегда откатывается.

    Каждый тест заводит своих арендаторов и не оставляет следов: реестр —
    таблица общая на всю базу, и тест, дописывающий в неё, ломает соседей.
    """
    engine = create_async_engine(_TEST_DB_URL, poolclass=NullPool)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            yield connection
        finally:
            await transaction.rollback()
    await engine.dispose()


async def _make_tenant(conn, slug: str, engine_tenant_id: UUID | None = None) -> UUID:
    tenant_id = uuid4()
    await conn.execute(
        text(
            "INSERT INTO tenants (id, name, slug, engine_tenant_id) "
            "VALUES (:id, :name, :slug, :eng)"
        ),
        {"id": tenant_id, "name": f"Тест {slug}", "slug": slug, "eng": engine_tenant_id},
    )
    return tenant_id


# ── реестр ────────────────────────────────────────────────────────────────────


async def test_link_sets_the_pointer(conn) -> None:
    slug = f"probe-{uuid4().hex[:8]}"
    await _make_tenant(conn, slug)
    engine_tenant = uuid4()

    row = await directory.link(conn, slug, engine_tenant)

    assert row.engine_tenant_id == engine_tenant
    assert row.linked


async def test_link_is_idempotent(conn) -> None:
    """Повтор той же привязки — не ошибка: подключение могли делать дважды."""
    slug = f"probe-{uuid4().hex[:8]}"
    engine_tenant = uuid4()
    await _make_tenant(conn, slug, engine_tenant)

    row = await directory.link(conn, slug, engine_tenant)

    assert row.engine_tenant_id == engine_tenant


async def test_one_engine_tenant_cannot_serve_two_clients(conn) -> None:
    """Иначе вход одного клиента вёл бы в данные другого."""
    engine_tenant = uuid4()
    first = f"probe-{uuid4().hex[:8]}"
    second = f"probe-{uuid4().hex[:8]}"
    await _make_tenant(conn, first, engine_tenant)
    await _make_tenant(conn, second)

    with pytest.raises(EngineTenantTakenError, match=str(engine_tenant)):
        await directory.link(conn, second, engine_tenant)


async def test_existing_link_is_not_replaced_silently(conn) -> None:
    slug = f"probe-{uuid4().hex[:8]}"
    was = uuid4()
    await _make_tenant(conn, slug, was)

    with pytest.raises(AlreadyLinkedError, match=str(was)):
        await directory.link(conn, slug, uuid4())

    still = await directory.get_by_slug(conn, slug)
    assert still.engine_tenant_id == was, "неудавшаяся привязка не должна ничего менять"


async def test_force_replaces_the_link(conn) -> None:
    slug = f"probe-{uuid4().hex[:8]}"
    await _make_tenant(conn, slug, uuid4())
    now = uuid4()

    row = await directory.link(conn, slug, now, force=True)

    assert row.engine_tenant_id == now


async def test_unlink_clears_the_pointer(conn) -> None:
    slug = f"probe-{uuid4().hex[:8]}"
    await _make_tenant(conn, slug, uuid4())

    row = await directory.unlink(conn, slug)

    assert row.engine_tenant_id is None
    assert not row.linked


async def test_unknown_slug_is_a_named_failure(conn) -> None:
    with pytest.raises(TenantNotFoundError, match="нет-такого"):
        await directory.get_by_slug(conn, "нет-такого")


async def test_count_unlinked_counts_only_unlinked(conn) -> None:
    before = await directory.count_unlinked(conn)
    await _make_tenant(conn, f"probe-{uuid4().hex[:8]}")
    await _make_tenant(conn, f"probe-{uuid4().hex[:8]}")
    await _make_tenant(conn, f"probe-{uuid4().hex[:8]}", uuid4())

    assert await directory.count_unlinked(conn) == before + 2


async def test_find_by_engine_tenant_is_what_login_uses(conn) -> None:
    """Тот самый запрос, которым вход определяет арендатора."""
    slug = f"probe-{uuid4().hex[:8]}"
    engine_tenant = uuid4()
    tenant_id = await _make_tenant(conn, slug, engine_tenant)

    assert await directory.find_id_by_engine_tenant(conn, engine_tenant) == tenant_id
    assert await directory.find_id_by_engine_tenant(conn, uuid4()) is None


# ── команда ───────────────────────────────────────────────────────────────────


async def _run_cli(*argv: str) -> int:
    """Вызвать команду вне цикла событий теста.

    `main` внутри делает `asyncio.run`, а из работающего цикла это невозможно:
    падение случится до того, как команда что-либо сделает, и тест сообщит не
    «команда отказала», а «следов команды нет».
    """
    import asyncio

    return await asyncio.to_thread(main, list(argv))


@pytest.fixture
def cli(monkeypatch):
    """Команда, направленная на тестовую базу.

    Команда открывает собственное соединение и фиксирует транзакцию — откатить
    её вместе с тестовой нельзя, поэтому заведённые арендаторы убираются явно
    через `_cleanup_tenants`.
    """
    monkeypatch.setattr("app.core.config.settings.database_url", _TEST_DB_URL)
    made: list[str] = []

    async def _create(slug: str, engine_tenant_id: UUID | None = None) -> None:
        engine = create_async_engine(_TEST_DB_URL, poolclass=NullPool)
        async with engine.begin() as c:
            await _make_tenant(c, slug, engine_tenant_id)
        await engine.dispose()
        made.append(slug)

    return _create, made


async def _cleanup_tenants(slugs: list[str]) -> None:
    engine = create_async_engine(_TEST_DB_URL, poolclass=NullPool)
    async with engine.begin() as c:
        for slug in slugs:
            await c.execute(text("DELETE FROM tenants WHERE slug = :s"), {"s": slug})
    await engine.dispose()


async def test_cli_links_and_says_so(cli, capsys) -> None:
    create, made = cli
    slug = f"probe-{uuid4().hex[:8]}"
    await create(slug)
    engine_tenant = uuid4()
    try:
        assert await _run_cli("tenants", "link", slug, str(engine_tenant)) == 0
        assert str(engine_tenant) in capsys.readouterr().out
    finally:
        await _cleanup_tenants(made)


async def test_cli_refuses_a_taken_engine_tenant(cli, capsys) -> None:
    create, made = cli
    engine_tenant = uuid4()
    first = f"probe-{uuid4().hex[:8]}"
    second = f"probe-{uuid4().hex[:8]}"
    await create(first, engine_tenant)
    await create(second)
    try:
        assert await _run_cli("tenants", "link", second, str(engine_tenant)) == 1
        assert "уже привязан к другому" in capsys.readouterr().out
    finally:
        await _cleanup_tenants(made)


async def test_cli_refuses_to_replace_without_force(cli, capsys) -> None:
    create, made = cli
    slug = f"probe-{uuid4().hex[:8]}"
    was = uuid4()
    await create(slug, was)
    try:
        assert await _run_cli("tenants", "link", slug, str(uuid4())) == 1
        assert "--force" in capsys.readouterr().out

        assert await _run_cli("tenants", "link", slug, str(uuid4()), "--force") == 0
    finally:
        await _cleanup_tenants(made)


async def test_cli_unknown_slug_exits_nonzero(cli, capsys) -> None:
    _, made = cli
    try:
        assert await _run_cli("tenants", "link", "нет-такого", str(uuid4())) == 1
        assert "нет" in capsys.readouterr().out
    finally:
        await _cleanup_tenants(made)


async def test_cli_list_names_the_unlinked(cli, capsys) -> None:
    create, made = cli
    slug = f"probe-{uuid4().hex[:8]}"
    await create(slug)
    try:
        assert await _run_cli("tenants", "list") == 0
        out = capsys.readouterr().out
        assert slug in out
        assert "не привязан" in out
        assert "войти не смогут" in out
    finally:
        await _cleanup_tenants(made)
