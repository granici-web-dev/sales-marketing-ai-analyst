from __future__ import annotations

# models package
#
# Importing all SQLAlchemy model classes here ensures Alembic's autogenerate
# can discover them when running `alembic revision --autogenerate`.
#
# See: https://alembic.sqlalchemy.org/en/latest/autogenerate.html
#      "Ensure the target_metadata refers to the MetaData of the Base class
#      that contains the mapped classes you want to autogenerate against."
#
# Phase 1 models
from app.models.pipeline import PipelineRun, SyncRun  # noqa: F401
from app.models.tenant import Tenant  # noqa: F401
from app.models.user import User  # noqa: F401

# Phase 2 models — MEFI CRM raw data storage
from app.models.mefi import MefiLeadHistory, MefiSalesperson, RawMefiLead  # noqa: F401

# Phase 3 models — metric tables (daily_kpi, salesperson_daily_kpi, source_daily_kpi)
from app.models.metrics import DailyKpi, SalespersonDailyKpi, SourceDailyKpi  # noqa: F401

# Phase 4 models — anomaly detection (detected_problems)
from app.models.anomaly import DetectedProblem  # noqa: F401

__all__ = [
    # Phase 1
    "PipelineRun",
    "SyncRun",
    "Tenant",
    "User",
    # Phase 2
    "RawMefiLead",
    "MefiLeadHistory",
    "MefiSalesperson",
    # Phase 3
    "DailyKpi",
    "SalespersonDailyKpi",
    "SourceDailyKpi",
    # Phase 4
    "DetectedProblem",
]
