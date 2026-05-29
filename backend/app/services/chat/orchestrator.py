from __future__ import annotations

"""ChatOrchestrator — streaming + tool-loop + hallucination guard + persistence.

This is the heart of Phase 8 AI Chat. It runs ONE user turn end-to-end:

  1. Persist the user message + emit `conversation_meta` (so frontend can swap
     optimistic IDs to DB IDs).
  2. Build the cached Romanian system prompt + load D-16 history window.
  3. Multi-round Claude tool loop (D-30): up to MAX_TOOL_ROUNDS=5 rounds.
     Tools dispatched in parallel via asyncio.gather. Each tool call writes
     a chat_tool_calls audit row (D-21).
  4. Post-stream hallucination guard (D-08). On FAIL round 1, emit
     `regenerate_notice` and re-stream with a corrective instruction.
     On FAIL round 2 (D-07 retry budget = 1): stream the Romanian fallback
     and persist with hallucination_flag=True.
  5. Persist the assistant message + emit `done`.
  6. On first turn (history was empty), schedule fire-and-forget title
     generation via D-14 Haiku→Sonnet fallback.

Per CLAUDE.md and the documented exception (D-25): this is the ONLY HTTP
path that calls Anthropic synchronously. The router (plan 08-05) calls
`orch.run_turn(...)` directly from the SSE handler.

Threat mitigations applied here:
  - T-08-01: TOOLS_REGISTRY handlers receive self._tenant_id explicitly so
             every read query is tenant-scoped; repositories validate too.
  - T-08-02: system prompt forbids fabrication; guard rejects un-grounded
             numbers/entities/links post-stream.
  - T-08-03: outer try/except collapses Anthropic errors to a sanitized
             `error` SSE event ({code:"internal", message_ro:"..."}).
  - T-08-04: MAX_TOOL_ROUNDS=5 + HISTORY_LIMIT=20 + MAX_TOKENS=4096 + guard
             retry budget=1 cap per-turn cost.
  - T-08-05: structlog binds tenant_id + conversation_id + service name only;
             never user text or accumulated_text.
  - T-08-06: disconnect_probe is checked inside the stream inner loop so a
             client hang-up aborts before further tokens drain.

References:
  - .planning/phases/08-ai-chat/08-CONTEXT.md (D-08..D-31)
  - .planning/phases/08-ai-chat/08-RESEARCH.md §2 lines 552-716
  - .planning/phases/08-ai-chat/08-PATTERNS.md § orchestrator.py
  - backend/app/services/insights/insight_service.py (cost formula + LM-1 pattern)
"""

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from decimal import Decimal
from time import perf_counter
from uuid import UUID, uuid4

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

# Module-level import for test patchability (LM-1 mitigation — same pattern as
# Phase 5 InsightService and Phase 8 title_generator). Instantiated INSIDE
# `run_turn` per INFRA-05 fork safety (D-29) — NEVER at module level.
from anthropic import AsyncAnthropic

from app.services.chat.hallucination_guard import (
    build_entity_whitelist,
    check_response,
)
from app.services.chat.prompt_builder import (
    _build_tenant_facts,
    build_system_prompt,
)
from app.services.chat.repositories import (
    ConversationRepository,
    MessageRepository,
    ToolCallRepository,
)
from app.services.chat.title_generator import schedule_title_generation
from app.services.chat.tools import TOOLS_REGISTRY, get_all_tools


log = structlog.get_logger(__name__)


# ── Module-level constants ───────────────────────────────────────────────────
MODEL = "claude-sonnet-4-5"  # D-26 — LOCKED
MAX_TOKENS = 4096
TEMPERATURE = 0.3  # D-30 — slightly higher than Phase 5's 0.2 (chat is conversational)
MAX_TOOL_ROUNDS = 5  # D-30 hard cap (cost guard)
HISTORY_LIMIT = 20  # D-16
GUARD_RETRY_BUDGET = 1  # D-07: max 1 regenerate on guard failure

