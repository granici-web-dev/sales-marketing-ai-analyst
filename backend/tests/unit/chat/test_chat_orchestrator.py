from __future__ import annotations

"""Unit tests for `app.services.chat.orchestrator.ChatOrchestrator` (Plan 08-04 Task 3).

Coverage per <behavior> Tests O1-O13:
  - O1: construction + structlog bind
  - O2: run_turn yields (event_name, payload) tuples
  - O3: single-turn no-tool happy path (basic_turn cassette)
  - O4: single tool round + final text (events ordered)
  - O5: parallel dispatch of 3 distinct tools via asyncio.gather (multi_tool cassette)
  - O6: MAX_TOOL_ROUNDS=5 cap (loop bounded)
  - O7: hallucination guard PASS path → done.hallucination_flag=False
  - O8: guard FAIL round 1 + PASS round 2 → regenerate_notice + regenerate_count=1
  - O9: guard FAIL both rounds → Romanian fallback + hallucination_flag=True
  - O10: disconnect_probe mid-stream → returns early without persisting assistant
  - O11: title-gen scheduled on turn 1 only (history empty); not on turn 2+
  - O12: total_usage accumulates input + output + cache_read across rounds
  - O13: tool handler exception → tool_result error=True + chat_tool_calls.error set
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from tests.fixtures.anthropic_responses.basic_turn import BASIC_TURN_EVENTS, BASIC_TURN_TEXT


TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
USER_ID = UUID("00000000-0000-0000-0000-000000000010")
CONV_ID = UUID("00000000-0000-0000-0000-000000aaaaaa")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers — build a streaming context manager mock with a `get_final_message`
# ─────────────────────────────────────────────────────────────────────────────


def _build_final_message(
    *, stop_reason: str, content: list[Any] | None = None, usage: dict | None = None
) -> MagicMock:
    """Build a fake stream.get_final_message() return value."""
    msg = MagicMock()
    msg.stop_reason = stop_reason
    msg.content = content or []
    u = MagicMock()
    u.input_tokens = (usage or {}).get("input_tokens", 0)
    u.output_tokens = (usage or {}).get("output_tokens", 0)
    u.cache_read_input_tokens = (usage or {}).get("cache_read_input_tokens", 0)
    msg.usage = u
    return msg


def _build_stream_ctx(
    events: list[dict],
    final_msg: MagicMock,
) -> MagicMock:
    """Build an async-context-manager mock for `client.messages.stream(...)`."""

    async def _aiter():
        for evt in events:
            yield _wrap_event_namespace(evt)

    stream_obj = MagicMock()
    stream_obj.__aiter__ = lambda self: _aiter()
    stream_obj.get_final_message = AsyncMock(return_value=final_msg)
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=stream_obj)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


def _wrap_event_namespace(evt: dict) -> MagicMock:
    """Convert a dict-event from the recorded fixtures into a SimpleNamespace-like
    object with attribute access matching Anthropic's SSE event API surface."""
    m = MagicMock()
    m.type = evt.get("type")
    if "content_block" in evt:
        cb = MagicMock()
        for k, v in evt["content_block"].items():
            setattr(cb, k, v)
        m.content_block = cb
    if "delta" in evt:
        d = MagicMock()
        for k, v in evt["delta"].items():
            setattr(d, k, v)
        m.delta = d
    return m


def _build_text_block(text: str) -> MagicMock:
    """Build a fake Anthropic content block of type=text."""
    b = MagicMock()
    b.type = "text"
    b.text = text
    return b


def _build_tool_use_block(*, id: str, name: str, input: dict) -> MagicMock:
    """Build a fake Anthropic content block of type=tool_use."""
    b = MagicMock()
    b.type = "tool_use"
    b.id = id
    b.name = name
    b.input = input
    return b


async def _noop_disconnect() -> bool:
    return False


async def _drain(gen) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    async for evt in gen:
        out.append(evt)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Common patches for ChatOrchestrator runs
# ─────────────────────────────────────────────────────────────────────────────


