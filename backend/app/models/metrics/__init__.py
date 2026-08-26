"""Phase 3 metric models package.

Re-exports all three metric table SQLAlchemy ORM model classes.
Import via: from app.models.metrics import DailyKpi, SalespersonDailyKpi, SourceDailyKpi

All three models inherit TenantScopedMixin — every row is tenant-scoped.
Migration 004 creates the corresponding tables and UNIQUE constraints.
"""

from __future__ import annotations

from app.models.metrics.daily_kpi import DailyKpi
from app.models.metrics.salesperson_kpi import SalespersonDailyKpi
from app.models.metrics.source_kpi import SourceDailyKpi

__all__ = [
    "DailyKpi",
    "SalespersonDailyKpi",
    "SourceDailyKpi",
]
