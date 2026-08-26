"""SQLAlchemy ORM model for chat_messages table.

One row per turn in a chat conversation (user input, assistant reply,
tool_use block, tool_result block). Phase 8 Plan 02 — schema foundation.

D-20 column spec (includes two D-20 extensions BEYOND SPEC.md):
  id, tenant_id, created_at, updated_at  — from TenantScopedMixin
  conversation_id     — FK to chat_conversations.id, ON DELETE CASCADE
                        (messages die with their parent conversation)
  role                — TEXT NOT NULL; CHECK in (user, assistant, tool_use, tool_result)
                        (DB-level constraint = T-08-02 tampering mitigation;
                         application-level Literal typing rejects earlier)
  content             — TEXT NULL (NULL for pure tool_use / tool_result turns)
  tool_calls          — JSONB NULL (Claude tool_use blocks from the assistant turn)
  tool_results        — JSONB NULL (tool_result blocks from a follow-up turn)
  tokens_used         — INT NULL (CHAT-09 latency profiling)
  duration_ms         — INT NULL (CHAT-09 latency profiling)

  ── D-20 extensions (not in SPEC.md): ──
  hallucination_flag  — BOOLEAN NOT NULL DEFAULT false (set by the
                        hallucination guard in plan 08-04 when post-stream
                        verification detects unsupported claims)
  regenerate_count    — INT NOT NULL DEFAULT 0 (UI "Regenerate" button
                        increments per re-roll of an assistant turn)

T-08-01 (Information Disclosure): inherits TenantScopedMixin so the Phase 1
`with_loader_criteria` event listener filters every ORM select() by tenant_id.

T-08-05 (PII): per CLAUDE.md the `content` column may store the owner's
questions and Claude's answers but NOT raw client PII (names/phones/emails).
The no-PII rule in CLAUDE.md applies to LOGS, not product data — this is the
documented schema decision per D-20.

T-08-02 (Tampering): the migration adds a DB-level CHECK constraint
`role IN ('user','assistant','tool_use','tool_result')` so an INSERT with
a malformed role fails at the database layer.

D-22 (audit logging): each `tool_calls` / `tool_results` JSONB blob has a
matching row in `chat_tool_calls` for structured audit lookup by tool_name.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin


class ChatMessage(Base, TenantScopedMixin):
    """One row per turn (user / assistant / tool_use / tool_result).

    The parent FK is `conversation_id` with ON DELETE CASCADE at the DDL level
    (see migration 009) — deleting a conversation deletes its message stream.

    The `role` column is constrained by a DB-level CHECK (T-08-02). Application
    code (plan 08-04 orchestrator) uses a `Literal["user","assistant","tool_use",
    "tool_result"]` type so invalid roles are rejected before the SQL round-trip.

    `hallucination_flag` and `regenerate_count` are D-20 extensions on top of
    SPEC.md — they let the UI surface "AI may be uncertain about this" badges
    (hallucination_flag) and dedupe re-rolls (regenerate_count).
    """

    __tablename__ = "chat_messages"

    # Parent FK — ondelete=CASCADE lives in the migration DDL.
    conversation_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)

    # 'user' | 'assistant' | 'tool_use' | 'tool_result'
    # DB CHECK constraint ck_chat_messages_role enforces T-08-02 at DDL layer.
    role: Mapped[str] = mapped_column(Text, nullable=False)

    # Plain-text body. NULL for pure tool_use / tool_result rows where the
    # payload lives in tool_calls / tool_results JSONB.
    content: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Assistant's tool_use blocks (Anthropic content block JSON).
    tool_calls: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Tool runner's tool_result blocks for the following turn.
    tool_results: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # CHAT-09 latency telemetry.
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── D-20 extensions (beyond SPEC.md) ─────────────────────────────────────
    # Set by the hallucination guard (plan 08-04) when post-stream verification
    # finds unsupported numeric claims. Surfaces a UI warning badge.
    hallucination_flag: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # Incremented each time the user clicks "Regenerate" on this assistant turn.
    # Used by the UI to dedupe re-rolls and by analytics to track satisfaction.
    regenerate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