def _orchestrator_patches(
    *,
    history: list[dict] | None = None,
    user_msg_id: UUID | None = None,
    assistant_msg_id: UUID | None = None,
    entity_whitelist: dict | None = None,
    guard_results: list[list[str]] | None = None,
):
    """Build a list of patches to neutralize repositories + helpers used by orchestrator.

    Returns: list of patch objects (start them yourself).
    """
    from app.services.chat import orchestrator as orch

    uid = user_msg_id or uuid4()
    aid = assistant_msg_id or uuid4()

    msg_repo = MagicMock()
    msg_repo.insert_user_message = AsyncMock(return_value=uid)
    msg_repo.insert_assistant_message = AsyncMock(return_value=aid)
    # finalize_assistant_message added with Option A fix (FK ordering): the
    # orchestrator inserts an assistant-message stub upfront so chat_tool_calls
    # FK targets exist, then finalizes after the tool loop. Tests mocking
    # msg_repo MUST stub this method or `await` raises on plain MagicMock.
    msg_repo.finalize_assistant_message = AsyncMock(return_value=None)
    msg_repo.load_history = AsyncMock(return_value=history if history is not None else [])

    conv_repo = MagicMock()
    conv_repo.update_title = AsyncMock()

    tool_repo = MagicMock()
    tool_repo.insert_tool_call = AsyncMock()

    patches = [
        patch.object(orch, "MessageRepository", MagicMock(return_value=msg_repo)),
        patch.object(orch, "ConversationRepository", MagicMock(return_value=conv_repo)),
        patch.object(orch, "ToolCallRepository", MagicMock(return_value=tool_repo)),
        patch.object(
            orch, "build_entity_whitelist", AsyncMock(return_value=entity_whitelist or {})
        ),
    ]
    if guard_results is not None:
        # Default check_response returns [] (PASS); when guard_results provided,
        # return them in order across attempts.
        check_mock = MagicMock(side_effect=guard_results)
        patches.append(patch.object(orch, "check_response", check_mock))
    else:
        patches.append(patch.object(orch, "check_response", MagicMock(return_value=[])))
    return patches, (uid, aid, msg_repo, conv_repo, tool_repo)


# ─────────────────────────────────────────────────────────────────────────────
# Test O1 + O2 — Construction
# ─────────────────────────────────────────────────────────────────────────────


class TestConstruction:
    def test_o1_constructor_binds_structlog(self) -> None:
        from app.services.chat.orchestrator import ChatOrchestrator

        session = AsyncMock()
        orch = ChatOrchestrator(session, TENANT_ID, USER_ID)
        assert orch._session is session
        assert orch._tenant_id == TENANT_ID
        # _log exists and has bind attribute
        assert orch._log is not None

    def test_module_constants(self) -> None:
        from app.services.chat.orchestrator import (
            HISTORY_LIMIT,
            MAX_TOKENS,
            MAX_TOOL_ROUNDS,
            MODEL,
            TEMPERATURE,
        )

        assert MODEL == "claude-sonnet-4-5"
        assert MAX_TOOL_ROUNDS == 5
        assert HISTORY_LIMIT == 20
        assert MAX_TOKENS == 4096
        assert isinstance(TEMPERATURE, float)


# ─────────────────────────────────────────────────────────────────────────────
# Test O3 — single-turn happy path (no tools, end_turn)
# ─────────────────────────────────────────────────────────────────────────────


class TestSingleTurnNoTool:
    @pytest.mark.asyncio
    async def test_o3_streams_assistant_chunks_and_done(self) -> None:
        from app.services.chat.orchestrator import ChatOrchestrator

        patches, (uid, aid, msg_repo, _, _) = _orchestrator_patches()

        final = _build_final_message(
            stop_reason="end_turn",
            content=[_build_text_block(BASIC_TURN_TEXT)],
            usage={"input_tokens": 1200, "output_tokens": 80},
        )

        client = MagicMock()
        client.messages = MagicMock()
        client.messages.stream = MagicMock(return_value=_build_stream_ctx(BASIC_TURN_EVENTS, final))

        from app.services.chat import orchestrator as orch

        with patch.object(orch, "AsyncAnthropic", MagicMock(return_value=client)):
            for p in patches:
                p.start()
            try:
                session = AsyncMock()
                o = ChatOrchestrator(session, TENANT_ID, USER_ID)
                events = await _drain(o.run_turn(CONV_ID, "Cum stăm?", _noop_disconnect))
            finally:
                for p in patches:
                    p.stop()

        names = [e[0] for e in events]
        # conversation_meta first
        assert names[0] == "conversation_meta"
        # Has assistant_chunks
        assert "assistant_chunk" in names
        # Ends with done; no tool_use / tool_result
        assert names[-1] == "done"
        assert "tool_use" not in names
        assert "regenerate_notice" not in names

        # User message persisted; assistant message persisted with hallucination_flag=False
        msg_repo.insert_user_message.assert_awaited_once()
        msg_repo.insert_assistant_message.assert_awaited_once()
        kwargs = msg_repo.insert_assistant_message.await_args.kwargs
        assert kwargs["hallucination_flag"] is False


# ─────────────────────────────────────────────────────────────────────────────
# Test O5 + O6 — Tool dispatch (parallel + cap)
# ─────────────────────────────────────────────────────────────────────────────


