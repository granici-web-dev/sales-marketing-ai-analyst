from __future__ import annotations

"""Unit tests for insights router rate limiting and AI-09 compliance.

Tests the rate-limit logic in POST /api/v1/insights/refresh in isolation —
no real Redis or Celery required.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

MOCK_USER_ID = UUID("00000000-0000-0000-0000-000000000002")


@pytest.mark.asyncio
async def test_refresh_rate_limit_first_call_enqueues() -> None:
    """First call within window: Redis SET NX returns True → 202 + pipeline_run_id."""
    from app.api.v1.insights import refresh_insights
    from app.schemas.auth import UserOut

    mock_user = UserOut(id=MOCK_USER_ID, email="test@sofabelle.ro", is_active=True)
    mock_task = MagicMock()
    mock_task.id = "abc123-task-id"

    mock_pipeline = MagicMock()
    mock_pipeline.return_value.delay.return_value = mock_task

    mock_r = AsyncMock()
    mock_r.set = AsyncMock(return_value=True)

    mock_redis_ctx = AsyncMock()
    mock_redis_ctx.__aenter__ = AsyncMock(return_value=mock_r)
    mock_redis_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_response = MagicMock()

    with patch("app.api.v1.insights.aioredis.from_url", return_value=mock_redis_ctx):
        with patch("app.tasks.etl.sync_mefi_leads.daily_pipeline", mock_pipeline):
            result = await refresh_insights(
                response=mock_response,
                session=AsyncMock(),
                current_user=mock_user,
            )

    assert result.pipeline_run_id == "abc123-task-id"
    assert result.enqueued_at is not None
    mock_pipeline.return_value.delay.assert_called_once()


@pytest.mark.asyncio
async def test_refresh_rate_limit_second_call_returns_429() -> None:
    """Second call within window: Redis SET NX returns None → 429 with Retry-After."""
    from fastapi import HTTPException

    from app.api.v1.insights import refresh_insights
    from app.schemas.auth import UserOut

    mock_user = UserOut(id=MOCK_USER_ID, email="test@sofabelle.ro", is_active=True)

    mock_r = AsyncMock()
    mock_r.set = AsyncMock(return_value=None)  # key already exists
    mock_r.ttl = AsyncMock(return_value=3000)

    mock_redis_ctx = AsyncMock()
    mock_redis_ctx.__aenter__ = AsyncMock(return_value=mock_r)
    mock_redis_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_response = MagicMock()

    with patch("app.api.v1.insights.aioredis.from_url", return_value=mock_redis_ctx):
        with pytest.raises(HTTPException) as exc_info:
            await refresh_insights(
                response=mock_response,
                session=AsyncMock(),
                current_user=mock_user,
            )

    assert exc_info.value.status_code == 429
    assert exc_info.value.headers["Retry-After"] == "3000"


@pytest.mark.asyncio
async def test_refresh_ai09_no_anthropic() -> None:
    """AI-09: refresh endpoint must not import or call AsyncAnthropic directly."""
    import importlib
    import sys

    # Reload module to get fresh namespace
    if "app.api.v1.insights" in sys.modules:
        module = sys.modules["app.api.v1.insights"]
    else:
        module = importlib.import_module("app.api.v1.insights")

    module_source_file = getattr(module, "__file__", "")

    with open(module_source_file) as f:
        source = f.read()

    assert "AsyncAnthropic" not in source, "AI-09 violation: AsyncAnthropic found in insights.py"
    assert "client.messages" not in source, "AI-09 violation: client.messages found in insights.py"
