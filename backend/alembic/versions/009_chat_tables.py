"""Create chat_conversations, chat_messages, chat_tool_calls tables (Phase 8).

Revision ID: 009
Revises: 008
Create Date: 2026-05-29

Schema foundation for AI Chat (Phase 8 Plan 02). Implements D-20 from
.planning/phases/08-ai-chat/08-CONTEXT.md with two extensions BEYOND SPEC.md:

  chat_messages.hallucination_flag  BOOLEAN NOT NULL DEFAULT false
  chat_messages.regenerate_count    INTEGER NOT NULL DEFAULT 0

Tables:
  1. chat_conversations — one row per chat session, owned by a (tenant, user)
  2. chat_messages      — one row per turn (user/assistant/tool_use/tool_result)
  3. chat_tool_calls    — D-21 audit row per tool invocation by the orchestrator

Foreign keys:
  chat_conversations.tenant_id      → tenants.id
  chat_conversations.user_id        → users.id
  chat_messages.tenant_id           → tenants.id
  chat_messages.conversation_id     → chat_conversations.id   ON DELETE CASCADE
  chat_tool_calls.tenant_id         → tenants.id
  chat_tool_calls.message_id        → chat_messages.id        ON DELETE CASCADE

Constraints:
  ck_chat_messages_role  — CHECK role IN ('user','assistant','tool_use','tool_result')
                            T-08-02 tampering mitigation; application also enforces via Literal.

Indexes:
  ix_chat_conversations_tenant_user_last  — (tenant_id, user_id, last_message_at DESC)
                                              backs the "recent conversations" sidebar query.
  ix_chat_messages_conv_created           — (conversation_id, created_at)
                                              backs the per-conversation history fetch (CHAT-09).
  ix_chat_tool_calls_tenant_tool_created  — (tenant_id, tool_name, created_at DESC)
                                              backs the D-21 tool audit lookup ("which tools today?").

Security notes:
  T-08-01: tenant_id NOT NULL on every table + FK to tenants.id. Combined with
           the Phase 1 `with_loader_criteria` event listener (which fires on
           every ORM select() against `TenantScopedMixin`-inheriting models),
           this is the cross-tenant isolation seam.
  T-08-02: role CHECK constraint prevents tampering at the DB layer.
  T-08-DDL: downgrade() drops indexes before tables in strict reverse-FK order
           so a rollback always succeeds (Task 2 verifies the roundtrip).
  T-08-05: content/tool_calls/tool_results store owner Q&A + Claude output —
           NOT raw client PII. No-PII rule from CLAUDE.md applies to LOGS,
           not product data (documented in D-20).
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Table 1: chat_conversations ──────────────────────────────────────────
    op.create_table(
        "chat_conversations",
        # TenantScopedMixin columns (replicated manually — standalone DDL pattern)
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # Owner of the conversation — FK to users.id
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        # Lazy-generated short label (NULL until D-14 title generator runs)
        sa.Column("title", sa.Text, nullable=True),
        # Updated on every appended message — drives the sidebar "recent" sort
        sa.Column(
            "last_message_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # Soft-hide toggle — MVP1 has no hard delete (GDPR delete = Iteration 4)
        sa.Column(
            "archived",
            sa.Boolean,
            server_default=sa.text("false"),
            nullable=False,
        ),
        # FKs — T-08-01 tenant isolation + user ownership
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_chat_conversations_tenant_id",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_chat_conversations_user_id",
        ),
    )

    # Sidebar "recent conversations" — newest first per (tenant, user)
    op.create_index(
        "ix_chat_conversations_tenant_user_last",
        "chat_conversations",
        ["tenant_id", "user_id", sa.text("last_message_at DESC")],
    )

    # ── Table 2: chat_messages ──────────────────────────────────────────────
    op.create_table(
        "chat_messages",
        # TenantScopedMixin columns
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # Parent FK — CASCADE so the message stream dies with its conversation
        sa.Column("conversation_id", UUID(as_uuid=True), nullable=False),
        # 'user' | 'assistant' | 'tool_use' | 'tool_result'  (T-08-02 CHECK below)
        sa.Column("role", sa.Text, nullable=False),
        # Plain-text body — NULL for pure tool_use / tool_result turns
        sa.Column("content", sa.Text, nullable=True),
        # Assistant's tool_use blocks (Anthropic content block JSON)
        sa.Column("tool_calls", JSONB, nullable=True),
        # Tool runner's tool_result blocks
        sa.Column("tool_results", JSONB, nullable=True),
        # CHAT-09 latency telemetry
        sa.Column("tokens_used", sa.Integer, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        # ── D-20 extensions beyond SPEC.md ───────────────────────────────────
        sa.Column(
            "hallucination_flag",
            sa.Boolean,
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "regenerate_count",
            sa.Integer,
            server_default=sa.text("0"),
            nullable=False,
        ),
        # FKs
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_chat_messages_tenant_id",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["chat_conversations.id"],
            name="fk_chat_messages_conversation_id",
            ondelete="CASCADE",
        ),
        # T-08-02 tampering mitigation — role values constrained at DB layer
        sa.CheckConstraint(
            "role IN ('user','assistant','tool_use','tool_result')",
            name="ck_chat_messages_role",
        ),
    )

    # Per-conversation history fetch — CHAT-09 latency budget
    op.create_index(
        "ix_chat_messages_conv_created",
        "chat_messages",
        ["conversation_id", "created_at"],
    )

    # ── Table 3: chat_tool_calls ────────────────────────────────────────────
    op.create_table(
        "chat_tool_calls",
        # TenantScopedMixin columns
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # Parent FK — CASCADE so the audit row dies with its message
        sa.Column("message_id", UUID(as_uuid=True), nullable=False),
        # Registered tool name (e.g. 'get_kpi', 'compare_periods', ...)
        sa.Column("tool_name", sa.Text, nullable=False),
        # Sanitized tool arguments (NOT NULL)
        sa.Column("input_args", JSONB, nullable=False),
        # Tool result payload (NULL on error)
        sa.Column("output_data", JSONB, nullable=True),
        # CHAT-09 latency telemetry
        sa.Column("duration_ms", sa.Integer, nullable=True),
        # Exception message (NULL on success)
        sa.Column("error", sa.Text, nullable=True),
        # FKs
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_chat_tool_calls_tenant_id",
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["chat_messages.id"],
            name="fk_chat_tool_calls_message_id",
            ondelete="CASCADE",
        ),
    )

    # D-21 audit lookup — "which tools did we call today, how long did each take"
    op.create_index(
        "ix_chat_tool_calls_tenant_tool_created",
        "chat_tool_calls",
        ["tenant_id", "tool_name", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    # Strict reverse-FK order — drop children before parents.
    # Indexes go first (drop_table also drops dependent indexes on most DBs,
    # but we keep them explicit so the rollback is auditable).
    op.drop_index("ix_chat_tool_calls_tenant_tool_created", table_name="chat_tool_calls")
    op.drop_table("chat_tool_calls")

    op.drop_index("ix_chat_messages_conv_created", table_name="chat_messages")
    op.drop_table("chat_messages")

    op.drop_index("ix_chat_conversations_tenant_user_last", table_name="chat_conversations")
    op.drop_table("chat_conversations")
