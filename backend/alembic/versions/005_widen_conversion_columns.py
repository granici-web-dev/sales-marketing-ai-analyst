from __future__ import annotations

"""Widen conversion rate columns from NUMERIC(5,4) to NUMERIC(8,4).

Revision ID: 005
Revises: 004
Create Date: 2026-05-28

Root cause: daily cohort-independent counts produce ratios > 9.9999 (e.g. 13
offers / 1 visit = 13.0) which overflow NUMERIC(5,4). NUMERIC(8,4) allows up
to 9999.9999, matching the existing *_wow_delta / *_mom_delta columns.

Affected tables and columns:
  daily_kpi:             conversion_l_to_v, conversion_v_to_o, conversion_l_to_o,
                         conversion_o_to_c, conversion_l_to_c
  salesperson_daily_kpi: conversion_l_to_v, conversion_v_to_o, conversion_o_to_c,
                         conversion_l_to_c
  source_daily_kpi:      conversion_rate

Note: daily_kpi.web_conversion_rate (also NUMERIC(5,4)) is populated by GA4
      (Phase 4+) and excluded from this migration per Phase 3 scope.

Downgrade: narrows back to NUMERIC(5,4). Will fail if any stored value exceeds
           9.9999 — truncate or NULL affected rows first if needed.
"""

import sqlalchemy as sa
from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None

# Columns that receive the same type change in each table
_DAILY_KPI_COLS = [
    "conversion_l_to_v",
    "conversion_v_to_o",
    "conversion_l_to_o",
    "conversion_o_to_c",
    "conversion_l_to_c",
]

_SALESPERSON_KPI_COLS = [
    "conversion_l_to_v",
    "conversion_v_to_o",
    "conversion_o_to_c",
    "conversion_l_to_c",
]

_SOURCE_KPI_COLS = [
    "conversion_rate",
]

_WIDE = sa.Numeric(8, 4)
_NARROW = sa.Numeric(5, 4)


def upgrade() -> None:
    for col in _DAILY_KPI_COLS:
        op.alter_column(
            "daily_kpi",
            col,
            existing_type=_NARROW,
            type_=_WIDE,
            existing_nullable=True,
            postgresql_using=f"{col}::numeric(8,4)",
        )

    for col in _SALESPERSON_KPI_COLS:
        op.alter_column(
            "salesperson_daily_kpi",
            col,
            existing_type=_NARROW,
            type_=_WIDE,
            existing_nullable=True,
            postgresql_using=f"{col}::numeric(8,4)",
        )

    for col in _SOURCE_KPI_COLS:
        op.alter_column(
            "source_daily_kpi",
            col,
            existing_type=_NARROW,
            type_=_WIDE,
            existing_nullable=True,
            postgresql_using=f"{col}::numeric(8,4)",
        )


def downgrade() -> None:
    for col in _SOURCE_KPI_COLS:
        op.alter_column(
            "source_daily_kpi",
            col,
            existing_type=_WIDE,
            type_=_NARROW,
            existing_nullable=True,
            postgresql_using=f"{col}::numeric(5,4)",
        )

    for col in _SALESPERSON_KPI_COLS:
        op.alter_column(
            "salesperson_daily_kpi",
            col,
            existing_type=_WIDE,
            type_=_NARROW,
            existing_nullable=True,
            postgresql_using=f"{col}::numeric(5,4)",
        )

    for col in _DAILY_KPI_COLS:
        op.alter_column(
            "daily_kpi",
            col,
            existing_type=_WIDE,
            type_=_NARROW,
            existing_nullable=True,
            postgresql_using=f"{col}::numeric(5,4)",
        )
