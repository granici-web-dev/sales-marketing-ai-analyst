from __future__ import annotations

"""ConversationRepository — tenant + user scoped CRUD for `chat_conversations` (Phase 8).

D-15: soft archive via `archived` boolean — no hard delete in MVP1.
D-22: every method filters by `self._tenant_id` for defense in depth on top of
      the Phase 1 `with_loader_criteria` event listener that auto-applies the
      same predicate to ORM SELECTs.
WR-04: NO commit — caller commits atomically (mirrors Phase 5
       `InsightRepository.upsert_daily_insight`).
T-08-01: cross-tenant write attempts raise ValueError before the SQL round-trip.
CR-01 (Plan 08-07): per-user authorization — every method also filters by
      `self._user_id` to close cross-user-within-tenant reads/writes. The
      `chat_conversations.user_id` column exists (model docstring "owned by a
      single user inside a tenant") but was never used as a query predicate
      pre-08-07. Defense-in-depth on top of the tenant_id seam so a future
      contributor cannot accidentally fetch another user's conversation by
      constructing the repo with the wrong scope.
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatConversation


class ConversationRepository:
    """Persistence operations for chat_conversations within a (tenant, user) scope.

    All read/update methods filter by `(tenant_id, user_id)` so users within
    the same tenant cannot read or mutate each other's conversations (CR-01).

    The tenant_id predicate is also enforced by the Phase 1
    `with_loader_criteria` event listener for ORM SELECTs; we add the
    explicit filter in Core UPDATE statements because the loader criteria
    seam only applies to ORM SELECT. The user_id predicate is exclusively
    enforced here — the Phase 1 seam does not scope by user_id.
    """

    def __init__(self, session: AsyncSession, tenant_id: UUID, user_id: UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id
        self._user_id = user_id

    async def insert_conversation(self, row: dict) -> UUID:
        """INSERT a new chat conversation row. Returns the new id.

        Args:
            row: Dict matching ChatConversation columns. MUST contain tenant_id
                 and user_id, both matching the repository's scope.

        Raises:
            ValueError: if row missing tenant_id, tenant_id is None, or
                        row.tenant_id != repository.tenant_id (T-08-01 guard);
                        or row.user_id != repository.user_id (CR-01 guard).

        Notes:
            Does NOT commit — caller commits atomically (WR-04).
        """
        if "tenant_id" not in row or row["tenant_id"] is None:
            raise ValueError(
                "ConversationRepository.insert_conversation: row missing tenant_id"
            )
        if row["tenant_id"] != self._tenant_id:
            raise ValueError(
                "ConversationRepository.insert_conversation: cross-tenant write blocked "
                f"(row.tenant_id={row['tenant_id']!r} != repo.tenant_id={self._tenant_id!r})"
            )
        if "user_id" not in row or row["user_id"] is None:
            raise ValueError(
                "ConversationRepository.insert_conversation: row missing user_id"
            )
        if row["user_id"] != self._user_id:
            raise ValueError(
                "ConversationRepository.insert_conversation: cross-user write blocked "
                f"(row.user_id={row['user_id']!r} != repo.user_id={self._user_id!r})"
            )

        conv = ChatConversation(**row)
        self._session.add(conv)
        await self._session.flush()
        return conv.id

    async def list_conversations(
        self, *, archived: bool = False, limit: int = 50
    ) -> list[ChatConversation]:
        """List conversations for the (tenant, user) scope filtered by archived flag.

        D-15: default `archived=False` returns the active sidebar list.
        Ordered by `last_message_at DESC` per the sidebar query.

        Filters by tenant_id (defense in depth on top of with_loader_criteria)
        and user_id (CR-01 — Phase 1 seam does not scope by user_id).
        """
        stmt = (
            select(ChatConversation)
            .where(ChatConversation.tenant_id == self._tenant_id)
            .where(ChatConversation.user_id == self._user_id)
            .where(ChatConversation.archived == archived)
            .order_by(desc(ChatConversation.last_message_at))
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, conversation_id: UUID) -> ChatConversation | None:
        """Fetch a single conversation by id within the (tenant, user) scope.

        CR-01: returns None for any conversation NOT owned by self._user_id.
        We do NOT distinguish "row does not exist" from "row exists but is
        owned by another user" — both paths return None so callers can map
        both to a 404 without leaking existence information (see T-08-01b
        in 08-07-PLAN.md threat model).
        """
        stmt = (
            select(ChatConversation)
            .where(ChatConversation.tenant_id == self._tenant_id)
            .where(ChatConversation.user_id == self._user_id)
            .where(ChatConversation.id == conversation_id)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def update_title(self, conversation_id: UUID, title: str) -> None:
        """UPDATE the title (used by the D-14 title generator).

        CR-01: filtered by `(tenant_id, user_id)` — a cross-user title update
        is a silent no-op (zero rows matched), not an error. The caller is
        expected to have already verified ownership via `get_by_id`.
        """
        stmt = (
            update(ChatConversation)
            .where(ChatConversation.tenant_id == self._tenant_id)
            .where(ChatConversation.user_id == self._user_id)
            .where(ChatConversation.id == conversation_id)
            .values(title=title)
        )
        await self._session.execute(stmt)

    async def update_last_message_at(self, conversation_id: UUID) -> None:
        """UPDATE `last_message_at = now()` to bump the sidebar sort order.

        CR-01: filtered by `(tenant_id, user_id)`.
        """
        stmt = (
            update(ChatConversation)
            .where(ChatConversation.tenant_id == self._tenant_id)
            .where(ChatConversation.user_id == self._user_id)
            .where(ChatConversation.id == conversation_id)
            .values(last_message_at=datetime.now(timezone.utc))
        )
        await self._session.execute(stmt)

    async def soft_archive(self, conversation_id: UUID) -> None:
        """Soft archive — sets `archived=True` (D-15, no hard delete in MVP1).

        CR-01: filtered by `(tenant_id, user_id)` — a cross-user archive is
        a silent no-op. Combined with the router's `get_by_id` pre-check,
        the endpoint surfaces a 404 before this UPDATE ever fires for a
        cross-user request.
        """
        stmt = (
            update(ChatConversation)
            .where(ChatConversation.tenant_id == self._tenant_id)
            .where(ChatConversation.user_id == self._user_id)
            .where(ChatConversation.id == conversation_id)
            .values(archived=True)
        )
        await self._session.execute(stmt)
