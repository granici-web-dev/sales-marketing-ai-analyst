# Phase 3: Metrics Engine - Pattern Map

**Mapped:** 2026-05-25
**Files analyzed:** 13
**Analogs found:** 13 / 13

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/alembic/versions/004_metrics_schema.py` | migration | batch | `backend/alembic/versions/003_mefi_schema.py` | exact |
| `backend/app/models/metrics/daily_kpi.py` | model | CRUD | `backend/app/models/mefi.py` (`RawMefiLead`) | exact |
| `backend/app/models/metrics/salesperson_kpi.py` | model | CRUD | `backend/app/models/mefi.py` (`MefiSalesperson`) | exact |
| `backend/app/models/metrics/source_kpi.py` | model | CRUD | `backend/app/models/mefi.py` (`RawMefiLead`) | exact |
| `backend/app/services/metrics/daily_kpi_service.py` | service | batch | `backend/app/services/repositories/mefi_repository.py` | role-match |
| `backend/app/services/metrics/salesperson_kpi_service.py` | service | batch | `backend/app/services/repositories/mefi_repository.py` | role-match |
| `backend/app/services/metrics/source_kpi_service.py` | service | batch | `backend/app/services/repositories/mefi_repository.py` | role-match |
| `backend/app/services/repositories/metrics_repository.py` | repository | CRUD | `backend/app/services/repositories/mefi_repository.py` | exact |
| `backend/app/tasks/etl/calculate_daily_kpis.py` | task | event-driven | `backend/app/tasks/etl/sync_mefi_leads.py` | exact |
| `backend/tests/unit/test_daily_kpi_service.py` | test | — | `backend/tests/unit/test_mefi_repository.py` | exact |
| `backend/tests/unit/test_salesperson_kpi_service.py` | test | — | `backend/tests/unit/test_mefi_repository.py` | exact |
| `backend/tests/unit/test_source_kpi_service.py` | test | — | `backend/tests/unit/test_mefi_repository.py` | exact |
| `backend/tests/unit/test_business_hours.py` | test | — | `backend/tests/unit/test_mefi_repository.py` | role-match |
| `backend/tests/unit/test_metrics_repository.py` | test | — | `backend/tests/unit/test_mefi_repository.py` | exact |
| `backend/tests/factories/metrics_factory.py` | test-factory | — | `backend/tests/factories/mefi_factory.py` | exact |

---

## Pattern Assignments

### `backend/alembic/versions/004_metrics_schema.py` (migration, batch)

**Analog:** `backend/alembic/versions/003_mefi_schema.py`

**File header and revision chain** (lines 1–65):
```python
from __future__ import annotations

