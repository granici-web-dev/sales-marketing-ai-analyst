"""Phase 4 anomaly detection models package.

Re-exports the DetectedProblem SQLAlchemy ORM model class.
Import via: from app.models.anomaly import DetectedProblem

The model inherits TenantScopedMixin — every row is tenant-scoped.
Migration 007 creates the corresponding table and UNIQUE constraint.
"""

from __future__ import annotations

from app.models.anomaly.detected_problem import DetectedProblem

__all__ = ["DetectedProblem"]
