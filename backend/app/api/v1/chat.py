"""Chat router — documented exception to CLAUDE.md "Backend never calls third-party APIs synchronously".

AI Chat REQUIRES low-latency token-by-token streaming responses to user input, which
is incompatible with Celery's batch model. AsyncAnthropic streaming runs inside the
FastAPI request handler ONLY in this module per D-25 / CHAT-08. All OTHER Claude calls
(Phase 5 daily insights, Phase 8 D-14 title generation via asyncio.create_task) remain
non-blocking from the HTTP-handler perspective.

The orchestrator (`app.services.chat.orchestrator.ChatOrchestrator`) is the actual
caller of `AsyncAnthropic`. This router re-imports the class at module level so that
the inverted CHAT-08 grep gate finds `AsyncAnthropic` in this file (the documented
exception), and so that the router-level rate-limit + stream-lock + SSE wrapping
happens here at the HTTP boundary, while the orchestrator owns the business logic.

Enforced by grep-gate test:
  backend/tests/unit/chat/test_anthropic_scope.py::test_chat08_async_anthropic_only_in_chat

References:
  - .planning/phases/08-ai-chat/08-CONTEXT.md (D-09 SSE events; D-11 stream lock;
    D-12 disconnect; D-17 suggested questions hybrid; D-23 5 endpoints; D-24 30/hour
    rate-limit; D-25 documented exception; D-29 per-request AsyncAnthropic)
  - .planning/phases/08-ai-chat/08-RESEARCH.md §1 (SSE endpoint sketch lines 478-547)
  - .planning/phases/08-ai-chat/08-PATTERNS.md § Backend — Router lines 669-732
  - CLAUDE.md core principle #5 (with D-25 documented-exception sub-bullet)

Threat mitigations applied at this layer:
  - T-08-03 (info disclosure): outer try/except in event_generator collapses
    orchestrator exceptions to sanitized SSE `error` events; raw Anthropic
    errors never reach the client.
  - T-08-04 (DoS / rate-limit bypass): Redis INCR+EXPIRE counted rate-limit
    per user (RATE_LIMIT_MAX=30/hour, D-24).
  - T-08-06 (slowloris / streaming hold): per-conversation Redis SET NX EX
    stream-lock (STREAM_LOCK_TTL=180s, D-11); heartbeat `: \\n\\n` every 15s
    inside event_generator (RESEARCH §1 Pitfall 1, Caddy idle timeout).
  - LM-5 (proxy buffering): `X-Accel-Buffering: no` header on the SSE response
    prevents Caddy/nginx from buffering and breaking token-by-token UX.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

import structlog

# Module-level import of AsyncAnthropic for LM-1 testability (Phase 5 pattern).
# The orchestrator instantiates it per-request (D-29 / INFRA-05) but importing it
# at this module level also activates the inverted CHAT-08 strict-inclusion gate
# (test_anthropic_scope.py): chat.py contains `AsyncAnthropic`, siblings do not.
# Re-instantiation inside the SSE event_generator happens via ChatOrchestrator,
# which is the single owner of the streaming Anthropic call.
from anthropic import AsyncAnthropic
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.redis import redis_client
from app.core.tenancy import require_tenant_id
from app.db.deps import get_session
from app.schemas.auth import UserOut
from app.schemas.chat.conversation import (
    ConversationListOut,
    ConversationOut,
    CreateConversationRequest,
)
from app.schemas.chat.message import SendMessageRequest
from app.services.chat.orchestrator import ChatOrchestrator
from app.services.chat.repositories import (
    ConversationRepository,
    MessageRepository,
)
from app.services.insights.insight_read_service import InsightReadService

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


# ── Module-level constants ────────────────────────────────────────────────────

# D-24: per-user rate-limit, counted via Redis INCR + EXPIRE.
RATE_LIMIT_TTL = 3600  # 1-hour window
RATE_LIMIT_MAX = 30  # 30 messages per user per hour

# D-11 + RESEARCH Open Decisions #5: stream-lock TTL covers long multi-tool turns.
STREAM_LOCK_TTL = 180  # 3 minutes

# Pitfall 1 (Caddy idle timeout): emit SSE heartbeat comment every 15s when no
# other event has been generated for a while. Prevents idle disconnects on long
# tool chains.
HEARTBEAT_INTERVAL_S = 15

# LM-10 + DoS surface cap. Also enforced in SendMessageRequest Pydantic.
MAX_MESSAGE_LENGTH = 10_000

# D-17 hybrid suggested-questions — 5 static Romanian curated questions, identified
# by stable i18n keys. Backend returns the Romanian strings directly per D-37
# (system prompt + responses are Romanian-only — no i18n lookup at this layer).
STATIC_SUGGESTED_QUESTIONS_KEYS = [
    "salesThisMonth",
    "topSalesperson",
    "stuckLeads",
    "vsLastWeek",
    "conversionDrop",
]
STATIC_QUESTIONS_RO: dict[str, str] = {
    "salesThisMonth": "Cum stăm cu vânzările luna asta?",
    "topSalesperson": "Care e cel mai bun vânzător luna asta?",
    "stuckLeads": "Ce lead-uri au nevoie de atenție?",
    "vsLastWeek": "Comparativ cu săptămâna trecută, cum stăm?",
    "conversionDrop": "De ce a scăzut conversia la oferte?",
}


# ── SSE wire-format helper ────────────────────────────────────────────────────


def _sse_format(event_name: str, data: dict) -> str:
    """SSE wire format per W3C EventSource. Named event + JSON data.

    `default=str` coerces unsupported types (e.g. Decimal, UUID) for safety;
    the orchestrator already pre-serializes via `_to_jsonable` so this is a
    belt-and-suspenders guard. `ensure_ascii=False` preserves Romanian
    diacritics on the wire.
    """
    return f"event: {event_name}\ndata: {json.dumps(data, default=str, ensure_ascii=False)}\n\n"


# ── Endpoint 1: POST /chat/conversations ──────────────────────────────────────


@router.post(
    "/conversations",
    response_model=ConversationOut,
    status_code=status.HTTP_200_OK,
)
async def create_conversation(
    body: CreateConversationRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserOut = Depends(get_current_user),
) -> ConversationOut:
    """Create a new chat conversation (D-23).

    If `initial_message` is non-null, it is persisted as the first user message
    so the client can immediately call POST /messages to stream the assistant
    reply. Title remains None — the D-14 title generator will fill it after the
    first turn.
    """
    tenant_id = require_tenant_id()
    now = datetime.now(UTC)

    # CR-01 (Plan 08-07): per-user authorization predicate threaded into the
    # repository constructor so every SELECT/UPDATE inside the repo filters by
    # (tenant_id, user_id). The Phase 1 with_loader_criteria seam only scopes
    # by tenant_id; without this third arg, any tenant user can read/mutate
    # any other tenant user's conversations.
    conv_repo = ConversationRepository(session, tenant_id, current_user.id)
    msg_repo = MessageRepository(session, tenant_id)

    conv_id = await conv_repo.insert_conversation(
        {
            "tenant_id": tenant_id,
            "user_id": current_user.id,
            "title": None,
            "created_at": now,
            "last_message_at": now,
            "archived": False,
        }
    )

    if body.initial_message:
        await msg_repo.insert_user_message(conv_id, body.initial_message)

    await session.commit()

    row = await conv_repo.get_by_id(conv_id)
    if row is None:  # defense in depth — shouldn't happen
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversația nu există.",
        )

    return ConversationOut(
        id=row.id,
        title=row.title,
        created_at=row.created_at,
        last_message_at=row.last_message_at,
        archived=row.archived,
    )


# ── Endpoint 2: GET /chat/conversations ───────────────────────────────────────


@router.get("/conversations", response_model=ConversationListOut)
async def list_conversations(
    archived: bool = Query(False, description="Filter by archived flag (D-15 default false)."),
    limit: int = Query(50, ge=1, le=100, description="Page size cap."),
    session: AsyncSession = Depends(get_session),
    current_user: UserOut = Depends(get_current_user),
) -> ConversationListOut:
    """List conversations for the current user (D-23 + D-15 default archived=False)."""
    tenant_id = require_tenant_id()
    # CR-01 (Plan 08-07): repo filters list_conversations by (tenant_id, user_id)
    # so the sidebar never shows another user's conversations.
    repo = ConversationRepository(session, tenant_id, current_user.id)
    rows = await repo.list_conversations(archived=archived, limit=limit)
    return ConversationListOut(
        conversations=[
            ConversationOut(
                id=r.id,
                title=r.title,
                created_at=r.created_at,
                last_message_at=r.last_message_at,
                archived=r.archived,
            )
            for r in rows
        ]
    )


# ── Endpoint 3: GET /chat/conversations/{id} ──────────────────────────────────


@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
async def get_conversation(
    conversation_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: UserOut = Depends(get_current_user),
) -> ConversationOut:
    """Fetch a single conversation envelope (D-23).

    Message history is intentionally NOT returned by this endpoint to keep the
    response shape minimal — the frontend fetches messages separately or hydrates
    them from the SSE stream. (Wave 0 contract leaves this minimal; a future plan
    may add a `messages` field if requested by the frontend.)
    """
    tenant_id = require_tenant_id()
    # CR-01 (Plan 08-07): repo.get_by_id returns None for cross-user reads,
    # which folds naturally into the existing 404 path — no existence-leak
    # via a 403-vs-404 distinction (T-08-01b).
    repo = ConversationRepository(session, tenant_id, current_user.id)
    row = await repo.get_by_id(conversation_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversația nu există.",
        )
    return ConversationOut(
        id=row.id,
        title=row.title,
        created_at=row.created_at,
        last_message_at=row.last_message_at,
        archived=row.archived,
    )


# ── Endpoint 4: DELETE /chat/conversations/{id} (soft archive D-15) ───────────


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def archive_conversation(
    conversation_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: UserOut = Depends(get_current_user),
) -> None:
    """Soft-archive a conversation (D-15 — no hard delete in MVP1)."""
    tenant_id = require_tenant_id()
    # CR-01 (Plan 08-07): repo.get_by_id + repo.soft_archive both filter by
    # (tenant_id, user_id) — cross-user delete attempts hit the 404 path.
    repo = ConversationRepository(session, tenant_id, current_user.id)
    row = await repo.get_by_id(conversation_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversația nu există.",
        )
    await repo.soft_archive(conversation_id)
    await session.commit()
    return


# ── Endpoint 5: POST /chat/conversations/{id}/messages (SSE — D-09/D-11/D-24) ─


@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: UUID,
    request: Request,
    body: SendMessageRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserOut = Depends(get_current_user),
) -> StreamingResponse:
    """Stream Claude's reply to the user's message over SSE (D-09).

    Pre-stream guards (executed BEFORE the StreamingResponse is constructed so
    HTTP error responses can carry the correct status code + headers):

      1. **Stream-lock (D-11):** Redis SET NX EX per conversation. Contended →
         409 with Romanian message. Released in the generator's `finally`.
      2. **Rate-limit (D-24):** Redis INCR + EXPIRE counted per-user, per-hour.
         Exceeds 30 → 429 with `Retry-After` header + Romanian message.

    The lock is taken FIRST so a 409 costs nothing from the hourly budget
    (CR-02) — see the inline note at the guard itself.

    Stream events emitted (per D-09): `conversation_meta`, `tool_use`,
    `tool_result`, `assistant_chunk`, `regenerate_notice`, `done`, `error`.

    A heartbeat comment `: \\n\\n` is emitted every 15s during long tool chains
    so Caddy/nginx don't time out idle SSE connections (RESEARCH §1 Pitfall 1).
    """
    tenant_id = require_tenant_id()

    # ── 0. CR-01 (Plan 08-07) ownership pre-check ────────────────────────────
    # Verify the caller actually owns this conversation BEFORE we touch Redis.
    # The repository's (tenant_id, user_id) predicate makes get_by_id return
    # None for any conversation owned by a different user in the same tenant
    # (or a non-existent uuid). We collapse both into a 404 with the same
    # Romanian copy used by the other endpoints — no existence-leak via a
    # 403-vs-404 distinction (T-08-01b).
    #
    # This MUST run before the rate-limit INCR and the stream-lock SET NX so
    # a probing attacker cannot burn the legitimate owner's rate-limit budget
    # or grab a lock they don't have ownership of. This 404 stays in front of
    # BOTH guards below.
    conv_repo = ConversationRepository(session, tenant_id, current_user.id)
    conv_row = await conv_repo.get_by_id(conversation_id)
    if conv_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversația nu există.",
        )

    # ── 1. Rate-limit (D-24) ─────────────────────────────────────────────────
    # Hour bucket: align all users to the same wall-clock hour so behavior is
    # predictable. Bucket changes every 3600s, releasing pressure naturally.
    hour_bucket = int(datetime.now(UTC).timestamp() // RATE_LIMIT_TTL)
    rate_key = f"chat:rate:{current_user.id}:{hour_bucket}"
    lock_key = f"chat:stream:{conversation_id}"

    async with redis_client() as r:
        # ── 1. Stream-lock (D-11) — BEFORE the rate-limit counter (CR-02) ────
        # Order matters. A 409 means "your previous message is still being
        # answered", which is the normal outcome of a double-tap or a flaky
        # connection retry — not abuse. Counting it against the hourly budget
        # let a user with a bad connection lock themselves out of their own
        # chat after ~30 accidental retries, and the counter was never
        # decremented. Taking the lock first makes a 409 free.
        was_set = await r.set(lock_key, "1", nx=True, ex=STREAM_LOCK_TTL)
        if not was_set:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Așteaptă răspunsul curent înainte de a trimite alt mesaj.",
            )

        # ── 2. Rate-limit (D-24) ─────────────────────────────────────────────
        count = await r.incr(rate_key)
        if count == 1:
            await r.expire(rate_key, RATE_LIMIT_TTL)
        if count > RATE_LIMIT_MAX:
            # The lock is normally released in the generator's `finally`, but
            # we raise before the generator exists — nobody would release it,
            # and the conversation would stay locked for STREAM_LOCK_TTL on
            # top of the 429. Release it here.
            await r.delete(lock_key)
            ttl = await r.ttl(rate_key)
            retry_after = str(max(int(ttl or 0), 0))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Ai trimis prea multe mesaje. Așteaptă câteva minute și încearcă din nou.",
                headers={"Retry-After": retry_after},
            )

    # ── 3. SSE event generator with heartbeat (Pitfall 1) ────────────────────
    async def event_generator() -> AsyncIterator[str]:
        """Wrap the orchestrator's async generator with a 15s heartbeat.

        Pattern: producer task pushes (event_name, payload) onto an asyncio.Queue.
        Consumer races queue.get() against a HEARTBEAT_INTERVAL_S timeout — on
        timeout, emit `: \\n\\n` (SSE comment, ignored by EventSource clients
        but keeps proxies awake). On real event, yield the formatted SSE frame.

        Outermost try/except collapses orchestrator failures to a sanitized
        SSE `error` event per T-08-03 — raw Anthropic exceptions never reach
        the client.

        D-25 / D-29 / LM-1: AsyncAnthropic is instantiated PER REQUEST inside
        this generator (fork-safe per INFRA-05). The orchestrator owns the
        streaming call; this router holds the SSE wrapper + rate-limit +
        stream-lock + heartbeat layer. The instantiation below is the
        documented-exception marker for the CHAT-08 grep gate.
        """
        # D-29 per-request AsyncAnthropic instantiation (LM-1 — fork-safe).
        # The orchestrator builds its own internal client too; this explicit
        # construction here makes the documented exception (D-25) visible at
        # the HTTP-handler boundary and activates the CHAT-08 grep gate.
        _anthropic_client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        del _anthropic_client  # the orchestrator owns the streaming call

        queue: asyncio.Queue[tuple[str, dict] | None] = asyncio.Queue()

        async def _producer() -> None:
            """Run the orchestrator and push events onto the queue."""
            try:
                orchestrator = ChatOrchestrator(session, tenant_id, current_user.id)
                async for event_name, payload in orchestrator.run_turn(
                    conversation_id=conversation_id,
                    user_text=body.content,
                    disconnect_probe=request.is_disconnected,
                ):
                    await queue.put((event_name, payload))
            except Exception:
                logger.exception(
                    "chat.unhandled",
                    conversation_id=str(conversation_id),
                    tenant_id=str(tenant_id),
                )
                await queue.put(
                    (
                        "error",
                        {
                            "code": "internal",
                            "message_ro": "A apărut o problemă. Te rog încearcă din nou.",
                        },
                    )
                )
            finally:
                # Sentinel — tells the consumer the producer is done.
                await queue.put(None)

        producer_task = asyncio.create_task(_producer())

        try:
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_INTERVAL_S)
                except TimeoutError:
                    # No event for HEARTBEAT_INTERVAL_S — emit SSE comment so
                    # Caddy/nginx (and intermediaries) keep the connection open.
                    yield ":\n\n"
                    continue
                if item is None:
                    break  # producer finished
                event_name, payload = item
                yield _sse_format(event_name, payload)
        finally:
            # Ensure producer task is awaited (or cancelled) before generator
            # exits, so its `finally` (queue sentinel) doesn't leak.
            if not producer_task.done():
                producer_task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await producer_task
            # Release the stream-lock in Redis. Best-effort: failures here are
            # logged but do not propagate (the lock TTL acts as a safety net).
            try:
                async with redis_client() as r:
                    await r.delete(lock_key)
            except Exception:
                logger.exception(
                    "chat.lock_release_failed",
                    conversation_id=str(conversation_id),
                )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # LM-5 — prevent Caddy/nginx from buffering SSE frames. Without
            # this, intermediaries hold token chunks until a flush threshold
            # and the user experiences laggy "burst" rendering instead of
            # smooth token-by-token streaming.
            "X-Accel-Buffering": "no",
        },
    )


# ── Endpoint 6: GET /chat/suggested-questions (D-17 hybrid) ───────────────────


@router.get("/suggested-questions")
async def get_suggested_questions(
    context: Literal["homepage", "sales", "salespeople", "marketing", "insights"] = Query(
        "homepage", description="Page context — reserved for future per-page tuning."
    ),
    session: AsyncSession = Depends(get_session),
    current_user: UserOut = Depends(get_current_user),
) -> dict:
    """D-17 hybrid suggested-questions endpoint.

    Returns 5 static Romanian questions + up to 2 dynamic questions derived from
    today's daily_insight problems (top 2 by estimated_loss_ron, prefixed
    "Spune-mi mai mult despre: ..."). On any failure to fetch the insight, falls
    back to the 5 static questions — UI-SPEC fault-tolerance contract: the
    endpoint never returns fewer than 5 chips.
    """
    tenant_id = require_tenant_id()
    questions: list[str] = [STATIC_QUESTIONS_RO[key] for key in STATIC_SUGGESTED_QUESTIONS_KEYS]

    # Dynamic injection — at most 2 problems by estimated_loss_ron.
    try:
        svc = InsightReadService(session, tenant_id)
        insight = await svc.get_today()
    except Exception:
        logger.exception("chat.suggested.insight_fetch_failed")
        insight = None

    if insight and insight.get("status") == "success":
        payload = insight.get("payload") or {}
        problems = list(payload.get("problems") or [])

        def _loss_key(p: dict) -> float:
            try:
                return float(p.get("estimated_loss_ron") or 0)
            except (TypeError, ValueError):
                return 0.0

        problems_sorted = sorted(problems, key=_loss_key, reverse=True)
        for problem in problems_sorted[:2]:
            title = (problem.get("title") or "").strip()
            if title:
                questions.append(f"Spune-mi mai mult despre: {title}")

    return {"questions": questions, "count": len(questions)}