"""Create metric tables, update v_mefi_leads_active, seed business_hours in funnel_config.

Revision ID: 004
Revises: 003
Create Date: 2026-05-25

Creates Phase 3 metric schema:
  1. CREATE TABLE daily_kpi                — full SPEC.md §7 schema + WoW/MoM delta columns
  2. CREATE TABLE salesperson_daily_kpi   — SPEC.md §7 schema + data_completeness_pct
  3. CREATE TABLE source_daily_kpi        — SPEC.md §7 schema (TEXT source column)
  4. CREATE INDEXes and UNIQUE CONSTRAINTs for all three tables
  5. CREATE OR REPLACE VIEW v_mefi_leads_active — updated with history-based reached_* (Gap 5)
  6. UPDATE tenants SET funnel_config = funnel_config || '...'  — adds business_hours key (D-07)
"""

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
```

**JSONB seed constant pattern** (from 003 lines 77–95):
```python
# One constant dict per seed — never inline JSON strings in op.execute()
BUSINESS_HOURS_PATCH = {
    "business_hours": {
        "days": [0, 1, 2, 3, 4, 5, 6],   # Mon=0 … Sun=6 (D-07: 7 days/week)
        "open": "09:00",
        "close": "19:00",
        "tz": "Europe/Bucharest",
    }
}
```

**Table creation pattern** — copy from 003 lines 213–283, adapting column sets:
```python
op.create_table(
    "daily_kpi",
    # TenantScopedMixin columns (replicated — migration is standalone DDL)
    sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
    sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
    sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),

    # Business date — NOT NULL; UPSERT conflict target with tenant_id
    sa.Column("date", sa.Date, nullable=False),

    # --- Ad spend (nullable — populated Iteration 2) ---
    sa.Column("spend_meta", sa.Numeric(10, 2), nullable=True),
    sa.Column("spend_google", sa.Numeric(10, 2), nullable=True),
    sa.Column("spend_tiktok", sa.Numeric(10, 2), nullable=True),
    sa.Column("spend_digital_total", sa.Numeric(10, 2), nullable=True),

    # --- GA4 (nullable — populated Iteration 3) ---
    sa.Column("web_sessions", sa.Integer, nullable=True),
    sa.Column("web_conversion_rate", sa.Numeric(5, 4), nullable=True),

    # --- Lead volume by source (nullable — 0 means "calculated but zero") ---
    sa.Column("leads_mail_fb_ig", sa.Integer, nullable=True),
    sa.Column("leads_telefon", sa.Integer, nullable=True),
    sa.Column("leads_whatsapp", sa.Integer, nullable=True),
    sa.Column("leads_site", sa.Integer, nullable=True),
    sa.Column("leads_designer", sa.Integer, nullable=True),
    sa.Column("leads_alte", sa.Integer, nullable=True),
    sa.Column("leads_total", sa.Integer, nullable=True),

    # --- CPL (nullable — populated Iteration 2) ---
    sa.Column("cpl_overall", sa.Numeric(8, 2), nullable=True),
    sa.Column("cpl_by_channel", JSONB, nullable=True),

    # --- Funnel counts (NOT NULL — populated by Phase 3) ---
    sa.Column("visits_count", sa.Integer, nullable=False, server_default=sa.text("0")),
    sa.Column("offers_count", sa.Integer, nullable=False, server_default=sa.text("0")),
    sa.Column("contracts_count", sa.Integer, nullable=False, server_default=sa.text("0")),

    # --- Conversion rates (NUMERIC(5,4)) ---
    sa.Column("conversion_l_to_v", sa.Numeric(5, 4), nullable=True),
    sa.Column("conversion_v_to_o", sa.Numeric(5, 4), nullable=True),
    sa.Column("conversion_l_to_o", sa.Numeric(5, 4), nullable=True),
    sa.Column("conversion_o_to_c", sa.Numeric(5, 4), nullable=True),
    sa.Column("conversion_l_to_c", sa.Numeric(5, 4), nullable=True),

    # --- Revenue (NUMERIC(12,2) — DATA-04) ---
    sa.Column("revenue", sa.Numeric(12, 2), nullable=True),
    sa.Column("avg_deal_size", sa.Numeric(10, 2), nullable=True),
    sa.Column("avg_deal_size_per_day", sa.Numeric(10, 2), nullable=True),
    sa.Column("cost_acquisition_contract", sa.Numeric(12, 2), nullable=True),

    # --- CAC/ROAS (nullable — Iteration 2) ---
    sa.Column("cac", sa.Numeric(10, 2), nullable=True),
    sa.Column("roas", sa.Numeric(8, 2), nullable=True),

    # --- Calls (nullable — future telephony) ---
    sa.Column("calls_total", sa.Integer, nullable=True),
    sa.Column("calls_answered", sa.Integer, nullable=True),
    sa.Column("calls_missed", sa.Integer, nullable=True),
    sa.Column("avg_call_duration_seconds", sa.Integer, nullable=True),
    sa.Column("avg_sentiment_score", sa.Numeric(3, 2), nullable=True),

    # --- WoW / MoM deltas (METR-05 — NOT in SPEC.md §7, added by this migration) ---
    sa.Column("leads_total_wow_delta", sa.Numeric(8, 4), nullable=True),
    sa.Column("leads_total_mom_delta", sa.Numeric(8, 4), nullable=True),
    sa.Column("conversion_l_to_v_wow_delta", sa.Numeric(8, 4), nullable=True),
    sa.Column("conversion_l_to_v_mom_delta", sa.Numeric(8, 4), nullable=True),
    sa.Column("conversion_v_to_o_wow_delta", sa.Numeric(8, 4), nullable=True),
    sa.Column("conversion_v_to_o_mom_delta", sa.Numeric(8, 4), nullable=True),
    sa.Column("conversion_l_to_o_wow_delta", sa.Numeric(8, 4), nullable=True),
    sa.Column("conversion_l_to_o_mom_delta", sa.Numeric(8, 4), nullable=True),
    sa.Column("conversion_o_to_c_wow_delta", sa.Numeric(8, 4), nullable=True),
    sa.Column("conversion_o_to_c_mom_delta", sa.Numeric(8, 4), nullable=True),
    sa.Column("conversion_l_to_c_wow_delta", sa.Numeric(8, 4), nullable=True),
    sa.Column("conversion_l_to_c_mom_delta", sa.Numeric(8, 4), nullable=True),
    sa.Column("revenue_wow_delta", sa.Numeric(8, 4), nullable=True),
    sa.Column("revenue_mom_delta", sa.Numeric(8, 4), nullable=True),
    sa.Column("avg_deal_size_wow_delta", sa.Numeric(8, 4), nullable=True),
    sa.Column("avg_deal_size_mom_delta", sa.Numeric(8, 4), nullable=True),

    sa.Column("calculated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),

    sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_daily_kpi_tenant_id"),
)
```

**Idempotent JSONB seed pattern** (from 003 lines 422–438):
```python
# CAST(:patch AS jsonb) — NOT ::jsonb — SQLAlchemy text() parser mistakes ::
# cast operator for a named parameter (same pitfall documented in 003)
op.execute(
    sa.text(
        """
        UPDATE tenants
        SET funnel_config = funnel_config || CAST(:patch AS jsonb)
        WHERE slug = 'sofa-belle'
          AND (funnel_config->>'business_hours') IS NULL
        """
    ).bindparams(patch=json.dumps(BUSINESS_HOURS_PATCH))
)
```

**downgrade() pattern** (from 003 lines 441–461):
```python
def downgrade() -> None:
    # Drop views that depend on raw tables first
    op.execute("DROP VIEW IF EXISTS v_mefi_leads_active")  # recreated — drop then recreate old version
    # Drop tables in reverse creation order
    op.drop_table("source_daily_kpi")
    op.drop_table("salesperson_daily_kpi")
    op.drop_table("daily_kpi")
    # Remove business_hours key from funnel_config (no clean JSONB key-delete in pure alembic
    # — use op.execute with jsonb minus operator)
    op.execute(
        sa.text("UPDATE tenants SET funnel_config = funnel_config - 'business_hours' WHERE slug = 'sofa-belle'")
    )
    # Re-create old v_mefi_leads_active (current-status-only version from 003)
    op.execute(V_MEFI_LEADS_ACTIVE_V003)  # store the 003 DDL as a module-level constant
