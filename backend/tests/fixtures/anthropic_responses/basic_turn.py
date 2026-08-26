"""Recorded streaming response: basic single-turn assistant reply (no tools).

Models the simplest Claude Sonnet 4.5 streaming flow per RESEARCH §2 events:
  1. message_start
  2. content_block_start (type=text)
  3. content_block_delta x N (text_delta deltas streaming the Romanian answer)
  4. content_block_stop
  5. message_delta (stop_reason=end_turn, output_tokens)
  6. message_stop

Used by:
  - tests/unit/chat/test_orchestrator.py (plan 08-04): asserts the orchestrator
    correctly streams text_delta events to the SSE collector.
  - tests/integration/chat/test_chat_endpoint.py (plan 08-05): end-to-end
    happy-path streaming reply with no tool round.

Decisions referenced:
  D-09: SSE event schema — frontend `assistant_chunk` event maps to each text_delta.
  D-26: System prompt produces Romanian assistant text.
  D-31: usage block tracks input_tokens + output_tokens + cache_read_input_tokens.
"""

from __future__ import annotations

from typing import Any

# Recorded Romanian assistant reply text, segmented as Claude streamed it.
_BASIC_RESPONSE_CHUNKS: list[str] = [
    "Vânzările luna asta",
    " sunt în creștere cu ",
    "**5%**",
    " față de luna trecută.",
    " Ai înregistrat **23 contracte**",
    " noi în această perioadă.",
]


BASIC_TURN_EVENTS: list[dict[str, Any]] = [
    {
        "type": "message_start",
        "message": {
            "id": "msg_basic_001",
            "type": "message",
            "role": "assistant",
            "model": "claude-sonnet-4-5",
            "content": [],
            "stop_reason": None,
            "usage": {
                "input_tokens": 1200,
                "output_tokens": 0,
                "cache_read_input_tokens": 0,
            },
        },
    },
    {
        "type": "content_block_start",
        "index": 0,
        "content_block": {"type": "text", "text": ""},
    },
    *[
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": chunk},
        }
        for chunk in _BASIC_RESPONSE_CHUNKS
    ],
    {
        "type": "content_block_stop",
        "index": 0,
    },
    {
        "type": "message_delta",
        "delta": {"stop_reason": "end_turn", "stop_sequence": None},
        "usage": {
            "input_tokens": 1200,
            "output_tokens": 80,
            "cache_read_input_tokens": 0,
        },
    },
    {
        "type": "message_stop",
    },
]


# Convenience constant for tests that need the assembled assistant text.
BASIC_TURN_TEXT: str = "".join(_BASIC_RESPONSE_CHUNKS)
