from __future__ import annotations

import uuid as uuid_mod
from contextlib import asynccontextmanager
from uuid import UUID

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.tenancy import set_tenant_id

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    """Pure ASGI middleware — sets tenant context and structlog bindings per request.

    D-05: tenant_id MUST be set inside __call__ (per-request), not in lifespan.
    Uses pure ASGI class pattern (not BaseHTTPMiddleware) to avoid async context
    copy issues that would break bind_contextvars propagation (Pitfall #5).
    """

    def __init__(self, app: object) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: object, send: object) -> None:
        if scope["type"] == "http":
            clear_contextvars()
            # D-05: Set tenant per-request here, NOT in lifespan.
            set_tenant_id(UUID(settings.sofa_belle_tenant_id))
            bind_contextvars(
                request_id=str(uuid_mod.uuid4()),
                path=scope.get("path", ""),
                tenant_id=str(settings.sofa_belle_tenant_id),
            )
        await self.app(scope, receive, send)


app.add_middleware(StructlogContextMiddleware)

app.include_router(api_router, prefix="/api/v1")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