# Romanian fallback message streamed when guard fails twice (D-07).
GUARD_FALLBACK_TEXT = (
    "Nu pot da un răspuns precis pe baza datelor disponibile. "
    "Te rog reformulează întrebarea."
)


DisconnectProbe = Callable[[], Awaitable[bool]]


class ChatOrchestrator:
    """One-shot orchestrator for a single user → assistant turn.

    Instantiate per HTTP request:
        orch = ChatOrchestrator(session, tenant_id, user_id)
        async for event_name, payload in orch.run_turn(conv_id, user_text, probe):
            ...

    Yields `(event_name, payload)` tuples matching the D-09 SSE event schema.
    The router wraps these in `event:` / `data:` SSE wire frames.
    """

    def __init__(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
    ) -> None:
        self._session = session
        self._tenant_id = tenant_id
        self._user_id = user_id
        # CLAUDE.md #6: bind only non-PII context. NEVER bind user_text/content.
        self._log = log.bind(
            tenant_id=str(tenant_id),
            service="chat_orchestrator",
        )

    async def run_turn(
        self,
        conversation_id: UUID,
        user_text: str,
        disconnect_probe: DisconnectProbe,
    ) -> AsyncIterator[tuple[str, dict]]:
        """Run a complete user → assistant turn.

        Args:
            conversation_id: parent chat_conversations.id.
            user_text: the user's plain-text question (Romanian).
            disconnect_probe: async callable that returns True if the client
                has disconnected. Checked inside the inner streaming loop so
                the orchestrator aborts before persisting the assistant message.

        Yields:
            (event_name, payload) tuples per D-09. Event names:
              conversation_meta, tool_use, tool_result, assistant_chunk,
              regenerate_notice, done, error.
        """
        log_ = self._log.bind(conversation_id=str(conversation_id))
        turn_start = perf_counter()

        # Instantiate repositories from the registered classes (module-level
        # patch targets so tests can swap them).
        msg_repo = MessageRepository(self._session, self._tenant_id)
        conv_repo = ConversationRepository(self._session, self._tenant_id, self._user_id)
        tool_repo = ToolCallRepository(self._session, self._tenant_id)

        # ── 1. Persist user message + emit conversation_meta ───────────────
        try:
            user_msg_id = await msg_repo.insert_user_message(conversation_id, user_text)
        except Exception as exc:  # noqa: BLE001 — sanitize per T-08-03
            log_.exception("chat.user_persist_failed")
            yield (
                "error",
                {"code": "internal", "message_ro": "A apărut o problemă. Te rog încearcă din nou."},
            )
            return

        assistant_msg_id = uuid4()

        # Insert assistant-message STUB before the Claude tool loop so each
        # `tool_repo.insert_tool_call(message_id=assistant_msg_id, ...)` below
        # has a valid FK target. Without this the per-tool flush raises
        # ForeignKeyViolationError, which poisons the session (PendingRollback)
        # and makes the final assistant insert at the bottom of run_turn fail
        # too — surfacing as the generic "A apărut o problemă." SSE error event.
        # Final content/tokens/duration are filled in by `finalize_assistant_message`
        # after the tool loop completes (see section 4 below).
        try:
            await msg_repo.insert_assistant_message(
                conversation_id,
                content="",
                tokens_used=None,
                duration_ms=None,
                hallucination_flag=False,
                regenerate_count=0,
                message_id=assistant_msg_id,
            )
        except Exception:  # noqa: BLE001 — sanitize per T-08-03
            log_.exception("chat.assistant_stub_failed")
            yield (
                "error",
                {"code": "internal", "message_ro": "A apărut o problemă. Te rog încearcă din nou."},
            )
            return

        yield (
            "conversation_meta",
            {
                "conversation_id": str(conversation_id),
                "message_id_user": str(user_msg_id),
                "message_id_assistant": str(assistant_msg_id),
            },
        )

        # ── 2. Build prompt + history + whitelist ──────────────────────────
        from app.core.config import settings  # local import — fork-safe (INFRA-05)

        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        system_blocks = build_system_prompt(_build_tenant_facts())
        tools = get_all_tools()

        try:
            history = await msg_repo.load_history(conversation_id, limit=HISTORY_LIMIT)
        except Exception:  # noqa: BLE001
            history = []
        # D-16: D-16 anchor + recent is built by load_history; we just append the new user message.
        base_messages: list[dict] = list(history) + [{"role": "user", "content": user_text}]
        is_first_turn = len(history) == 0

        try:
            entity_whitelist = await build_entity_whitelist(self._session, self._tenant_id)
        except Exception:  # noqa: BLE001
            entity_whitelist = {}

        # ── 3. Tool loop + guard retry ──────────────────────────────────────
        total_usage: dict[str, int] = {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_input_tokens": 0,
        }
        accumulated_text = ""
        guard_attempt = 0
        fallback_used = False

        try:
            for guard_attempt in range(GUARD_RETRY_BUDGET + 1):  # 0, 1
                accumulated_text = ""
                accumulated_tool_results: list[dict] = []
                messages = list(base_messages)

                # Inner tool-use loop, capped at MAX_TOOL_ROUNDS (D-30).
                for round_idx in range(MAX_TOOL_ROUNDS):
                    # NB: stream(...) is a context manager that returns the
                    # response stream. Anthropic 0.104 supports tools=[...]
                    # + system=[...] (with cache_control) on stream.
                    async with client.messages.stream(
                        model=MODEL,
                        max_tokens=MAX_TOKENS,
                        temperature=TEMPERATURE,
                        system=system_blocks,
                        tools=tools,
                        messages=messages,
                    ) as stream:
                        disconnected = False
                        async for event in stream:
                            if await disconnect_probe():
                                disconnected = True
                                break
                            etype = getattr(event, "type", None)
                            if etype == "content_block_delta":
                                delta = getattr(event, "delta", None)
                                if delta is not None and getattr(delta, "type", None) == "text_delta":
                                    text = getattr(delta, "text", "")
                                    accumulated_text += text
                                    yield ("assistant_chunk", {"text": text})
                            # NOTE: `content_block_start` for tool_use is not
                            # emitted here — see the post-stream loop below
                            # that emits one definitive `tool_use` SSE per
                            # parsed block from final_msg.content (carries
                            # the fully-assembled `input` dict).
                        if disconnected:
                            log_.info("chat.disconnect_mid_stream")
                            return
                        final_msg = await stream.get_final_message()

                    # Accumulate token usage (D-31).
                    usage = getattr(final_msg, "usage", None)
                    if usage is not None:
                        total_usage["input_tokens"] += getattr(usage, "input_tokens", 0) or 0
                        total_usage["output_tokens"] += getattr(usage, "output_tokens", 0) or 0
                        total_usage["cache_read_input_tokens"] += (
                            getattr(usage, "cache_read_input_tokens", 0) or 0
                        )

                    stop_reason = getattr(final_msg, "stop_reason", None)
                    if stop_reason != "tool_use":
                        # Final assistant text in hand — exit inner loop.
                        break

                    # Extract tool_use blocks for this round.
                    content = list(getattr(final_msg, "content", []) or [])
                    tool_use_blocks = [
                        b for b in content if getattr(b, "type", None) == "tool_use"
                    ]
                    if not tool_use_blocks:
                        break

                    # Emit one `tool_use` SSE event per detected tool block
                    # using the FULL parsed input (the SDK assembles it from
                    # input_json_delta events into block.input). This is more
                    # reliable than emitting on `content_block_start`, which
                    # has only a placeholder empty `input` dict at that point.
                    for block in tool_use_blocks:
                        yield (
                            "tool_use",
                            {
                                "tool_use_id": getattr(block, "id", ""),
                                "name": getattr(block, "name", ""),
                                "input": _to_jsonable(getattr(block, "input", {}) or {}),
                            },
                        )

                    # ── Parallel tool dispatch (D-30) ────────────────────
                    results = await asyncio.gather(
                        *(self._execute_tool(block) for block in tool_use_blocks),
                        return_exceptions=False,
                    )

                    # Emit tool_result events + audit row + extend conversation.
                    tool_results_for_claude: list[dict] = []
                    for block, result, is_error, duration_ms in results:
                        accumulated_tool_results.append(result)
                        try:
                            await tool_repo.insert_tool_call(
                                message_id=assistant_msg_id,
                                tool_name=getattr(block, "name", "unknown"),
                                input_args=_to_jsonable(getattr(block, "input", {})),
                                output_data=None if is_error else _to_jsonable(result),
                                duration_ms=duration_ms,
                                error=(str(result.get("error", ""))[:500] if is_error else None),
                            )
                        except Exception:  # noqa: BLE001
                            log_.exception("chat.tool_audit_failed")
                        preview = json.dumps(result, default=str, ensure_ascii=False)[:200]
                        yield (
                            "tool_result",
                            {
                                "tool_use_id": getattr(block, "id", ""),
                                "output_preview": preview,
                                "duration_ms": duration_ms,
                                "error": True if is_error else None,
                            },
                        )
                        tool_results_for_claude.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": getattr(block, "id", ""),
                                "content": json.dumps(result, default=str, ensure_ascii=False),
                                "is_error": bool(is_error),
                            }
                        )

                    # Append assistant + user(tool_result) to messages for next round.
                    messages.append({"role": "assistant", "content": content})
                    messages.append({"role": "user", "content": tool_results_for_claude})

                # ── Post-stream hallucination guard (D-08) ────────────────
                unsupported = check_response(
                    accumulated_text,
                    accumulated_tool_results,
                    entity_whitelist=entity_whitelist,
                )
                if not unsupported:
                    break  # PASS — exit outer guard retry loop

                if guard_attempt < GUARD_RETRY_BUDGET:
                    # D-08: emit regenerate_notice + corrective user message.
                    yield ("regenerate_notice", {"reason": "hallucination_guard"})
                    base_messages = list(history) + [
                        {"role": "user", "content": user_text},
                        {
                            "role": "user",
                            "content": (
                                "Răspunsul anterior conținea numere/entități nesusținute "
                                f"de date: {unsupported[:5]}. Reformulează folosind doar "
                                "valori din rezultatele uneltelor."
                            ),
                        },
                    ]
                    continue
                else:
                    # D-07: second failure — stream Romanian fallback copy.
                    fallback_used = True
                    accumulated_text = GUARD_FALLBACK_TEXT
                    yield ("assistant_chunk", {"text": GUARD_FALLBACK_TEXT})
                    break

        except Exception as exc:  # noqa: BLE001 — sanitize per T-08-03
            self._log.exception("chat.run_turn_failed")
            yield (
                "error",
                {"code": "internal", "message_ro": "A apărut o problemă. Te rog încearcă din nou."},
            )
            return

        # ── 4. Finalize assistant message + emit done ──────────────────────
        # The stub row was inserted before the tool loop (see section 1) so
        # chat_tool_calls.message_id FK targets exist. Fill in real values now.
        duration_ms = int((perf_counter() - turn_start) * 1000)
        hallucination_flag = fallback_used
        try:
            await msg_repo.finalize_assistant_message(
                assistant_msg_id,
                content=accumulated_text,
                tokens_used=total_usage["input_tokens"] + total_usage["output_tokens"],
                duration_ms=duration_ms,
                hallucination_flag=hallucination_flag,
                regenerate_count=guard_attempt if not hallucination_flag else GUARD_RETRY_BUDGET,
            )
        except Exception:  # noqa: BLE001
            self._log.exception("chat.assistant_persist_failed")
            yield (
                "error",
                {"code": "internal", "message_ro": "A apărut o problemă. Te rog încearcă din nou."},
            )
            return

        # Persist all writes from this turn — without this, get_session's
        # `async with AsyncSessionLocal()` closes the session without committing
        # and SQLAlchemy rolls back EVERY write from the turn (user message,
        # assistant stub, tool_calls, finalize UPDATE). chat_messages stays
        # empty across all turns and history.load_history returns nothing on
        # follow-up turns. Plan 08-08 CR-05 refines this into per-section
        # commit boundaries; for now ONE final commit makes /chat usable.
        try:
            await self._session.commit()
        except Exception:  # noqa: BLE001 — sanitize per T-08-03
            self._log.exception("chat.turn_commit_failed")
            yield (
                "error",
                {"code": "internal", "message_ro": "A apărut o problemă. Te rog încearcă din nou."},
            )
            return

        # D-31 cost logging — structlog only, no DB column in MVP1.
        cost_usd = _compute_cost(total_usage)
        self._log.info(
            "chat.turn.complete",
            conversation_id=str(conversation_id),
            input_tokens=total_usage["input_tokens"],
            output_tokens=total_usage["output_tokens"],
            cache_read=total_usage["cache_read_input_tokens"],
            cost_usd=str(cost_usd),
            duration_ms=duration_ms,
            hallucination_flag=hallucination_flag,
        )

        yield (
            "done",
            {
                "message_id": str(assistant_msg_id),
                "total_input_tokens": total_usage["input_tokens"],
                "total_output_tokens": total_usage["output_tokens"],
                "duration_ms": duration_ms,
                "hallucination_flag": hallucination_flag,
            },
        )

        # ── 5. D-14: fire-and-forget title generation on turn 1 only ───────
        if is_first_turn:
            async def _update_title(cid: UUID, title: str) -> None:
                await conv_repo.update_title(cid, title)
                # The title generator runs detached — commit explicitly so
                # the UPDATE lands even after the main request closes.
                try:
                    await self._session.commit()
                except Exception:  # noqa: BLE001
                    pass

            try:
                schedule_title_generation(
                    conversation_id, user_text, accumulated_text, _update_title
                )
            except Exception:  # noqa: BLE001
                self._log.exception("chat.title_schedule_failed")

    # ──────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────

    async def _execute_tool(self, block: object) -> tuple[object, dict, bool, int]:
        """Execute a single tool_use block. Returns (block, result_dict, is_error, duration_ms).

        Tool handler exceptions are caught and translated to `{"error": "..."}`
        dicts with `is_error=True` so Anthropic receives a `tool_result` with
        `is_error: true` — Claude apologizes gracefully rather than hallucinating.
        """
        name = getattr(block, "name", "")
        raw_input = getattr(block, "input", {}) or {}
        t0 = perf_counter()
        tool = TOOLS_REGISTRY.get(name)
        if tool is None:
            duration_ms = int((perf_counter() - t0) * 1000)
            return block, {"error": f"unknown_tool:{name}"}, True, duration_ms
        try:
            validated = tool.input_schema.model_validate(raw_input)
            result = await tool.handler(self._tenant_id, self._session, validated)
            duration_ms = int((perf_counter() - t0) * 1000)
            return block, result, False, duration_ms
        except Exception as exc:  # noqa: BLE001
            duration_ms = int((perf_counter() - t0) * 1000)
            return block, {"error": str(exc)[:500]}, True, duration_ms


# ──────────────────────────────────────────────────────────────────────────
# Module-level helpers
# ──────────────────────────────────────────────────────────────────────────


def _compute_cost(total_usage: dict[str, int]) -> Decimal:
    """Compute USD cost via the same formula as Phase 5 InsightService.

    Claude Sonnet 4.5 pricing: $3/MTok input, $15/MTok output (SPEC.md §10).
    Cache reads are billed at the full input rate for MVP1 (Anthropic discounts
    cache_read at 10% of input rate — we apply that). Stored in structlog only.
    """
    input_tok = total_usage.get("input_tokens", 0)
    output_tok = total_usage.get("output_tokens", 0)
    return Decimal(str((input_tok / 1_000_000) * 3.0 + (output_tok / 1_000_000) * 15.0))


def _to_jsonable(value: object) -> object:
    """Recursively coerce Decimals to str + UUIDs to str + dates to ISO for JSONB."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:  # noqa: BLE001
            return str(value)
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, tuple):
        return [_to_jsonable(v) for v in value]
    return value
