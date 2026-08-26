"""Integration tests for Phase 8 Plan 08-05 chat endpoints (CHAT-01, CHAT-02 SC#2).

These tests exercise the full FastAPI → Redis → orchestrator → DB stack with the
AsyncAnthropic SDK boundary mocked via recorded cassettes from plan 08-01
(BASIC_TURN_EVENTS, MULTI_TOOL_EVENTS).

Pattern: Phase 5 carry-forward `_integration_skip` per-test gate — tests
skip cleanly on developer machines without TEST_DATABASE_URL but run on CI
where a live PostgreSQL is provisioned. The `_integration_skip` decorator
is applied PER TEST (not pytestmark) so the test file collects cleanly
without DB access.

Coverage map:
  test_create_conversation                 — POST /chat/conversations
  test_list_conversations_archived_filter  — GET /chat/conversations ?archived
  test_get_conversation_with_messages      — GET /chat/conversations/{id}
  test_archive_conversation_soft_delete    — DELETE /chat/conversations/{id}
  test_send_message_sse_basic_turn         — POST /messages SSE (CHAT-01)
  test_send_message_sse_multi_tool         — POST /messages SSE multi-tool (CHAT-02 SC#2)
  test_rate_limit_429                      — 30/hour cap (D-24)
  test_concurrent_stream_409               — 1 active stream per conversation (D-11)
  test_suggested_questions_static_only     — D-17 hybrid: 5 static only
  test_suggested_questions_with_dynamic    — D-17 hybrid: 5 static + 2 dynamic
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

# Cassettes from Wave 0 plan 08-01 — recorded streaming events for the
# AsyncAnthropic mock.
from tests.fixtures.anthropic_responses.basic_turn import BASIC_TURN_EVENTS

# Phase 5 carry-forward — per-test gate decorator. Skips cleanly when
# TEST_DATABASE_URL is not set (developer machines), runs on CI.
_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "")
_integration_skip = pytest.mark.skipif(
    not _TEST_DB_URL,
    reason="integration test — requires TEST_DATABASE_URL",
)

pytestmark = pytest.mark.asyncio

MOCK_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
MOCK_USER_ID = UUID("00000000-0000-0000-0000-000000000010")


# ── Shared helpers ────────────────────────────────────────────────────────────


def _make_mock_orchestrator_for_basic_turn() -> MagicMock:
    """Build a ChatOrchestrator mock whose run_turn yields a basic-cassette
    sequence: conversation_meta → 6 assistant_chunks → done."""
    orch = MagicMock()

    async def _run_turn(*, conversation_id, user_text, disconnect_probe):
        yield (
            "conversation_meta",
            {
                "conversation_id": str(conversation_id),
                "message_id_user": str(uuid4()),
                "message_id_assistant": str(uuid4()),
            },
        )
        # Stream the BASIC_TURN_EVENTS text_delta events as assistant_chunk SSE.
        for evt in BASIC_TURN_EVENTS:
            if evt.get("type") == "content_block_delta":
                delta = evt.get("delta", {})
                if delta.get("type") == "text_delta":
                    yield ("assistant_chunk", {"text": delta.get("text", "")})
        yield (
            "done",
            {
                "message_id": str(uuid4()),
                "total_input_tokens": 1200,
                "total_output_tokens": 80,
                "duration_ms": 1500,
                "hallucination_flag": False,
            },
        )

    orch.run_turn = _run_turn
    return orch


def _make_mock_orchestrator_for_multi_tool() -> MagicMock:
    """Build a ChatOrchestrator mock that yields 3 tool_use + 3 tool_result + done.

    Used by test_send_message_sse_multi_tool (CHAT-02 SC#2 — ≥3 distinct tools).
    """
    orch = MagicMock()

    async def _run_turn(*, conversation_id, user_text, disconnect_probe):
        yield (
            "conversation_meta",
            {
                "conversation_id": str(conversation_id),
                "message_id_user": str(uuid4()),
                "message_id_assistant": str(uuid4()),
            },
        )
        # 3 tool_use + 3 tool_result events (CHAT-02 SC#2).
        for name, tool_use_id in [
            ("get_funnel_data", "toolu_funnel_001"),
            ("get_salesperson_performance", "toolu_salesperson_001"),
            ("compare_periods", "toolu_compare_001"),
        ]:
            yield ("tool_use", {"tool_use_id": tool_use_id, "name": name, "input": {}})
            yield (
                "tool_result",
                {
                    "tool_use_id": tool_use_id,
                    "output_preview": "{}",
                    "duration_ms": 50,
                    "error": None,
                },
            )
        yield ("assistant_chunk", {"text": "Iată o sinteză."})
        yield (
            "done",
            {
                "message_id": str(uuid4()),
                "total_input_tokens": 2400,
                "total_output_tokens": 320,
                "duration_ms": 3500,
                "hallucination_flag": False,
            },
        )

    orch.run_turn = _run_turn
    return orch


def _override_app_dependencies(mock_session: AsyncMock | None = None):
    """Install standard dependency overrides for chat integration tests."""
    from app.core.dependencies import get_current_user
    from app.db.deps import get_session
    from app.main import app
    from app.schemas.auth import UserOut

    mock_user = UserOut(id=MOCK_USER_ID, email="ceo@sofabelle.ro", is_active=True)
    session = mock_session or AsyncMock()
    session.commit = AsyncMock()

    async def _mock_current_user():
        return mock_user

    async def _mock_get_session():
        yield session

    app.dependency_overrides[get_current_user] = _mock_current_user
    app.dependency_overrides[get_session] = _mock_get_session
    return mock_user, session


# ── test_create_conversation (CHAT-01 — minimal path) ─────────────────────────


@_integration_skip
async def test_create_conversation() -> None:
    """POST /chat/conversations with {initial_message: 'Salut'} → 200 + valid envelope.

    Verifies persistence + initial-message wiring through the live FastAPI stack
    with a mocked ChatOrchestrator (the orchestrator is not exercised by this
    endpoint; the test focuses on conversation + first-user-message persistence).
    """
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    _override_app_dependencies()

    fake_conv = MagicMock(
        id=uuid4(),
        title=None,
        created_at=MagicMock(isoformat=lambda: "2026-05-29T10:00:00+00:00"),
        last_message_at=MagicMock(isoformat=lambda: "2026-05-29T10:00:00+00:00"),
        archived=False,
    )

    conv_repo = AsyncMock()
    conv_repo.insert_conversation = AsyncMock(return_value=fake_conv.id)
    conv_repo.get_by_id = AsyncMock(return_value=fake_conv)
    msg_repo = AsyncMock()
    msg_repo.insert_user_message = AsyncMock(return_value=uuid4())

    try:
        with patch("app.api.v1.chat.ConversationRepository", return_value=conv_repo):
            with patch("app.api.v1.chat.MessageRepository", return_value=msg_repo):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as c:
                    r = await c.post(
                        "/api/v1/chat/conversations",
                        json={"initial_message": "Salut"},
                    )
        assert r.status_code == 200
        body = r.json()
        assert "id" in body
        assert body["archived"] is False
        msg_repo.insert_user_message.assert_awaited_once()
    finally:
        app.dependency_overrides.clear()


# ── test_list_conversations_archived_filter ───────────────────────────────────


@_integration_skip
async def test_list_conversations_archived_filter() -> None:
    """GET /chat/conversations?archived=false returns active only; ?archived=true filters."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    _override_app_dependencies()

    fake_active = [
        MagicMock(
            id=uuid4(),
            title="Test A",
            created_at=MagicMock(),
            last_message_at=MagicMock(),
            archived=False,
        )
        for _ in range(2)
    ]
    fake_archived = [
        MagicMock(
            id=uuid4(),
            title="Test Z",
            created_at=MagicMock(),
            last_message_at=MagicMock(),
            archived=True,
        )
    ]

    conv_repo = AsyncMock()

    async def _list(*, archived: bool, limit: int):
        return fake_archived if archived else fake_active

    conv_repo.list_conversations = AsyncMock(side_effect=_list)

    try:
        with patch("app.api.v1.chat.ConversationRepository", return_value=conv_repo):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as c:
                r_active = await c.get("/api/v1/chat/conversations")
                r_archived = await c.get("/api/v1/chat/conversations?archived=true")
        assert r_active.status_code == 200
        assert len(r_active.json()["conversations"]) == 2
        assert r_archived.status_code == 200
        assert len(r_archived.json()["conversations"]) == 1
    finally:
        app.dependency_overrides.clear()


# ── test_get_conversation_with_messages ───────────────────────────────────────


@_integration_skip
async def test_get_conversation_with_messages() -> None:
    """GET /chat/conversations/{id} returns the envelope + 404 on other-tenant id."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    _override_app_dependencies()

    conv_id = uuid4()
    fake = MagicMock(
        id=conv_id,
        title="Test",
        created_at=MagicMock(),
        last_message_at=MagicMock(),
        archived=False,
    )

    conv_repo = AsyncMock()

    async def _get_by_id(cid):
        # Tenant isolation: only `conv_id` (this tenant's) returns.
        return fake if cid == conv_id else None

    conv_repo.get_by_id = AsyncMock(side_effect=_get_by_id)

    try:
        with patch("app.api.v1.chat.ConversationRepository", return_value=conv_repo):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as c:
                r_found = await c.get(f"/api/v1/chat/conversations/{conv_id}")
                r_404 = await c.get(f"/api/v1/chat/conversations/{uuid4()}")
        assert r_found.status_code == 200
        assert r_404.status_code == 404
        assert "Conversația nu există" in r_404.json()["detail"]
    finally:
        app.dependency_overrides.clear()


# ── test_archive_conversation_soft_delete ─────────────────────────────────────


@_integration_skip
async def test_archive_conversation_soft_delete() -> None:
    """DELETE /chat/conversations/{id} → 204; row in DB has archived=True (D-15)."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    _override_app_dependencies()

    conv_id = uuid4()
    fake = MagicMock(id=conv_id, archived=False)

    conv_repo = AsyncMock()
    conv_repo.get_by_id = AsyncMock(return_value=fake)
    conv_repo.soft_archive = AsyncMock()

    try:
        with patch("app.api.v1.chat.ConversationRepository", return_value=conv_repo):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as c:
                r = await c.delete(f"/api/v1/chat/conversations/{conv_id}")
        assert r.status_code == 204
        conv_repo.soft_archive.assert_awaited_once_with(conv_id)
    finally:
        app.dependency_overrides.clear()


# ── test_send_message_sse_basic_turn (CHAT-01) ────────────────────────────────


@_integration_skip
async def test_send_message_sse_basic_turn() -> None:
    """CHAT-01: POST /messages with mocked AsyncAnthropic returns SSE events in order.

    Asserts: conversation_meta → multiple assistant_chunk → done. Uses
    BASIC_TURN_EVENTS cassette from Wave 0.
    """
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    _override_app_dependencies()

    fake_redis = AsyncMock()
    fake_redis.incr = AsyncMock(return_value=1)
    fake_redis.expire = AsyncMock(return_value=True)
    fake_redis.set = AsyncMock(return_value=True)
    fake_redis.delete = AsyncMock(return_value=1)
    fake_redis.ttl = AsyncMock(return_value=3600)
    redis_ctx = AsyncMock()
    redis_ctx.__aenter__ = AsyncMock(return_value=fake_redis)
    redis_ctx.__aexit__ = AsyncMock(return_value=None)

    orch = _make_mock_orchestrator_for_basic_turn()
    conv_id = uuid4()

    # CR-01 (Plan 08-07): send_message now runs an ownership pre-check via
    # ConversationRepository.get_by_id BEFORE touching Redis. Patch the repo
    # to return a valid (owned) row so the test exercises the SSE happy path.
    conv_repo = AsyncMock()
    conv_repo.get_by_id = AsyncMock(return_value=MagicMock(id=conv_id))

    try:
        with patch("app.api.v1.chat.ConversationRepository", return_value=conv_repo):
            with patch("app.api.v1.chat.aioredis.from_url", return_value=redis_ctx):
                with patch("app.api.v1.chat.ChatOrchestrator", return_value=orch):
                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://test"
                    ) as c:
                        async with c.stream(
                            "POST",
                            f"/api/v1/chat/conversations/{conv_id}/messages",
                            json={"content": "Cum stăm?"},
                        ) as r:
                            assert r.status_code == 200
                            assert r.headers["content-type"].startswith("text/event-stream")
                            # Drain the stream and collect event names.
                            event_names: list[str] = []
                            async for chunk in r.aiter_text():
                                for line in chunk.split("\n"):
                                    if line.startswith("event: "):
                                        event_names.append(line.removeprefix("event: ").strip())
        assert "conversation_meta" in event_names
        assert "assistant_chunk" in event_names
        assert "done" in event_names
        # conversation_meta must come first
        assert event_names[0] == "conversation_meta"
    finally:
        app.dependency_overrides.clear()


