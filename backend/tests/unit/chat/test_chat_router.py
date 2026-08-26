"""Unit tests for the Phase 8 Plan 08-05 chat router.

Covers per the plan <behavior> block R1-R12:
  R1  router import + prefix
  R2  D-25 module docstring substrings
  R3  AsyncAnthropic import + per-request instantiation site
  R4  CHAT-08 grep gate now strict-inclusion (chat.py present)
  R5  rate-limit 429 with Retry-After + Romanian message (D-24)
  R6  stream-lock 409 with Romanian message (D-11)
  R7  auth 401 (HTTPBearer auto_error)
  R8  POST /conversations creates row + optional initial_message
  R9  GET /conversations defaults to archived=false
  R10 DELETE /conversations/{id} → 204 + archived=True (D-15)
  R11 GET /suggested-questions hybrid (5 static + ≤2 dynamic) — fault tolerant
  R12 SSE endpoint returns text/event-stream + X-Accel-Buffering: no (LM-5)

Plus the CR-02 guard-ordering regressions (plan 08-08):
  R13 a contended stream-lock (409) never touches the rate-limit counter
  R14 a rate-limited request (429) releases the lock it just took

These tests mock AsyncSession, Redis, and ChatOrchestrator — no real DB or API.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

MOCK_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
MOCK_USER_ID = UUID("00000000-0000-0000-0000-000000000010")


# ── R1 — router import + prefix ──────────────────────────────────────────────


def test_r1_router_imports_with_chat_prefix() -> None:
    """R1: `from app.api.v1.chat import router` works; prefix='/chat'."""
    from app.api.v1.chat import router

    assert router.prefix == "/chat"


# ── R2 — D-25 module docstring substrings ────────────────────────────────────


def test_r2_module_docstring_cites_d25_documented_exception() -> None:
    """R2: module-level docstring contains D-25, documented exception, CHAT-08, AsyncAnthropic, CLAUDE.md."""
    import app.api.v1.chat as chat_mod

    docstring = (chat_mod.__doc__ or "").lower()
    for token in ("d-25", "documented exception", "chat-08", "asyncanthropic", "claude.md"):
        assert token in docstring, f"Module docstring missing required substring: {token!r}"


# ── R3 — AsyncAnthropic import + per-request instantiation (D-29 / LM-1) ─────


def test_r3_chat_module_imports_async_anthropic_and_instantiates_inside_handler() -> None:
    """R3: chat.py imports AsyncAnthropic (LM-1 module-level for patchability)
    AND calls `AsyncAnthropic(api_key=...)` (per-request instantiation per D-29)."""
    import app.api.v1.chat as chat_mod

    source_path = Path(chat_mod.__file__)
    source = source_path.read_text(encoding="utf-8")

    assert "from anthropic import AsyncAnthropic" in source, (
        "chat.py must import AsyncAnthropic at module level (LM-1 — Phase 5 carry-forward pattern)"
    )
    assert "AsyncAnthropic(api_key=" in source, (
        "chat.py must instantiate AsyncAnthropic(api_key=...) per request (D-29 / INFRA-05)"
    )


# ── R4 — CHAT-08 grep gate STRICT mode now active ────────────────────────────


def test_r4_chat08_grep_gate_strict_inclusion_active() -> None:
    """R4: with chat.py landed, the inverse CHAT-08 gate now ENFORCES
    strict-inclusion: chat.py contains AsyncAnthropic AND no sibling does.

    This mirrors the gate logic from test_anthropic_scope.py — once chat.py
    exists, the strict-inclusion clause activates. We verify both clauses here
    so the router plan's own tests catch a regression even if the dedicated
    gate test happens to drift.
    """
    here = Path(__file__).resolve()
    api_dir = here.parents[3] / "app" / "api" / "v1"
    chat_file = api_dir / "chat.py"

    # Strict-inclusion: chat.py MUST contain AsyncAnthropic.
    assert chat_file.exists(), "chat.py must exist after plan 08-05"
    chat_source = chat_file.read_text(encoding="utf-8")
    assert "AsyncAnthropic" in chat_source, (
        "CHAT-08 violation — chat.py exists but does not import AsyncAnthropic (D-25/D-29)"
    )

    # Strict-exclusion: no sibling file may import AsyncAnthropic.
    excluded = {"__init__.py", "router.py", "chat.py"}
    siblings = [p for p in api_dir.glob("*.py") if p.name not in excluded]
    for sibling in siblings:
        sib_source = sibling.read_text(encoding="utf-8")
        assert "AsyncAnthropic" not in sib_source, (
            f"CHAT-08 violation — AsyncAnthropic leaked into {sibling.name}"
        )
        assert "client.messages" not in sib_source, (
            f"CHAT-08 violation — client.messages leaked into {sibling.name}"
        )


# ── helpers for endpoint unit tests ──────────────────────────────────────────


def _make_user() -> object:
    """Build a minimal current_user object exposing `.id`."""
    from app.schemas.auth import UserOut

    return UserOut(id=MOCK_USER_ID, email="ceo@sofabelle.ro", is_active=True)


@pytest.fixture(autouse=True)
def _set_tenant_context():
    """Auto-set tenant context for every test (ContextVar isolation)."""
    from app.core.tenancy import set_tenant_id

    set_tenant_id(MOCK_TENANT_ID)
    return


def _make_redis_mock(
    *, incr_return=1, set_nx_return=True, ttl_return=3600
) -> tuple[AsyncMock, AsyncMock]:
    """Build (redis_ctx, redis_client) mocks that emulate the
    `async with redis_client() as r:` pattern."""
    r = AsyncMock()
    r.incr = AsyncMock(return_value=incr_return)
    r.expire = AsyncMock(return_value=True)
    r.set = AsyncMock(return_value=set_nx_return)
    r.ttl = AsyncMock(return_value=ttl_return)
    r.delete = AsyncMock(return_value=1)
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=r)
    ctx.__aexit__ = AsyncMock(return_value=None)
    return ctx, r


# ── R5 — rate-limit 429 with Retry-After + Romanian (D-24) ───────────────────


@pytest.mark.asyncio
async def test_r5_post_messages_returns_429_when_rate_limit_exceeded() -> None:
    """R5: when Redis INCR returns 31 (over the 30/hour cap), the endpoint raises
    429 with `Retry-After` header and the exact Romanian message from UI-SPEC.

    CR-01 (Plan 08-07): send_message now runs a ConversationRepository.get_by_id
    ownership pre-check BEFORE touching Redis. The repo is patched here to
    return a valid (owned) conversation so this test exercises the
    rate-limit path, not the new ownership path (covered by R-CR01 tests in
    tests/integration/chat/test_cross_user_isolation.py).
    """
    from fastapi import HTTPException

    from app.api.v1.chat import send_message

    ctx, r = _make_redis_mock(incr_return=31, ttl_return=900)

    body = MagicMock()
    body.content = "Test"

    mock_request = MagicMock()
    mock_request.is_disconnected = AsyncMock(return_value=False)

    # CR-01 pre-check passes — caller owns the conversation.
    conv_repo = AsyncMock()
    conv_repo.get_by_id = AsyncMock(return_value=MagicMock(id=uuid4()))

    with patch("app.api.v1.chat.ConversationRepository", return_value=conv_repo):
        with patch("app.api.v1.chat.redis_client", return_value=ctx):
            with pytest.raises(HTTPException) as exc_info:
                await send_message(
                    conversation_id=uuid4(),
                    request=mock_request,
                    body=body,
                    session=AsyncMock(),
                    current_user=_make_user(),
                )

    assert exc_info.value.status_code == 429
    assert "Retry-After" in exc_info.value.headers
    assert "Ai trimis prea multe mesaje" in exc_info.value.detail


# ── R6 — stream-lock 409 with Romanian (D-11) ────────────────────────────────


@pytest.mark.asyncio
async def test_r6_post_messages_returns_409_when_stream_lock_held() -> None:
    """R6: when Redis SET NX returns False (lock already held), the endpoint
    raises 409 with the exact Romanian message from UI-SPEC.

    CR-01 (Plan 08-07): repo patched with a valid (owned) row so the new
    ownership pre-check passes and flow reaches the stream-lock branch.
    """
    from fastapi import HTTPException

    from app.api.v1.chat import send_message

    # rate-limit OK (incr=1) but stream-lock contended (set=False).
    ctx, r = _make_redis_mock(incr_return=1, set_nx_return=False)

    body = MagicMock()
    body.content = "Test"

    mock_request = MagicMock()
    mock_request.is_disconnected = AsyncMock(return_value=False)

    # CR-01 pre-check passes — caller owns the conversation.
    conv_repo = AsyncMock()
    conv_repo.get_by_id = AsyncMock(return_value=MagicMock(id=uuid4()))

    with patch("app.api.v1.chat.ConversationRepository", return_value=conv_repo):
        with patch("app.api.v1.chat.redis_client", return_value=ctx):
            with pytest.raises(HTTPException) as exc_info:
                await send_message(
                    conversation_id=uuid4(),
                    request=mock_request,
                    body=body,
                    session=AsyncMock(),
                    current_user=_make_user(),
                )

    assert exc_info.value.status_code == 409
    assert "Așteaptă răspunsul curent" in exc_info.value.detail


# ── R7 — auth 401 ────────────────────────────────────────────────────────────


def test_r7_endpoints_require_authentication_via_get_current_user_dependency() -> None:
    """R7: every router operation must include the get_current_user dependency
    in its dependencies graph (FastAPI then raises 401 on missing/invalid token)."""
    from app.api.v1.chat import router
    from app.core.dependencies import get_current_user

    # Inspect every route's dependencies and ensure get_current_user is wired
    # somewhere in the dependency chain (FastAPI stores Depends as `dependant`).
    for route in router.routes:
        deps = getattr(route, "dependant", None)
        if deps is None:
            continue
        # Walk the dependant tree looking for get_current_user.
        stack = [deps]
        found = False
        while stack:
            d = stack.pop()
            if d.call is get_current_user:
                found = True
                break
            stack.extend(d.dependencies)
        assert found, f"Route {route.path} missing get_current_user dependency (auth gap)"


# ── R8 — POST /conversations creates row + initial_message ───────────────────


@pytest.mark.asyncio
async def test_r8_post_conversations_creates_row_with_optional_initial_message() -> None:
    """R8: POST /conversations with `{initial_message: 'Salut'}` persists a new
    ChatConversation row AND the first user message via MessageRepository."""
    from app.api.v1.chat import create_conversation
    from app.schemas.chat.conversation import CreateConversationRequest

    body = CreateConversationRequest(initial_message="Salut")

    fake_conv_id = uuid4()
    fake_msg_id = uuid4()

    conv_repo = AsyncMock()
    conv_repo.insert_conversation = AsyncMock(return_value=fake_conv_id)
    conv_repo.get_by_id = AsyncMock(
        return_value=MagicMock(
            id=fake_conv_id,
            title=None,
            created_at=MagicMock(),
            last_message_at=MagicMock(),
            archived=False,
        )
    )

    msg_repo = AsyncMock()
    msg_repo.insert_user_message = AsyncMock(return_value=fake_msg_id)

    session = AsyncMock()
    session.commit = AsyncMock()

    with patch("app.api.v1.chat.ConversationRepository", return_value=conv_repo):
        with patch("app.api.v1.chat.MessageRepository", return_value=msg_repo):
            result = await create_conversation(
                body=body,
                session=session,
                current_user=_make_user(),
            )

    conv_repo.insert_conversation.assert_awaited_once()
    msg_repo.insert_user_message.assert_awaited_once_with(fake_conv_id, "Salut")
    session.commit.assert_awaited()
    # Result is a ConversationOut envelope with id matching the fake conv id.
    assert result.id == fake_conv_id


# ── R9 — GET /conversations defaults to archived=False ───────────────────────


@pytest.mark.asyncio
async def test_r9_list_conversations_defaults_archived_false() -> None:
    """R9: GET /conversations without ?archived only returns active rows."""
    from app.api.v1.chat import list_conversations

    conv_repo = AsyncMock()
    # Empty list — assertion is on the kwarg passed to repo.
    conv_repo.list_conversations = AsyncMock(return_value=[])

    with patch("app.api.v1.chat.ConversationRepository", return_value=conv_repo):
        result = await list_conversations(
            archived=False,
            limit=50,
            session=AsyncMock(),
            current_user=_make_user(),
        )

    conv_repo.list_conversations.assert_awaited_once_with(archived=False, limit=50)
    assert hasattr(result, "conversations")


# ── R10 — DELETE /conversations/{id} → archived=True (D-15) ──────────────────


@pytest.mark.asyncio
async def test_r10_delete_conversation_soft_archives_returns_204() -> None:
    """R10: DELETE /conversations/{id} calls soft_archive on the repo
    and returns 204 No Content (D-15)."""
    from app.api.v1.chat import archive_conversation

    conv_id = uuid4()
    fake_conv = MagicMock(id=conv_id, archived=False)

    conv_repo = AsyncMock()
    conv_repo.get_by_id = AsyncMock(return_value=fake_conv)
    conv_repo.soft_archive = AsyncMock()

    session = AsyncMock()
    session.commit = AsyncMock()

    with patch("app.api.v1.chat.ConversationRepository", return_value=conv_repo):
        result = await archive_conversation(
            conversation_id=conv_id,
            session=session,
            current_user=_make_user(),
        )

    conv_repo.soft_archive.assert_awaited_once_with(conv_id)
    session.commit.assert_awaited()
    # The handler returns either None (204) or a Response with 204 status
    # — both are acceptable representations of "no content".
    if result is not None:
        assert getattr(result, "status_code", 204) == 204


# ── R11 — GET /suggested-questions hybrid 5+(0..2) ───────────────────────────


@pytest.mark.asyncio
async def test_r11a_suggested_questions_static_only_when_no_insight() -> None:
    """R11a: with no daily_insight available, returns exactly the 5 static
    Romanian questions from D-17 / STATIC_QUESTIONS_RO."""
    from app.api.v1.chat import get_suggested_questions

    insight_svc = MagicMock()
    insight_svc.get_today = AsyncMock(return_value=None)

    with patch("app.api.v1.chat.InsightReadService", return_value=insight_svc):
        result = await get_suggested_questions(
            context="homepage",
            session=AsyncMock(),
            current_user=_make_user(),
        )

    assert result["count"] == 5
    assert len(result["questions"]) == 5
    # All 5 static D-17 questions should be in Romanian
    joined = " ".join(result["questions"])
    assert "vânzările" in joined.lower() or "vânzător" in joined.lower()


@pytest.mark.asyncio
async def test_r11b_suggested_questions_hybrid_with_dynamic_problems() -> None:
    """R11b: with daily_insight.status='success' + 2 problems, returns 5+2=7."""
    from app.api.v1.chat import get_suggested_questions

    insight_svc = MagicMock()
    insight_svc.get_today = AsyncMock(
        return_value={
            "date": "2026-05-29",
            "status": "success",
            "generation_failed": False,
            "generated_at": None,
            "payload": {
                "problems": [
                    {
                        "id": "p1",
                        "title": "Lead-uri blocate la ofertă",
                        "estimated_loss_ron": "5000.00",
                    },
                    {
                        "id": "p2",
                        "title": "Răspuns lent la lead noi",
                        "estimated_loss_ron": "3000.00",
                    },
                ],
            },
        }
    )

    with patch("app.api.v1.chat.InsightReadService", return_value=insight_svc):
        result = await get_suggested_questions(
            context="homepage",
            session=AsyncMock(),
            current_user=_make_user(),
        )

    assert result["count"] == 7
    assert len(result["questions"]) == 7
    # Dynamic chips are prefixed per UI-SPEC.
    dynamic = [q for q in result["questions"] if q.startswith("Spune-mi mai mult despre:")]
    assert len(dynamic) == 2


@pytest.mark.asyncio
async def test_r11c_suggested_questions_fault_tolerant_on_insight_failure() -> None:
    """R11c: if InsightReadService raises, fall back to 5 static questions
    (never returns < 5 — UI-SPEC fault-tolerance contract)."""
    from app.api.v1.chat import get_suggested_questions

    insight_svc = MagicMock()
    insight_svc.get_today = AsyncMock(side_effect=RuntimeError("db down"))

    with patch("app.api.v1.chat.InsightReadService", return_value=insight_svc):
        result = await get_suggested_questions(
            context="homepage",
            session=AsyncMock(),
            current_user=_make_user(),
        )

    assert result["count"] >= 5
    assert len(result["questions"]) >= 5


# ── R12 — SSE endpoint headers (LM-5) ────────────────────────────────────────


@pytest.mark.asyncio
async def test_r12_sse_endpoint_sets_text_event_stream_and_x_accel_buffering() -> None:
    """R12: POST /conversations/{id}/messages returns a StreamingResponse with
    media_type='text/event-stream' AND X-Accel-Buffering: no header (LM-5 — prevents
    Caddy/nginx from buffering and breaking token-by-token UX).

    CR-01 (Plan 08-07): repo patched with a valid (owned) row so the new
    ownership pre-check passes and flow reaches StreamingResponse construction.
    """
    from fastapi.responses import StreamingResponse

    from app.api.v1.chat import send_message

    ctx, r = _make_redis_mock(incr_return=1, set_nx_return=True)

    # Orchestrator yields a single (event_name, payload) tuple then exits.
    async def fake_run_turn(**kwargs):
        yield ("conversation_meta", {"conversation_id": str(uuid4())})
        yield ("done", {"message_id": str(uuid4())})

    fake_orch = MagicMock()
    fake_orch.run_turn = fake_run_turn

    body = MagicMock()
    body.content = "Test"

    mock_request = MagicMock()
    mock_request.is_disconnected = AsyncMock(return_value=False)

    # CR-01 pre-check passes — caller owns the conversation.
    conv_repo = AsyncMock()
    conv_repo.get_by_id = AsyncMock(return_value=MagicMock(id=uuid4()))

    with patch("app.api.v1.chat.ConversationRepository", return_value=conv_repo):
        with patch("app.api.v1.chat.redis_client", return_value=ctx):
            with patch("app.api.v1.chat.ChatOrchestrator", return_value=fake_orch):
                response = await send_message(
                    conversation_id=uuid4(),
                    request=mock_request,
                    body=body,
                    session=AsyncMock(),
                    current_user=_make_user(),
                )

    assert isinstance(response, StreamingResponse)
    assert response.media_type == "text/event-stream"
    assert response.headers.get("x-accel-buffering") == "no"  # LM-5 mitigation
    assert response.headers.get("cache-control") == "no-cache"


# ── R13/R14 — CR-02: the 409 must be free, the 429 must not leave a lock ─────
#
# These two assert an ORDER, which is the whole of CR-02 and the one thing the
# existing R5/R6 cannot see: both of those pass under either ordering, because
# each only checks the status code it provoked.


@pytest.mark.asyncio
async def test_r13_cr02_stream_lock_conflict_does_not_burn_rate_limit() -> None:
    """R13: a 409 costs nothing from the hourly budget.

    A contended lock means the user's previous message is still streaming —
    the ordinary result of a double-tap or a reconnect, not abuse. Under the
    old order the counter was INCR'd first and never decremented, so ~30
    accidental retries locked a user out of their own chat for an hour.
    """
    from fastapi import HTTPException

    from app.api.v1.chat import send_message

    ctx, r = _make_redis_mock(set_nx_return=False)

    body = MagicMock()
    body.content = "Test"
    mock_request = MagicMock()
    mock_request.is_disconnected = AsyncMock(return_value=False)

    conv_repo = AsyncMock()
    conv_repo.get_by_id = AsyncMock(return_value=MagicMock(id=uuid4()))

    with patch("app.api.v1.chat.ConversationRepository", return_value=conv_repo):
        with patch("app.api.v1.chat.redis_client", return_value=ctx):
            with pytest.raises(HTTPException) as exc_info:
                await send_message(
                    conversation_id=uuid4(),
                    request=mock_request,
                    body=body,
                    session=AsyncMock(),
                    current_user=_make_user(),
                )

    assert exc_info.value.status_code == 409
    r.incr.assert_not_called()
    r.expire.assert_not_called()


@pytest.mark.asyncio
async def test_r14_cr02_rate_limited_request_releases_the_stream_lock() -> None:
    """R14: taking the lock first means a 429 must give it back.

    The lock is normally released in the SSE generator's `finally`, but a 429
    is raised before that generator exists. Without an explicit delete the
    conversation would stay locked for STREAM_LOCK_TTL on top of the 429 —
    trading CR-02's bug for a worse one.
    """
    from fastapi import HTTPException

    from app.api.v1.chat import send_message

    conversation_id = uuid4()
    ctx, r = _make_redis_mock(incr_return=31, ttl_return=900)

    body = MagicMock()
    body.content = "Test"
    mock_request = MagicMock()
    mock_request.is_disconnected = AsyncMock(return_value=False)

    conv_repo = AsyncMock()
    conv_repo.get_by_id = AsyncMock(return_value=MagicMock(id=conversation_id))

    with patch("app.api.v1.chat.ConversationRepository", return_value=conv_repo):
        with patch("app.api.v1.chat.redis_client", return_value=ctx):
            with pytest.raises(HTTPException) as exc_info:
                await send_message(
                    conversation_id=conversation_id,
                    request=mock_request,
                    body=body,
                    session=AsyncMock(),
                    current_user=_make_user(),
                )

    assert exc_info.value.status_code == 429
    r.delete.assert_awaited_once_with(f"chat:stream:{conversation_id}")