class TestToolDispatch:
    @pytest.mark.asyncio
    async def test_o5_parallel_dispatch_three_tools(self) -> None:
        """CHAT-02 SC#2: 3 distinct tools dispatched in parallel via asyncio.gather."""
        from app.services.chat import orchestrator as orch
        from app.services.chat.orchestrator import ChatOrchestrator

        patches, (uid, aid, msg_repo, _, tool_repo) = _orchestrator_patches()

        # Round 1: returns 3 tool_use blocks + stop_reason="tool_use"
        round1_final = _build_final_message(
            stop_reason="tool_use",
            content=[
                _build_tool_use_block(
                    id="toolu_1", name="get_funnel_data", input={"date_from": "2026-05-01", "date_to": "2026-05-29"}
                ),
                _build_tool_use_block(
                    id="toolu_2",
                    name="get_salesperson_performance",
                    input={"date_from": "2026-05-01", "date_to": "2026-05-29"},
                ),
                _build_tool_use_block(
                    id="toolu_3",
                    name="compare_periods",
                    input={
                        "period_a": {"from": "2026-05-01", "to": "2026-05-29"},
                        "period_b": {"from": "2026-04-01", "to": "2026-04-29"},
                        "metrics": ["leads_total"],
                    },
                ),
            ],
            usage={"input_tokens": 2400, "output_tokens": 320, "cache_read_input_tokens": 1800},
        )
        round1_events = [{"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Caut..."}}]

        # Round 2: returns final text, stop_reason=end_turn
        round2_final = _build_final_message(
            stop_reason="end_turn",
            content=[_build_text_block("Finalizat.")],
            usage={"input_tokens": 100, "output_tokens": 5},
        )
        round2_events = [{"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Finalizat."}}]

        # The stream mock returns different contexts on each call
        client = MagicMock()
        client.messages = MagicMock()
        client.messages.stream = MagicMock(
            side_effect=[
                _build_stream_ctx(round1_events, round1_final),
                _build_stream_ctx(round2_events, round2_final),
            ]
        )

        # Mock TOOLS_REGISTRY so tool handlers are no-op AsyncMocks
        tool_mock_1 = MagicMock()
        tool_mock_1.input_schema.model_validate = MagicMock(return_value=MagicMock())
        tool_mock_1.handler = AsyncMock(return_value={"funnel": 1})
        tool_mock_2 = MagicMock()
        tool_mock_2.input_schema.model_validate = MagicMock(return_value=MagicMock())
        tool_mock_2.handler = AsyncMock(return_value={"sales": 2})
        tool_mock_3 = MagicMock()
        tool_mock_3.input_schema.model_validate = MagicMock(return_value=MagicMock())
        tool_mock_3.handler = AsyncMock(return_value={"compare": 3})

        with patch.object(orch, "AsyncAnthropic", MagicMock(return_value=client)), patch.object(
            orch,
            "TOOLS_REGISTRY",
            {
                "get_funnel_data": tool_mock_1,
                "get_salesperson_performance": tool_mock_2,
                "compare_periods": tool_mock_3,
            },
        ), patch.object(orch, "get_all_tools", MagicMock(return_value=[])):
            for p in patches:
                p.start()
            try:
                session = AsyncMock()
                o = ChatOrchestrator(session, TENANT_ID, USER_ID)
                events = await _drain(o.run_turn(CONV_ID, "Compară lunile", _noop_disconnect))
            finally:
                for p in patches:
                    p.stop()

        names = [e[0] for e in events]
        # 3 tool_use + 3 tool_result events
        assert names.count("tool_use") == 3
        assert names.count("tool_result") == 3
        # All three handlers were invoked
        tool_mock_1.handler.assert_awaited_once()
        tool_mock_2.handler.assert_awaited_once()
        tool_mock_3.handler.assert_awaited_once()
        # Audit row written per tool
        assert tool_repo.insert_tool_call.await_count == 3

    @pytest.mark.asyncio
    async def test_o6_max_tool_rounds_cap_breaks_loop(self) -> None:
        """If Claude keeps returning stop_reason=tool_use, orchestrator stops at MAX_TOOL_ROUNDS."""
        from app.services.chat import orchestrator as orch
        from app.services.chat.orchestrator import ChatOrchestrator

        patches, (_, _, _, _, tool_repo) = _orchestrator_patches()

        # Build a final message that always says stop_reason=tool_use
        def _persistent_tool_use(round_n: int) -> MagicMock:
            return _build_final_message(
                stop_reason="tool_use",
                content=[
                    _build_tool_use_block(
                        id=f"toolu_{round_n}", name="get_kpi", input={"date_from": "x", "date_to": "y"}
                    )
                ],
                usage={"input_tokens": 100, "output_tokens": 10},
            )

        # 7 rounds available — but cap is 5
        client = MagicMock()
        client.messages = MagicMock()
        client.messages.stream = MagicMock(
            side_effect=[_build_stream_ctx([], _persistent_tool_use(i)) for i in range(10)]
        )

        tool_mock = MagicMock()
        tool_mock.input_schema.model_validate = MagicMock(return_value=MagicMock())
        tool_mock.handler = AsyncMock(return_value={"kpi": 1})

        with patch.object(orch, "AsyncAnthropic", MagicMock(return_value=client)), patch.object(
            orch, "TOOLS_REGISTRY", {"get_kpi": tool_mock}
        ), patch.object(orch, "get_all_tools", MagicMock(return_value=[])):
            for p in patches:
                p.start()
            try:
                session = AsyncMock()
                o = ChatOrchestrator(session, TENANT_ID, USER_ID)
                await _drain(o.run_turn(CONV_ID, "Tot tool_use", _noop_disconnect))
            finally:
                for p in patches:
                    p.stop()

        # MAX_TOOL_ROUNDS = 5 — handler invoked exactly 5 times (one per round
        # since each round returns 1 tool_use block) PER guard attempt. With
        # guard PASS on first attempt the outer loop runs once. Floor: ≤ 5.
        # We expect exactly 5 — the cap is the only thing stopping the loop.
        assert tool_mock.handler.await_count == 5
        assert tool_repo.insert_tool_call.await_count == 5


