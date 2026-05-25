from __future__ import annotations

"""Phase 3 metric models package.

Re-exports all three metric table SQLAlchemy ORM model classes.
Import via: from app.models.metrics import DailyKpi, SalespersonDailyKpi, SourceDailyKpi

All three models inherit TenantScopedMixin — every row is tenant-scoped.
Migration 004 creates the corresponding tables and UNIQUE constraints.
"""

from app.models.metrics.daily_kpi import DailyKpi  # noqa: F401
from app.models.metrics.salesperson_kpi import SalespersonDailyKpi  # noqa: F401
from app.models.metrics.source_kpi import SourceDailyKpi  # noqa: F401

__all__ = [
    "DailyKpi",
    "SalespersonDailyKpi",
    "SourceDailyKpi",
]
