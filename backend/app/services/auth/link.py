"""Личность движка → записи аналитика.

Движок отвечает, кто вошёл. Здесь этот ответ превращается в арендатора и
пользователя ЭТОЙ базы: без них ни переписку сохранить, ни данные отфильтровать.

── Арендатор не заводится сам ──

Пользователь заводится, арендатор — нет. Разница не в лени: пользователь без
записи здесь просто ещё не заходил, а арендатор без записи означает, что
аналитик этому клиенту не подключён — нет ни синхронизации с CRM, ни
показателей, ни настроенной воронки. Завести пустого арендатора значило бы
впустить человека в кабинет, где всё по нулям, и заставить его гадать,
сломано это или так и надо.

Привязка ставится один раз при подключении клиента:

    python -m app.cli tenants link <slug> <uuid из движка>

Раньше здесь стоял UPDATE, который следовало выполнить руками. Шаг, живущий
в комментарии, — не процедура: его нельзя ни повторить, ни проверить, ни
запретить сделать неправильно. Команда отказывается переставить готовую
привязку без явного `--force` и не даёт привязать одного арендатора движка
к двум клиентам; при запуске приложение вслух говорит, сколько клиентов
осталось непривязанными.
"""

from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenancy import set_tenant_id
from app.models.user import User
from app.schemas.auth import UserOut
from app.services.auth.engine_session import EngineIdentity
from app.services.tenants import directory

logger = structlog.get_logger(__name__)


class TenantNotLinkedError(RuntimeError):
    """У клиента движка нет арендатора аналитика."""


async def resolve_local_user(session: AsyncSession, identity: EngineIdentity) -> UserOut:
    """Найти арендатора и пользователя, поставить тенантный контекст.

    Raises:
        TenantNotLinkedError: аналитик этому клиенту не подключён.
    """
    # Единственный запрос на пути входа, который выполняется ДО того, как
    # арендатор известен, — потому что им арендатор и определяется. Он и все
    # прочие обращения к `tenants` живут в `services/tenants/directory.py`,
    # где объяснено, почему идут мимо ORM.
    #
    # Соединение то же самое, что у сессии: своей транзакции здесь не заводится.
    connection = await session.connection()
    tenant_id = await directory.find_id_by_engine_tenant(connection, identity.engine_tenant_id)

    if tenant_id is None:
        logger.warning(
            "engine_session.tenant_not_linked",
            engine_tenant_id=str(identity.engine_tenant_id),
        )
        raise TenantNotLinkedError(str(identity.engine_tenant_id))

    # Контекст ставится ЗДЕСЬ — до первого запроса к тенантным таблицам.
    # Всё, что ниже, уже отфильтровано этим арендатором.
    set_tenant_id(tenant_id)

    row = (
        await session.execute(
            select(User.id, User.email, User.is_active).where(
                User.engine_user_id == identity.engine_user_id
            )
        )
    ).first()

    if row is not None:
        if not row.is_active:
            # Выключенный здесь остаётся выключенным, даже если движок его
            # пустил: это два разных решения, и наше про наш кабинет.
            raise TenantNotLinkedError(f"user {row.id} inactive")
        return UserOut(id=row.id, email=row.email, is_active=True)

    # Записи с этим идентификатором ещё нет. Прежде чем заводить новую,
    # ищем ту же почту среди непривязанных: у клиента, работавшего до перехода
    # на общий вход, здесь уже лежит пользователь со своими переписками, и
    # завести ему второго значило бы показать пустой кабинет человеку,
    # который вчера в нём работал.
    #
    # Это не вход по почте: кто перед нами, уже решил движок, а арендатор уже
    # определён. Почта здесь — только способ найти его прежнюю запись внутри
    # этого арендатора.
    orphan = (
        await session.execute(
            select(User).where(User.email == identity.email, User.engine_user_id.is_(None))
        )
    ).scalar_one_or_none()

    if orphan is not None:
        orphan.engine_user_id = identity.engine_user_id
        await session.commit()
        logger.info("engine_session.user_adopted", user_id=str(orphan.id))
        return UserOut(id=orphan.id, email=orphan.email, is_active=orphan.is_active)

    # Первый заход. Движок уже проверил, кто это, — заводим зеркало.
    # Пароля у такого пользователя нет и быть не должно.
    user = User(
        tenant_id=tenant_id,
        email=identity.email,
        hashed_password=None,
        engine_user_id=identity.engine_user_id,
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    logger.info("engine_session.user_created", user_id=str(user.id))
    return UserOut(id=user.id, email=user.email, is_active=user.is_active)
