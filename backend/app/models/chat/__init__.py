from __future__ import annotations

"""Chat SQLAlchemy models package (Phase 8).

Re-exports the three AI Chat ORM model classes used for persistence per D-20:
  - ChatConversation — owner of a multi-turn dialog (one per chat session)
  - ChatMessage      — individual turn (user / assistant / tool_use / tool_result)
  - ChatToolCall     — audit row for every tool invocation (D-21)

Import via:
    from app.models.chat import ChatConversation, ChatMessage, ChatToolCall

All three models inherit `TenantScopedMixin`, so the Phase 1
`with_loader_criteria` event listener automatically filters every ORM `select()`
by tenant_id (T-08-01 mitigation seam — see 08-02-PLAN.md threat_model).

Migration 009 (`alembic/versions/009_chat_tables.py`) creates the matching
PostgreSQL tables with FK constraints, ON DELETE CASCADE on the parent links,
a CHECK constraint on chat_messages.role, and indexes on the common query
shapes (history fetch + tool-call audit lookup).
"""

from app.models.chat.chat_conversation import ChatConversation  # noqa: F401
from app.models.chat.chat_message import ChatMessage  # noqa: F401
from app.models.chat.chat_tool_call import ChatToolCall  # noqa: F401

__all__ = ["ChatConversation", "ChatMessage", "ChatToolCall"]
