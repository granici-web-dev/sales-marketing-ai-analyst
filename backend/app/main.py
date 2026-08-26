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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # configure_logging only — set_tenant_id MUST NOT be called here.
    # ContextVars set in lifespan do not propagate to HTTP request coroutines;
    # each request runs in its own asyncio task with a fresh context copy (D-05).
    configure_logging(settings.log_level)
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
