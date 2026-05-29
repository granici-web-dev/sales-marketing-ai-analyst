from __future__ import annotations

"""Message request/response Pydantic DTOs for Phase 8 AI Chat.

D-09: MessageOut.role is `Literal["user","assistant"]` — `tool_use`/`tool_result`
      are internal Anthropic content-block types persisted in `chat_messages.role`
      but NEVER returned to the frontend (the SSE stream renders tools as pills,
      not as messages).
D-23: shapes consumed by 5 endpoints under /api/v1/chat.
D-37: SendMessageRequest content length 1-10000 chars (Romanian-only).
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class MessageOut(BaseModel):
    """A single chat message as returned by GET /chat/conversations/{id}.

    `tool_use` / `tool_result` rows in `chat_messages` are filtered out of the
    response — only the final user / assistant text bubbles are rendered.
    """

    role: Literal["user", "assistant"]
    content: str
    created_at: datetime
    tokens_used: int | None
    hallucination_flag: bool
    regenerate_count: int


class SendMessageRequest(BaseModel):
    """Body for POST /chat/conversations/{id}/messages.

    `content` is the user's plain-text question in Romanian. The orchestrator
    streams the assistant reply back over SSE per D-09.
    """

    content: str = Field(..., min_length=1, max_length=10_000)
