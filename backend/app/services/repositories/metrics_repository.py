"""Database write layer for Phase 3 metric tables.

All writes use pg_insert().on_conflict_do_update() — atomic UPSERT.

CLAUDE.md Principle #3: tenant_id validated in every row dict before INSERT.
Raises ValueError loudly rather than inserting unscoped rows (Pitfall 6 —
with_loader_criteria fires only on ORM SELECT, NOT on Core INSERT).

Conflict targets per table (Pitfall 5):
  - daily_kpi:              (tenant_id, date)
  - salesperson_daily_kpi:  (tenant_id, salesperson_external_id, date)
  - source_daily_kpi:       (tenant_id, source, date)  ← 3-col, easy to miss

Phase 3 Plan 03 — repository layer for MetricsService writes.
"""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from sqlalchemy import CursorResult
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession


class MetricsRepository:
    """Database write layer for Phase 3 metric tables.

    All writes use pg_insert().on_conflict_do_update() — atomic UPSERT.
    CLAUDE.md Principle #3: tenant_id validated in every row dict before INSERT.
    Raises ValueError loudly rather than inserting unscoped rows (Pitfall 6).
    """

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def upsert_daily_kpi(self, row: dict) -> None:
        """Upsert a single daily_kpi row.

        UPSERT conflict target: (tenant_id, date) — 2-col unique key.
        Idempotent: safe to re-run for the same (tenant_id, date) pair.

        Args:
            row: Dict matching DailyKpi columns. MUST contain tenant_id.

        Raises:
            ValueError: If row is missing tenant_id or tenant_id is None (Pitfall 6).
        """
        # Validate tenant_id before INSERT — Core bypasses with_loader_criteria (Pitfall 6)
        if "tenant_id" not in row or row["tenant_id"] is None:
            raise ValueError(
                f"MetricsRepository.upsert_daily_kpi: row missing tenant_id — "
                f"date={row.get('date', '<unknown>')}"
            )

        from app.models.metrics.daily_kpi import DailyKpi  # deferred — fork-safe

        update_cols = [c for c in row if c not in {"id", "tenant_id", "date"}]
        stmt = pg_insert(DailyKpi).values([row])
        stmt = stmt.on_conflict_do_update(
            index_elements=["tenant_id", "date"],
            set_={col: stmt.excluded[col] for col in update_cols},
        )
        # WR-04 FIX: removed self._session.commit() here. The task in
        # calculate_daily_kpis.py commits after all three upserts complete,
        # making the three metric table writes atomic. A commit here breaks
        # atomicity: a failure between upsert_daily_kpi and upsert_salesperson_kpis
        # would leave daily_kpi updated but salesperson_daily_kpi stale.
        await self._session.execute(stmt)

    async def upsert_salesperson_kpi(self, row: dict) -> int:
        """Upsert a single salesperson_daily_kpi row.

        UPSERT conflict target: (tenant_id, salesperson_external_id, date) — 3-col key.
        Idempotent: safe to re-run.

        Args:
            row: Dict matching SalespersonDailyKpi columns. MUST contain tenant_id.

        Returns:
            Number of rows affected.

        Raises:
            ValueError: If row is missing tenant_id or tenant_id is None (Pitfall 6).
        """
        if "tenant_id" not in row or row["tenant_id"] is None:
            raise ValueError(
                f"MetricsRepository.upsert_salesperson_kpi: row missing tenant_id — "
                f"salesperson_external_id={row.get('salesperson_external_id', '<unknown>')}, "
                f"date={row.get('date', '<unknown>')}"
            )

        from app.models.metrics.salesperson_kpi import SalespersonDailyKpi  # deferred — fork-safe

        update_cols = [
            c for c in row if c not in {"id", "tenant_id", "salesperson_external_id", "date"}
        ]
        stmt = pg_insert(SalespersonDailyKpi).values([row])
        stmt = stmt.on_conflict_do_update(
            index_elements=["tenant_id", "salesperson_external_id", "date"],
            set_={col: stmt.excluded[col] for col in update_cols},
        )
        # WR-04 FIX: removed self._session.commit() — caller (task) commits atomically.
        result = cast("CursorResult[Any]", await self._session.execute(stmt))
        return result.rowcount

    async def upsert_salesperson_kpis(self, rows: list[dict]) -> int:
        """Upsert a list of salesperson_daily_kpi rows.

        Short-circuits on empty input (Pitfall 6 short-circuit).

        Args:
            rows: List of dicts, each MUST contain tenant_id.

        Returns:
            Total rows affected.

        Raises:
            ValueError: If any row is missing tenant_id or tenant_id is None.
        """
        if not rows:
            return 0

        for row in rows:
            if "tenant_id" not in row or row["tenant_id"] is None:
                raise ValueError(
                    f"MetricsRepository.upsert_salesperson_kpis: row missing tenant_id — "
                    f"salesperson_external_id={row.get('salesperson_external_id', '<unknown>')}, "
                    f"date={row.get('date', '<unknown>')}"
                )

        from app.models.metrics.salesperson_kpi import SalespersonDailyKpi  # deferred — fork-safe

        # Use first row to determine update columns (all rows share the same schema)
        update_cols = [
            c for c in rows[0] if c not in {"id", "tenant_id", "salesperson_external_id", "date"}
        ]

        total = 0
        for row in rows:
            stmt = pg_insert(SalespersonDailyKpi).values([row])
            stmt = stmt.on_conflict_do_update(
                index_elements=["tenant_id", "salesperson_external_id", "date"],
                set_={col: stmt.excluded[col] for col in update_cols},
            )
            result = cast("CursorResult[Any]", await self._session.execute(stmt))
            total += result.rowcount
        await self._session.commit()
        return total

    async def upsert_source_kpi(self, row: dict) -> int:
        """Upsert a single source_daily_kpi row.

        UPSERT conflict target: (tenant_id, source, date) — 3-col key (Pitfall 5).

        Args:
            row: Dict matching SourceDailyKpi columns. MUST contain tenant_id.

        Returns:
            Number of rows affected.

        Raises:
            ValueError: If row is missing tenant_id or tenant_id is None (Pitfall 6).
        """
        if "tenant_id" not in row or row["tenant_id"] is None:
            raise ValueError(
                f"MetricsRepository.upsert_source_kpi: row missing tenant_id — "
                f"source={row.get('source', '<unknown>')}, "
                f"date={row.get('date', '<unknown>')}"
            )

        from app.models.metrics.source_kpi import SourceDailyKpi  # deferred — fork-safe

        update_cols = [c for c in row if c not in {"id", "tenant_id", "source", "date"}]
        stmt = pg_insert(SourceDailyKpi).values([row])
        stmt = stmt.on_conflict_do_update(
            index_elements=["tenant_id", "source", "date"],
            set_={col: stmt.excluded[col] for col in update_cols},
        )
        # WR-04 FIX: removed self._session.commit() — caller (task) commits atomically.
        result = cast("CursorResult[Any]", await self._session.execute(stmt))
        return result.rowcount

    async def upsert_source_kpis(self, rows: list[dict]) -> int:
        """Upsert a list of source_daily_kpi rows.

        Short-circuits on empty input (Pitfall 6 short-circuit).
        3-col conflict target: (tenant_id, source, date) — Pitfall 5.

        Args:
            rows: List of dicts, each MUST contain tenant_id and source.

        Returns:
            Total rows affected.

        Raises:
            ValueError: If any row is missing tenant_id or tenant_id is None.
        """
        if not rows:
            return 0

        for row in rows:
            if "tenant_id" not in row or row["tenant_id"] is None:
                raise ValueError(
                    f"MetricsRepository.upsert_source_kpis: row missing tenant_id — "
                    f"source={row.get('source', '<unknown>')}, "
                    f"date={row.get('date', '<unknown>')}"
                )

        from app.models.metrics.source_kpi import SourceDailyKpi  # deferred — fork-safe

        update_cols = [c for c in rows[0] if c not in {"id", "tenant_id", "source", "date"}]

        total = 0
        for row in rows:
            stmt = pg_insert(SourceDailyKpi).values([row])
            stmt = stmt.on_conflict_do_update(
                index_elements=["tenant_id", "source", "date"],
                set_={col: stmt.excluded[col] for col in update_cols},
            )
            result = cast("CursorResult[Any]", await self._session.execute(stmt))
            total += result.rowcount
        await self._session.commit()
        return total
