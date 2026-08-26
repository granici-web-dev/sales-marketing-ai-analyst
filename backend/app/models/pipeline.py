from __future__ import annotations

from datetime import datetime

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TIMESTAMPTZ, Base, TenantScopedMixin


class SyncRun(Base, TenantScopedMixin):
    """Tracks a single ETL sync run from an external data source.

    Records the source (mefi, meta_ads, google_ads, etc.), status, and
    performance metrics for each sync task execution. Written to by
    Celery ETL tasks (Phase 2+); read by the health dashboard endpoint.

    PIPE-04: This table is created in Phase 1 so the Phase 2 worker can
    write to it from day 1 without a schema migration.

    Inherits TenantScopedMixin:
      - id: UUID primary key
      - tenant_id: UUID NOT NULL
      - created_at / updated_at: TIMESTAMPTZ
    """

    __tablename__ = "sync_runs"

    source: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    records_synced: Mapped[int | None] = mapped_column(nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)


class PipelineRun(Base, TenantScopedMixin):
    """Tracks a single stage execution within the daily analytics pipeline.

    Records which pipeline stage ran (metrics_calculation, anomaly_detection,
    insight_generation, etc.), its status, and processing metrics.
    Written by Celery pipeline tasks (Phase 3+).

    PIPE-04: This table is created in Phase 1 so Phase 3 tasks can write
    to it without a schema migration.

    Inherits TenantScopedMixin:
      - id: UUID primary key
      - tenant_id: UUID NOT NULL
      - created_at / updated_at: TIMESTAMPTZ
    """

    __tablename__ = "pipeline_runs"

    stage: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    records_processed: Mapped[int | None] = mapped_column(nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_date: Mapped[datetime | None] = mapped_column(nullable=True)
    started_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)
