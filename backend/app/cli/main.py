"""Обслуживание аренд из командной строки.

    python -m app.cli tenants list
    python -m app.cli tenants link <slug> <engine-tenant-uuid> [--force]
    python -m app.cli tenants unlink <slug>

Появилось на месте инструкции «выполните UPDATE» в комментарии. Разница не
в удобстве: в комментарии нельзя ни отказать, ни предупредить. Команда
отказывается привязать одного арендатора движка к двум клиентам и не
переставляет готовую привязку без явного `--force`, потому что переставленная
привязка отправляет всех, кто войдёт следующим, в чужие данные.

Идентификатор арендатора движка берётся там же, где заводится клиент:
`npm run client list` в репозитории движка.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.services.tenants import directory

if TYPE_CHECKING:  # аннотации только — импорт остаётся отложенным (INFRA-05)
    from sqlalchemy.ext.asyncio import AsyncConnection

from app.services.tenants.directory import (
    AlreadyLinkedError,
    EngineTenantTakenError,
    TenantNotFoundError,
    TenantRow,
)


def _describe(row: TenantRow) -> str:
    link = str(row.engine_tenant_id) if row.linked else "не привязан"
    return f"  {row.slug:<24} {link:<38} {row.name}"


async def _with_connection(work: Callable[..., Awaitable[int]], **kwargs: Any) -> int:
    """Открыть соединение в транзакции и отдать его команде.

    Движок собственный, а не общий из `db.session`: команда живёт свой
    короткий срок и не должна оставлять за собой пул.
    """
    from sqlalchemy.ext.asyncio import create_async_engine  # deferred (INFRA-05)
    from sqlalchemy.pool import NullPool

    from app.core.config import settings  # deferred (INFRA-05)

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            return await work(conn, **kwargs)
    finally:
        await engine.dispose()


async def _cmd_list(conn: AsyncConnection) -> int:
    rows = await directory.list_all(conn)
    if not rows:
        print("Арендаторов нет.")
        return 0

    print(f"  {'slug':<24} {'арендатор движка':<38} название")
    for row in rows:
        print(_describe(row))

    unlinked = [r for r in rows if not r.linked]
    print()
    if unlinked:
        print(f"Не привязано: {len(unlinked)} из {len(rows)}. Эти клиенты войти не смогут.")
        print("Привязать:  python -m app.cli tenants link <slug> <engine-tenant-uuid>")
    else:
        print(f"Привязаны все {len(rows)}.")
    return 0


async def _cmd_link(conn: AsyncConnection, slug: str, engine_tenant_id: UUID, force: bool) -> int:
    try:
        before = await directory.get_by_slug(conn, slug)
        row = await directory.link(conn, slug, engine_tenant_id, force=force)
    except TenantNotFoundError:
        print(f"Арендатора «{slug}» нет. Посмотреть список: python -m app.cli tenants list")
        return 1
    except EngineTenantTakenError as exc:
        print(
            f"Арендатор движка {exc} уже привязан к другому клиенту.\n"
            "Один арендатор движка — один клиент аналитика; иначе войти можно было бы "
            "в чужие данные."
        )
        return 1
    except AlreadyLinkedError as exc:
        print(
            f"У «{slug}» уже стоит привязка к {exc}.\n"
            "Переставить её значит отправить всех, кто войдёт следующим, в другие данные.\n"
            "Если это и требуется — повторите с --force."
        )
        return 1

    if before.engine_tenant_id == row.engine_tenant_id:
        print(f"«{slug}» уже привязан к {row.engine_tenant_id} — ничего не менялось.")
    else:
        print(f"«{slug}» → {row.engine_tenant_id}")
    return 0


async def _cmd_unlink(conn: AsyncConnection, slug: str) -> int:
    try:
        before = await directory.get_by_slug(conn, slug)
    except TenantNotFoundError:
        print(f"Арендатора «{slug}» нет.")
        return 1

    if not before.linked:
        print(f"У «{slug}» привязки и не было.")
        return 0

    await directory.unlink(conn, slug)
    print(f"Привязка «{slug}» снята. Клиент больше не войдёт, пока её не поставят снова.")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description="Обслуживание аренд аналитика.",
    )
    sub = parser.add_subparsers(dest="group", required=True)

    tenants = sub.add_parser("tenants", help="арендаторы и их привязка к движку")
    actions = tenants.add_subparsers(dest="action", required=True)

    actions.add_parser("list", help="показать арендаторов и состояние привязки")

    link = actions.add_parser("link", help="привязать арендатора к арендатору движка")
    link.add_argument("slug", help="slug арендатора аналитика")
    link.add_argument("engine_tenant_id", type=UUID, help="идентификатор арендатора в движке")
    link.add_argument(
        "--force",
        action="store_true",
        help="переставить уже существующую привязку на другую",
    )

    unlink = actions.add_parser("unlink", help="снять привязку")
    unlink.add_argument("slug")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv if argv is not None else sys.argv[1:])

    if args.action == "list":
        return asyncio.run(_with_connection(_cmd_list))
    if args.action == "link":
        return asyncio.run(
            _with_connection(
                _cmd_link,
                slug=args.slug,
                engine_tenant_id=args.engine_tenant_id,
                force=args.force,
            )
        )
    if args.action == "unlink":
        return asyncio.run(_with_connection(_cmd_unlink, slug=args.slug))

    raise AssertionError(f"необработанная команда: {args.action}")
