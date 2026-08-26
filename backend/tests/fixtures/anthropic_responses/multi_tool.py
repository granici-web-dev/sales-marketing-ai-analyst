"""Recorded streaming response: assistant turn that calls 3 distinct tools.

Models a Claude Sonnet 4.5 streaming response that exercises CHAT-02 SC#2
("≥3 distinct tools used across the conversation per assistant turn").

Round shape per D-30 (multi-turn tool loop):
  ROUND 1 (tools requested) — events here:
    - message_start (usage.input_tokens populated)
    - content_block_start (type=text) — Claude narrates "Caut datele..."
    - content_block_delta x few text deltas
    - content_block_stop
    - content_block_start (type=tool_use) — tool #1: get_funnel_data
    - content_block_delta (input_json_delta)
    - content_block_stop
    - content_block_start (type=tool_use) — tool #2: get_salesperson_performance
    - content_block_delta (input_json_delta)
    - content_block_stop
    - content_block_start (type=tool_use) — tool #3: compare_periods
    - content_block_delta (input_json_delta)
    - content_block_stop
    - message_delta (stop_reason=tool_use)
    - message_stop

  ROUND 2 happens AFTER orchestrator executes the 3 tools and re-calls
  Claude with tool_result messages — modeled in basic_turn.py (or via a
  separate cassette in plan 08-04). This fixture only carries ROUND 1.

Used by:
  - tests/unit/chat/test_orchestrator.py — assert orchestrator dispatches all
    3 tools (via TOOLS_REGISTRY) in parallel per D-30.
  - tests/integration/chat/test_chat_endpoint.py — assert frontend SSE stream
    receives 3 `tool_use` events + 3 `tool_result` events.

Decisions referenced:
  D-02: 12 canonical chat tools — get_funnel_data, get_salesperson_performance,
        compare_periods are tier-1 tools (always allowed).
  D-09: SSE `tool_use` event carries {tool_use_id, name, input}.
  D-10: tool pills render inline in the frontend bubble for each tool_use.
  D-30: tool dispatch uses asyncio.gather for parallel execution.
"""

from __future__ import annotations

from typing import Any

# Pre-narrative chunks Claude streams before requesting tools.
_PREAMBLE_TEXT_CHUNKS: list[str] = [
    "Caut datele",
    " pentru luna asta.",
]


MULTI_TOOL_EVENTS: list[dict[str, Any]] = [
    {
        "type": "message_start",
        "message": {
            "id": "msg_multi_tool_001",
            "type": "message",
            "role": "assistant",
            "model": "claude-sonnet-4-5",
            "content": [],
            "stop_reason": None,
            "usage": {
                "input_tokens": 2400,
                "output_tokens": 0,
                "cache_read_input_tokens": 1800,
            },
        },
    },
    # Preamble text — orchestrator must stream these as `assistant_chunk` SSE events
    # (D-30: intermediate text during tool-use rounds also emits assistant_chunk).
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
        for chunk in _PREAMBLE_TEXT_CHUNKS
    ],
    {
        "type": "content_block_stop",
        "index": 0,
    },
    # Tool #1: get_funnel_data
    {
        "type": "content_block_start",
        "index": 1,
        "content_block": {
            "type": "tool_use",
            "id": "toolu_funnel_001",
            "name": "get_funnel_data",
            "input": {},
        },
    },
    {
        "type": "content_block_delta",
        "index": 1,
        "delta": {
            "type": "input_json_delta",
            "partial_json": '{"date_from":"2026-05-01","date_to":"2026-05-29"}',
        },
    },
    {
        "type": "content_block_stop",
        "index": 1,
    },
    # Tool #2: get_salesperson_performance
    {
        "type": "content_block_start",
        "index": 2,
        "content_block": {
            "type": "tool_use",
            "id": "toolu_salesperson_001",
            "name": "get_salesperson_performance",
            "input": {},
        },
    },
    {
        "type": "content_block_delta",
        "index": 2,
        "delta": {
            "type": "input_json_delta",
            "partial_json": '{"date_from":"2026-05-01","date_to":"2026-05-29"}',
        },
    },
    {
        "type": "content_block_stop",
        "index": 2,
    },
    # Tool #3: compare_periods
    {
        "type": "content_block_start",
        "index": 3,
        "content_block": {
            "type": "tool_use",
            "id": "toolu_compare_001",
            "name": "compare_periods",
            "input": {},
        },
    },
    {
        "type": "content_block_delta",
        "index": 3,
        "delta": {
            "type": "input_json_delta",
            "partial_json": (
                '{"period_a":{"from":"2026-05-01","to":"2026-05-29"},'
                '"period_b":{"from":"2026-04-01","to":"2026-04-29"},'
                '"metrics":["leads_total","contracts_closed"]}'
            ),
        },
    },
    {
        "type": "content_block_stop",
        "index": 3,
    },
    {
        "type": "message_delta",
        "delta": {"stop_reason": "tool_use", "stop_sequence": None},
        "usage": {
            "input_tokens": 2400,
            "output_tokens": 320,
            "cache_read_input_tokens": 1800,
        },
    },
    {
        "type": "message_stop",
    },
]


# Convenience extractors for tests.

def get_tool_use_blocks() -> list[dict[str, Any]]:
    """Returns the 3 tool_use content_block_start events from this cassette."""
    return [
        e
        for e in MULTI_TOOL_EVENTS
        if e.get("type") == "content_block_start"
        and e.get("content_block", {}).get("type") == "tool_use"
    ]


def get_tool_names() -> list[str]:
    """Returns the ordered list of tool names this cassette invokes."""
    return [block["content_block"]["name"] for block in get_tool_use_blocks()]
