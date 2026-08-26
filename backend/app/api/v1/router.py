from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import chat, dashboards, health, insights, sync

# Входа здесь нет намеренно: удостоверяет движок, а кабинет только
# разбирает его сессию. Свой вход был второй дверью в один дом.
api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(dashboards.router)
api_router.include_router(insights.router)
api_router.include_router(sync.router)
api_router.include_router(chat.router)
