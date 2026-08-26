"""Unit tests for Phase 8 AI Chat repositories + SSE event schemas (Plan 08-04 Task 1).

Coverage (per 08-04-PLAN.md <behavior>):
  - Test 1: 7 SSE event schemas exist with documented fields per D-09
  - Test 2: ConversationOut / MessageOut shape (D-15 / D-09)
  - Test 3: ConversationRepository.insert raises ValueError on cross-tenant write (T-08-01)
  - Test 4: ConversationRepository.list_conversations SQL filters tenant + archived
  - Test 5: MessageRepository.load_history honors D-16 anchor-and-recent
  - Test 6: MessageRepository.insert_user/assistant_message returns UUID + updates last_message_at
  - Test 7: ToolCallRepository.insert_tool_call audits per D-21
  - Test 8: ConversationRepository.soft_archive sets archived=true (D-15)

References:
  - .planning/phases/08-ai-chat/08-CONTEXT.md (D-09, D-15, D-16, D-21, D-22)
  - .planning/phases/08-ai-chat/08-PATTERNS.md § sse_events.py lines 311-349
  - backend/app/services/repositories/insight_repository.py (cross-tenant guard pattern)
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Test 1 — 7 SSE event Pydantic schemas (D-09)
# ─────────────────────────────────────────────────────────────────────────────


class TestSseEventSchemas:
    def test_seven_event_schemas_importable(self) -> None:
        """All 7 SSE event schemas per D-09 are importable from app.schemas.chat.sse_events."""
        from app.schemas.chat.sse_events import (
            AssistantChunkEvent,
            ConversationMetaEvent,
            DoneEvent,
            ErrorEvent,
            RegenerateNoticeEvent,
            ToolResultEvent,
            ToolUseEvent,
        )

        # All 7 names defined
        assert ConversationMetaEvent is not None
        assert ToolUseEvent is not None
        assert ToolResultEvent is not None
        assert AssistantChunkEvent is not None
        assert RegenerateNoticeEvent is not None
        assert DoneEvent is not None
        assert ErrorEvent is not None

    def test_conversation_meta_event_fields(self) -> None:
        from app.schemas.chat.sse_events import ConversationMetaEvent

        ev = ConversationMetaEvent(
            conversation_id=uuid4(),
            message_id_user=uuid4(),
            message_id_assistant=uuid4(),
        )
        d = ev.model_dump()
        assert "conversation_id" in d
        assert "message_id_user" in d
        assert "message_id_assistant" in d

    def test_tool_use_event_fields(self) -> None:
        from app.schemas.chat.sse_events import ToolUseEvent

        ev = ToolUseEvent(
            tool_use_id="toolu_001", name="get_kpi", input={"date_from": "2026-05-01"}
        )
        assert ev.tool_use_id == "toolu_001"
        assert ev.name == "get_kpi"
        assert ev.input == {"date_from": "2026-05-01"}

    def test_tool_result_event_fields(self) -> None:
        from app.schemas.chat.sse_events import ToolResultEvent

        ev = ToolResultEvent(
            tool_use_id="toolu_001",
            output_preview='{"leads_total": 47}',
            duration_ms=120,
            error=False,
        )
        assert ev.tool_use_id == "toolu_001"
        assert ev.duration_ms == 120

    def test_assistant_chunk_event_fields(self) -> None:
        from app.schemas.chat.sse_events import AssistantChunkEvent

        ev = AssistantChunkEvent(text="Vânzările")
        assert ev.text == "Vânzările"

    def test_regenerate_notice_event_fields(self) -> None:
        from app.schemas.chat.sse_events import RegenerateNoticeEvent

        ev = RegenerateNoticeEvent(reason="hallucination_guard")
        assert ev.reason == "hallucination_guard"

    def test_done_event_fields(self) -> None:
        from app.schemas.chat.sse_events import DoneEvent

        ev = DoneEvent(
            message_id=uuid4(),
            total_input_tokens=1200,
            total_output_tokens=80,
            duration_ms=3400,
            hallucination_flag=False,
        )
        assert ev.total_input_tokens == 1200
        assert ev.hallucination_flag is False

    def test_error_event_fields(self) -> None:
        from app.schemas.chat.sse_events import ErrorEvent

        ev = ErrorEvent(code="internal", message_ro="A apărut o problemă.")
        assert ev.code == "internal"
        assert ev.message_ro == "A apărut o problemă."


# ─────────────────────────────────────────────────────────────────────────────
# Test 2 — ConversationOut + MessageOut DTO shape
# ─────────────────────────────────────────────────────────────────────────────


class TestRequestResponseSchemas:
    def test_conversation_out_fields(self) -> None:
        from app.schemas.chat.conversation import ConversationOut

        out = ConversationOut(
            id=uuid4(),
            title="Vânzări mai 2026",
            created_at=datetime.now(UTC),
            last_message_at=datetime.now(UTC),
            archived=False,
        )
        d = out.model_dump()
        assert set(d.keys()) >= {
            "id",
            "title",
            "created_at",
            "last_message_at",
            "archived",
        }

    def test_message_out_role_is_literal_user_or_assistant(self) -> None:
        from pydantic import ValidationError

        from app.schemas.chat.message import MessageOut

        ok = MessageOut(
            role="assistant",
            content="Răspuns",
            created_at=datetime.now(UTC),
            tokens_used=80,
            hallucination_flag=False,
            regenerate_count=0,
        )
        assert ok.role == "assistant"

        # tool_use / tool_result must be rejected — those are internal
        with pytest.raises(ValidationError):
            MessageOut(
                role="tool_use",  # type: ignore[arg-type]
                content="",
                created_at=datetime.now(UTC),
                tokens_used=None,
                hallucination_flag=False,
                regenerate_count=0,
            )


# ─────────────────────────────────────────────────────────────────────────────
# Tests 3, 4, 8 — ConversationRepository
# ─────────────────────────────────────────────────────────────────────────────


TENANT_A = UUID("00000000-0000-0000-0000-000000000001")
TENANT_B = UUID("00000000-0000-0000-0000-00000000000b")
USER_ID = UUID("00000000-0000-0000-0000-000000000010")
# CR-01 (Plan 08-07): same-tenant different-user fixture for cross-user isolation tests.
SOFA_BELLE_USER_ID = USER_ID
OTHER_USER_ID = UUID("00000000-0000-0000-0000-000000000099")


class TestConversationRepository:
    @pytest.mark.asyncio
    async def test_insert_blocks_cross_tenant_write(self) -> None:
        """Test 3: cross-tenant row rejected (Phase 5 WR-04 pattern)."""
        from app.services.chat.repositories.conversation_repository import (
            ConversationRepository,
        )

        session = AsyncMock()
        repo = ConversationRepository(session, TENANT_A, USER_ID)

        bad_row = {
            "id": uuid4(),
            "tenant_id": TENANT_B,  # mismatch
            "user_id": USER_ID,
            "title": None,
            "last_message_at": datetime.now(UTC),
            "archived": False,
        }
        with pytest.raises(ValueError, match="cross-tenant write blocked"):
            await repo.insert_conversation(bad_row)

    @pytest.mark.asyncio
    async def test_insert_blocks_missing_tenant_id(self) -> None:
        from app.services.chat.repositories.conversation_repository import (
            ConversationRepository,
        )

        session = AsyncMock()
        repo = ConversationRepository(session, TENANT_A, USER_ID)

        with pytest.raises(ValueError, match="tenant_id"):
            await repo.insert_conversation(
                {
                    "id": uuid4(),
                    "user_id": USER_ID,
                    "title": None,
                    "last_message_at": datetime.now(UTC),
                    "archived": False,
                }
            )

    @pytest.mark.asyncio
    async def test_list_conversations_filters_tenant_and_archived(self) -> None:
        """Test 4: list_conversations builds a SELECT scoped by tenant + user + archived."""
        from app.services.chat.repositories.conversation_repository import (
            ConversationRepository,
        )

        session = AsyncMock()
        # session.execute returns Result-like mock whose .scalars().all() yields []
        result = MagicMock()
        scalars = MagicMock()
        scalars.all = MagicMock(return_value=[])
        result.scalars = MagicMock(return_value=scalars)
        session.execute = AsyncMock(return_value=result)

        repo = ConversationRepository(session, TENANT_A, USER_ID)
        rows = await repo.list_conversations(archived=False, limit=50)
        assert rows == []
        # Verify the SQL statement was constructed (execute was called)
        session.execute.assert_called_once()
        stmt = session.execute.call_args[0][0]
        sql_text = str(stmt.compile(compile_kwargs={"literal_binds": False}))
        # Must filter by tenant_id, user_id, and archived
        assert "tenant_id" in sql_text.lower()
        assert "user_id" in sql_text.lower()
        assert "archived" in sql_text.lower()
        # ORDER BY last_message_at DESC
        assert "last_message_at desc" in sql_text.lower()

    @pytest.mark.asyncio
    async def test_soft_archive_sets_archived_true(self) -> None:
        """Test 8: soft_archive (D-15) — UPDATE archived=True (no hard delete)."""
        from app.services.chat.repositories.conversation_repository import (
            ConversationRepository,
        )

        session = AsyncMock()
        session.execute = AsyncMock()
        repo = ConversationRepository(session, TENANT_A, USER_ID)

        await repo.soft_archive(uuid4())
        session.execute.assert_called_once()
        stmt = session.execute.call_args[0][0]
        sql_text = str(stmt.compile(compile_kwargs={"literal_binds": False}))
        assert "update" in sql_text.lower()
        assert "archived" in sql_text.lower()
        assert "tenant_id" in sql_text.lower()
        assert "user_id" in sql_text.lower()


# ─────────────────────────────────────────────────────────────────────────────
# CR-01 (Plan 08-07) — Cross-user-within-tenant authorization predicate
#
# Per 08-VERIFICATION.md gap "SC#4 + SC#5", the repository must apply
# `WHERE user_id = self._user_id` to every SELECT and UPDATE so a user in the
# same tenant cannot read or mutate another user's conversation rows.
#
# These tests verify the predicate is present in the emitted SQL for each of
# the 5 public read/update methods AND that insert_conversation raises when
# row.user_id ≠ repo.user_id.
# ─────────────────────────────────────────────────────────────────────────────


class TestConversationRepositoryCrossUserCR01:
    """CR-01 (Plan 08-07): per-user authorization predicate on every method."""

    @pytest.mark.asyncio
    async def test_insert_blocks_cross_user_write(self) -> None:
        """insert_conversation rejects a row whose user_id ≠ repo.user_id."""
        from app.services.chat.repositories.conversation_repository import (
            ConversationRepository,
        )

        session = AsyncMock()
        repo = ConversationRepository(session, TENANT_A, SOFA_BELLE_USER_ID)

        bad_row = {
            "id": uuid4(),
            "tenant_id": TENANT_A,
            "user_id": OTHER_USER_ID,  # mismatch — User B writing through User A's repo
            "title": None,
            "last_message_at": datetime.now(UTC),
            "archived": False,
        }
        with pytest.raises(ValueError, match="cross-user write blocked"):
            await repo.insert_conversation(bad_row)

    @pytest.mark.asyncio
    async def test_get_by_id_emits_user_id_predicate(self) -> None:
        """get_by_id SELECT must include `user_id == self._user_id`."""
        from app.services.chat.repositories.conversation_repository import (
            ConversationRepository,
        )

        session = AsyncMock()
        result = MagicMock()
        scalars = MagicMock()
        scalars.first = MagicMock(return_value=None)
        result.scalars = MagicMock(return_value=scalars)
        session.execute = AsyncMock(return_value=result)

        repo = ConversationRepository(session, TENANT_A, SOFA_BELLE_USER_ID)
        await repo.get_by_id(uuid4())
        stmt = session.execute.call_args[0][0]
        sql_text = str(stmt.compile(compile_kwargs={"literal_binds": False}))
        assert "tenant_id" in sql_text.lower()
        assert "user_id" in sql_text.lower()

    @pytest.mark.asyncio
    async def test_list_conversations_emits_user_id_predicate(self) -> None:
        """list_conversations SELECT must include `user_id == self._user_id`."""
        from app.services.chat.repositories.conversation_repository import (
            ConversationRepository,
        )

        session = AsyncMock()
        result = MagicMock()
        scalars = MagicMock()
        scalars.all = MagicMock(return_value=[])
        result.scalars = MagicMock(return_value=scalars)
        session.execute = AsyncMock(return_value=result)

        repo = ConversationRepository(session, TENANT_A, SOFA_BELLE_USER_ID)
        await repo.list_conversations()
        stmt = session.execute.call_args[0][0]
        sql_text = str(stmt.compile(compile_kwargs={"literal_binds": False}))
        assert "tenant_id" in sql_text.lower()
        assert "user_id" in sql_text.lower()

    @pytest.mark.asyncio
    async def test_update_title_emits_user_id_predicate(self) -> None:
        """update_title UPDATE must include `user_id == self._user_id`."""
        from app.services.chat.repositories.conversation_repository import (
            ConversationRepository,
        )

        session = AsyncMock()
        session.execute = AsyncMock()
        repo = ConversationRepository(session, TENANT_A, SOFA_BELLE_USER_ID)

        await repo.update_title(uuid4(), "Titlu nou")
        stmt = session.execute.call_args[0][0]
        sql_text = str(stmt.compile(compile_kwargs={"literal_binds": False}))
        assert "update" in sql_text.lower()
        assert "tenant_id" in sql_text.lower()
        assert "user_id" in sql_text.lower()

    @pytest.mark.asyncio
    async def test_update_last_message_at_emits_user_id_predicate(self) -> None:
        """update_last_message_at UPDATE must include `user_id == self._user_id`."""
        from app.services.chat.repositories.conversation_repository import (
            ConversationRepository,
        )

        session = AsyncMock()
        session.execute = AsyncMock()
        repo = ConversationRepository(session, TENANT_A, SOFA_BELLE_USER_ID)

        await repo.update_last_message_at(uuid4())
        stmt = session.execute.call_args[0][0]
        sql_text = str(stmt.compile(compile_kwargs={"literal_binds": False}))
        assert "update" in sql_text.lower()
        assert "tenant_id" in sql_text.lower()
        assert "user_id" in sql_text.lower()
        assert "last_message_at" in sql_text.lower()

    @pytest.mark.asyncio
    async def test_soft_archive_emits_user_id_predicate(self) -> None:
        """soft_archive UPDATE must include `user_id == self._user_id`."""
        from app.services.chat.repositories.conversation_repository import (
            ConversationRepository,
        )

        session = AsyncMock()
        session.execute = AsyncMock()
        repo = ConversationRepository(session, TENANT_A, SOFA_BELLE_USER_ID)

        await repo.soft_archive(uuid4())
        stmt = session.execute.call_args[0][0]
        sql_text = str(stmt.compile(compile_kwargs={"literal_binds": False}))
        assert "update" in sql_text.lower()
        assert "archived" in sql_text.lower()
        assert "tenant_id" in sql_text.lower()
        assert "user_id" in sql_text.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Tests 5, 6 — MessageRepository
# ─────────────────────────────────────────────────────────────────────────────


class TestMessageRepository:
    @pytest.mark.asyncio
    async def test_insert_user_message_returns_uuid_and_updates_last_message_at(self) -> None:
        """Test 6 (user): insert_user_message persists and bumps conversation.last_message_at."""
        from app.services.chat.repositories.message_repository import MessageRepository

        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.execute = AsyncMock()
        repo = MessageRepository(session, TENANT_A)

        conv_id = uuid4()
        new_id = await repo.insert_user_message(conv_id, "Cum stăm?")
        assert isinstance(new_id, UUID)
        session.add.assert_called()
        # last_message_at UPDATE should fire
        assert session.execute.call_count >= 1

    @pytest.mark.asyncio
    async def test_insert_assistant_message_with_pre_allocated_id(self) -> None:
        """Test 6 (assistant): pre-allocated UUID is honored so SSE event ID matches DB row."""
        from app.services.chat.repositories.message_repository import MessageRepository

        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.execute = AsyncMock()
        repo = MessageRepository(session, TENANT_A)

        conv_id = uuid4()
        pre_id = uuid4()
        new_id = await repo.insert_assistant_message(
            conv_id,
            "Răspuns",
            tokens_used=80,
            duration_ms=3400,
            hallucination_flag=False,
            regenerate_count=0,
            message_id=pre_id,
        )
        assert new_id == pre_id

    @pytest.mark.asyncio
    async def test_load_history_anchor_first_user_plus_recent_n_minus_1(self) -> None:
        """Test 5 (D-16): load_history keeps first user msg + most recent 19 messages."""
        from app.services.chat.repositories.message_repository import MessageRepository

        # Build 25 fake rows: 1 first-user msg + 24 follow-ups
        first_user_row = MagicMock(
            role="user",
            content="Prima întrebare",
            created_at=datetime(2026, 5, 1, 9, 0, tzinfo=UTC),
        )
        followups = [
            MagicMock(
                role="assistant" if i % 2 else "user",
                content=f"Mesaj #{i}",
                created_at=datetime(2026, 5, 1, 9, i + 1, tzinfo=UTC),
            )
            for i in range(24)
        ]
        all_rows = [first_user_row] + followups

        session = AsyncMock()
        result = MagicMock()
        scalars = MagicMock()
        scalars.all = MagicMock(return_value=all_rows)
        result.scalars = MagicMock(return_value=scalars)
        session.execute = AsyncMock(return_value=result)
        repo = MessageRepository(session, TENANT_A)

        history = await repo.load_history(uuid4(), limit=20)
        # D-16: first user message anchored + most recent 19
        assert len(history) == 20
        # Last item is the very latest follow-up
        assert history[-1]["content"] == "Mesaj #23"
        # First item is the anchored first user message
        assert history[0]["content"] == "Prima întrebare"
        # Every entry must be {"role": ..., "content": ...} shape for Anthropic
        for entry in history:
            assert set(entry.keys()) == {"role", "content"}
            assert entry["role"] in {"user", "assistant"}

    @pytest.mark.asyncio
    async def test_load_history_under_limit_returns_all(self) -> None:
        """D-16: if total < limit, returns all messages in chronological order."""
        from app.services.chat.repositories.message_repository import MessageRepository

        rows = [
            MagicMock(
                role="user",
                content="A",
                created_at=datetime(2026, 5, 1, 9, 0, tzinfo=UTC),
            ),
            MagicMock(
                role="assistant",
                content="B",
                created_at=datetime(2026, 5, 1, 9, 1, tzinfo=UTC),
            ),
        ]
        session = AsyncMock()
        result = MagicMock()
        scalars = MagicMock()
        scalars.all = MagicMock(return_value=rows)
        result.scalars = MagicMock(return_value=scalars)
        session.execute = AsyncMock(return_value=result)
        repo = MessageRepository(session, TENANT_A)

        history = await repo.load_history(uuid4(), limit=20)
        assert len(history) == 2
        assert history[0]["content"] == "A"
        assert history[1]["content"] == "B"


# ─────────────────────────────────────────────────────────────────────────────
# Test 7 — ToolCallRepository
# ─────────────────────────────────────────────────────────────────────────────


class TestToolCallRepository:
    @pytest.mark.asyncio
    async def test_insert_tool_call_writes_audit_row(self) -> None:
        """Test 7 (D-21): one audit row per tool invocation."""
        from app.services.chat.repositories.tool_call_repository import (
            ToolCallRepository,
        )

        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        repo = ToolCallRepository(session, TENANT_A)

        new_id = await repo.insert_tool_call(
            message_id=uuid4(),
            tool_name="get_kpi",
            input_args={"date_from": "2026-05-01"},
            output_data={"leads_total": 47},
            duration_ms=120,
            error=None,
        )
        assert isinstance(new_id, UUID)
        session.add.assert_called_once()
        added_obj = session.add.call_args[0][0]
        assert added_obj.tool_name == "get_kpi"
        assert added_obj.tenant_id == TENANT_A
        assert added_obj.error is None
