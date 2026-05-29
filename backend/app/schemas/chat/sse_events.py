from __future__ import annotations

"""SSE event Pydantic v2 schemas (Phase 8 Plan 08-04 Task 1).

D-09 declares 7 SSE event types streamed from `POST /chat/conversations/{id}/messages`
to the browser. This module declares the matching Pydantic envelopes so the
orchestrator (plan 08-04) and router (plan 08-05) can `model_dump` payloads with
typed guarantees rather than ad-hoc dicts.

D-09 event vocabulary:
  - conversation_meta — fired FIRST so the frontend can persist message IDs
  - tool_use — emitted when Claude requests a tool (rendered as pill)
  - tool_result — emitted after handler completes (pill state transitions)
  - assistant_chunk — per content_block_delta text_delta (token streaming)
  - regenerate_notice — fired on hallucination_guard rejection round 1 (D-08)
  - done — fired at end of stream with token + cost telemetry
  - error — fired on unrecoverable failure (sanitized — never raw API errors,
    per T-08-03)

The shapes here MUST match `frontend/src/lib/chat/parseSSE.ts` SSEEvent union
declared in plan 08-06. A wire-format contract change is breaking — bump the
SSE schema version comment + update both sides.
"""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class ConversationMetaEvent(BaseModel):
    """D-09: fired first so the frontend can persist user + assistant message IDs.

    Both `message_id_user` and `message_id_assistant` are pre-allocated by the
    orchestrator BEFORE the stream starts so the frontend can render an
    optimistic assistant bubble that survives reconnects/reloads.
    """

    conversation_id: UUID
    message_id_user: UUID
    message_id_assistant: UUID


class ToolUseEvent(BaseModel):
    """D-09: Claude requested a tool — render a pill ("looking up …")."""

    tool_use_id: str
    name: str
    input: dict


class ToolResultEvent(BaseModel):
    """D-09: tool handler returned — transition pill to done/error state.

    `output_preview` is the first ~200 chars of JSON-serialized handler output.
    The full payload is persisted in `chat_tool_calls.output_data` for audit.
    `error` is the truthy-error flag (None/False = success, True = exception).
    """

    tool_use_id: str
    output_preview: str
    duration_ms: int
    error: bool | None = None


class AssistantChunkEvent(BaseModel):
    """D-09: per `content_block_delta` text_delta token chunk.

    The orchestrator emits one of these per text fragment Claude streams.
    The frontend appends them to the in-progress assistant bubble.
    """

    text: str


class RegenerateNoticeEvent(BaseModel):
    """D-09: emitted when hallucination_guard rejects round 1 (D-07 retry budget).

    Frontend shows "Verific cifrele..." while the second stream replaces the
    first. Only ever fired with reason="hallucination_guard" in MVP1.
    """

    reason: Literal["hallucination_guard"]


class DoneEvent(BaseModel):
    """D-09: final event with token + cost telemetry (D-31 cost tracking).

    `hallucination_flag` is True only when D-07 retry budget exhausted AND the
    fallback Romanian copy was streamed (so the UI can show a warning badge).
    """

    message_id: UUID
    total_input_tokens: int
    total_output_tokens: int
    duration_ms: int
    hallucination_flag: bool


class ErrorEvent(BaseModel):
    """D-09: sanitized error envelope (T-08-03 information-disclosure mitigation).

    `code` is a stable string the frontend may key error UI from. `message_ro`
    is the Romanian copy shown to the user. Raw Anthropic exception details
    NEVER reach the client — they're collapsed to {code:'internal', message_ro:…}
    server-side and logged separately via structlog.
    """

    code: str
    message_ro: str