```

---

### `backend/app/models/metrics/daily_kpi.py` (model, CRUD)

**Analog:** `backend/app/models/mefi.py`

**Imports and header pattern** (from mefi.py lines 1–30):
```python
from __future__ import annotations

"""SQLAlchemy ORM model for daily_kpi metric table.

Inherits TenantScopedMixin (id, tenant_id, created_at, updated_at).
UPSERT conflict target: (tenant_id, date) — see migration 004.

Phase 3 Plan XX — daily aggregate KPI row per tenant per calendar day.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, Integer, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin, TIMESTAMPTZ
```

**Model class and UniqueConstraint pattern** (from mefi.py lines 32–55):
```python
class DailyKpi(Base, TenantScopedMixin):
    """One row per tenant per calendar day — aggregate daily KPIs.

    UPSERT conflict target: (tenant_id, date).
    Ad-spend, GA4, and calls columns are NULLABLE — populated by future phases.
    WoW/MoM delta columns are NOT in SPEC.md §7; added by migration 004 (METR-05).
    """

    __tablename__ = "daily_kpi"

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "date",
            name="uq_daily_kpi_tenant_date",
        ),
    )

    date: Mapped[date] = mapped_column(Date, nullable=False)
    # ... columns following the same Mapped[type | None] pattern as RawMefiLead
    leads_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    conversion_l_to_v: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    revenue: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    calculated_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default="now()", nullable=False)
```

**Three-column UniqueConstraint** — for `salesperson_daily_kpi` and `source_daily_kpi`, copy the pattern but with three columns:
```python
__table_args__ = (
    UniqueConstraint(
        "tenant_id",
        "salesperson_external_id",  # or "source" for SourceDailyKpi
        "date",
        name="uq_salesperson_daily_kpi_tenant_sp_date",
    ),
)
```

---

### `backend/app/services/metrics/daily_kpi_service.py` (service, batch)

**Analog:** `backend/app/services/repositories/mefi_repository.py`

**Class constructor pattern** (from mefi_repository.py lines 11–24):
```python
from __future__ import annotations

"""Daily KPI aggregation service.

