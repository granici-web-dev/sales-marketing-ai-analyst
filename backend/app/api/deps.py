"""Зависимости обработчиков: кто делает запрос и за какой период.

Лежит под `api/`, а не в `core/`. В `core/` этот модуль давал единственный
цикл в графе зависимостей — `core ⇄ db`: он тянул `app.db.deps`, а `db`
тянет `app.core.config` и `app.core.tenancy`. На выполнение это не влияло
(цикл был на уровне пакетов), но и пользы в нём не было никакой: проводка
FastAPI — это слой веба, а не ядро.

## Что изменилось и почему

Раньше здесь проверялся собственный JWT аналитика. Теперь личность
удостоверяет движок: у него отзываемая серверная сессия, печенье с HttpOnly и
SameSite=Strict, scrypt и сравнение постоянного времени, — а главное, у клиента
Davoq должна быть одна учётная запись на семь агентов, а не своя у каждого.

Тенантный контекст ставится ЗДЕСЬ же, из разобранной сессии. Прежде его
ставил посредник из настройки `sofa_belle_tenant_id` — одно и то же значение
на любой запрос. Пока клиент был один, разницы не было; с приходом второго
это была бы выдача чужих данных с кодом 200.

"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import structlog
from fastapi import Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.deps import get_session
from app.schemas.auth import UserOut
from app.services.auth.engine_session import (
    ENGINE_SESSION_COOKIE,
    EngineUnreachableError,
    resolve,
)
from app.services.auth.link import TenantNotLinkedError, resolve_local_user

logger = structlog.get_logger(__name__)

UNAUTHORIZED = "Invalid or expired session"


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    """Удостоверить запрос и поставить тенантный контекст.

    Returns:
        UserOut с id, email, is_active — без хеша пароля и без tenant_id (T-06-01-02).

    Raises:
        HTTPException(401): сессия недействительна.
        HTTPException(503): движок не ответил — это наша неполадка, а не отказ
            в доступе, и выглядеть она обязана по-разному.
    """
    engine_token = request.cookies.get(ENGINE_SESSION_COOKIE)
    if not engine_token:
        raise HTTPException(status_code=401, detail=UNAUTHORIZED)

    try:
        identity = await resolve(engine_token)
    except EngineUnreachableError as exc:
        # Отправить человека на форму входа означало бы предложить ему войти
        # заново и не объяснить, почему не пускает: сессия-то у него верная.
        logger.warning("auth.engine_unreachable", error=str(exc)[:200])
        raise HTTPException(
            status_code=503,
            detail="Контур учётных записей недоступен. Попробуйте через минуту.",
        ) from exc

    if identity is None:
        raise HTTPException(status_code=401, detail=UNAUTHORIZED)

    try:
        return await resolve_local_user(session, identity)
    except TenantNotLinkedError as exc:
        logger.warning("auth.tenant_not_linked", reason=str(exc)[:120])
        raise HTTPException(
            status_code=403,
            detail="Аналитик не подключён для этого клиента.",
        ) from exc


# ── Период выборки ────────────────────────────────────────────────────────

# Потолок периода. Самая широкая кнопка в интерфейсе — «Tot anul», то есть
# не больше 366 дней; два года оставлены с запасом на сравнение год к году
# через API напрямую.
#
# Потолок нужен не от злоумышленника: доступ сюда только у вошедшего клиента.
# Он нужен от опечатки в дате — запрос за двести лет это семьдесят тысяч
# строк на каждую из трёх таблиц, и стоит он ровно один неверный символ.
MAX_RANGE_DAYS = 731


@dataclass(frozen=True)
class DateRange:
    """Разобранный и проверенный период выборки."""

    from_date: date
    to_date: date


def date_range(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
) -> DateRange:
    """Проверить период до того, как он дойдёт до базы.

    Порядок дат проверяется отдельно от длины: перепутанные местами `from`
    и `to` давали не ошибку, а пустой ответ — то есть график без данных
    и никакого объяснения, почему.

    Raises:
        HTTPException(422): даты переставлены местами или период шире потолка.
    """
    if from_date > to_date:
        raise HTTPException(
            status_code=422,
            detail=f"Начало периода ({from_date}) позже конца ({to_date}).",
        )

    span = (to_date - from_date).days + 1
    if span > MAX_RANGE_DAYS:
        raise HTTPException(
            status_code=422,
            detail=(f"Период {span} дн. шире допустимых {MAX_RANGE_DAYS}. Проверьте год в датах."),
        )

    return DateRange(from_date=from_date, to_date=to_date)