# ─────────────────────────────────────────────────────────────────────────────
# Test O7-O9 — Hallucination guard paths
# ─────────────────────────────────────────────────────────────────────────────


class TestHallucinationGuardPaths:
    @pytest.mark.asyncio
    async def test_o7_guard_pass_clean_done(self) -> None:
        """Guard returns [] → no regenerate_notice, hallucination_flag=False."""
        from app.services.chat import orchestrator as orch
        from app.services.chat.orchestrator import ChatOrchestrator

        patches, (_, _, _, _, _) = _orchestrator_patches(guard_results=[[]])

        final = _build_final_message(
            stop_reason="end_turn", content=[_build_text_block("Ok")], usage={"input_tokens": 100, "output_tokens": 5}
        )
        client = MagicMock()
        client.messages = MagicMock()
        client.messages.stream = MagicMock(return_value=_build_stream_ctx([], final))

        with patch.object(orch, "AsyncAnthropic", MagicMock(return_value=client)):
            for p in patches:
                p.start()
            try:
                session = AsyncMock()
                o = ChatOrchestrator(session, TENANT_ID, USER_ID)
                events = await _drain(o.run_turn(CONV_ID, "Cum stăm?", _noop_disconnect))
            finally:
                for p in patches:
                    p.stop()
        names = [e[0] for e in events]
        assert "regenerate_notice" not in names
        done_payload = next(p for n, p in events if n == "done")
        assert done_payload["hallucination_flag"] is False

    @pytest.mark.asyncio
    async def test_o8_guard_fail_then_pass(self) -> None:
        """Round 1 guard fails, regenerate_notice emitted, round 2 passes."""
        from app.services.chat import orchestrator as orch
        from app.services.chat.orchestrator import ChatOrchestrator

        patches, (_, _, msg_repo, _, _) = _orchestrator_patches(
            guard_results=[["number:99999"], []]
        )

        # Two streams — first round1 attempt, then round2 attempt after regenerate
        f1 = _build_final_message(
            stop_reason="end_turn",
            content=[_build_text_block("Cu 99.999 RON")],
            usage={"input_tokens": 100, "output_tokens": 5},
        )
        f2 = _build_final_message(
            stop_reason="end_turn",
            content=[_build_text_block("Răspuns corect.")],
            usage={"input_tokens": 50, "output_tokens": 3},
        )
        client = MagicMock()
        client.messages = MagicMock()
        client.messages.stream = MagicMock(
            side_effect=[_build_stream_ctx([], f1), _build_stream_ctx([], f2)]
        )

        with patch.object(orch, "AsyncAnthropic", MagicMock(return_value=client)):
            for p in patches:
                p.start()
            try:
                session = AsyncMock()
                o = ChatOrchestrator(session, TENANT_ID, USER_ID)
                events = await _drain(o.run_turn(CONV_ID, "Cum stăm?", _noop_disconnect))
            finally:
                for p in patches:
                    p.stop()

        names = [e[0] for e in events]
        assert "regenerate_notice" in names
        done_payload = next(p for n, p in events if n == "done")
        assert done_payload["hallucination_flag"] is False
        # Option A (FK fix): final state lives on `finalize_assistant_message`,
        # not the upfront stub call to `insert_assistant_message`.
        kwargs = msg_repo.finalize_assistant_message.await_args.kwargs
        assert kwargs["regenerate_count"] == 1

    @pytest.mark.asyncio
    async def test_o9_guard_fail_both_rounds_streams_fallback(self) -> None:
        """Both rounds fail → Romanian fallback + hallucination_flag=True (D-07)."""
        from app.services.chat import orchestrator as orch
        from app.services.chat.orchestrator import ChatOrchestrator

        patches, (_, _, msg_repo, _, _) = _orchestrator_patches(
            guard_results=[["number:99999"], ["number:88888"]]
        )
        f = _build_final_message(
            stop_reason="end_turn",
            content=[_build_text_block("Cifre inventate")],
            usage={"input_tokens": 100, "output_tokens": 5},
        )
        client = MagicMock()
        client.messages = MagicMock()
        client.messages.stream = MagicMock(
            side_effect=[_build_stream_ctx([], f), _build_stream_ctx([], f)]
        )

        with patch.object(orch, "AsyncAnthropic", MagicMock(return_value=client)):
            for p in patches:
                p.start()
            try:
                session = AsyncMock()
                o = ChatOrchestrator(session, TENANT_ID, USER_ID)
                events = await _drain(o.run_turn(CONV_ID, "Cum stăm?", _noop_disconnect))
            finally:
                for p in patches:
                    p.stop()

        names = [e[0] for e in events]
        assert "regenerate_notice" in names
        done_payload = next(p for n, p in events if n == "done")
        assert done_payload["hallucination_flag"] is True

        # Option A (FK fix): final state lives on finalize_assistant_message.
        # The upfront stub from insert_assistant_message always has
        # hallucination_flag=False / content="" / regenerate_count=0.
        kwargs = msg_repo.finalize_assistant_message.await_args.kwargs
        assert kwargs["hallucination_flag"] is True
        assert kwargs["regenerate_count"] == 1
        assert "Nu pot da un răspuns precis" in kwargs.get("content", "")


