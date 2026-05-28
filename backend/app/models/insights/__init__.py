from __future__ import annotations

"""Insights SQLAlchemy models package (Phase 5).

Re-exports the DailyInsight SQLAlchemy ORM model class.
Import via: from app.models.insights import DailyInsight

The model inherits TenantScopedMixin — every row is tenant-scoped.
Migration 008 creates the corresponding table and UNIQUE constraint.
"""

from app.models.insights.daily_insight import DailyInsight  # noqa: F401

__all__ = ["DailyInsight"]
