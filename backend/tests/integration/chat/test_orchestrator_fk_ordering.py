from __future__ import annotations

"""Real-DB regression test for the chat_tool_calls.message_id FK ordering bug.

Bug (caught in production logs on 2026-05-29, fixed in plan 08-07 hotfix):
    The orchestrator generated `assistant_msg_id = uuid4()`, then ran Claude's
    tool-use loop, inserting `chat_tool_calls(message_id=assistant_msg_id, ...)`
    rows BEFORE the matching `chat_messages` row was inserted. Each
    `tool_repo.insert_tool_call()` call flushes immediately, hitting
    `ForeignKeyViolationError`, which poisoned the SQLAlchemy session
    (PendingRollbackError) and made the eventual `insert_assistant_message`
    fail too. User saw the generic "A apărut o problemă." SSE error event.

Why unit tests with mocks missed it:
    All orchestrator unit tests mock `MessageRepository` and `ToolCallRepository`
    with MagicMock+AsyncMock. The constructor / call-order contract is verified
    but the actual DB-level FK constraint is bypassed entirely. This is the
    SECOND ordering bug in the chat orchestrator that mocked unit tests missed
    (first was the CR-01 user_id signature mismatch caught by the
    `chat.unhandled` TypeError in production).

Fix (Option A — stub + finalize):
    `MessageRepository.insert_assistant_message(content="", ...)` is called
    BEFORE the tool loop. `MessageRepository.finalize_assistant_message(...)`
    UPDATEs the row with real content/tokens/duration after the loop.

This test asserts the FK ordering contract DIRECTLY against the real DB
(no orchestrator mocking, no Claude mocking) — exercising the exact sequence
the orchestrator now follows. If the bug regresses, this test fails fast with
a ForeignKeyViolationError or PendingRollbackError.

Skips cleanly when TEST_DATABASE_URL is not set (developer machines that don't
have a live PostgreSQL); runs on CI and when developers run `docker compose
up -d` + export TEST_DATABASE_URL.
"""

import os
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "")
_integration_skip = pytest.mark.skipif(
    not _TEST_DB_URL,
    reason="integration test — requires TEST_DATABASE_URL (run: docker compose up -d && export TEST_DATABASE_URL=postgresql+asyncpg://...)",
)

# Sofa Belle seed identifiers — must match conftest + Alembic data migration.
SOFA_BELLE_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
SOFA_BELLE_USER_ID = UUID("00000000-0000-0000-0000-000000000002")  # admin@sofabelle.ro per migration seed


