"""Единственное место, где открывается соединение с Redis.

Все шесть вызовов в коде были дословно одинаковы, включая `decode_responses`.
Это не совпадение, а требование: половина кода, читающая байты, и половина,
читающая строки, расходятся молча и обнаруживаются на живом ключе.

Здесь же закрыт разрыв в типах. Пакет `redis` поставляет `py.typed`, но
`from_url` оставлен без аннотаций, поэтому под `strict` каждый его вызов —
обращение к нетипизированной функции. Приведение стоит один раз тут, а не
шестью `type: ignore` по всему приложению.
"""

from __future__ import annotations

from typing import Any, cast

import redis.asyncio as aioredis


def redis_client(**overrides: Any) -> aioredis.Redis:
    """Клиент Redis по адресу из настроек.

    Настройки читаются в теле функции, а не на уровне модуля: этот модуль
    импортируется в том числе из тел задач Celery, где отложенный импорт —
    правило (INFRA-05).
    """
    from app.core.config import settings  # deferred (INFRA-05)

    return cast(
        "aioredis.Redis",
        # `from_url` объявлен как `(url, **kwargs)` без единой аннотации, хотя
        # пакет и помечен py.typed. Один маркер здесь — цена за то, что во всём
        # остальном приложении вызовов этой функции не осталось.
        aioredis.from_url(  # type: ignore[no-untyped-call]
            settings.redis_url, decode_responses=True, **overrides
        ),
    )
