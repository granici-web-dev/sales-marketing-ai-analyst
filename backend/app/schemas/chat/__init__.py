"""AI Chat Pydantic schemas (Phase 8).

Three families of schemas:
  - conversation: request/response shapes for /api/v1/chat/conversations
  - message: request/response shapes for chat messages
  - sse_events: 7 D-09 SSE event Pydantic envelopes streamed to the frontend

References:
  - .planning/phases/08-ai-chat/08-CONTEXT.md (D-09 — SSE event schema list)
  - .planning/phases/08-ai-chat/08-PATTERNS.md § sse_events.py lines 311-349
"""

from __future__ import annotations

from app.schemas.chat.conversation import (
    ConversationListOut,
    ConversationOut,
    CreateConversationRequest,
)
from app.schemas.chat.message import MessageOut, SendMessageRequest
from app.schemas.chat.sse_events import (
    AssistantChunkEvent,
    ConversationMetaEvent,
    DoneEvent,
    ErrorEvent,
    RegenerateNoticeEvent,
    ToolResultEvent,
    ToolUseEvent,
)

__all__ = [
    "ConversationOut",
    "ConversationListOut",
    "CreateConversationRequest",
    "MessageOut",
    "SendMessageRequest",
    "AssistantChunkEvent",
    "ConversationMetaEvent",
    "DoneEvent",
    "ErrorEvent",
    "RegenerateNoticeEvent",
    "ToolResultEvent",
    "ToolUseEvent",
]
