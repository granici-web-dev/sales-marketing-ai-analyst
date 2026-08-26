"""Реестр арендаторов: единственные запросы, идущие мимо затвора изоляции.

Затвор в `db/session.py` отвергает ЛЮБОЙ ORM-запрос, выполненный без
тенантного контекста, не разбирая, к какой таблице. Это правильная строгость:
разбирать «эта таблица тенантная, а эта нет» на каждом запросе значит однажды
разобрать неверно.

Но сама таблица `tenants` тенантной не является — арендатор ею и определяется,
— и обращаться к ней приходится именно тогда, когда контекста ещё нет: при
входе (кто это?), при запуске (сколько клиентов не привязано?) и из командной
строки (привязать). Поэтому такие запросы собраны здесь, идут через Core на
соединении сессии, и исключение из общего правила описано в одном месте, а не
повторено в трёх.

Ничего тенантного отсюда не читается и не пишется. Если сюда однажды
потребуется добавить запрос к тенантной таблице — это признак, что запрос
не на своём месте.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast
from uuid import UUID

from sqlalchemy import Table, func, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models.tenant import Tenant

# `__table__` объявлен в SQLAlchemy как `FromClause` — этого хватает для SELECT,
# но не для UPDATE, которому нужна именно таблица. Приведение стоит один раз тут.
_tenants = cast("Table", Tenant.__table__)


@dataclass(frozen=True)
class TenantRow:
    """Арендатор так, как его показывают человеку."""

    id: UUID
    slug: str
    name: str
    engine_tenant_id: UUID | None

    @property
    def linked(self) -> bool:
        return self.engine_tenant_id is not None


class TenantNotFoundError(LookupError):
    """Арендатора с таким slug нет."""


class EngineTenantTakenError(ValueError):
    """Этот арендатор движка уже привязан к другому арендатору аналитика."""


class AlreadyLinkedError(ValueError):
    """У арендатора уже есть привязка, и она другая."""


async def find_id_by_engine_tenant(conn: AsyncConnection, engine_tenant_id: UUID) -> UUID | None:
    """Найти арендатора аналитика по арендатору движка.

    Выполняется при каждом входе — до того, как арендатор известен, потому что
    им он и определяется.
    """
    result = await conn.execute(
        select(_tenants.c.id).where(_tenants.c.engine_tenant_id == engine_tenant_id)
    )
    return result.scalar_one_or_none()


async def list_all(conn: AsyncConnection) -> list[TenantRow]:
    """Все арендаторы, привязанные и нет, по slug."""
    result = await conn.execute(
        select(
            _tenants.c.id, _tenants.c.slug, _tenants.c.name, _tenants.c.engine_tenant_id
        ).order_by(_tenants.c.slug)
    )
    return [TenantRow(**row._mapping) for row in result]


async def count_unlinked(conn: AsyncConnection) -> int:
    """Сколько арендаторов не привязано к движку.

    Непривязанный арендатор — это клиент, который не сможет войти: движок его
    пустит, аналитик не найдёт, и человек увидит отказ без объяснения. Число
    произносится вслух при запуске, потому что молчащая привязка и была
    исходной бедой: шаг жил в комментарии, а комментарий — не процедура.
    """
    result = await conn.execute(
        select(func.count()).select_from(_tenants).where(_tenants.c.engine_tenant_id.is_(None))
    )
    return int(result.scalar_one())


async def get_by_slug(conn: AsyncConnection, slug: str) -> TenantRow:
    """Арендатор по slug.

    Raises:
        TenantNotFoundError: такого slug нет.
    """
    result = await conn.execute(
        select(_tenants.c.id, _tenants.c.slug, _tenants.c.name, _tenants.c.engine_tenant_id).where(
            _tenants.c.slug == slug
        )
    )
    row = result.first()
    if row is None:
        raise TenantNotFoundError(slug)
    return TenantRow(**row._mapping)


async def link(
    conn: AsyncConnection,
    slug: str,
    engine_tenant_id: UUID,
    *,
    force: bool = False,
) -> TenantRow:
    """Привязать арендатора аналитика к арендатору движка.

    Идемпотентна: повторная привязка к тому же значению проходит молча.

    Raises:
        TenantNotFoundError: такого slug нет.
        EngineTenantTakenError: этот арендатор движка уже привязан к другому.
        AlreadyLinkedError: у этого арендатора уже есть ДРУГАЯ привязка и не
            задан `force`. Переставить привязку значит отправить всех, кто
            войдёт следующим, в чужие данные — такое делается только вслух.
    """
    current = await get_by_slug(conn, slug)

    if current.engine_tenant_id == engine_tenant_id:
        return current

    taken = await find_id_by_engine_tenant(conn, engine_tenant_id)
    if taken is not None and taken != current.id:
        raise EngineTenantTakenError(str(engine_tenant_id))

    if current.linked and not force:
        raise AlreadyLinkedError(str(current.engine_tenant_id))

    await conn.execute(
        update(_tenants)
        .where(_tenants.c.id == current.id)
        .values(engine_tenant_id=engine_tenant_id)
    )
    return await get_by_slug(conn, slug)


async def unlink(conn: AsyncConnection, slug: str) -> TenantRow:
    """Снять привязку. Клиент перестанет входить — это и есть смысл действия.

    Raises:
        TenantNotFoundError: такого slug нет.
    """
    current = await get_by_slug(conn, slug)
    await conn.execute(
        update(_tenants).where(_tenants.c.id == current.id).values(engine_tenant_id=None)
    )
    return await get_by_slug(conn, slug)
