"""Base integration class for all external data sources.

All integrations (MEFI CRM, Meta Ads, Google Ads, TikTok Ads, GA4, GSC)
must inherit from BaseIntegration and implement the three abstract methods.

Source: docs/INTEGRATIONS.md — Common patterns / Base integration class
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SyncResult(BaseModel):
    """Result returned by integration.sync() after a completed sync run."""

    source: str
    started_at: datetime
    finished_at: datetime
    records_synced: int
    errors: list[str]
    status: str  # 'success' | 'partial' | 'failed'


class BaseIntegration(ABC):
    """Abstract base class for all external integrations.

    Each integration inherits this class and implements authenticate(),
    sync(), and health_check().

    CLAUDE.md conventions:
    - All I/O operations must be async/await.
    - Never call external APIs from HTTP handlers — only from Celery tasks.
    - Log at INFO level without PII.
    """

    source_name: str

    @abstractmethod
    async def authenticate(self, credentials: dict) -> bool:
        """Verify credentials are valid.

        Returns True if the credentials allow API access, False otherwise.
        Must NOT raise for auth failures — return False instead.
        """
        ...

    @abstractmethod
    async def sync(
        self,
        tenant_id: UUID,
        since: datetime | None = None,
    ) -> SyncResult:
        """Sync data from source into the database.

        Args:
            tenant_id: The tenant whose data to sync.
            since: If provided, only sync records changed after this datetime.
                   If None, perform a full (backfill) sync.

        Returns:
            SyncResult with outcome metrics.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Quick liveness probe for the integration.

        Returns True if the integration is reachable and responding,
        False if unreachable or returning empty data.
        Must NOT raise — return False on any error.
        """
        ...
