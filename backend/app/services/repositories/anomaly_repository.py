from __future__ import annotations

"""Database write layer for Phase 4 detected_problems table.

Uses pg_insert().on_conflict_do_update() — atomic UPSERT.

Decisions:
  D-01: 3-column conflict target (tenant_id, date, rule_id) — one row per rule per day per tenant
  D-10: Mirrors MetricsRepository pattern exactly
  Pitfall 5: 3-col conflict target for detected_problems — same as source_daily_kpi
  Pitfall 6: tenant_id validated before INSERT — Core INSERT bypasses with_loader_criteria

CLAUDE.md Principle #3: tenant_id validated in every row dict before INSERT.
Raises ValueError loudly rather than inserting unscoped rows (Pitfall 6 —
with_loader_criteria fires only on ORM SELECT, NOT on Core INSERT).

Phase 4 Plan 03 — repository layer for AnomalyService writes.
"""

from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession


class AnomalyRepository:
    """Database write layer for Phase 4 detected_problems table.

    All writes use pg_insert().on_conflict_do_update() — atomic UPSERT.
    CLAUDE.md Principle #3: tenant_id validated in every row dict before INSERT.
    Raises ValueError loudly rather than inserting unscoped rows (Pitfall 6).
    """

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def upsert_detected_problem(self, row: dict) -> None:
        """Upsert a single detected_problems row.

        UPSERT conflict target: (tenant_id, date, rule_id) — 3-col unique key (D-01, Pitfall 5).
        Idempotent: safe to re-run for the same (tenant_id, date, rule_id) triple.

        Args:
            row: Dict matching DetectedProblem columns. MUST contain tenant_id.

        Raises:
            ValueError: If row is missing tenant_id or tenant_id is None (Pitfall 6).

        Notes:
            Does NOT call session.commit() — caller (detect_anomalies task) commits
            atomically after all rule upserts complete (WR-04 pattern from Phase 3).
        """
        # Validate tenant_id before INSERT — Core bypasses with_loader_criteria (Pitfall 6)
        if "tenant_id" not in row or row["tenant_id"] is None:
            raise ValueError(
                f"AnomalyRepository.upsert_detected_problem: row missing tenant_id — "
                f"date={row.get('date', '<unknown>')}, rule_id={row.get('rule_id', '<unknown>')}"
            )
        # Cross-tenant write guard (WR-01, CLAUDE.md Principle #3):
        # Core INSERT bypasses with_loader_criteria, so validate here that the
        # caller has not wired the wrong service-to-repository pair.
        if row["tenant_id"] != self._tenant_id:
            raise ValueError(
                f"AnomalyRepository.upsert_detected_problem: cross-tenant write blocked — "
                f"row.tenant_id={row['tenant_id']!r} != repository.tenant_id={self._tenant_id!r}"
            )

        from app.models.anomaly.detected_problem import DetectedProblem  # deferred — fork-safe

        # 3-col conflict target: exclude id + all 3 conflict-target columns from update set
        update_cols = [c for c in row if c not in {"id", "tenant_id", "date", "rule_id"}]
        stmt = pg_insert(DetectedProblem).values([row])
        stmt = stmt.on_conflict_do_update(
            index_elements=["tenant_id", "date", "rule_id"],
            set_={col: stmt.excluded[col] for col in update_cols},
        )
        # No commit — caller (detect_anomalies task) commits after all upserts (WR-04)
        await self._session.execute(stmt)