# ─────────────────────────────────────────────────────────────────────────────
# Test O10 — Disconnect mid-stream
# ─────────────────────────────────────────────────────────────────────────────


class TestDisconnectMidStream:
    @pytest.mark.asyncio
    async def test_o10_disconnect_returns_without_persisting_assistant(self) -> None:
        from app.services.chat import orchestrator as orch
        from app.services.chat.orchestrator import ChatOrchestrator

        patches, (_, _, msg_repo, _, _) = _orchestrator_patches()

        # Disconnect probe returns True immediately
        async def _disconnect_true() -> bool:
            return True

        f = _build_final_message(
            stop_reason="end_turn", content=[_build_text_block("partial")], usage={"input_tokens": 100, "output_tokens": 5}
        )
        client = MagicMock()
        client.messages = MagicMock()
        client.messages.stream = MagicMock(
            return_value=_build_stream_ctx(
                [{"type": "content_block_delta", "delta": {"type": "text_delta", "text": "X"}}], f
            )
        )

        with patch.object(orch, "AsyncAnthropic", MagicMock(return_value=client)):
            for p in patches:
                p.start()
            try:
                session = AsyncMock()
                o = ChatOrchestrator(session, TENANT_ID, USER_ID)
                events = await _drain(o.run_turn(CONV_ID, "Cum stăm?", _disconnect_true))
            finally:
                for p in patches:
                    p.stop()

        # User message WAS persisted. Option A (FK fix): the assistant-message
        # STUB is also inserted upfront (so chat_tool_calls FK targets exist);
        # the FINAL content is only written by finalize_assistant_message,
        # which is what disconnect must skip. The stub remains in DB with empty
        # content — an honest "started but never completed" audit row.
        msg_repo.insert_user_message.assert_awaited_once()
        msg_repo.insert_assistant_message.assert_awaited_once()
        msg_repo.finalize_assistant_message.assert_not_awaited()
        assert all(n != "done" for n, _ in events)


# ─────────────────────────────────────────────────────────────────────────────
# Test O11 — Title generation only on turn 1
# ─────────────────────────────────────────────────────────────────────────────


