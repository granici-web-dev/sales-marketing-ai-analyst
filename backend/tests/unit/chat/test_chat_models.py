"""Unit tests for Phase 8 AI Chat SQLAlchemy ORM models.

Tests cover D-20 schema contract for the 3 persistence tables:
  - chat_conversations (ChatConversation)
  - chat_messages     (ChatMessage)
  - chat_tool_calls   (ChatToolCall)

No database connection required — pure introspection via SQLAlchemy `inspect()`.

Requirements: CHAT-03 (persistence), CHAT-09 (low-latency tool calls — backed by indexes).

D-20 column contract (from 08-CONTEXT.md + 08-RESEARCH.md §5):
  - All three models inherit `Base, TenantScopedMixin` so they automatically
    receive id/tenant_id/created_at/updated_at + the Phase 1 `with_loader_criteria`
    cross-tenant filter (T-08-01 mitigation).
  - chat_messages adds two D-20 extensions BEYOND SPEC.md:
      - hallucination_flag BOOLEAN DEFAULT false
      - regenerate_count   INTEGER DEFAULT 0
  - chat_tool_calls.message_id FK is ON DELETE CASCADE (audit row dies with parent).
  - chat_messages.conversation_id FK is ON DELETE CASCADE (messages die with conversation).

Wrapped in try/except so test collection succeeds in RED state (before Task 1
implementation lands). Tests fail with descriptive messages when models missing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ── Import stubs ──────────────────────────────────────────────────────────────
# Wrapped per Phase-3 / Phase-5 convention so collection survives the RED state.

try:
    from app.models.chat.chat_conversation import ChatConversation

    _chat_conv_import_error: Exception | None = None
except (ImportError, ModuleNotFoundError) as exc:
    ChatConversation = None  # type: ignore[assignment, misc]
    _chat_conv_import_error = exc

try:
    from app.models.chat.chat_message import ChatMessage

    _chat_msg_import_error: Exception | None = None
except (ImportError, ModuleNotFoundError) as exc:
    ChatMessage = None  # type: ignore[assignment, misc]
    _chat_msg_import_error = exc

try:
    from app.models.chat.chat_tool_call import ChatToolCall

    _chat_tc_import_error: Exception | None = None
except (ImportError, ModuleNotFoundError) as exc:
    ChatToolCall = None  # type: ignore[assignment, misc]
    _chat_tc_import_error = exc


# ── Helpers ───────────────────────────────────────────────────────────────────


def _require_chat_conversation() -> None:
    if ChatConversation is None:
        pytest.fail(
            f"Cannot import ChatConversation: {_chat_conv_import_error}. "
            "Run Plan 08-02 Task 1 (chat models) before these tests."
        )


def _require_chat_message() -> None:
    if ChatMessage is None:
        pytest.fail(
            f"Cannot import ChatMessage: {_chat_msg_import_error}. "
            "Run Plan 08-02 Task 1 (chat models) before these tests."
        )


def _require_chat_tool_call() -> None:
    if ChatToolCall is None:
        pytest.fail(
            f"Cannot import ChatToolCall: {_chat_tc_import_error}. "
            "Run Plan 08-02 Task 1 (chat models) before these tests."
        )


def _column_names(model) -> set[str]:
    """Return the set of column names on a SQLAlchemy model via `inspect()`."""
    from sqlalchemy import inspect

    return {c.name for c in inspect(model).columns}


# ── Test 1: chat package re-exports all three classes ────────────────────────


def test_chat_package_exports_all_three_models() -> None:
    """`from app.models.chat import ...` must work for all 3 classes.

    Verifies backend/app/models/chat/__init__.py re-exports per insights pattern.
    """
    from app.models import chat as chat_pkg

    assert hasattr(chat_pkg, "ChatConversation"), "chat package missing ChatConversation"
    assert hasattr(chat_pkg, "ChatMessage"), "chat package missing ChatMessage"
    assert hasattr(chat_pkg, "ChatToolCall"), "chat package missing ChatToolCall"


# ── Test 2: Every model inherits Base + TenantScopedMixin (T-08-01 seam) ─────


def test_chat_models_inherit_tenant_scoped_mixin() -> None:
    """Every chat model MUST inherit TenantScopedMixin.

    The Phase 1 `with_loader_criteria` event listener targets TenantScopedMixin
    (NOT Base) — models that miss the mixin would silently leak cross-tenant.
    This is the T-08-01 mitigation seam.
    """
    _require_chat_conversation()
    _require_chat_message()
    _require_chat_tool_call()

    from app.db.base import Base, TenantScopedMixin

    for model in (ChatConversation, ChatMessage, ChatToolCall):
        assert issubclass(model, Base), f"{model.__name__} must inherit Base"
        assert issubclass(model, TenantScopedMixin), (
            f"{model.__name__} must inherit TenantScopedMixin "
            "(T-08-01: cross-tenant isolation seam). Without it, the Phase 1 "
            "with_loader_criteria filter does NOT fire."
        )


# ── Test 3: Each model has the correct __tablename__ ─────────────────────────


def test_chat_conversation_tablename() -> None:
    _require_chat_conversation()
    assert ChatConversation.__tablename__ == "chat_conversations"


def test_chat_message_tablename() -> None:
    _require_chat_message()
    assert ChatMessage.__tablename__ == "chat_messages"


def test_chat_tool_call_tablename() -> None:
    _require_chat_tool_call()
    assert ChatToolCall.__tablename__ == "chat_tool_calls"


# ── Test 4: ChatMessage carries the full D-20 column set ─────────────────────


def test_chat_message_has_all_d20_columns() -> None:
    """ChatMessage MUST expose every D-20 column including the two extensions
    `hallucination_flag` and `regenerate_count` (NOT in SPEC.md — added per
    08-CONTEXT.md D-20).
    """
    _require_chat_message()

    required = {
        # TenantScopedMixin columns
        "id",
        "tenant_id",
        "created_at",
        "updated_at",
        # Foreign keys + role + payload
        "conversation_id",
        "role",
        "content",
        "tool_calls",
        "tool_results",
        # Telemetry (CHAT-09 latency profiling)
        "tokens_used",
        "duration_ms",
        # D-20 extensions beyond SPEC.md
        "hallucination_flag",
        "regenerate_count",
    }
    cols = _column_names(ChatMessage)
    missing = required - cols
    assert not missing, (
        f"ChatMessage missing D-20 columns: {sorted(missing)}. Present: {sorted(cols)}"
    )


# ── Test 5: ChatToolCall carries the full D-20 column set ────────────────────


def test_chat_tool_call_has_all_d20_columns() -> None:
    """ChatToolCall MUST expose the audit-row column set per D-20 + D-21
    (tool call audit logging).
    """
    _require_chat_tool_call()

    required = {
        # TenantScopedMixin columns
        "id",
        "tenant_id",
        "created_at",
        "updated_at",
        # FK + audit payload
        "message_id",
        "tool_name",
        "input_args",
        "output_data",
        "duration_ms",
        "error",
    }
    cols = _column_names(ChatToolCall)
    missing = required - cols
    assert not missing, (
        f"ChatToolCall missing D-20 columns: {sorted(missing)}. Present: {sorted(cols)}"
    )


# ── Test 5b: ChatConversation column contract ────────────────────────────────


def test_chat_conversation_has_all_d20_columns() -> None:
    """ChatConversation MUST expose user_id / title / last_message_at / archived
    on top of the TenantScopedMixin columns.
    """
    _require_chat_conversation()

    required = {
        "id",
        "tenant_id",
        "created_at",
        "updated_at",
        "user_id",
        "title",
        "last_message_at",
        "archived",
    }
    cols = _column_names(ChatConversation)
    missing = required - cols
    assert not missing, (
        f"ChatConversation missing D-20 columns: {sorted(missing)}. Present: {sorted(cols)}"
    )


# ── Test 6: top-level app.models package registers all 3 chat classes ────────


def test_chat_models_registered_with_app_models_package() -> None:
    """`from app.models import ChatConversation, ChatMessage, ChatToolCall` works.

    Required so Alembic autogenerate discovers the chat tables when
    `target_metadata = Base.metadata` is set in alembic/env.py.
    """
    from app.models import ChatConversation as ConvFromPkg
    from app.models import ChatMessage as MsgFromPkg
    from app.models import ChatToolCall as TCFromPkg

    # Identity check: package-level export and module-level definition
    # MUST be the same class object (no shadow / duplicate).
    assert ConvFromPkg is ChatConversation
    assert MsgFromPkg is ChatMessage
    assert TCFromPkg is ChatToolCall


# ── Test 7: Migration 009 file exists with correct revision header ───────────


def test_migration_009_exists_with_correct_revision_chain() -> None:
    """Migration 009 must exist, target revision="009", chain from "008"."""
    here = Path(__file__).resolve()
    # backend/tests/unit/chat/test_chat_models.py → backend/
    backend_root = here.parents[3]
    migration_path = backend_root / "alembic" / "versions" / "009_chat_tables.py"

    assert migration_path.exists(), (
        f"Migration file not found: {migration_path}. "
        "Run Plan 08-02 Task 1 to create alembic/versions/009_chat_tables.py."
    )

    source = migration_path.read_text(encoding="utf-8")
    assert 'revision = "009"' in source, (
        f'Migration 009 must declare `revision = "009"` — got header:\n{source[:300]}'
    )
    assert 'down_revision = "008"' in source, (
        'Migration 009 must chain from `down_revision = "008"` (008 = daily_insights from Phase 5).'
    )

    # Three create_table calls (chat_conversations, chat_messages, chat_tool_calls)
    assert source.count("create_table") >= 3, (
        "Migration 009 must create at least 3 tables; found "
        f"{source.count('create_table')} `create_table` references."
    )

    # CASCADE on chat_messages.conversation_id AND chat_tool_calls.message_id
    cascade_hits = source.count('ondelete="CASCADE"')
    assert cascade_hits >= 2, (
        f'Migration 009 must declare ondelete="CASCADE" at least twice '
        f"(chat_messages.conversation_id + chat_tool_calls.message_id); found {cascade_hits}."
    )

    # CHECK constraint on role
    assert "ck_chat_messages_role" in source, (
        "Migration 009 must include CHECK constraint `ck_chat_messages_role` "
        "on chat_messages.role per T-08-02 (tampering mitigation)."
    )
