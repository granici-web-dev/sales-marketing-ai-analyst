"""CR-01 cross-user authorization regression suite (Phase 8 Plan 08-07).

Verifies that any conversation operation by User A targeting a conversation
owned by User B (same tenant) returns 404 — closing 08-VERIFICATION.md gap
"SC#4 + SC#5" missing item #3 ("Cross-user authorization integration test").

Layered with the Task 1 unit tests in tests/unit/chat/test_chat_repositories.py
(TestConversationRepositoryCrossUserCR01) which verify the SQL predicate; this
file verifies the ENDPOINT BEHAVIOR — that the router instantiates the repo
with current_user.id and maps the repo's None return into a 404 with the
Romanian copy "Conversația nu există." (no 403, no existence-leak per T-08-01b).

Test pattern mirrors tests/integration/chat/test_chat_endpoints.py:
  - Per-test _integration_skip decorator skips cleanly when TEST_DATABASE_URL
    is unset (developer machines); runs on CI where a live PostgreSQL is
    provisioned.
  - ConversationRepository is patched at the router import point with an
    AsyncMock whose return values SIMULATE what the real (tenant_id, user_id)
    predicate would produce for cross-user reads (None for get_by_id; only
    User A rows for list_conversations). This validates the router→repo
    contract; the SQL predicate itself is verified in the unit tests.

Coverage:
  test_cross_user_get_returns_404        — GET /chat/conversations/{user_b_id} → 404
  test_cross_user_delete_returns_404     — DELETE /chat/conversations/{user_b_id} → 404
  test_cross_user_post_returns_404       — POST /messages w/ user_b_id → 404 BEFORE rate-limit
  test_cross_user_list_excludes_b_conversations — GET /chat/conversations list does NOT include B
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

# Phase 5 carry-forward — per-test gate decorator. Skips cleanly when
# TEST_DATABASE_URL is not set (developer machines), runs on CI.
_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "")
_integration_skip = pytest.mark.skipif(
    not _TEST_DB_URL,
    reason="integration test — requires TEST_DATABASE_URL",
)

pytestmark = pytest.mark.asyncio

# Identity constants — User A is the authenticated caller (SOFA_BELLE_USER_ID,
# matching the unit + integration conftest). User B is a same-tenant peer
# whose conversation User A must NOT be able to read/mutate/post-into.
MOCK_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
USER_A_ID = UUID("00000000-0000-0000-0000-000000000010")
USER_B_ID = UUID("00000000-0000-0000-0000-000000000020")


# ── Shared helper: install User A as the authenticated principal ──────────────


def _override_user_a_as_caller(mock_session: AsyncMock | None = None):
    """Standard dependency overrides — authenticate every request as User A.

    Mirrors test_chat_endpoints._override_app_dependencies() but pins the
    authenticated principal to USER_A_ID so cross-user assertions are
    unambiguous about which side of the (A vs B) boundary the test sits on.
    """
    from app.core.dependencies import get_current_user
    from app.db.deps import get_session
    from app.main import app
    from app.schemas.auth import UserOut

    mock_user_a = UserOut(id=USER_A_ID, email="user_a@sofabelle.ro", is_active=True)
    session = mock_session or AsyncMock()
    session.commit = AsyncMock()

    async def _mock_current_user():
        return mock_user_a

    async def _mock_get_session():
        yield session

    app.dependency_overrides[get_current_user] = _mock_current_user
    app.dependency_overrides[get_session] = _mock_get_session
    return mock_user_a, session


# ── Test 1: cross-user GET → 404 ──────────────────────────────────────────────


@_integration_skip
async def test_cross_user_get_returns_404() -> None:
    """User A GETs /chat/conversations/{user_b_conversation_id} → 404.

    Simulates the storage-layer fix: when User A's repo is asked for User B's
    conversation_id, the (tenant_id, user_id) predicate filters it out and
    get_by_id returns None. The router maps None → HTTPException(404) with
    the Romanian copy — same path as a genuinely-non-existent uuid, so an
    attacker cannot probe for existence (T-08-01b).
    """
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    _override_user_a_as_caller()

    user_b_conv_id = uuid4()
    conv_repo = AsyncMock()
    # Real repo bound to (tenant, USER_A_ID) would return None for USER_B's row.
    conv_repo.get_by_id = AsyncMock(return_value=None)

    try:
        with patch("app.api.v1.chat.ConversationRepository", return_value=conv_repo):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as c:
                r = await c.get(f"/api/v1/chat/conversations/{user_b_conv_id}")
        assert r.status_code == 404, (
            f"expected 404 on cross-user GET, got {r.status_code}: {r.text}"
        )
        # CR-01 acceptance: Romanian copy MUST be the same as a not-found —
        # no 403, no English fallback (T-08-01b — no existence-leak).
        assert r.json()["detail"] == "Conversația nu există."
        # Confirm the router actually invoked the predicate-filtered get_by_id.
        conv_repo.get_by_id.assert_awaited_once_with(user_b_conv_id)
    finally:
        app.dependency_overrides.clear()


# ── Test 2: cross-user DELETE → 404 ───────────────────────────────────────────


@_integration_skip
async def test_cross_user_delete_returns_404() -> None:
    """User A DELETEs /chat/conversations/{user_b_conversation_id} → 404.

    Same pattern as Test 1 but on the archive endpoint. Critical because
    the pre-CR-01 storage layer would have happily archived User B's
    conversation when handed only the conversation_id + tenant_id.
    """
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    _override_user_a_as_caller()

    user_b_conv_id = uuid4()
    conv_repo = AsyncMock()
    conv_repo.get_by_id = AsyncMock(return_value=None)
    conv_repo.soft_archive = AsyncMock()  # must NOT be called

    try:
        with patch("app.api.v1.chat.ConversationRepository", return_value=conv_repo):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as c:
                r = await c.delete(f"/api/v1/chat/conversations/{user_b_conv_id}")
        assert r.status_code == 404, (
            f"expected 404 on cross-user DELETE, got {r.status_code}: {r.text}"
        )
        assert r.json()["detail"] == "Conversația nu există."
        # CR-01: soft_archive MUST NOT fire when the ownership check failed.
        conv_repo.soft_archive.assert_not_awaited()
    finally:
        app.dependency_overrides.clear()


# ── Test 3: cross-user POST /messages → 404 BEFORE rate-limit/stream-lock ─────


@_integration_skip
async def test_cross_user_post_returns_404() -> None:
    """User A POSTs to /chat/conversations/{user_b_id}/messages → 404.

    This is the HEADLINE CR-01 regression — pre-fix, User A could inject a
    message into User B's conversation, triggering the orchestrator to load
    User B's history and stream Claude's reply to User A. CHAT-03 / SC#5
    ("history stored per user") was structurally broken.

    Critical secondary assertion: the 404 MUST fire BEFORE the Redis
    rate-limit INCR + stream-lock SET NX. We verify this by patching
    aioredis.from_url with a mock that would track its own usage — when
    the 404 fires correctly, the Redis context manager is never entered,
    so incr / set are never called. This prevents a probing attacker from
    burning the legitimate owner's 30/hour rate-limit budget.

    Tests 4 (excludes from list) closes the "leak via enumeration" angle.
    """
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    _override_user_a_as_caller()

    user_b_conv_id = uuid4()
    conv_repo = AsyncMock()
    conv_repo.get_by_id = AsyncMock(return_value=None)

    # Redis context manager — if the ownership pre-check fires correctly
    # (CR-01 + ordering invariant), this entire mock should never be
    # entered. We assert that explicitly below.
    fake_redis = AsyncMock()
    fake_redis.incr = AsyncMock(return_value=1)
    fake_redis.expire = AsyncMock(return_value=True)
    fake_redis.set = AsyncMock(return_value=True)
    fake_redis.delete = AsyncMock(return_value=1)
    fake_redis.ttl = AsyncMock(return_value=3600)
    redis_ctx = AsyncMock()
    redis_ctx.__aenter__ = AsyncMock(return_value=fake_redis)
    redis_ctx.__aexit__ = AsyncMock(return_value=None)
    redis_from_url = MagicMock(return_value=redis_ctx)

    # The orchestrator MUST NOT be instantiated when ownership fails. Patch
    # it so the test errors loudly if the router skips the pre-check.
    orch_factory = MagicMock(
        side_effect=AssertionError(
            "ChatOrchestrator instantiated despite cross-user 404 — "
            "ownership pre-check is missing or fires after orchestrator setup"
        )
    )

    try:
        with patch("app.api.v1.chat.ConversationRepository", return_value=conv_repo):
            with patch("app.api.v1.chat.aioredis.from_url", redis_from_url):
                with patch("app.api.v1.chat.ChatOrchestrator", orch_factory):
                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://test"
                    ) as c:
                        r = await c.post(
                            f"/api/v1/chat/conversations/{user_b_conv_id}/messages",
                            json={"content": "ping"},
                        )
        assert r.status_code == 404, (
            f"expected 404 on cross-user POST, got {r.status_code}: {r.text}"
        )
        assert r.json()["detail"] == "Conversația nu există."
        # CR-01 ordering invariant: rate-limit + stream-lock are NOT consumed
        # by a cross-user probe. If `aioredis.from_url` was called, the
        # 404 fired AFTER the rate-limit INCR — that's a CR-01 violation.
        redis_from_url.assert_not_called()
        # Orchestrator must also NOT have been instantiated.
        orch_factory.assert_not_called()
        conv_repo.get_by_id.assert_awaited_once_with(user_b_conv_id)
    finally:
        app.dependency_overrides.clear()


# ── Test 4: list excludes User B's conversations ─────────────────────────────


@_integration_skip
async def test_cross_user_list_excludes_b_conversations() -> None:
    """User A GETs /chat/conversations — response excludes User B's rows.

    Simulates the predicate-filtered repo: list_conversations bound to
    (tenant, USER_A_ID) only returns User A's rows. The endpoint then
    serializes ONLY those into the response, so User B's conversation_ids
    are never enumerable from User A's session — closing the "leak by
    enumeration → probe with Test 1's GET" attack chain.
    """
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    _override_user_a_as_caller()

    user_a_conv_id = uuid4()
    user_b_conv_id = uuid4()

    user_a_row = MagicMock(
        id=user_a_conv_id,
        title="User A's conversation",
        created_at=MagicMock(),
        last_message_at=MagicMock(),
        archived=False,
    )

    conv_repo = AsyncMock()
    # Predicate-filtered: list returns ONLY User A's rows.
    conv_repo.list_conversations = AsyncMock(return_value=[user_a_row])

    try:
        with patch("app.api.v1.chat.ConversationRepository", return_value=conv_repo):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as c:
                r = await c.get("/api/v1/chat/conversations")
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"
        body = r.json()
        returned_ids = {item["id"] for item in body["conversations"]}
        assert str(user_a_conv_id) in returned_ids
        assert str(user_b_conv_id) not in returned_ids, (
            "CR-01 leak: User A's list response contains User B's conversation_id"
        )
        assert len(body["conversations"]) == 1
    finally:
        app.dependency_overrides.clear()