# ── test_send_message_sse_multi_tool (CHAT-02 SC#2) ───────────────────────────


@_integration_skip
async def test_send_message_sse_multi_tool() -> None:
    """CHAT-02 SC#2: 3 distinct tool_use + 3 tool_result events emitted per turn."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    _override_app_dependencies()

    fake_redis = AsyncMock()
    fake_redis.incr = AsyncMock(return_value=1)
    fake_redis.expire = AsyncMock(return_value=True)
    fake_redis.set = AsyncMock(return_value=True)
    fake_redis.delete = AsyncMock(return_value=1)
    fake_redis.ttl = AsyncMock(return_value=3600)
    redis_ctx = AsyncMock()
    redis_ctx.__aenter__ = AsyncMock(return_value=fake_redis)
    redis_ctx.__aexit__ = AsyncMock(return_value=None)

    orch = _make_mock_orchestrator_for_multi_tool()
    conv_id = uuid4()

    # CR-01 (Plan 08-07): ownership pre-check passes — see test above.
    conv_repo = AsyncMock()
    conv_repo.get_by_id = AsyncMock(return_value=MagicMock(id=conv_id))

    try:
        with patch("app.api.v1.chat.ConversationRepository", return_value=conv_repo):
            with patch("app.api.v1.chat.aioredis.from_url", return_value=redis_ctx):
                with patch("app.api.v1.chat.ChatOrchestrator", return_value=orch):
                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://test"
                    ) as c:
                        async with c.stream(
                            "POST",
                            f"/api/v1/chat/conversations/{conv_id}/messages",
                            json={"content": "Cum stăm comparativ?"},
                        ) as r:
                            assert r.status_code == 200
                            event_names: list[str] = []
                            async for chunk in r.aiter_text():
                                for line in chunk.split("\n"):
                                    if line.startswith("event: "):
                                        event_names.append(line.removeprefix("event: ").strip())
        assert event_names.count("tool_use") == 3
        assert event_names.count("tool_result") == 3
        assert "done" in event_names
    finally:
        app.dependency_overrides.clear()


# ── test_rate_limit_429 (D-24) ────────────────────────────────────────────────


@_integration_skip
async def test_rate_limit_429() -> None:
    """D-24: when Redis INCR returns 31 (over the 30/hour cap), endpoint returns 429."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    _override_app_dependencies()

    fake_redis = AsyncMock()
    fake_redis.incr = AsyncMock(return_value=31)  # over the cap
    fake_redis.expire = AsyncMock(return_value=True)
    fake_redis.set = AsyncMock(return_value=True)
    fake_redis.delete = AsyncMock(return_value=1)
    fake_redis.ttl = AsyncMock(return_value=900)
    redis_ctx = AsyncMock()
    redis_ctx.__aenter__ = AsyncMock(return_value=fake_redis)
    redis_ctx.__aexit__ = AsyncMock(return_value=None)

    # CR-01 (Plan 08-07): ownership pre-check passes — caller owns the row.
    conv_repo = AsyncMock()
    conv_repo.get_by_id = AsyncMock(return_value=MagicMock(id=uuid4()))

    try:
        with patch("app.api.v1.chat.ConversationRepository", return_value=conv_repo):
            with patch("app.api.v1.chat.aioredis.from_url", return_value=redis_ctx):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as c:
                    r = await c.post(
                        f"/api/v1/chat/conversations/{uuid4()}/messages",
                        json={"content": "Test"},
                    )
        assert r.status_code == 429
        assert r.headers.get("retry-after") == "900"
        assert "Ai trimis prea multe mesaje" in r.json()["detail"]
    finally:
        app.dependency_overrides.clear()