Queries v_mefi_leads_active + mefi_lead_history via SQLAlchemy async ORM.
Never queries raw_mefi_* tables directly (D-14).
All date grouping uses AT TIME ZONE 'Europe/Bucharest' (D-15).
"""

from decimal import Decimal
from datetime import date
from uuid import UUID

from sqlalchemy import func, case, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import Numeric

import structlog

logger = structlog.get_logger(__name__)


class DailyKpiService:
    """Computes tenant-level daily KPIs from conformed MEFI views."""

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id
```

**Deferred model import pattern** (from mefi_repository.py lines 51, 89, 152):
```python
async def compute_daily_kpis(self, kpi_date: date) -> dict:
    # All model imports deferred — fork-safety (INFRA-05)
    from app.models.mefi import RawMefiLead, MefiLeadHistory  # noqa

    # ... query logic
```

**Zero-division guard pattern** (METR-02 requirement — use func.nullif):
```python
from sqlalchemy import func
from sqlalchemy.types import Numeric as NumericType

leads_total_expr = func.count(v.c.id)
visits_count_expr = func.count(case((v.c.reached_visit == True, v.c.id)))

conversion_l_to_v = (
    func.cast(visits_count_expr, NumericType(12, 4))
    / func.nullif(leads_total_expr, 0)
).label("conversion_l_to_v")
```

**WoW/MoM delta helper pattern** (from RESEARCH.md Pattern 4):
```python
async def _fetch_prior_row(self, kpi_date: date, days_back: int) -> dict | None:
    """Read daily_kpi row for (date - days_back). Returns None if absent (D-11)."""
    from app.models.metrics.daily_kpi import DailyKpi
    from datetime import timedelta

    prior_date = kpi_date - timedelta(days=days_back)
    stmt = select(DailyKpi).where(
        DailyKpi.tenant_id == self._tenant_id,
        DailyKpi.date == prior_date,
    )
    result = await self._session.execute(stmt)
    row = result.scalar_one_or_none()
    return row

def _compute_delta(
    self,
    current: Decimal | None,
    prior: Decimal | None,
) -> Decimal | None:
    """(current - prior) / prior. Returns None if either is None or prior is 0 (D-11)."""
    if current is None or prior is None or prior == 0:
        return None
    return (current - prior) / prior
```

**structlog binding pattern** (from sync_mefi_leads.py line 98):
```python
log = logger.bind(tenant_id=str(self._tenant_id), service="daily_kpi_service")
log.info("daily_kpi.compute_start", kpi_date=str(kpi_date))
```

---

### `backend/app/services/metrics/salesperson_kpi_service.py` (service, batch)

**Analog:** `backend/app/services/repositories/mefi_repository.py`

Same class constructor pattern as `DailyKpiService`. Key additions:

**Active salesperson filter** (D-17):
```python
# Always JOIN mefi_salespeople and filter is_active = True (D-17)
# Never emit rows for is_active = False or is_active = NULL
from app.models.mefi import MefiSalesperson

stmt = (
    select(...)
    .join(MefiSalesperson, ...)
    .where(
        MefiSalesperson.tenant_id == self._tenant_id,
        MefiSalesperson.is_active == True,  # noqa: E712 — SQLAlchemy requires ==
    )
)
```

**data_completeness_pct pattern** (METR-06):
```python
data_completeness_pct = (
    func.cast(
        func.count(v.c.estimated_value),  # COUNT ignores NULLs automatically
        NumericType(5, 2),
    )
    / func.nullif(func.count(v.c.id), 0)
    * 100
).label("data_completeness_pct")
```

**business_hours config read pattern** (D-07 — read from DB, not hardcoded):
```python
async def _get_business_hours(self) -> dict:
    """Read business_hours config from tenants.funnel_config JSONB (D-07).

    Returns default Sofa Belle schedule if not configured.
    """
    from app.models.tenant import Tenant  # deferred — fork-safe

    stmt = select(Tenant.funnel_config).where(Tenant.id == self._tenant_id)
    result = await self._session.execute(stmt)
    config = result.scalar_one_or_none()
    if config and "business_hours" in config:
        return config["business_hours"]
    # Fallback: D-07 default
    return {"days": [0,1,2,3,4,5,6], "open": "09:00", "close": "19:00", "tz": "Europe/Bucharest"}
```

---

### `backend/app/services/metrics/source_kpi_service.py` (service, batch)

**Analog:** `backend/app/services/repositories/mefi_repository.py`

**Designer detection subquery pattern** (from RESEARCH.md Pattern 3 + D-02):
```python
from sqlalchemy import select
from app.models.mefi import MefiLeadHistory

# D-02: designer = ever had to_status_id=24 in history
# MUST include tenant_id filter — not covered by with_loader_criteria for Core queries
designer_subq = (
    select(MefiLeadHistory.lead_external_id)
    .where(
        MefiLeadHistory.tenant_id == self._tenant_id,  # explicit tenant filter — security
        MefiLeadHistory.to_status_id == 24,
    )
    .distinct()
    .subquery()
)
```

**Source categorization CASE expression pattern** (from RESEARCH.md Pattern 3):
```python
from sqlalchemy import case

# Read mapping from funnel_config — never hardcode source_id → category
# source_categories from config: {"mail_fb_ig": [2, 11], "telefon": [10], ...}
source_category_expr = case(
    (v.c.external_id.in_(select(designer_subq.c.lead_external_id)), "designer"),
    (v.c.source_id == 1, "google"),
    (v.c.source_id.in_([2, 11]), "mail_fb_ig"),
    (v.c.source_id == 10, "telefon"),
    (v.c.source_id == 9, "whatsapp"),
    (v.c.source_id == 6, "site"),
    else_="alte",
)
```

**funnel_config read pattern** — read `source_categories` mapping from DB at service init, same as `_get_business_hours()` pattern above.

---

### `backend/app/services/repositories/metrics_repository.py` (repository, CRUD)

**Analog:** `backend/app/services/repositories/mefi_repository.py`

**Full class structure** — copy exactly from mefi_repository.py lines 11–71 (`__init__` + `bulk_upsert_leads`), adapting for three metric tables:

**Constructor** (from mefi_repository.py lines 22–24):
```python
class MetricsRepository:
    """Database write layer for Phase 3 metric tables.

    All writes use pg_insert().on_conflict_do_update() — atomic UPSERT.
    CLAUDE.md Principle #3: tenant_id validated in every row dict before INSERT.
    Raises ValueError loudly rather than inserting unscoped rows (Pitfall 6).
    """

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id
```

**Tenant_id validation guard** (from mefi_repository.py lines 44–49 — copy verbatim):
```python
for row in rows:
    if "tenant_id" not in row or row["tenant_id"] is None:
        raise ValueError(
            f"MetricsRepository.upsert_daily_kpi: row missing tenant_id — "
            f"date={row.get('date', '<unknown>')}"
        )
```

**UPSERT with two-column conflict target** (from mefi_repository.py lines 64–71):
```python
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.models.metrics.daily_kpi import DailyKpi  # deferred — fork-safe

stmt = pg_insert(DailyKpi).values([row])
update_cols = [c for c in row if c not in ("id", "tenant_id", "date")]
stmt = stmt.on_conflict_do_update(
    index_elements=["tenant_id", "date"],
    set_={col: stmt.excluded[col] for col in update_cols},
)
result = await self._session.execute(stmt)
await self._session.commit()
```

**UPSERT with three-column conflict target** — for `SourceDailyKpi` (Pitfall 5 — must use 3 columns):
```python
stmt = stmt.on_conflict_do_update(
    index_elements=["tenant_id", "source", "date"],  # 3-column key — Pitfall 5
    set_={col: stmt.excluded[col] for col in update_cols},
)
```

---

### `backend/app/tasks/etl/calculate_daily_kpis.py` (task, event-driven)

**Analog:** `backend/app/tasks/etl/sync_mefi_leads.py`

**Task decorator and sync entry point** (from sync_mefi_leads.py lines 39–69):
```python
from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    max_retries=3,
    default_retry_delay=60,
    name="tasks.etl.calculate_daily_kpis",
)
def calculate_daily_kpis(
    self,
    tenant_id: str,
    calculation_date: str | None = None,  # ISO date string or None → yesterday (D-12)
) -> dict:
    """Calculate daily KPIs for the given tenant and date.

    Args:
        tenant_id: UUID string — validated as UUID at entry point (T-02-11).
        calculation_date: ISO date string (YYYY-MM-DD) or None → defaults to yesterday (D-10).
    """
    try:
        return asyncio.run(_calc_async(UUID(tenant_id), calculation_date))
    except Exception as exc:
        raise self.retry(exc=exc) from exc
```

**Deferred-import async body with NullPool** (from sync_mefi_leads.py lines 72–103 — copy this structure exactly):
```python
async def _calc_async(tenant_id: UUID, calculation_date: str | None) -> dict:
    """Core calculation coroutine — all DB/model imports deferred (INFRA-05, Pitfall 2).

    NullPool prevents cross-loop Future references when asyncio.run() creates
    a fresh event loop on each Celery task call (Pitfall 2 documented in RESEARCH.md).
    """
    # Deferred imports — must stay inside this function body (fork-safety)
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.core.config import settings
    from app.core.tenancy import set_tenant_id
    from app.models.pipeline import SyncRun

    set_tenant_id(tenant_id)
    calc_start_at = datetime.now(UTC)
    log = logger.bind(tenant_id=str(tenant_id), task="calculate_daily_kpis")

    task_engine = create_async_engine(settings.database_url, poolclass=NullPool)
    TaskSession = async_sessionmaker(task_engine, expire_on_commit=False, class_=AsyncSession)

    # Resolve calculation date (D-10: default to yesterday in Bucharest time)
    from zoneinfo import ZoneInfo
    from datetime import date as date_type
    BUCHAREST = ZoneInfo("Europe/Bucharest")
    if calculation_date is not None:
        kpi_date = date_type.fromisoformat(calculation_date)
    else:
        kpi_date = datetime.now(BUCHAREST).date() - timedelta(days=1)

    try:
        async with TaskSession() as session:
            # ... service calls + SyncRun write (same pattern as sync_mefi_leads.py)
            pass
    except Exception as exc:
        # Error handler writes SyncRun.status = "failed" — copy pattern from
        # sync_mefi_leads.py lines 281–308 exactly
        raise
    finally:
        await task_engine.dispose()
```

**SyncRun write pattern** (from sync_mefi_leads.py lines 124–133 — same for metrics task):
```python
sync_run = SyncRun(
    tenant_id=tenant_id,
    source="metrics",          # "metrics" not "mefi" — distinguishes in pipeline_runs table
    status="running",
    started_at=calc_start_at,
)
session.add(sync_run)
await session.commit()
await session.refresh(sync_run)
```

**daily_pipeline() extension** (from sync_mefi_leads.py lines 311–321):
```python
# In sync_mefi_leads.py — Phase 3 MODIFIES this function:
def daily_pipeline(tenant_id: str) -> object:
    from celery import chain
    from app.tasks.etl.calculate_daily_kpis import calculate_daily_kpis

    return chain(
        sync_mefi_leads.si(tenant_id),
        calculate_daily_kpis.si(tenant_id),  # .si() — immutable, no result passing (D-18)
    )
```

---

### `backend/tests/unit/test_daily_kpi_service.py` (test)

**Analog:** `backend/tests/unit/test_mefi_repository.py`

**Module header and mock setup pattern** (from test_mefi_repository.py lines 1–26):
```python
from __future__ import annotations

"""Unit tests for DailyKpiService.