@pytest.fixture
async def real_session():
    if not _TEST_DB_URL:
        pytest.skip("TEST_DATABASE_URL not set")
    # Tenant ContextVar must be set or the global with_loader_criteria event
    # listener (app.db.session._add_tenant_filter) raises TenantIsolationError
    # on every SELECT. In production this is set by app.core.dependencies on
    # every HTTP request; in tests we set it manually for the duration.
    from app.core.tenancy import set_tenant_id  # noqa: PLC0415

    set_tenant_id(SOFA_BELLE_TENANT_ID)
    engine = create_async_engine(_TEST_DB_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def seeded_conversation_id(real_session) -> UUID:
    """Insert a fresh conversation row owned by SOFA_BELLE_USER_ID; clean up after."""
    from app.models.chat import ChatConversation  # noqa: PLC0415

    conv_id = uuid4()
    conv = ChatConversation(
        id=conv_id,
        tenant_id=SOFA_BELLE_TENANT_ID,
        user_id=SOFA_BELLE_USER_ID,
        title="FK ordering regression test",
        archived=False,
        last_message_at=datetime.now(timezone.utc),
    )
    real_session.add(conv)
    await real_session.commit()
    yield conv_id
    # Cleanup: cascade-delete via tool_calls → messages → conversation.
    await real_session.execute(
        text("DELETE FROM chat_tool_calls WHERE message_id IN (SELECT id FROM chat_messages WHERE conversation_id = :c)"),
        {"c": str(conv_id)},
    )
    await real_session.execute(
        text("DELETE FROM chat_messages WHERE conversation_id = :c"),
        {"c": str(conv_id)},
    )
    await real_session.execute(
        text("DELETE FROM chat_conversations WHERE id = :c"),
        {"c": str(conv_id)},
    )
    await real_session.commit()


@_integration_skip
@pytest.mark.asyncio
async def test_assistant_stub_then_tool_call_then_finalize_no_fk_violation(
    real_session, seeded_conversation_id: UUID
) -> None:
    """The exact sequence the orchestrator now follows must not violate the
    chat_tool_calls.message_id FK and must not poison the session."""
    from app.services.chat.repositories import (  # noqa: PLC0415
        MessageRepository,
        ToolCallRepository,
    )

    msg_repo = MessageRepository(real_session, SOFA_BELLE_TENANT_ID)
    tool_repo = ToolCallRepository(real_session, SOFA_BELLE_TENANT_ID)
    conv_id = seeded_conversation_id

    # ── Phase 1: insert user message (matches orchestrator section 1) ────────
    user_msg_id = await msg_repo.insert_user_message(conv_id, "Cum stăm cu vânzările?")
    assert isinstance(user_msg_id, UUID)

    # ── Phase 2: pre-allocate assistant_msg_id + insert STUB upfront ─────────
    # This is the Option A fix — without it, Phase 3 below raises FK violation.
    assistant_msg_id = uuid4()
    returned_id = await msg_repo.insert_assistant_message(
        conv_id,
        content="",
        tokens_used=None,
        duration_ms=None,
        hallucination_flag=False,
        regenerate_count=0,
        message_id=assistant_msg_id,
    )
    assert returned_id == assistant_msg_id

    # ── Phase 3: insert tool_call referencing the stub (FK target now exists) ─
    # Pre-fix, this raised:
    #   ForeignKeyViolationError: chat_tool_calls.message_id not in chat_messages
    # If the regression returns, this await raises immediately.
    await tool_repo.insert_tool_call(
        message_id=assistant_msg_id,
        tool_name="get_kpi",
        input_args={"date_from": "2026-05-01", "date_to": "2026-05-29"},
        output_data={"leads": 47, "contracts": 4},
        duration_ms=92,
        error=None,
    )

    # ── Phase 4: finalize the assistant message with real content ────────────
    await msg_repo.finalize_assistant_message(
        assistant_msg_id,
        content="Luna asta aveți 47 lead-uri noi și 4 contracte semnate.",
        tokens_used=210,
        duration_ms=4321,
        hallucination_flag=False,
        regenerate_count=0,
    )

    await real_session.commit()

    # ── Assertions: all rows landed, FK satisfied, content finalized ─────────
    result = await real_session.execute(
        text("SELECT content, tokens_used FROM chat_messages WHERE id = :id"),
        {"id": str(assistant_msg_id)},
    )
    row = result.first()
    assert row is not None, "assistant message row missing after finalize"
    assert "47 lead-uri" in row[0], "finalize_assistant_message did not UPDATE content"
    assert row[1] == 210, "finalize_assistant_message did not UPDATE tokens_used"

    result = await real_session.execute(
        text("SELECT tool_name FROM chat_tool_calls WHERE message_id = :id"),
        {"id": str(assistant_msg_id)},
    )
    tool_rows = result.all()
    assert len(tool_rows) == 1, f"expected 1 tool_call row, got {len(tool_rows)}"
    assert tool_rows[0][0] == "get_kpi"


@_integration_skip
@pytest.mark.asyncio
async def test_finalize_without_stub_is_noop(real_session, seeded_conversation_id: UUID) -> None:
    """Defensive: calling finalize on a non-existent message_id must be a no-op,
    not raise. (UPDATE with no matching row affects zero rows in PostgreSQL.)
    """
    from app.services.chat.repositories import MessageRepository  # noqa: PLC0415

    msg_repo = MessageRepository(real_session, SOFA_BELLE_TENANT_ID)
    nonexistent_id = uuid4()
    # Should not raise; just affects 0 rows.
    await msg_repo.finalize_assistant_message(
        nonexistent_id,
        content="nope",
        tokens_used=0,
        duration_ms=0,
        hallucination_flag=False,
        regenerate_count=0,
    )
    await real_session.commit()
    result = await real_session.execute(
        text("SELECT 1 FROM chat_messages WHERE id = :id"),
        {"id": str(nonexistent_id)},
    )
    assert result.first() is None
