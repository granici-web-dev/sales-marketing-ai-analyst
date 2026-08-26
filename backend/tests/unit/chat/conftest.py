"""Shared fixtures for Phase 8 AI Chat unit tests.

Provides reusable test infrastructure that every chat unit test relies on:
  - Sofa Belle test tenant + user UUIDs (Phase 5 carry-forward via project conftest)
  - AsyncSession mock for repository-layer tests
  - AsyncAnthropic patch target + mock client for orchestrator tests
  - SSE collector to drain async event streams into asserted tuples
  - mock_anthropic_stream factory for replaying recorded streaming events

Wave 0 contract (plan 08-01 D-38/D-39): these fixtures DO NOT import from
`app.services.chat.*` at module load time. All such references are deferred to
fixture bodies (via string-targeted `patch()`) so this conftest is importable
BEFORE the production orchestrator code lands in plans 08-04..08-05.

Patch target convention:
  - `app.services.chat.orchestrator.AsyncAnthropic` — the canonical patch site
    (mirrors Phase 5's `app.services.insights.insight_service.AsyncAnthropic`).
  - If the orchestrator module name diverges in plan 08-04, update this string
    AND the corresponding `_active_chat_module` constant so future plans don't
    silently no-op the patch (see T-08 threat register: tampering — patch drift).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

# Canonical patch target — the future orchestrator's AsyncAnthropic import site.
# If plan 08-04 places the orchestrator at a different module path, update here.
ORCHESTRATOR_ANTHROPIC_PATCH_TARGET = "app.services.chat.orchestrator.AsyncAnthropic"

# Sofa Belle pilot tenant — mirrors tests/conftest.py TEST_TENANT_ID
SOFA_BELLE_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
# Stable owner-user UUID for chat conversation persistence tests
SOFA_BELLE_USER_ID = UUID("00000000-0000-0000-0000-000000000010")


# ── Identity fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def tenant_id() -> UUID:
    """Sofa Belle pilot tenant UUID (T-08-01: never reused cross-tenant)."""
    return SOFA_BELLE_TENANT_ID


@pytest.fixture
def user_id() -> UUID:
    """Stable owner-user UUID for chat conversation persistence tests."""
    return SOFA_BELLE_USER_ID


# ── DB session mock ────────────────────────────────────────────────────────────


@pytest.fixture
def mock_session() -> AsyncMock:
    """AsyncMock standing in for an SQLAlchemy AsyncSession.

    Tests that exercise repository methods configure return values on
    `mock_session.execute.return_value.scalars.return_value.all.return_value` etc.
    Uses AsyncMock (not MagicMock) so `await session.execute(...)` works
    out-of-the-box. spec=AsyncSession deferred until the production code
    actually imports it (Wave 0 mustn't depend on production imports).
    """
    return AsyncMock()


# ── AsyncAnthropic client mock ─────────────────────────────────────────────────


@pytest.fixture
def mock_anthropic_client() -> AsyncMock:
    """Pre-built AsyncMock client mimicking the AsyncAnthropic surface.

    Shape mirrors `app/services/insights/insight_service.py` lines 92-98:
        client = AsyncAnthropic(api_key=...)
        response = await client.messages.create(...)
        async with client.messages.stream(...) as stream: ...

    Returns the inner client (what `AsyncAnthropic(...)` constructor returns).
    Combine with `mock_anthropic_class` to control the constructor itself.
    """
    client = AsyncMock()
    client.messages = AsyncMock()
    client.messages.create = AsyncMock()
    client.messages.stream = MagicMock()  # context manager — sync entry, async body
    return client


@pytest.fixture
def mock_anthropic_class(mock_anthropic_client: AsyncMock):
    """Patches `app.services.chat.orchestrator.AsyncAnthropic` at the call site.

    NOTE: patch is INERT until plan 08-04 creates the orchestrator module.
    Until then, `start()` raises ModuleNotFoundError; fixture catches and yields
    a no-op MagicMock so Wave 0 tests can still parametrize against it.

    After 08-04 lands: this fixture activates the patch, AsyncAnthropic(...)
    returns `mock_anthropic_client`, and tests can drive both streaming and
    non-streaming flows from a single mock surface (mirrors Phase 5
    `test_insight_service.py:139-149` pattern).
    """
    try:
        patcher = patch(ORCHESTRATOR_ANTHROPIC_PATCH_TARGET)
        mock_cls = patcher.start()
        mock_cls.return_value = mock_anthropic_client
        yield mock_cls
        patcher.stop()
    except (ModuleNotFoundError, AttributeError):
        # Orchestrator not yet present — yield a no-op double so Wave 0 tests pass.
        yield MagicMock(return_value=mock_anthropic_client)


# ── SSE collector ──────────────────────────────────────────────────────────────


@pytest.fixture
def sse_collector():
    """Async helper draining an SSE async generator into list[tuple[event, payload]].

    Usage:
        events = await sse_collector(orchestrator.stream(conversation_id, user_text))
        assert ("conversation_meta", {...}) in events

    The async generator is expected to yield dicts shaped per D-09:
        {"event": "tool_use" | "assistant_chunk" | "done" | ..., "data": {...}}
    Returns the collected list once the generator exhausts.
    """

    async def _collect(stream: AsyncIterator[dict]) -> list[tuple[str, dict]]:
        out: list[tuple[str, dict]] = []
        async for evt in stream:
            event_name = evt.get("event", "unknown")
            payload = evt.get("data", {})
            out.append((event_name, payload))
        return out

    return _collect


# ── mock_anthropic_stream factory ──────────────────────────────────────────────


@pytest.fixture
def mock_anthropic_stream():
    """Factory producing an async-context-manager mock matching `messages.stream(...)`.

    Args:
        events: list of dicts describing streaming events. Each dict mirrors a
            single Anthropic SSE chunk per RESEARCH §2 (see anthropic_responses/
            basic_turn.py for shape examples). Recognized top-level keys:
                - "type": "message_start" | "content_block_start" |
                          "content_block_delta" | "content_block_stop" |
                          "message_delta" | "message_stop"
                - "content_block": {"type": "text"|"tool_use", ...}
                - "delta": {"type":"text_delta"|"input_json_delta", "text"|"partial_json": ...}
                - "usage": {"input_tokens": int, "output_tokens": int,
                            "cache_read_input_tokens": int}

    Returns:
        A MagicMock such that:
            with mock_client.messages.stream(...) as stream:
                async for event in stream:
                    ...
        yields each dict from `events` in order. Also exposes
        `stream.get_final_message()` returning a MagicMock with `.stop_reason`
        and `.usage` populated from the last `message_delta` / `message_stop`
        events.
    """

    def _factory(events: list[dict]):
        async def _aiter():
            for evt in events:
                yield evt

        stream_obj = MagicMock()
        stream_obj.__aiter__ = lambda self: _aiter()

        # get_final_message() pattern — Anthropic SDK exposes this on the stream.
        final_msg = MagicMock()
        # Extract stop_reason + usage from the final message_delta / message_stop event.
        final_msg.stop_reason = "end_turn"
        final_msg.usage = MagicMock(
            input_tokens=0,
            output_tokens=0,
            cache_read_input_tokens=0,
        )
        for evt in events:
            if evt.get("type") == "message_delta":
                delta = evt.get("delta", {})
                if "stop_reason" in delta:
                    final_msg.stop_reason = delta["stop_reason"]
            usage = evt.get("usage")
            if usage:
                final_msg.usage.input_tokens = usage.get("input_tokens", 0)
                final_msg.usage.output_tokens = usage.get("output_tokens", 0)
                final_msg.usage.cache_read_input_tokens = usage.get(
                    "cache_read_input_tokens", 0
                )
        stream_obj.get_final_message = AsyncMock(return_value=final_msg)

        # Async-context-manager wrapper for `with client.messages.stream(...) as stream`.
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=stream_obj)
        ctx.__aexit__ = AsyncMock(return_value=False)
        return ctx

    return _factory
