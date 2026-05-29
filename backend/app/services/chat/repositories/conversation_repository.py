from __future__ import annotations

"""ConversationRepository — tenant-scoped CRUD for `chat_conversations` (Phase 8 Plan 08-04).

D-15: soft archive via `archived` boolean — no hard delete in MVP1.
D-22: every method filters by `self._tenant_id` for defense in depth on top of
      the Phase 1 `with_loader_criteria` event listener that auto-applies the
      same predicate to ORM SELECTs.
WR-04: NO commit — caller commits atomically (mirrors Phase 5
       `InsightRepository.upsert_daily_insight`).
T-08-01: cross-tenant write attempts raise ValueError before the SQL round-trip.
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatConversation


class ConversationRepository:
    """Persistence operations for chat_conversations within a tenant.

    All methods inherit the implicit `tenant_id == self._tenant_id` predicate
    via TenantScopedMixin + with_loader_criteria for SELECTs, and add an
    explicit filter on UPDATEs so the with_loader_criteria seam (which only
    applies to ORM SELECT) cannot be bypassed by Core UPDATE statements.
    """

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def insert_conversation(self, row: dict) -> UUID:
        """INSERT a new chat conversation row. Returns the new id.

        Args:
            row: Dict matching ChatConversation columns. MUST contain tenant_id.

        Raises:
            ValueError: if row missing tenant_id, tenant_id is None, or
                        row.tenant_id != repository.tenant_id (T-08-01 guard).

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

        conv = ChatConversation(**row)
        self._session.add(conv)
        await self._session.flush()
        return conv.id

    async def list_conversations(
        self, *, archived: bool = False, limit: int = 50
    ) -> list[ChatConversation]:
        """List conversations for the tenant filtered by archived flag.

        D-15: default `archived=False` returns the active sidebar list.
        Ordered by `last_message_at DESC` per the sidebar query.

        The base SQL filters explicitly on `tenant_id` for defense in depth on
        top of the Phase 1 with_loader_criteria event listener.
        """
        stmt = (
            select(ChatConversation)
            .where(ChatConversation.tenant_id == self._tenant_id)
            .where(ChatConversation.archived == archived)
            .order_by(desc(ChatConversation.last_message_at))
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, conversation_id: UUID) -> ChatConversation | None:
        """Fetch a single conversation by id within the tenant scope."""
        stmt = (
            select(ChatConversation)
            .where(ChatConversation.tenant_id == self._tenant_id)
            .where(ChatConversation.id == conversation_id)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def update_title(self, conversation_id: UUID, title: str) -> None:
        """UPDATE the title (used by the D-14 title generator)."""
        stmt = (
            update(ChatConversation)
            .where(ChatConversation.tenant_id == self._tenant_id)
            .where(ChatConversation.id == conversation_id)
            .values(title=title)
        )
        await self._session.execute(stmt)

    async def update_last_message_at(self, conversation_id: UUID) -> None:
        """UPDATE `last_message_at = now()` to bump the sidebar sort order."""
        stmt = (
            update(ChatConversation)
            .where(ChatConversation.tenant_id == self._tenant_id)
            .where(ChatConversation.id == conversation_id)
            .values(last_message_at=datetime.now(timezone.utc))
        )
        await self._session.execute(stmt)

    async def soft_archive(self, conversation_id: UUID) -> None:
        """Soft archive — sets `archived=True` (D-15, no hard delete in MVP1)."""
        stmt = (
            update(ChatConversation)
            .where(ChatConversation.tenant_id == self._tenant_id)
            .where(ChatConversation.id == conversation_id)
            .values(archived=True)
        )
        await self._session.execute(stmt)
