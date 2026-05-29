from __future__ import annotations

"""Unit tests for `app.services.chat.title_generator` (Plan 08-04 Task 2).

Coverage per <behavior> Tests TG1-TG5:
  - TG1: schedule_title_generation adds task to module-level _pending (LM-8)
  - TG2: primary=claude-haiku-4-5; falls back to claude-sonnet-4-5 on failure
  - TG3: 3s timeout twice → fallback to truncated first user message
  - TG4: on success, calls update_callback(conversation_id, title)
  - TG5: title stripped of final punctuation + quotes
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest


CONV_ID: UUID = uuid4()


def _build_message_response(title: str) -> MagicMock:
    """Build a fake Anthropic response with .content[0].text = title."""
    resp = MagicMock()
    block = MagicMock()
    block.type = "text"
    block.text = title
    resp.content = [block]
    return resp


class TestTitleGenerator:
    @pytest.mark.asyncio
    async def test_tg1_schedule_adds_task_to_pending_set(self) -> None:
        """LM-8: fire-and-forget task is retained in module-level _pending set."""
        from app.services.chat.title_generator import _pending, schedule_title_generation

        cb = AsyncMock()
        # Patch _generate to avoid real Anthropic call
        with patch("app.services.chat.title_generator._generate", new=AsyncMock()):
            schedule_title_generation(CONV_ID, "Test user msg", "Test assistant msg", cb)
            # Task should be in _pending (until it completes)
            # Snapshot pending IDs before yielding control
            snapshot = list(_pending)
            assert len(snapshot) >= 1
            # Drain
            await asyncio.gather(*snapshot, return_exceptions=True)
        # After completion the discard callback removes the task.

    @pytest.mark.asyncio
    async def test_tg2_falls_back_from_haiku_to_sonnet(self) -> None:
        from app.services.chat import title_generator as tg

        cb = AsyncMock()
        client = MagicMock()
        client.messages = MagicMock()

        # First call (Haiku) raises Exception; second call (Sonnet) returns title.
        primary_exc = RuntimeError("400 model not available")
        sonnet_resp = _build_message_response("Titlu generat de Sonnet")
        client.messages.create = AsyncMock(side_effect=[primary_exc, sonnet_resp])

        with patch.object(tg, "AsyncAnthropic", MagicMock(return_value=client)):
            await tg._generate(CONV_ID, "Întrebare?", "Răspuns.", cb)

        # 2 attempts: Haiku then Sonnet
        assert client.messages.create.await_count == 2
        # Models in order: Haiku first, Sonnet second
        first_model = client.messages.create.await_args_list[0].kwargs["model"]
        second_model = client.messages.create.await_args_list[1].kwargs["model"]
        assert first_model == "claude-haiku-4-5"
        assert second_model == "claude-sonnet-4-5"
        cb.assert_awaited_once_with(CONV_ID, "Titlu generat de Sonnet")

    @pytest.mark.asyncio
    async def test_tg3_both_timeout_falls_back_to_truncated_first_user(self) -> None:
        from app.services.chat import title_generator as tg

        cb = AsyncMock()
        client = MagicMock()
        client.messages = MagicMock()
        # Both attempts time out
        client.messages.create = AsyncMock(side_effect=asyncio.TimeoutError())

        with patch.object(tg, "AsyncAnthropic", MagicMock(return_value=client)):
            first_user = "Aceasta este o întrebare foarte lungă despre vânzările Sofa Belle din luna mai 2026 și cum merge echipa"
            await tg._generate(CONV_ID, first_user, "Răspuns.", cb)

        # Both attempts called
        assert client.messages.create.await_count == 2
        # Fallback: first_user[:60].rstrip() + "…" since len > 60
        expected = first_user[:60].rstrip() + "…"
        cb.assert_awaited_once_with(CONV_ID, expected)

    @pytest.mark.asyncio
    async def test_tg4_success_invokes_callback(self) -> None:
        from app.services.chat import title_generator as tg

        cb = AsyncMock()
        client = MagicMock()
        client.messages = MagicMock()
        client.messages.create = AsyncMock(
            return_value=_build_message_response("Vânzări mai 2026")
        )

        with patch.object(tg, "AsyncAnthropic", MagicMock(return_value=client)):
            await tg._generate(CONV_ID, "Cum stăm?", "Bine.", cb)

        cb.assert_awaited_once_with(CONV_ID, "Vânzări mai 2026")

    @pytest.mark.asyncio
    async def test_tg5_title_stripped_of_punctuation_and_quotes(self) -> None:
        from app.services.chat import title_generator as tg

        cb = AsyncMock()
        client = MagicMock()
        client.messages = MagicMock()
        # Claude returns a title with trailing period and surrounding quotes
        client.messages.create = AsyncMock(
            return_value=_build_message_response('"Vânzări mai 2026".')
        )

        with patch.object(tg, "AsyncAnthropic", MagicMock(return_value=client)):
            await tg._generate(CONV_ID, "Cum stăm?", "Bine.", cb)

        # Title should be stripped of quotes and trailing punctuation
        called_title = cb.await_args.args[1]
        assert called_title == "Vânzări mai 2026"

    def test_module_constants(self) -> None:
        from app.services.chat.title_generator import (
            TITLE_MODEL_FALLBACK,
            TITLE_MODEL_PRIMARY,
            TITLE_TIMEOUT_S,
            _pending,
        )

        assert TITLE_MODEL_PRIMARY == "claude-haiku-4-5"
        assert TITLE_MODEL_FALLBACK == "claude-sonnet-4-5"
        assert TITLE_TIMEOUT_S == 3.0
        assert isinstance(_pending, set)
