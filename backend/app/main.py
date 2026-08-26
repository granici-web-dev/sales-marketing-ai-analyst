from __future__ import annotations

import uuid as uuid_mod
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send
from structlog.contextvars import bind_contextvars, clear_contextvars

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging

logger = structlog.get_logger(__name__)


async def _report_unlinked_tenants() -> None:
    """Сказать вслух, сколько клиентов не привязано к движку.

    Непривязанный арендатор — это клиент, которого движок пустит, а аналитик
    не найдёт: человек получит отказ без объяснения, и разбираться придётся по
    журналу. Раньше о привязке напоминал только комментарий в исходниках.

    Отказ базы здесь не должен мешать приложению подняться: это отчёт о
    состоянии, а не условие работы. Но и молчать о нём нельзя — иначе строка
    «непривязанных нет» будет означать сразу две разные вещи.
    """
    from sqlalchemy.ext.asyncio import create_async_engine  # deferred (INFRA-05)
    from sqlalchemy.pool import NullPool

    from app.services.tenants import directory  # deferred (INFRA-05)

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            unlinked = await directory.count_unlinked(conn)
            total = len(await directory.list_all(conn))
    except Exception:
        logger.exception("startup.tenant_link_check_failed")
        return
    finally:
        await engine.dispose()

    if unlinked:
        logger.warning(
            "startup.tenants_unlinked",
            unlinked=unlinked,
            total=total,
            hint="python -m app.cli tenants link <slug> <engine-tenant-uuid>",
        )
    else:
        logger.info("startup.tenants_all_linked", total=total)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # configure_logging only — set_tenant_id MUST NOT be called here.
    # ContextVars set in lifespan do not propagate to HTTP request coroutines;
    # each request runs in its own asyncio task with a fresh context copy (D-05).
    configure_logging(settings.log_level)
    await _report_unlinked_tenants()
    yield


app = FastAPI(
    title="Sales & Marketing AI Analyst",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class StructlogContextMiddleware:
    """Pure ASGI middleware — per-request structlog bindings.

    Арендатора здесь больше нет. Прежде он ставился отсюда из настройки —
    одно и то же значение на любой запрос, кем бы тот ни был сделан. Пока
    клиент был один, разницы не было; со вторым это была бы выдача чужих
    данных с кодом 200.

    Теперь арендатор приходит из удостоверенной сессии и ставится в
    `get_current_user`, то есть тогда, когда уже известно, чей он. Запрос без
    удостоверения остаётся без арендатора, и тенантный запрос из него
    отвергается — это и есть работающая изоляция, а не её видимость.

    Pure ASGI class pattern (not BaseHTTPMiddleware) to avoid async context
    copy issues that would break bind_contextvars propagation (Pitfall #5).
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            clear_contextvars()
            bind_contextvars(
                request_id=str(uuid_mod.uuid4()),
                path=scope.get("path", ""),
            )
        await self.app(scope, receive, send)


app.add_middleware(StructlogContextMiddleware)

app.include_router(api_router, prefix="/api/v1")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
