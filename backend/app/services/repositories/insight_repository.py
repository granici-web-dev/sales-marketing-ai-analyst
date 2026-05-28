from __future__ import annotations

"""Database write layer for Phase 5 daily_insights table.

Uses pg_insert().on_conflict_do_update() — atomic UPSERT on (tenant_id, date).

D-16: UPSERT conflict target: (tenant_id, date) — one row per tenant per day.
Pitfall 6: tenant_id validated before INSERT — Core INSERT bypasses with_loader_criteria.
WR-04: upsert_daily_insight does NOT commit — caller commits atomically.

CLAUDE.md Principle #3: tenant_id validated in every row dict before INSERT.
Raises ValueError loudly rather than inserting unscoped rows (Pitfall 6 —
with_loader_criteria fires only on ORM SELECT, NOT on Core INSERT).

Phase 5 Plan 03 — repository layer for InsightService writes.
"""

from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession


class InsightRepository:
    """Database write layer for Phase 5 daily_insights table.

    All writes use pg_insert().on_conflict_do_update() — atomic UPSERT.
    CLAUDE.md Principle #3: tenant_id validated in every row dict before INSERT.
    Raises ValueError loudly rather than inserting unscoped rows (Pitfall 6).
    """

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def upsert_daily_insight(self, row: dict) -> None:
        """UPSERT daily_insights row.

        Conflict target: (tenant_id, date) — one row per tenant per day (D-16).
        Does NOT commit — caller commits atomically (WR-04).

        Args:
            row: Dict matching DailyInsight columns. MUST contain tenant_id.

        Raises:
            ValueError: If row is missing tenant_id, tenant_id is None, or
                        row.tenant_id != repository.tenant_id (Pitfall 6 cross-tenant guard).

        Notes:
            Does NOT call session.commit() — caller (generate_daily_insights task) commits
            atomically after all writes complete (WR-04 pattern from Phase 3/4).
        """
        # Validate tenant_id present and not None — Core INSERT bypasses with_loader_criteria (Pitfall 6)
        if "tenant_id" not in row or row["tenant_id"] is None:
            raise ValueError(
                f"InsightRepository.upsert_daily_insight: row missing tenant_id — "
                f"date={row.get('date', '<unknown>')}"
            )

        # Cross-tenant write guard (WR-01, CLAUDE.md Principle #3):
        # Core INSERT bypasses with_loader_criteria, so validate here that the
        # caller has not wired the wrong service-to-repository pair.
        if row["tenant_id"] != self._tenant_id:
            raise ValueError(
                f"InsightRepository.upsert_daily_insight: cross-tenant write blocked — "
                f"row.tenant_id={row['tenant_id']!r} != repository.tenant_id={self._tenant_id!r}"
            )

        from app.models.insights.daily_insight import DailyInsight  # noqa: PLC0415 — deferred, fork-safe

        # 2-col conflict target: exclude id + conflict-target cols from update set (D-16)
        update_cols = [c for c in row if c not in {"id", "tenant_id", "date"}]
        stmt = pg_insert(DailyInsight).values([row])
        stmt = stmt.on_conflict_do_update(
            index_elements=["tenant_id", "date"],
            set_={col: stmt.excluded[col] for col in update_cols},
        )
        # No commit — caller (generate_daily_insights task) commits after all writes (WR-04)
        await self._session.execute(stmt)
