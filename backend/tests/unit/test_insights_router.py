from __future__ import annotations

"""Unit tests for insights router rate limiting and AI-09 compliance.

Tests the rate-limit logic in POST /api/v1/insights/refresh in isolation —
no real Redis or Celery required.

These call the handler as a plain coroutine rather than through the app, so
FastAPI never resolves the signature. Anything FastAPI would have supplied has
to be passed explicitly — `target_date` included. Omitting it does not give the
default `None`: it hands the handler the `Query(None)` marker object itself,
and the first `target_date.isoformat()` inside raises AttributeError. That is
what broke both tests here (fixed 2026-08-25); the endpoint was always correct.

The tenant context is part of the same bargain. In a real request
`StructlogContextMiddleware` sets it before routing; calling the handler
directly skips that, so the test sets it itself.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

MOCK_USER_ID = UUID("00000000-0000-0000-0000-000000000002")
# Deliberately not the Sofa Belle UUID in config: if the handler ever goes back
# to reading settings, the assertion below sees a different value and fails.
MOCK_TENANT_ID = UUID("00000000-0000-0000-0000-0000000000ff")


@pytest.mark.asyncio
async def test_refresh_rate_limit_first_call_enqueues() -> None:
    """First call within window: Redis SET NX returns True → 202 + pipeline_run_id."""
    from app.api.v1.insights import refresh_insights
    from app.core.tenancy import set_tenant_id
    from app.schemas.auth import UserOut

    set_tenant_id(MOCK_TENANT_ID)

    mock_user = UserOut(id=MOCK_USER_ID, email="test@sofabelle.ro", is_active=True)
    mock_task = MagicMock()
    mock_task.id = "abc123-task-id"

    # The endpoint dispatches ONLY insight generation. It used to enqueue the
    # whole daily pipeline, and this test still patched `daily_pipeline` long
    # after that changed — patching a name the handler no longer calls, which
    # asserts nothing.
    mock_generate = MagicMock()
    mock_generate.delay.return_value = mock_task

    mock_r = AsyncMock()
    mock_r.set = AsyncMock(return_value=True)

    mock_redis_ctx = AsyncMock()
    mock_redis_ctx.__aenter__ = AsyncMock(return_value=mock_r)
    mock_redis_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_response = MagicMock()

    with patch("app.api.v1.insights.aioredis.from_url", return_value=mock_redis_ctx):
        with patch(
            "app.tasks.insights.generate_daily_insights.generate_daily_insights",
            mock_generate,
        ):
            result = await refresh_insights(
                response=mock_response,
                target_date=None,
                session=AsyncMock(),
                current_user=mock_user,
            )

    assert result.pipeline_run_id == "abc123-task-id"
    assert result.enqueued_at is not None
    mock_generate.delay.assert_called_once()
    # No date given → the task must be told "latest", not a stringified marker.
    tenant_id, kpi_date = mock_generate.delay.call_args.args
    assert kpi_date is None, f"expected no date, task received {kpi_date!r}"
    # The task must inherit the tenant of the request, not a value read from
    # config. Today both are equal in production and only this line tells them
    # apart; the day the context var comes from the JWT, it is the difference
    # between the right data and someone else's.
    assert tenant_id == str(MOCK_TENANT_ID), f"task got tenant {tenant_id!r}"


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
                target_date=None,
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
