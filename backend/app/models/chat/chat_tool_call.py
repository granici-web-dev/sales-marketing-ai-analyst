"""SQLAlchemy ORM model for chat_tool_calls table.

One row per tool invocation by the chat orchestrator. Phase 8 Plan 02 —
schema foundation. Implements D-21 (audit logging for tool calls).

D-20 / D-21 column spec:
  id, tenant_id, created_at, updated_at  — from TenantScopedMixin
  message_id   — FK to chat_messages.id, ON DELETE CASCADE
                 (audit row dies with the assistant turn that owns it)
  tool_name    — TEXT NOT NULL (one of the 12 chat tools from plan 08-03)
  input_args   — JSONB NOT NULL (sanitized arguments passed to the tool)
  output_data  — JSONB NULL (tool result; NULL if the call errored)
  duration_ms  — INT NULL (CHAT-09 latency profiling)
  error        — TEXT NULL (exception message; NULL on success)

T-08-01 (Information Disclosure): inherits TenantScopedMixin so the Phase 1
`with_loader_criteria` event listener filters every ORM select() by tenant_id.

D-21 (audit logging): the `(tenant_id, tool_name, created_at DESC)` index in
migration 009 backs the "which tools did we call today and how long did each
take" support query — critical for CHAT-09 latency budget enforcement.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin


class ChatToolCall(Base, TenantScopedMixin):
    """One row per tool call (D-21 audit logging).

    Parent FK is `message_id` with ON DELETE CASCADE at the DDL level — when
    a chat message is removed, its tool-call audit rows go too.

    `input_args` is NOT NULL because every tool invocation has at least the
    arguments the LLM passed. `output_data` is NULL on error rows where
    `error` is populated instead.
    """

    __tablename__ = "chat_tool_calls"

    # Parent FK — ondelete=CASCADE lives in the migration DDL.
    message_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)

    # Name of the registered tool (e.g. 'get_kpi', 'compare_periods', ...).
    tool_name: Mapped[str] = mapped_column(Text, nullable=False)

    # Sanitized arguments passed to the tool handler (NOT NULL).
    input_args: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Tool result payload. NULL when the call errored.
    output_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # CHAT-09 latency profiling.
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Exception message; NULL on success.
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