class TestTitleScheduling:
    @pytest.mark.asyncio
    async def test_o11_title_scheduled_when_history_empty(self) -> None:
        from app.services.chat import orchestrator as orch
        from app.services.chat.orchestrator import ChatOrchestrator

        patches, _ = _orchestrator_patches(history=[])

        f = _build_final_message(
            stop_reason="end_turn", content=[_build_text_block("Salut")], usage={"input_tokens": 100, "output_tokens": 5}
        )
        client = MagicMock()
        client.messages = MagicMock()
        client.messages.stream = MagicMock(return_value=_build_stream_ctx([], f))

        with patch.object(orch, "AsyncAnthropic", MagicMock(return_value=client)), patch.object(
            orch, "schedule_title_generation", MagicMock()
        ) as schedule_mock:
            for p in patches:
                p.start()
            try:
                session = AsyncMock()
                o = ChatOrchestrator(session, TENANT_ID, USER_ID)
                await _drain(o.run_turn(CONV_ID, "Cum stăm?", _noop_disconnect))
            finally:
                for p in patches:
                    p.stop()

        schedule_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_o11_title_not_scheduled_on_followup(self) -> None:
        from app.services.chat import orchestrator as orch
        from app.services.chat.orchestrator import ChatOrchestrator

        prior = [
            {"role": "user", "content": "Prima întrebare"},
            {"role": "assistant", "content": "Primul răspuns"},
        ]
        patches, _ = _orchestrator_patches(history=prior)

        f = _build_final_message(
            stop_reason="end_turn", content=[_build_text_block("Continuare")], usage={"input_tokens": 100, "output_tokens": 5}
        )
        client = MagicMock()
        client.messages = MagicMock()
        client.messages.stream = MagicMock(return_value=_build_stream_ctx([], f))

        with patch.object(orch, "AsyncAnthropic", MagicMock(return_value=client)), patch.object(
            orch, "schedule_title_generation", MagicMock()
        ) as schedule_mock:
            for p in patches:
                p.start()
            try:
                session = AsyncMock()
                o = ChatOrchestrator(session, TENANT_ID, USER_ID)
                await _drain(o.run_turn(CONV_ID, "Continuă", _noop_disconnect))
            finally:
                for p in patches:
                    p.stop()

        schedule_mock.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# Test O12 — Token accumulation
# ─────────────────────────────────────────────────────────────────────────────


class TestTokenAccumulation:
    @pytest.mark.asyncio
    async def test_o12_total_usage_summed_across_rounds(self) -> None:
        from app.services.chat import orchestrator as orch
        from app.services.chat.orchestrator import ChatOrchestrator

        patches, (_, _, msg_repo, _, _) = _orchestrator_patches()

        # Round 1: tool_use stop; Round 2: end_turn
        r1 = _build_final_message(
            stop_reason="tool_use",
            content=[_build_tool_use_block(id="toolu_a", name="get_kpi", input={"date_from": "x", "date_to": "y"})],
            usage={"input_tokens": 1000, "output_tokens": 100, "cache_read_input_tokens": 500},
        )
        r2 = _build_final_message(
            stop_reason="end_turn",
            content=[_build_text_block("Final")],
            usage={"input_tokens": 200, "output_tokens": 50, "cache_read_input_tokens": 0},
        )
        client = MagicMock()
        client.messages = MagicMock()
        client.messages.stream = MagicMock(
            side_effect=[_build_stream_ctx([], r1), _build_stream_ctx([], r2)]
        )

        tool_mock = MagicMock()
        tool_mock.input_schema.model_validate = MagicMock(return_value=MagicMock())
        tool_mock.handler = AsyncMock(return_value={"ok": True})

        with patch.object(orch, "AsyncAnthropic", MagicMock(return_value=client)), patch.object(
            orch, "TOOLS_REGISTRY", {"get_kpi": tool_mock}
        ), patch.object(orch, "get_all_tools", MagicMock(return_value=[])):
            for p in patches:
                p.start()
            try:
                session = AsyncMock()
                o = ChatOrchestrator(session, TENANT_ID, USER_ID)
                events = await _drain(o.run_turn(CONV_ID, "Test", _noop_disconnect))
            finally:
                for p in patches:
                    p.stop()

        done = next(p for n, p in events if n == "done")
        # Sums of input + output across both rounds
        assert done["total_input_tokens"] == 1200
        assert done["total_output_tokens"] == 150


# ─────────────────────────────────────────────────────────────────────────────
# Test O13 — Tool exception → tool_result(error=True) + audit row error populated
# ─────────────────────────────────────────────────────────────────────────────


