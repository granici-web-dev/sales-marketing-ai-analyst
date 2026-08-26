"""Кто делает запрос.

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

import structlog
from fastapi import Depends, HTTPException, Request
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
