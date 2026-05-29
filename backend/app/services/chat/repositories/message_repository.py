from __future__ import annotations

"""MessageRepository — tenant-scoped persistence for `chat_messages` (Phase 8 Plan 08-04).

D-09: pre-allocated `assistant_msg_id` is honored so the SSE `conversation_meta`
      event carries the same UUID the row eventually persists with.
D-16: load_history follows the ANCHOR + RECENT strategy — keep the FIRST user
      message (topic anchor) and the most recent N-1 messages. Internal
      tool_use / tool_result rows are excluded from the API-facing history.
D-22: tenant_id explicit on every UPDATE (with_loader_criteria covers SELECT only).
WR-04: NO commit — caller commits atomically.
T-08-01: cross-tenant write attempts raise ValueError before the SQL round-trip.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import asc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatConversation, ChatMessage


class MessageRepository:
    """Persistence operations for chat_messages within a tenant."""

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def insert_user_message(self, conversation_id: UUID, content: str) -> UUID:
        """Persist a user message and bump the parent conversation's last_message_at.

        Tenant scoping is structural: `tenant_id` is sourced from `self._tenant_id`
        and never accepted as an argument, so cross-tenant write blocked by design
        — no row dict can carry a foreign tenant id into this method.

        Returns the new message UUID. Does NOT commit — caller commits.
        """
        new_id = uuid4()
        msg = ChatMessage(
            id=new_id,
            tenant_id=self._tenant_id,
            conversation_id=conversation_id,
            role="user",
            content=content,
            hallucination_flag=False,
            regenerate_count=0,
        )
        self._session.add(msg)
        await self._session.flush()

        # Bump parent conversation last_message_at (tenant_id explicit per D-22).
        bump = (
            update(ChatConversation)
            .where(ChatConversation.tenant_id == self._tenant_id)
            .where(ChatConversation.id == conversation_id)
            .values(last_message_at=datetime.now(timezone.utc))
        )
        await self._session.execute(bump)
        return new_id

    async def insert_assistant_message(
        self,
        conversation_id: UUID,
        content: str,
        *,
        tokens_used: int | None,
        duration_ms: int | None,
        hallucination_flag: bool,
        regenerate_count: int,
        message_id: UUID | None = None,
    ) -> UUID:
        """Persist an assistant message.

        `message_id` is the pre-allocated UUID emitted in the SSE `conversation_meta`
        event so the frontend's optimistic bubble identity matches the DB row.
        If omitted a fresh UUID is allocated.

        Returns the message UUID. Does NOT commit — caller commits.
        """
        new_id = message_id if message_id is not None else uuid4()
        msg = ChatMessage(
            id=new_id,
            tenant_id=self._tenant_id,
            conversation_id=conversation_id,
            role="assistant",
            content=content,
            tokens_used=tokens_used,
            duration_ms=duration_ms,
            hallucination_flag=hallucination_flag,
            regenerate_count=regenerate_count,
        )
        self._session.add(msg)
        await self._session.flush()

        bump = (
            update(ChatConversation)
            .where(ChatConversation.tenant_id == self._tenant_id)
            .where(ChatConversation.id == conversation_id)
            .values(last_message_at=datetime.now(timezone.utc))
        )
        await self._session.execute(bump)
        return new_id

    async def load_history(
        self, conversation_id: UUID, limit: int = 20
    ) -> list[dict[str, str]]:
        """Load conversation history scoped to user+assistant messages (D-16).

        ANCHOR + RECENT strategy (D-16):
          - If total messages <= limit: return all in chronological order.
          - Else: keep the FIRST user message (anchors topic) + the most recent
                   `limit - 1` messages. Older middle messages are dropped from
                   the Anthropic API call but remain in the DB for audit.

        Internal `tool_use` / `tool_result` rows are excluded — they're stored
        for audit but never replayed to Claude (the SDK re-binds tool blocks
        from the previous assistant turn during the multi-round loop).

        Returns:
            list of dicts shaped for the Anthropic Messages API:
              `[{"role": "user" | "assistant", "content": "..."}, ...]`
        """
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.tenant_id == self._tenant_id)
            .where(ChatMessage.conversation_id == conversation_id)
            .where(ChatMessage.role.in_(("user", "assistant")))
            .order_by(asc(ChatMessage.created_at))
        )
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())

        if len(rows) <= limit:
            keep = rows
        else:
            # D-16: first user message + most recent (limit - 1) messages.
            first_user = next((r for r in rows if r.role == "user"), None)
            recent = rows[-(limit - 1):]
            if first_user is not None and first_user not in recent:
                keep = [first_user, *recent]
            else:
                keep = recent

        return [
            {"role": r.role, "content": r.content or ""}
            for r in keep
        ]