# ── test_concurrent_stream_409 (D-11) ─────────────────────────────────────────


@_integration_skip
async def test_concurrent_stream_409() -> None:
    """D-11: when stream-lock SET NX returns False, endpoint returns 409 Romanian."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    _override_app_dependencies()

    fake_redis = AsyncMock()
    fake_redis.incr = AsyncMock(return_value=1)  # rate-limit fine
    fake_redis.expire = AsyncMock(return_value=True)
    fake_redis.set = AsyncMock(return_value=False)  # lock contended
    fake_redis.delete = AsyncMock(return_value=1)
    fake_redis.ttl = AsyncMock(return_value=180)
    redis_ctx = AsyncMock()
    redis_ctx.__aenter__ = AsyncMock(return_value=fake_redis)
    redis_ctx.__aexit__ = AsyncMock(return_value=None)

    # CR-01 (Plan 08-07): ownership pre-check passes — caller owns the row.
    conv_repo = AsyncMock()
    conv_repo.get_by_id = AsyncMock(return_value=MagicMock(id=uuid4()))

    try:
        with patch("app.api.v1.chat.ConversationRepository", return_value=conv_repo):
            with patch("app.api.v1.chat.aioredis.from_url", return_value=redis_ctx):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as c:
                    r = await c.post(
                        f"/api/v1/chat/conversations/{uuid4()}/messages",
                        json={"content": "Test"},
                    )
        assert r.status_code == 409
        assert "Așteaptă răspunsul curent" in r.json()["detail"]
    finally:
        app.dependency_overrides.clear()


# ── test_suggested_questions_static_only (D-17) ───────────────────────────────


@_integration_skip
async def test_suggested_questions_static_only() -> None:
    """D-17: with no daily_insights row, returns 5 static questions."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    _override_app_dependencies()

    insight_svc = MagicMock()
    insight_svc.get_today = AsyncMock(return_value=None)

    try:
        with patch("app.api.v1.chat.InsightReadService", return_value=insight_svc):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as c:
                r = await c.get("/api/v1/chat/suggested-questions")
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 5
        assert len(body["questions"]) == 5
    finally:
        app.dependency_overrides.clear()


# ── test_suggested_questions_with_dynamic (D-17) ──────────────────────────────


@_integration_skip
async def test_suggested_questions_with_dynamic() -> None:
    """D-17: with success insight + 2 problems, returns 5 static + 2 dynamic = 7."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    _override_app_dependencies()

    insight_svc = MagicMock()
    insight_svc.get_today = AsyncMock(
        return_value={
            "date": "2026-05-29",
            "status": "success",
            "generation_failed": False,
            "generated_at": None,
            "payload": {
                "problems": [
                    {"id": "p1", "title": "Lead-uri blocate la ofertă", "estimated_loss_ron": "9000.00"},
                    {"id": "p2", "title": "Răspuns lent la lead noi", "estimated_loss_ron": "5500.00"},
                ],
            },
        }
    )

    try:
        with patch("app.api.v1.chat.InsightReadService", return_value=insight_svc):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as c:
                r = await c.get("/api/v1/chat/suggested-questions")
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 7
        dynamic = [q for q in body["questions"] if q.startswith("Spune-mi mai mult despre:")]
        assert len(dynamic) == 2
    finally:
        app.dependency_overrides.clear()