class TestToolHandlerException:
    @pytest.mark.asyncio
    async def test_o13_tool_exception_yields_error_event_and_audit_row(self) -> None:
        from app.services.chat import orchestrator as orch
        from app.services.chat.orchestrator import ChatOrchestrator

        patches, (_, _, _, _, tool_repo) = _orchestrator_patches()

        r1 = _build_final_message(
            stop_reason="tool_use",
            content=[_build_tool_use_block(id="toolu_X", name="get_kpi", input={"date_from": "x", "date_to": "y"})],
            usage={"input_tokens": 100, "output_tokens": 10},
        )
        r2 = _build_final_message(
            stop_reason="end_turn",
            content=[_build_text_block("Recovery text.")],
            usage={"input_tokens": 50, "output_tokens": 5},
        )
        client = MagicMock()
        client.messages = MagicMock()
        client.messages.stream = MagicMock(
            side_effect=[_build_stream_ctx([], r1), _build_stream_ctx([], r2)]
        )

        # Tool handler raises
        tool_mock = MagicMock()
        tool_mock.input_schema.model_validate = MagicMock(return_value=MagicMock())
        tool_mock.handler = AsyncMock(side_effect=RuntimeError("DB connection lost"))

        with patch.object(orch, "AsyncAnthropic", MagicMock(return_value=client)), patch.object(
            orch, "TOOLS_REGISTRY", {"get_kpi": tool_mock}
        ), patch.object(orch, "get_all_tools", MagicMock(return_value=[])):
            for p in patches:
                p.start()
            try:
                session = AsyncMock()
                o = ChatOrchestrator(session, TENANT_ID, USER_ID)
                events = await _drain(o.run_turn(CONV_ID, "Test", _noop_disconnect))
            finally:
                for p in patches:
                    p.stop()

        # tool_result event must carry error=True
        tr = next(p for n, p in events if n == "tool_result")
        assert tr["error"] is True

        # chat_tool_calls audit row carries error
        tool_repo.insert_tool_call.assert_awaited_once()
        kwargs = tool_repo.insert_tool_call.await_args.kwargs
        assert kwargs["error"] is not None
        assert "DB connection lost" in kwargs["error"]


# ─────────────────────────────────────────────────────────────────────────────
# Test O13 + O14 — CR-05 commit boundaries, CR-03 detached title session
# ─────────────────────────────────────────────────────────────────────────────


class TestCommitBoundaries:
    @pytest.mark.asyncio
    async def test_o13_cr05_tool_audit_survives_assistant_persist_failure(self) -> None:
        """CR-05 / D-21: the audit rows must outlive the turn that fails.

        D-21 promises "every tool call writes exactly one row". Before this
        fix the orchestrator only flushed the audit rows and committed once,
        at the very end — so when finalizing the assistant message raised, the
        session rolled back and took every chat_tool_calls row with it. The
        record vanished on exactly the failure path worth recording.

        A flush is not a save. This asserts the commits, not the inserts.
        """
        from app.services.chat import orchestrator as orch
        from app.services.chat.orchestrator import ChatOrchestrator

        patches, (uid, aid, msg_repo, _, tool_repo) = _orchestrator_patches()

        round1_final = _build_final_message(
            stop_reason="tool_use",
            content=[
                _build_tool_use_block(
                    id="toolu_1",
                    name="get_funnel_data",
                    input={"date_from": "2026-05-01", "date_to": "2026-05-29"},
                )
            ],
            usage={"input_tokens": 2400, "output_tokens": 320},
        )
        round2_final = _build_final_message(
            stop_reason="end_turn",
            content=[_build_text_block("Finalizat.")],
            usage={"input_tokens": 100, "output_tokens": 5},
        )

        client = MagicMock()
        client.messages = MagicMock()
        client.messages.stream = MagicMock(
            side_effect=[
                _build_stream_ctx([], round1_final),
                _build_stream_ctx([], round2_final),
            ]
        )

        tool_mock = MagicMock()
        tool_mock.input_schema.model_validate = MagicMock(return_value=MagicMock())
        tool_mock.handler = AsyncMock(return_value={"funnel": 1})

        with patch.object(orch, "AsyncAnthropic", MagicMock(return_value=client)), patch.object(
            orch, "TOOLS_REGISTRY", {"get_funnel_data": tool_mock}
        ), patch.object(orch, "get_all_tools", MagicMock(return_value=[])):
            for p in patches:
                p.start()
            try:
                # The turn dies where CR-05 says it hurts most.
                msg_repo.finalize_assistant_message = AsyncMock(
                    side_effect=RuntimeError("assistant persist blew up")
                )
                session = AsyncMock()
                o = ChatOrchestrator(session, TENANT_ID, USER_ID)
                events = await _drain(o.run_turn(CONV_ID, "Compară lunile", _noop_disconnect))
            finally:
                for p in patches:
                    p.stop()

        # The turn did fail — otherwise this test proves nothing.
        assert events[-1][0] == "error"
        assert tool_repo.insert_tool_call.await_count == 1

        # Two boundaries closed before the failure: the user message (so the
        # ids handed to the frontend in conversation_meta are durable) and the
        # tool round. The final commit never runs on this path.
        assert session.commit.await_count >= 2, (
            "audit rows and the user message must be committed before the "
            f"assistant persist can roll them back; got {session.commit.await_count} commits"
        )

    @pytest.mark.asyncio
    async def test_o14_cr05_user_message_committed_before_conversation_meta(self) -> None:
        """CR-05: never advertise a UUID that a rollback can erase.

        `conversation_meta` tells the frontend which rows to swap its optimistic
        messages onto. Those rows have to exist by then.
        """
        from app.services.chat import orchestrator as orch
        from app.services.chat.orchestrator import ChatOrchestrator

        patches, (uid, aid, msg_repo, _, _) = _orchestrator_patches()

        final = _build_final_message(
            stop_reason="end_turn",
            content=[_build_text_block("Salut")],
            usage={"input_tokens": 100, "output_tokens": 5},
        )
        client = MagicMock()
        client.messages = MagicMock()
        client.messages.stream = MagicMock(return_value=_build_stream_ctx([], final))

        commits_at_meta: list[int] = []

        with patch.object(orch, "AsyncAnthropic", MagicMock(return_value=client)):
            for p in patches:
                p.start()
            try:
                session = AsyncMock()
                o = ChatOrchestrator(session, TENANT_ID, USER_ID)
                async for name, _payload in o.run_turn(CONV_ID, "Cum stăm?", _noop_disconnect):
                    if name == "conversation_meta":
                        commits_at_meta.append(session.commit.await_count)
            finally:
                for p in patches:
                    p.stop()

        assert commits_at_meta == [1], (
            "exactly one commit must have landed by the time conversation_meta "
            f"is emitted; saw {commits_at_meta}"
        )


