from __future__ import annotations

"""Fire-and-forget conversation title generator (Phase 8 D-14).

After the first assistant turn completes, the orchestrator schedules a separate
cheap Claude call to generate a 4-6 Romanian-word title. The call:

  1. Runs as a detached asyncio task (`asyncio.create_task`) so it does NOT
     block the user from sending the next message.
  2. Tries `claude-haiku-4-5` first; falls back to `claude-sonnet-4-5` on failure.
  3. Times out at 3 seconds per attempt.
  4. On both-failed: falls back to the user's truncated first message.
  5. Strips trailing punctuation and quotes from the generated title.

LM-8 mitigation: Python's asyncio garbage-collects orphan tasks. To prevent
that, we keep a strong reference in a module-level `_pending` set and discard
on completion via `task.add_done_callback(_pending.discard)`.

References:
  - .planning/phases/08-ai-chat/08-CONTEXT.md D-14 (auto-title via Haiku)
  - .planning/phases/08-ai-chat/08-RESEARCH.md §6 lines 994-1043
  - .planning/phases/08-ai-chat/08-PATTERNS.md § title_generator
"""

import asyncio
from collections.abc import Awaitable, Callable
from uuid import UUID

import structlog

# Module-level import for test patchability (LM-1 mitigation — same pattern as
# Phase 5 InsightService). Instantiation happens INSIDE _generate() — never at
# module level — to satisfy INFRA-05 fork-safety.
from anthropic import AsyncAnthropic


log = structlog.get_logger(__name__)


# Fire-and-forget task registry. The set holds strong references so Python's
# GC doesn't collect detached tasks mid-flight (LM-8). The discard callback
# removes the entry once the task completes.
_pending: set[asyncio.Task] = set()


# Model fallback chain — Haiku 4.5 primary (cheap), Sonnet 4.5 fallback.
TITLE_MODEL_PRIMARY = "claude-haiku-4-5"
TITLE_MODEL_FALLBACK = "claude-sonnet-4-5"
TITLE_TIMEOUT_S = 3.0
TITLE_MAX_TOKENS = 40
TITLE_TEMPERATURE = 0.3
TITLE_FALLBACK_MAX_LEN = 60  # truncated first-user-message length


UpdateCallback = Callable[[UUID, str], Awaitable[None]]


def schedule_title_generation(
    conversation_id: UUID,
    first_user: str,
    first_assistant: str,
    update_callback: UpdateCallback,
) -> None:
    """Fire-and-forget title generation. Returns immediately.

    LM-8: detaches via `_pending` set so GC can't drop the task.
    The `task.add_done_callback(_pending.discard)` line removes the task
    from the registry once it finishes (success or failure).

    Args:
        conversation_id: chat_conversations.id to update.
        first_user: text of the user's first message in this conversation.
        first_assistant: text of Claude's first assistant message.
        update_callback: async callable `(conversation_id, title) -> None` that
            persists the title (typically `ConversationRepository.update_title`
            wrapped to commit).
    """
    task = asyncio.create_task(
        _generate(conversation_id, first_user, first_assistant, update_callback)
    )
    _pending.add(task)
    task.add_done_callback(_pending.discard)


async def _generate(
    conversation_id: UUID,
    first_user: str,
    first_assistant: str,
    update_callback: UpdateCallback,
) -> None:
    """Run the actual Claude call(s) and invoke `update_callback` with the title.

    Tries Haiku, then Sonnet, then a truncated-first-user fallback. The
    structlog log line records WHICH model produced the title (or the fallback).
    """
    from app.core.config import settings  # local import — keeps module test-fast

    prompt = (
        "Generează un titlu de 4-6 cuvinte în română pentru această conversație, "
        "descriind tema principală. Răspunde DOAR cu titlul, fără punctuație finală "
        "sau ghilimele.\n\n"
        f"Întrebare utilizator: {first_user}\n\n"
        f"Răspuns asistent: {first_assistant[:500]}"
    )

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    for model in (TITLE_MODEL_PRIMARY, TITLE_MODEL_FALLBACK):
        try:
            resp = await asyncio.wait_for(
                client.messages.create(
                    model=model,
                    max_tokens=TITLE_MAX_TOKENS,
                    temperature=TITLE_TEMPERATURE,
                    messages=[{"role": "user", "content": prompt}],
                ),
                timeout=TITLE_TIMEOUT_S,
            )
        except asyncio.TimeoutError:
            log.warning("title.gen_timeout", model=model)
            continue
        except Exception as exc:  # noqa: BLE001 — defensive: any API failure
            log.warning("title.gen_failed", model=model, error=str(exc)[:100])
            continue

        title = _extract_title(resp)
        if title:
            try:
                await update_callback(conversation_id, title)
                log.info("title.generated", model=model, length=len(title))
            except Exception as exc:  # noqa: BLE001
                log.warning("title.callback_failed", error=str(exc)[:100])
            return

    # Both attempts failed — fall back to truncated first user message.
    fallback = _truncate_fallback(first_user)
    try:
        await update_callback(conversation_id, fallback)
        log.info("title.fallback_used", source="first_user_truncated")
    except Exception as exc:  # noqa: BLE001
        log.warning("title.callback_failed", error=str(exc)[:100])


def _extract_title(resp: object) -> str:
    """Pull the title string from a Messages API response and clean it.

    Strips surrounding quotes (`"..."`, `'...'`, `„..."` Romanian) and trailing
    `.,!?` punctuation per D-14 contract.
    """
    pieces: list[str] = []
    content = getattr(resp, "content", None) or []
    for block in content:
        if getattr(block, "type", None) == "text":
            text = getattr(block, "text", "")
            if isinstance(text, str):
                pieces.append(text)
    raw = "".join(pieces).strip()
    return _clean_title(raw)


def _clean_title(raw: str) -> str:
    """Strip surrounding quotes and trailing punctuation/whitespace.

    Iterates until the string is stable so combinations like `"...".` strip
    both the surrounding quote AND the trailing period regardless of order.
    """
    quote_chars = {'"', "'", "„", "”", "«", "»"}
    punct_chars = {".", ",", "!", "?"}
    s = raw.strip()
    while True:
        before = s
        # Strip surrounding quotes
        while s and s[0] in quote_chars:
            s = s[1:]
        while s and s[-1] in quote_chars:
            s = s[:-1]
        # Strip trailing punctuation
        while s and s[-1] in punct_chars:
            s = s[:-1]
        s = s.strip()
        if s == before:
            break
    return s


def _truncate_fallback(first_user: str) -> str:
    """Build the fallback title from the user's first message."""
    if len(first_user) <= TITLE_FALLBACK_MAX_LEN:
        return first_user.rstrip()
    return first_user[:TITLE_FALLBACK_MAX_LEN].rstrip() + "…"
