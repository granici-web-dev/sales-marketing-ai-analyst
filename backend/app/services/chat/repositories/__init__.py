"""Repository layer for Phase 8 AI Chat persistence (D-22).

Three tenant-scoped repositories backed by the migration-009 tables:
  - ConversationRepository — chat_conversations CRUD + soft archive (D-15)
  - MessageRepository      — chat_messages append + D-16 history window
  - ToolCallRepository     — chat_tool_calls audit row per D-21

All three follow the Phase 5 `InsightRepository` contract:
  - constructor receives (session: AsyncSession, tenant_id: UUID)
  - every row validates `row["tenant_id"] == self._tenant_id` before INSERT
    (Pitfall 6 — Core INSERT bypasses with_loader_criteria)
  - no `session.commit()` calls — caller commits atomically (WR-04)

T-08-01 mitigation: repositories are the second line of defense after
TenantScopedMixin + with_loader_criteria. ORM SELECTs are filtered automatically;
writes assert the dict's tenant_id explicitly.
"""

from __future__ import annotations

from app.services.chat.repositories.conversation_repository import (
    ConversationRepository,
)
from app.services.chat.repositories.message_repository import MessageRepository
from app.services.chat.repositories.tool_call_repository import (
    ToolCallRepository,
)

__all__ = [
    "ConversationRepository",
    "MessageRepository",
    "ToolCallRepository",
]
