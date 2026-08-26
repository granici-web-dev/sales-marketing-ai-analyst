"""Dict-builder factories for Phase 8 AI Chat test data.

Mirrors the shape of `backend/tests/factories/insight_factory.py`
(make_insight_row / make_kpi_snapshot / make_detected_problem_input).

Each `make_*` returns a plain dict compatible with the future
chat_conversations / chat_messages / chat_tool_calls repository UPSERT
signatures (plan 08-03 will land the SQLAlchemy models). Wave 0 contract:
these factories do NOT import production models — they're pure dict
builders so they remain usable before any chat code exists.

Decisions referenced:
  D-13: chat_conversations is scoped to a single owner-user in MVP1
  D-15: archived column defaults to False
  D-20: chat_messages.role ∈ {'user','assistant','tool_use','tool_result'}
  D-20: chat_tool_calls audits every tool invocation
  D-37: default title is the Romanian string "Conversație nouă"
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

# Canonical Sofa Belle tenant + owner-user (must match tests/conftest.py and
# tests/unit/chat/conftest.py to keep cross-fixture identities consistent).
DEFAULT_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
DEFAULT_USER_ID = UUID("00000000-0000-0000-0000-000000000010")


def _now() -> datetime:
    return datetime(2026, 5, 29, 10, 0, 0, tzinfo=UTC)


def make_chat_conversation(**overrides) -> dict:
    """Build a chat_conversations row dict.

    Schema mirrors D-20 (Plan 08-01 frontmatter spec / CONTEXT.md):
        id, tenant_id, user_id, title, created_at, last_message_at, archived
    """
    base = {
        "id": uuid4(),
        "tenant_id": DEFAULT_TENANT_ID,
        "user_id": DEFAULT_USER_ID,
        "title": "Conversație nouă",
        "created_at": _now(),
        "last_message_at": _now(),
        "archived": False,
    }
    base.update(overrides)
    return base


def make_chat_message(**overrides) -> dict:
    """Build a chat_messages row dict.

    D-20: role CHECK in ('user','assistant','tool_use','tool_result').
    Default role="user". `content` carries text for user/assistant rows;
    `tool_calls` / `tool_results` are populated for tool rows (D-21).
    `hallucination_flag` + `regenerate_count` capture D-07 guard outcomes.
    """
    base = {
        "id": uuid4(),
        "conversation_id": uuid4(),
        "tenant_id": DEFAULT_TENANT_ID,
        "role": "user",
        "content": "Cum stăm cu vânzările luna asta?",
        "tool_calls": None,
        "tool_results": None,
        "tokens_used": None,
        "duration_ms": None,
        "hallucination_flag": False,
        "regenerate_count": 0,
        "created_at": _now(),
    }
    base.update(overrides)
    return base


def make_chat_tool_call(**overrides) -> dict:
    """Build a chat_tool_calls row dict.

    D-21: each tool invocation logs one row with input_args, output_data,
    duration_ms, and optional error. Default builds a successful `get_kpi`
    call. Set `error="..."` to simulate a failed tool execution.
    """
    base = {
        "id": uuid4(),
        "tenant_id": DEFAULT_TENANT_ID,
        "message_id": uuid4(),
        "tool_name": "get_kpi",
        "input_args": {},
        "output_data": {"leads_total": 0},
        "duration_ms": 42,
        "error": None,
        "created_at": _now(),
    }
    base.update(overrides)
    return base


# ── Convenience composites ──────────────────────────────────────────────────────


def make_chat_turn_pair(conversation_id: UUID | None = None) -> tuple[dict, dict]:
    """Build a (user_message, assistant_message) pair for the same conversation.

    Used by integration tests to seed a conversation that already has one
    completed turn before the test sends the next user message.
    """
    conv_id = conversation_id or uuid4()
    user_msg = make_chat_message(
        conversation_id=conv_id,
        role="user",
        content="Cum stăm cu vânzările luna asta?",
    )
    assistant_msg = make_chat_message(
        conversation_id=conv_id,
        role="assistant",
        content="Vânzările luna asta sunt în creștere cu **5%** față de luna trecută.",
        tokens_used=1280,
        duration_ms=3400,
    )
    return user_msg, assistant_msg