class TestDetachedTitleSession:
    @pytest.mark.asyncio
    async def test_o15_cr03_title_callback_opens_its_own_session(self) -> None:
        """CR-03: the title arrives after the request's session is gone.

        `schedule_title_generation` fires a task that finishes ~3s later, by
        which point FastAPI's `get_session` dependency has closed the session
        the orchestrator ran on. The old callback committed on that dead
        session and swallowed the result with a bare `except: pass`, so every
        title in production silently failed to persist and nothing said so.

        The callback must therefore build its own session, its own repository
        scoped to the same (tenant, user), and commit there.
        """
        from app.services.chat import orchestrator as orch
        from app.services.chat.orchestrator import ChatOrchestrator
        from app.db import session as session_mod

        patches, (uid, aid, msg_repo, conv_repo, _) = _orchestrator_patches(history=[])

        final = _build_final_message(
            stop_reason="end_turn",
            content=[_build_text_block("Salut")],
            usage={"input_tokens": 100, "output_tokens": 5},
        )
        client = MagicMock()
        client.messages = MagicMock()
        client.messages.stream = MagicMock(return_value=_build_stream_ctx([], final))

        with patch.object(orch, "AsyncAnthropic", MagicMock(return_value=client)), patch.object(
            orch, "schedule_title_generation", MagicMock()
        ) as schedule_mock:
            for p in patches:
                p.start()
            try:
                session = AsyncMock()
                o = ChatOrchestrator(session, TENANT_ID, USER_ID)
                await _drain(o.run_turn(CONV_ID, "Cum stăm?", _noop_disconnect))
            finally:
                for p in patches:
                    p.stop()

        schedule_mock.assert_called_once()
        callback = schedule_mock.call_args.args[3]

        commits_before_callback = session.commit.await_count

        # Run the callback the way the detached task will: after the request's
        # session is long gone.
        detached = AsyncMock()
        factory_ctx = MagicMock()
        factory_ctx.__aenter__ = AsyncMock(return_value=detached)
        factory_ctx.__aexit__ = AsyncMock(return_value=None)
        factory = MagicMock(return_value=factory_ctx)

        repo_ctor = MagicMock(return_value=MagicMock(update_title=AsyncMock()))

        with patch.object(session_mod, "AsyncSessionLocal", factory), patch.object(
            orch, "ConversationRepository", repo_ctor
        ):
            await callback(CONV_ID, "Titlu generat")

        # Its own session, resolved through the module so a post-fork rebind
        # of AsyncSessionLocal is honoured (INFRA-05).
        factory.assert_called_once()
        detached.commit.assert_awaited_once()

        # Scoped to the same tenant AND user as the turn — CR-01 must not be
        # reopened through the back door of a detached task.
        assert repo_ctor.call_args.args[0] is detached
        assert repo_ctor.call_args.args[1] == TENANT_ID
        assert repo_ctor.call_args.args[2] == USER_ID

        # And it must not have touched the request's session.
        assert session.commit.await_count == commits_before_callback
