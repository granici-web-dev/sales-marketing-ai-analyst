from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "ok"


class HealthDataResponse(BaseModel):
    """Data freshness response for GET /api/v1/health/data (UI-06, PIPE-04).

    last_sync_at: datetime of last completed MEFI sync run (nullable — None if never synced).
    last_pipeline_status: status string from last PipelineRun row (nullable — None if no runs).
    stale: True when now() - last_sync_at > 26 hours or last_sync_at is None.
    """

    last_sync_at: datetime | None
    last_pipeline_status: str | None
    stale: bool