Tests mock AsyncSession — no live DB required.
Coverage: conversion rate calculation, WoW/MoM deltas, zero-division guard.

Requirements: METR-01, METR-02, METR-05
"""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


def _make_service(mock_session=None):
    from app.services.metrics.daily_kpi_service import DailyKpiService
    session = mock_session or AsyncMock()
    return DailyKpiService(session, TENANT_ID), session
```

**Test class grouping pattern** (from test_mefi_repository.py lines 60–116):
```python
class TestConversionRates:
    """Tests for 5 conversion rates — METR-02."""

    @pytest.mark.asyncio
    async def test_conversion_rate_zero_denominator_returns_none(self) -> None:
        """0 leads → conversion_l_to_v = None, not ZeroDivisionError (SC#2)."""
        ...

class TestWoWMoMDeltas:
    """Tests for WoW and MoM deltas — METR-05."""

    @pytest.mark.asyncio
    async def test_wow_delta_null_when_no_prior_row(self) -> None:
        """No D-7 row → wow_delta = None (D-11), not 0."""
        ...

    @pytest.mark.asyncio
    async def test_mom_delta_null_when_prior_is_zero(self) -> None:
        """Prior revenue = 0 → delta = None (division guard, D-11)."""
        ...
```

---

### `backend/tests/unit/test_business_hours.py` (test)

**Analog:** `backend/tests/unit/test_mefi_repository.py` (class/method structure)

**Business-hours utility test structure** — pure unit tests (no async needed, no DB):
```python
from __future__ import annotations

"""Unit tests for business-hours-adjusted time_to_first_touch calculation.

Pure Python — no AsyncSession or DB required.
Tests DST transitions, edge cases, and boundary conditions (D-06, D-07).

Requirements: METR-04
"""

from datetime import datetime, time
from zoneinfo import ZoneInfo

import pytest

BUCHAREST = ZoneInfo("Europe/Bucharest")

# Import the utility (path TBD — could be in daily_kpi_service or separate module)
# from app.services.metrics.business_hours import business_minutes_between


class TestBusinessMinutesBetween:

    def test_lead_created_inside_hours_first_touch_same_window(self) -> None:
        """Lead created 10:00, first touch 10:30 → 30 business minutes."""
        ...

    def test_lead_created_outside_hours_first_touch_next_window(self) -> None:
        """Lead created 20:00 Fri, first touch 09:30 Sat → 30 minutes (D-07: Mon-Sun)."""
        ...

    def test_end_before_start_returns_zero(self) -> None:
        """end_utc <= start_utc (data quality issue) → 0 (not negative, not error)."""
        ...

    def test_dst_spring_forward_bucharest(self) -> None:
        """Lead straddling EET→EEST spring-forward — zoneinfo handles DST correctly."""
        ...
```

---

### `backend/tests/unit/test_metrics_repository.py` (test)

**Analog:** `backend/tests/unit/test_mefi_repository.py`

Copy the `TestBulkUpsertLeads` structure (lines 60–116) adapting for `MetricsRepository.upsert_daily_kpi`:

```python
class TestUpsertDailyKpi:

    @pytest.mark.asyncio
    async def test_raises_when_tenant_id_missing(self) -> None:
        """upsert_daily_kpi raises ValueError if row missing tenant_id (Pitfall 6)."""
        repo, _ = _make_repo()
        with pytest.raises(ValueError, match="missing tenant_id"):
            await repo.upsert_daily_kpi({"date": date(2026, 5, 24)})

    @pytest.mark.asyncio
    async def test_source_daily_kpi_uses_three_column_conflict_target(self) -> None:
        """source_daily_kpi UPSERT uses (tenant_id, source, date) — Pitfall 5."""
        ...

    @pytest.mark.asyncio
    async def test_idempotent_double_upsert_no_duplicate(self) -> None:
        """Running upsert twice for same (tenant_id, date) → same row count."""
        ...
```

---

### `backend/tests/factories/metrics_factory.py` (test-factory)

**Analog:** `backend/tests/factories/mefi_factory.py`

**Factory structure** (from mefi_factory.py lines 1–61 — copy header + class pattern):
```python
from __future__ import annotations

"""factory-boy factories for metric table test data.

Provides DailyKpiRowFactory, SalespersonKpiRowFactory, SourceKpiRowFactory
for building row dicts used in unit tests without a real DB.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

import factory

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
TODAY = date(2026, 5, 24)


class DailyKpiRowFactory(factory.Factory):
    """Builds daily_kpi row dicts with realistic Sofa Belle values."""

    class Meta:
        model = dict  # plain dicts — not ORM instances

    tenant_id = TENANT_ID
    date = factory.LazyFunction(lambda: TODAY)
    leads_total = factory.Sequence(lambda n: 10 + n)
    visits_count = factory.LazyAttribute(lambda o: max(1, o.leads_total // 2))
    offers_count = factory.LazyAttribute(lambda o: max(0, o.visits_count // 2))
    contracts_count = factory.LazyAttribute(lambda o: max(0, o.offers_count // 3))
    revenue = factory.LazyFunction(lambda: Decimal("15000.00"))
    calculated_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
```

**Builder helper pattern** (from mefi_factory.py lines 47–61):
```python
def make_designer_source_row(
    kpi_date: date = TODAY,
    leads: int = 5,
) -> dict:
    """Build a source_daily_kpi row for the 'designer' category."""
    return SourceKpiRowFactory.build(
        source="designer",
        date=kpi_date,
        leads=leads,
    )


def make_seven_source_rows(kpi_date: date = TODAY) -> list[dict]:
    """Build one row per source category for a given date (7 rows — D-04)."""
    categories = ["mail_fb_ig", "telefon", "whatsapp", "site", "designer", "alte", "google"]
    return [SourceKpiRowFactory.build(source=cat, date=kpi_date) for cat in categories]
```

---

## Shared Patterns

### Deferred Imports (Fork-Safety)

**Source:** `backend/app/tasks/etl/sync_mefi_leads.py` — `_sync_async()` body
**Apply to:** `calculate_daily_kpis.py` (`_calc_async` function) and all service methods

All `app.models.*`, `app.db.session`, `app.core.config` imports MUST be inside the `_calc_async` coroutine body — never at module level in the task file. Service classes defer model imports inside each method body.

```python
# CORRECT — inside _calc_async or service method:
from app.models.metrics.daily_kpi import DailyKpi  # deferred — fork-safe

# WRONG — module level in task file:
from app.models.metrics.daily_kpi import DailyKpi  # triggers pool creation before fork
```

### NullPool Per Task Invocation

**Source:** `backend/app/tasks/etl/sync_mefi_leads.py` lines 101–102
**Apply to:** `calculate_daily_kpis.py` (`_calc_async`)

```python
task_engine = create_async_engine(settings.database_url, poolclass=NullPool)
TaskSession = async_sessionmaker(task_engine, expire_on_commit=False, class_=AsyncSession)
```

Always dispose in `finally`: `await task_engine.dispose()`.

### Tenant_id Validation in Repository

**Source:** `backend/app/services/repositories/mefi_repository.py` lines 44–49
**Apply to:** `MetricsRepository` — every `upsert_*` method

```python
for row in rows:
    if "tenant_id" not in row or row["tenant_id"] is None:
        raise ValueError(
            f"MetricsRepository.<method>: row missing tenant_id — "
            f"key={row.get('<conflict_key>', '<unknown>')}"
        )
```

### structlog No-PII Logging

**Source:** `backend/app/tasks/etl/sync_mefi_leads.py` lines 12–13, 98, 246–253
**Apply to:** All service and task files

```python
import structlog
logger = structlog.get_logger(__name__)

# Inside function:
log = logger.bind(tenant_id=str(tenant_id), task="calculate_daily_kpis")
log.info("kpi.compute_start", kpi_date=str(kpi_date))
log.info("kpi.compute_done", records_written=3, duration_ms=elapsed_ms)
# NEVER log: salesperson names, lead contents, customer PII
```

### AT TIME ZONE Bucharest in SQL

**Source:** `backend/alembic/versions/003_mefi_schema.py` lines 146–148 (view DDL)
**Apply to:** All date-grouped queries in service layer (D-15)

```sql
-- In SQLAlchemy text() or literal_column():
(r.created_at_source AT TIME ZONE 'Europe/Bucharest')::date AS created_date_local
```

In SQLAlchemy Core expressions use `func.timezone('Europe/Bucharest', column)`.

### pg_insert UPSERT Pattern

**Source:** `backend/app/services/repositories/mefi_repository.py` lines 64–71
**Apply to:** All three `upsert_*` methods in `MetricsRepository`

```python
from sqlalchemy.dialects.postgresql import insert as pg_insert

stmt = pg_insert(ModelClass).values([row])
update_cols = [c for c in row if c not in CONFLICT_COLUMNS | {"id"}]
stmt = stmt.on_conflict_do_update(
    index_elements=CONFLICT_COLUMNS,          # list — 2 or 3 columns depending on table
    set_={col: stmt.excluded[col] for col in update_cols},
)
result = await self._session.execute(stmt)
await self._session.commit()
```

Conflict columns per table:
- `daily_kpi`: `["tenant_id", "date"]`
- `salesperson_daily_kpi`: `["tenant_id", "salesperson_external_id", "date"]`
- `source_daily_kpi`: `["tenant_id", "source", "date"]` ← 3 columns, easy to miss (Pitfall 5)

### NUMERIC(12,2) / Decimal for Revenue

**Source:** `backend/app/models/mefi.py` line 76–78
**Apply to:** All `revenue`, `avg_deal_size`, `estimated_value` columns and Python calculations

```python
# Model:
estimated_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
# Python: always Decimal, never float
from decimal import Decimal
revenue = Decimal("15000.00")
```

### Test Helper Pattern

**Source:** `backend/tests/unit/test_mefi_repository.py` lines 22–57
**Apply to:** All Phase 3 unit test files

```python
TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")

def _make_service(mock_session=None):
    from app.services.metrics.XXX_service import XXXService
    session = mock_session or AsyncMock()
    return XXXService(session, TENANT_ID), session

def _make_row(**kwargs) -> dict:
    """Build a minimal valid metric row dict."""
    defaults = {
        "tenant_id": TENANT_ID,
        "date": date(2026, 5, 24),
        # ... phase-specific defaults
    }
    defaults.update(kwargs)
    return defaults
```

### conftest.py TEST_TENANT_ID

**Source:** `backend/tests/conftest.py` line 24
**Apply to:** All Phase 3 test files — use this constant, never a different UUID

```python
# In tests: import from conftest or replicate the constant:
TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")  # Sofa Belle pilot
```

### from __future__ import annotations

**Source:** Every existing file (`mefi.py` line 1, `mefi_repository.py` line 1, `sync_mefi_leads.py` line 1)
**Apply to:** Every new Phase 3 file — first line without exception (CLAUDE.md Core Principle #2)

---

## No Analog Found

All Phase 3 files have close analogs. The business-hours utility function has no direct analog in the codebase (no existing duration/interval calculation logic), but the RESEARCH.md Pattern 2 provides a concrete algorithm. The test file `test_business_hours.py` uses standard pytest class structure (analog: any existing test file).

| File | Reason for no codebase analog | Use instead |
|------|-------------------------------|-------------|
| Business-hours utility (inside `salesperson_kpi_service.py`) | No interval arithmetic exists yet | RESEARCH.md Pattern 2 (`business_minutes_between`) |

---

## Metadata

**Analog search scope:** `backend/app/`, `backend/alembic/`, `backend/tests/`
**Files scanned:** 10 source files read directly
**Pattern extraction date:** 2026-05-25
