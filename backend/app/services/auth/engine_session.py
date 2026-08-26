"""Кто вошёл — спрашиваем у движка.

## Зачем

У аналитика была своя таблица пользователей и свой пароль. Пока он был
единственным кабинетом, это было нормально. В портале, где семь агентов и одна
учётная запись Davoq, вторая пара «логин-пароль» — это вторая дверь в один дом.

Личность удостоверяет движок: у него отзываемая серверная сессия, печенье с
HttpOnly и SameSite=Strict, scrypt и сравнение постоянного времени. Здесь эта
сессия только разбирается — своей мы не заводим.

## Почему не свой токен в обмен

Обмен сессии движка на собственный JWT выглядел бы дешевле: ничего не трогать,
выдать привычный токен. Но тогда в браузере оказались бы два токена, а отзыв в
движке переставал бы действовать до истечения нашего. Своя сессия поверх чужой
живёт дольше чужой — это и есть определение дыры.

## Про кеш

Спрашивать движок на каждый запрос — это сетевой прыжок на каждую цифру
дашборда. Разобранная сессия кладётся в Redis на минуту по хешу токена.

Минута — не «чтобы быстрее», а «сколько живёт отозванная сессия». Час был бы
удобнее и означал бы час доступа после увольнения сотрудника.

В кеше лежат идентификаторы, а не токен: утечка дампа Redis не даёт войти.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from uuid import UUID

import httpx
import redis.asyncio as aioredis
import structlog

from app.core.config import settings
from app.core.redis import redis_client

logger = structlog.get_logger(__name__)

ENGINE_SESSION_COOKIE = "aw_session"

# Движок отвечает быстро либо не отвечает вовсе. Ждать дольше значит держать
# запрос клиента открытым ради чужой неполадки.
ENGINE_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class EngineIdentity:
    """Кто вошёл в движок. Ровно то, что нужно, чтобы найти его у нас."""

    engine_user_id: UUID
    engine_tenant_id: UUID
    email: str


class EngineUnreachableError(RuntimeError):
    """Движок не ответил.

    Отдельно от «не авторизован» намеренно: недоступный движок — это наша
    неполадка, и превращать её в «вы не вошли» значит выкидывать человека на
    форму входа, где он введёт верный пароль и не поймёт, почему не пускает.
    """


def _cache_key(token: str) -> str:
    return f"engine_session:{hashlib.sha256(token.encode()).hexdigest()}"


async def _from_cache(r: aioredis.Redis, token: str) -> EngineIdentity | None:
    raw = await r.get(_cache_key(token))
    if raw is None:
        return None
    data = json.loads(raw)
    return EngineIdentity(
        engine_user_id=UUID(data["user_id"]),
        engine_tenant_id=UUID(data["tenant_id"]),
        email=data["email"],
    )


async def _ask_engine(token: str) -> EngineIdentity | None:
    """Спросить движок. None — сессия недействительна."""
    url = f"{settings.engine_base_url.rstrip('/')}/admin/api/me"
    try:
        async with httpx.AsyncClient(timeout=ENGINE_TIMEOUT_SECONDS) as client:
            response = await client.get(url, cookies={ENGINE_SESSION_COOKIE: token})
    except httpx.HTTPError as exc:
        raise EngineUnreachableError(str(exc)[:200]) from exc

    if response.status_code == 401:
        return None
    if response.status_code >= 500:
        raise EngineUnreachableError(f"движок ответил {response.status_code}")
    if response.status_code != 200:
        # 403 и прочее — не наша область: сессия есть, но движок её чем-то
        # ограничил. Пускать в этом случае нельзя.
        logger.warning("engine_session.unexpected_status", status=response.status_code)
        return None

    body = response.json()
    user_id = body.get("userId")
    tenant_id = body.get("tenantId")
    if not user_id or not tenant_id:
        # Старая сборка движка идентификаторов не отдаёт. Сводить не по чему,
        # и догадываться по почте нельзя.
        raise EngineUnreachableError("движок не вернул идентификаторы сессии")

    return EngineIdentity(
        engine_user_id=UUID(user_id),
        engine_tenant_id=UUID(tenant_id),
        email=body.get("email", ""),
    )


async def resolve(token: str) -> EngineIdentity | None:
    """Разобрать сессию движка. None — недействительна.

    Raises:
        EngineUnreachableError: движок не ответил или ответил непонятным.
    """
    if not settings.engine_base_url:
        return None

    async with redis_client() as r:
        cached = await _from_cache(r, token)
        if cached is not None:
            return cached

        identity = await _ask_engine(token)
        if identity is None:
            # Отрицательный ответ не кешируется: он и так дёшев, а кеш на нём
            # продлевал бы отказ уже вошедшему заново человеку.
            return None

        await r.set(
            _cache_key(token),
            json.dumps(
                {
                    "user_id": str(identity.engine_user_id),
                    "tenant_id": str(identity.engine_tenant_id),
                    "email": identity.email,
                }
            ),
            ex=settings.engine_session_cache_seconds,
        )
        return identity
