from __future__ import annotations

"""InsightReadService — reads daily_insights rows for the FastAPI insights router.

Provides:
  get_today()       — returns yesterday's insight (Europe/Bucharest timezone)
  get_by_date(date) — returns insight for specific date, or None if absent

INSI-01: GET /insights/today queries daily_insights WHERE date = yesterday (Bucharest)
INSI-02: GET /insights?date=... returns 404 when service returns None
INSI-05: generation_failed=True when status in ('failed', 'fallback')
INSI-06: generated_at included in response

Phase 6 Plan 02 — read service for insights router in Plan 03.
"""

from datetime import date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.insights.daily_insight import DailyInsight

logger = structlog.get_logger(__name__)

BUCHAREST = ZoneInfo("Europe/Bucharest")


class InsightReadService:
    """Read-only service for querying DailyInsight rows.

    All queries filter by tenant_id (T-06-02-01).

    Usage:
        svc = InsightReadService(session, tenant_id)
        data = await svc.get_today()   # returns yesterday's insight or None
    """

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def get_today(self) -> dict | None:
        """Return yesterday's insight in Europe/Bucharest timezone, or None if absent.

        'Today's insight' means the insight generated for yesterday's data (pipeline
        runs at 06:00 for the previous day). Always queries date = yesterday_bucharest.

        Returns:
            Dict with {date, status, generation_failed, generated_at, payload} or None.
        """
        # Pitfall 6: GET /insights/today queries for YESTERDAY (Bucharest - 1 day)
        # because generate_daily_insights runs at 06:00 for the previous day's data.
        now_bucharest = datetime.now(BUCHAREST)
        yesterday = now_bucharest.date() - timedelta(days=1)
        return await self._fetch_for_date(yesterday)

    async def get_by_date(self, query_date: date) -> dict | None:
        """Return insight for a specific date, or None if no row exists.

        Args:
            query_date: The calendar date to look up.

        Returns:
            Dict with {date, status, generation_failed, generated_at, payload} or None.
            Router should raise HTTP 404 when None is returned (INSI-02).
        """
        return await self._fetch_for_date(query_date)

    async def _fetch_for_date(self, query_date: date) -> dict | None:
        """Internal: query DailyInsight for a specific date for this tenant.

        T-06-02-01: Filters by tenant_id.

        Args:
            query_date: The calendar date to query.

        Returns:
            Dict or None.
        """
        stmt = select(DailyInsight).where(
            DailyInsight.tenant_id == self._tenant_id,
            DailyInsight.date == query_date,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()

        if row is None:
            logger.bind(tenant_id=str(self._tenant_id)).debug(
                "insight.not_found", date=str(query_date)
            )
            return None

        # INSI-05: generation_failed when Claude failed or fallback was used
        generation_failed = row.status in ("failed", "fallback")

        return {
            "date": row.date,
            "status": row.status,
            "generation_failed": generation_failed,
            "generated_at": row.generated_at,
            "payload": row.payload_json,
        }
