"""HealthReadService — queries sync_runs and pipeline_runs for data freshness.

Returns the data freshness health status for the GET /health/data endpoint.

UI-06: stale=True when last_sync_at is None or > 26h ago
PIPE-04: last_pipeline_status from PipelineRun most recent row

Phase 6 Plan 02 — read service for health router in Plan 03.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pipeline import PipelineRun, SyncRun

logger = structlog.get_logger(__name__)


class HealthReadService:
    """Read-only service for pipeline + sync health data.

    Queries the two most-recent rows from sync_runs (source='mefi') and
    pipeline_runs to determine data freshness.

    UI-06: stale=True when last mefi sync completed more than 26h ago or never.
    PIPE-04: last_pipeline_status from the most recent PipelineRun row.

    Usage:
        svc = HealthReadService(session, tenant_id)
        data = await svc.get_health()
    """

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def get_health(self) -> dict:
        """Return data freshness health status.

        T-06-02-01: Filters by tenant_id.

        Returns:
            Dict with {last_sync_at: datetime | None, last_pipeline_status: str | None, stale: bool}.
        """
        # Most recent mefi sync run
        stmt_sync = select(SyncRun.completed_at, SyncRun.status).where(
            SyncRun.tenant_id == self._tenant_id,
            SyncRun.source == "mefi",
        ).order_by(SyncRun.started_at.desc()).limit(1)

        # Most recent pipeline run
        stmt_pipeline = select(PipelineRun.status).where(
            PipelineRun.tenant_id == self._tenant_id,
        ).order_by(PipelineRun.started_at.desc()).limit(1)

        sync_result = await self._session.execute(stmt_sync)
        sync_row = sync_result.first()

        pipeline_result = await self._session.execute(stmt_pipeline)
        pipeline_row = pipeline_result.first()

        last_sync_at: datetime | None = sync_row.completed_at if sync_row else None
        last_pipeline_status: str | None = pipeline_row.status if pipeline_row else None

        # UI-06: stale when no sync run or sync completed more than 26h ago
        now_utc = datetime.now(UTC)
        if last_sync_at is None:
            stale = True
        else:
            # Ensure timezone-aware comparison (defensive: completed_at should be TIMESTAMPTZ)
            sync_dt = last_sync_at
            if sync_dt.tzinfo is None:
                sync_dt = sync_dt.replace(tzinfo=UTC)
            stale = (now_utc - sync_dt) > timedelta(hours=26)

        logger.bind(tenant_id=str(self._tenant_id)).info(
            "health.read",
            stale=stale,
            last_pipeline_status=last_pipeline_status,
        )

        return {
            "last_sync_at": last_sync_at,
            "last_pipeline_status": last_pipeline_status,
            "stale": stale,
        }
