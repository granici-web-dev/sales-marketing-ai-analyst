"""Make daily_kpi.visits_count nullable.

Revision ID: 006
Revises: 005
Create Date: 2026-05-28

KI-03: MEFI API exposes only the CURRENT lead status, not the full status
history. "Ever reached SHOWROOM" (reached_visit) cannot be reconstructed for
historical dates — computing it from current status on a past date yields
cohort-contaminated counts (e.g. a lead that is now a Clienți but was created
6 months ago is counted as a visit for that creation date, which is wrong).

Consequence: visits_count, conversion_l_to_v, conversion_v_to_o are
unreliable and should be stored as NULL rather than a misleading integer.

This migration drops the NOT NULL constraint (and server default of 0) on
daily_kpi.visits_count. The service layer sets visits_count = None explicitly;
the two dependent conversion columns are already nullable from migration 004.

source_daily_kpi.visits and salesperson_daily_kpi.visits_conducted are
already nullable from migration 004 and require no DDL change.

Downgrade note: restoring NOT NULL requires backfilling NULL→0 first.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "daily_kpi",
        "visits_count",
        existing_type=sa.Integer(),
        nullable=True,
        existing_nullable=False,
        existing_server_default="0",
        server_default=None,
    )


def downgrade() -> None:
    # Restore NOT NULL — backfill NULLs to 0 first so constraint can be set.
    op.execute("UPDATE daily_kpi SET visits_count = 0 WHERE visits_count IS NULL")
    op.alter_column(
        "daily_kpi",
        "visits_count",
        existing_type=sa.Integer(),
        nullable=False,
        existing_nullable=True,
        server_default="0",
    )
