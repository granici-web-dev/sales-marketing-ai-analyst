# Phase 3: Metrics Engine — Research

**Researched:** 2026-05-25
**Domain:** PostgreSQL aggregation, business-hours arithmetic, SQLAlchemy async UPSERT, Celery chain extension
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Source Categorization**
- D-01: Google (source_id=1) stored as a single `google` row in `source_daily_kpi` — no UTM-based split in Phase 3.
- D-02: Designer leads derived from status_id=24 in `mefi_lead_history` — if a lead ever had status 24, its source category is `designer`, regardless of source_id.
- D-03: TikTok has no dedicated source_id — TikTok leads fall under Meta source IDs (2 or 11) and are folded into `mail_fb_ig` for Phase 3.
- D-04: `source_daily_kpi.source` values use funnel_config category names. Seven rows per day per tenant: `mail_fb_ig` | `telefon` | `whatsapp` | `site` | `designer` | `alte` | `google`

**time_to_first_touch Calculation**
- D-05: "First touch" = first row in `mefi_lead_history` for that lead (earliest changed_at after creation). Leads with no history rows get NULL — not imputed.
- D-06: `avg_time_to_first_touch_minutes` is business-hours-adjusted — only working minutes count.
- D-07: Sofa Belle business hours: Mon–Sun 09:00–19:00 Europe/Bucharest. Store in `tenants.funnel_config` JSONB as `business_hours` key.

**Schema Scope**
- D-08: Phase 3 Alembic migration creates the full SPEC.md §7 schema for all three tables with all ad-spend/GA4/calls columns as NULLABLE. No schema additions needed in Phases 4–9 for columns already defined in SPEC.md §7.
- D-09: `source_daily_kpi.source` uses funnel_config category names (not SPEC.md generic names). Phase 3 schema uses TEXT for `source` column.

**Metrics Date Window & Deltas**
- D-10: `calculate_daily_kpis` calculates KPIs for yesterday (previous full calendar day in Europe/Bucharest). Default behavior.
- D-11: WoW and MoM deltas store NULL when prior data doesn't exist. Never impute zero for a missing comparison point.
- D-12: Task signature: `calculate_daily_kpis(date: date | None = None)`. UPSERT on `(tenant_id, date)` handles idempotent re-runs.

**Locked from Phase 1/2**
- D-13: "Ever reached" funnel logic — Vizita if status ever IN [17], Oferta if status ever IN [3] OR form-cf-20="✅DA", Contract if status ever=1.
- D-14: Metric services query `v_mefi_leads_active` only — never `raw_mefi_*` tables directly.
- D-15: All date grouping uses `AT TIME ZONE 'Europe/Bucharest'`.
- D-16: Revenue amounts as NUMERIC(12,2), never float; API responses serialize as decimal strings.
- D-17: Per-salesperson metrics filter on `mefi_salespeople.is_active = true`.
- D-18: `calculate_daily_kpis` is second in the Celery chain(): `sync_mefi_leads → calculate_daily_kpis → detect_anomalies → generate_daily_insights`.

### Claude's Discretion

None explicitly listed in CONTEXT.md — all key decisions are locked.

### Deferred Ideas (OUT OF SCOPE)

- UTM-based Google Ads vs Organic split (Iteration 2)
- TikTok source category (Iteration 2)
- CPL, CAC, ROAS calculation (Iteration 2 — columns are created nullable)
- GA4 web_sessions and web_conversion_rate (Iteration 3 — columns created nullable)
- Calls data (calls_total, avg_call_duration_seconds) (future telephony integration)
- Intraday / real-time KPIs (out of v1 scope)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| METR-01 | Celery task calculates daily KPIs after ETL and writes to `daily_kpi`, `salesperson_daily_kpi`, `source_daily_kpi` | Task pattern confirmed in Phase 2 — extend chain with calculate_daily_kpis.si() |
| METR-02 | Funnel conversion rates L→V, V→O, L→O, O→C, L→C with zero-divisor guards | SQL NULLIF(denominator, 0) pattern; 5 rates map to SPEC.md §7 `conversion_*` columns |
| METR-03 | Lead volume by source (6/7 Sofa Belle categories) tracked per day | 7 source categories per D-04; `source_daily_kpi` table; designer from lead_history |
| METR-04 | Per-salesperson metrics: leads assigned, visits, offers, contracts, time_to_first_touch | `salesperson_daily_kpi` table; business-hours adjustment via Python zoneinfo |
| METR-05 | WoW and MoM delta for each KPI | LAG via subquery or separate read; NULL on missing prior rows |
| METR-06 | `estimated_value` null tracked as data_completeness metric per salesperson | COUNT FILTER (WHERE estimated_value IS NOT NULL) / COUNT(*) * 100 |
</phase_requirements>

---

## Summary

Phase 3 computes deterministic daily KPIs from the conformed MEFI views built in Phase 2 and persists them to three tables: `daily_kpi`, `salesperson_daily_kpi`, and `source_daily_kpi`. All computation is pure Python + SQLAlchemy SQL expressions running inside a Celery task that becomes the second link in the existing daily pipeline chain.

The most technically complex element is the **business-hours-adjusted time_to_first_touch**. The calculation requires converting TIMESTAMPTZ values to Europe/Bucharest local time, then iterating over working-time intervals between lead creation and first history row. Python `zoneinfo` (stdlib, Python 3.9+) is the correct tool — it is already available in this Python 3.11 environment and correctly handles Romanian DST transitions (EET/EEST). A pure-SQL approach using recursive CTEs would work but is harder to test and maintains business logic in DDL rather than service code.

The **schema gap** between SPEC.md §7 and the requirements is material: SPEC.md §7 DDL does not include WoW/MoM delta columns (`wow_delta_pct`, `mom_delta_pct`) or `data_completeness_pct`. The Phase 3 Alembic migration must extend the SPEC.md §7 schema with these columns. Similarly, ROADMAP SC#1 says "6 source categories" while CONTEXT.md D-04 locks in 7 (the CONTEXT takes precedence — 7 rows per day). The migration must also seed the new `business_hours` key into `tenants.funnel_config`.

**Primary recommendation:** Implement business-hours adjustment in pure Python using `zoneinfo`; use a single SQL aggregation query per table per calculation run; UPSERT via `pg_insert(...).on_conflict_do_update()` exactly as Phase 2 MefiRepository does.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Daily KPI aggregation | Database / Storage | API / Backend (orchestration) | Aggregation SQL runs in PostgreSQL; Python orchestrates and writes results |
| Business-hours time_to_first_touch | API / Backend (service layer) | Database / Storage | Business logic in Python service; DB provides raw timestamps |
| Source categorization | API / Backend (service layer) | Database / Storage | Category mapping loaded from funnel_config JSONB; SQL applies it |
| WoW/MoM delta computation | Database / Storage | — | Subquery reading prior-period rows from same metric table |
| Designer detection | API / Backend (service layer) | Database / Storage | Requires JOIN on mefi_lead_history; Python service builds query |
| UPSERT to metric tables | Database / Storage | — | PostgreSQL INSERT ON CONFLICT DO UPDATE, same pattern as Phase 2 |
| Celery chain wiring | API / Backend (task layer) | — | `daily_pipeline()` function in sync_mefi_leads.py extended with `.si()` call |

---

## Standard Stack

Phase 3 introduces **no new packages**. All dependencies are already installed in the Phase 1/2 venv.

### Core (already installed — verified via `pip show`)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy | 2.0.49 | Async ORM + Core for UPSERT | [VERIFIED: pip show] established in Phase 1/2 |
| asyncpg | 0.31.0 | PostgreSQL async driver | [VERIFIED: pip show] established in Phase 1/2 |
| Celery | 5.6.3 | Task execution and chain | [VERIFIED: pip show] established in Phase 1/2 |
| pydantic | 2.13.4 | Data validation for task I/O | [VERIFIED: pip show] established in Phase 1/2 |
| structlog | 25.5.0 | Structured JSON logging (no PII) | [VERIFIED: pip show] established in Phase 1/2 |
| zoneinfo | stdlib | Bucharest DST-aware timezone | [VERIFIED: pip show] built into Python 3.11 stdlib |

### Supporting (already installed)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytz | 2.9.0.post0 | Alternative timezone handling | zoneinfo preferred; pytz available as fallback |
| python-dateutil | 2.9.0.post0 | Date arithmetic helpers | For timedelta iteration in business-hours loop |
| pytest | 8.4.2 | Test runner | All Phase 3 tests |
| pytest-asyncio | 1.2.0 | Async test support | Integration tests with AsyncSession |
| factory-boy | 3.3.3 | Test data factories | Extend Phase 2 factories for metric fixtures |

**No new package installation required for Phase 3.**

---

## Package Legitimacy Audit

> Phase 3 installs no new packages — all required libraries were installed in Phases 1 and 2.

| Package | Registry | Disposition |
|---------|----------|-------------|
| sqlalchemy | PyPI | [VERIFIED: pip show] — existing Phase 1/2 install |
| asyncpg | PyPI | [VERIFIED: pip show] — existing Phase 1/2 install |
| celery | PyPI | [VERIFIED: slopcheck OK] — existing Phase 1/2 install |
| factory-boy | PyPI | [VERIFIED: slopcheck OK] — existing Phase 1/2 install |
| pytest | PyPI | [VERIFIED: slopcheck OK] — existing Phase 1/2 install |
| pytest-asyncio | PyPI | [VERIFIED: slopcheck OK] — existing Phase 1/2 install |
| pydantic | PyPI | [VERIFIED: slopcheck OK] — existing Phase 1/2 install |
| asyncpg | PyPI | [VERIFIED: slopcheck OK] — existing Phase 1/2 install |
| structlog | PyPI | [VERIFIED: slopcheck OK] — existing Phase 1/2 install |
| alembic | PyPI | [VERIFIED: slopcheck OK] — existing Phase 1/2 install |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

slopcheck ran clean (9/9 [OK]) on 2026-05-25.

---

## Architecture Patterns

### System Architecture Diagram

```
[Celery Beat 04:00 EET]
         │
         ▼
[sync_mefi_leads] ──success──► [calculate_daily_kpis] ──success──► [detect_anomalies] ──► [generate_daily_insights]
         │                               │
         │ failure                       │ writes
         ▼                               ▼
[pipeline_runs: failed]      ┌──────────────────────────┐
                             │  PostgreSQL metric layer  │
                             │  ┌─────────────────────┐  │
                             │  │ daily_kpi           │  │
                             │  │ salesperson_daily_  │  │
                             │  │   kpi               │  │
                             │  │ source_daily_kpi    │  │
                             │  └─────────────────────┘  │
                             └──────────────────────────┘
                                        ▲
                    [MetricsService] ───┘
                         │ reads
                         ▼
              [v_mefi_leads_active]
              [mefi_lead_history]
              [mefi_salespeople]
```

Data flows: Celery Beat triggers chain → ETL succeeds → calculate_daily_kpis reads from conformed views → MetricsService computes aggregates → MetricsRepository UPSERTs to three metric tables → downstream tasks consume those tables.

### Recommended Project Structure

```
backend/app/
├── models/
│   └── metrics/
│       ├── __init__.py
│       ├── daily_kpi.py           # DailyKpi SQLAlchemy model
│       ├── salesperson_kpi.py     # SalespersonDailyKpi model
│       └── source_kpi.py          # SourceDailyKpi model
├── services/
│   ├── metrics/
│   │   ├── __init__.py
│   │   ├── daily_kpi_service.py       # Aggregate queries + business-hours calc
│   │   ├── salesperson_kpi_service.py # Per-rep metrics
│   │   └── source_kpi_service.py      # Per-source metrics + designer detection
│   └── repositories/
│       └── metrics_repository.py  # UPSERT for all three metric tables
├── tasks/
│   └── etl/
│       └── calculate_daily_kpis.py  # Celery task entry point
└── alembic/versions/
    └── 004_metric_tables.py         # Full SPEC.md §7 schema + extensions
```

Note: `app/models/__init__.py` must be updated to export the three new metric models so Alembic autogenerate sees them.

### Pattern 1: SQLAlchemy async UPSERT (INSERT ON CONFLICT DO UPDATE)

Identical to Phase 2 `MefiRepository.bulk_upsert_leads`. The same `pg_insert` pattern works for metric tables with `(tenant_id, date)` as conflict target.

```python
# Source: Phase 2 mefi_repository.py (proven pattern in this codebase)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.models.metrics.daily_kpi import DailyKpi

async def upsert_daily_kpi(self, row: dict) -> None:
    stmt = pg_insert(DailyKpi).values([row])
    update_cols = [c for c in row if c not in ("tenant_id", "date", "id")]
    stmt = stmt.on_conflict_do_update(
        index_elements=["tenant_id", "date"],
        set_={col: stmt.excluded[col] for col in update_cols},
    )
    await self._session.execute(stmt)
    await self._session.commit()
```

[ASSUMED] The exact column exclusion list — "id", "tenant_id", "date" — must be confirmed against the actual model definition during implementation.

### Pattern 2: Business-Hours-Adjusted Duration in Python

The calculation uses Python `zoneinfo` (stdlib Python 3.9+) for DST-correct Bucharest time. The algorithm iterates minute-by-minute over the interval between lead creation and first history row, counting only minutes that fall within business hours.

For typical Sofa Belle data (a few dozen new leads per day, first-touch within the same day), a direct arithmetic approach is fast enough without minute-by-minute iteration.

```python
# [ASSUMED] — illustrative pattern, not copy-paste ready
from __future__ import annotations
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

BUCHAREST = ZoneInfo("Europe/Bucharest")

def business_minutes_between(
    start_utc: datetime,
    end_utc: datetime,
    open_time: time,          # e.g. time(9, 0)
    close_time: time,         # e.g. time(19, 0)
    work_days: list[int],     # e.g. [0,1,2,3,4,5,6] for Mon-Sun
) -> int:
    """Count business minutes between two UTC timestamps.

    DST-safe via zoneinfo. Counts minutes in [open_time, close_time) windows
    on work_days. If start_utc is outside business hours, skips forward to
    next open window before counting.

    Args:
        start_utc: Lead creation time (TIMESTAMPTZ from DB, tz-aware)
        end_utc: First history row changed_at (TIMESTAMPTZ, tz-aware)
        open_time: Business hours open (Bucharest local)
        close_time: Business hours close (Bucharest local)
        work_days: ISO weekday ints (Mon=0 ... Sun=6)

    Returns:
        Integer minutes of business time elapsed.
    """
    if end_utc <= start_utc:
        return 0

    # Convert to Bucharest local for day/time comparisons
    start_local = start_utc.astimezone(BUCHAREST)
    end_local = end_utc.astimezone(BUCHAREST)

    total_minutes = 0
    current = start_local

    while current < end_local:
        day_of_week = current.weekday()
        if day_of_week not in work_days:
            # Skip to next work day open
            current = _next_open(current, open_time, work_days, BUCHAREST)
            continue

        open_dt = current.replace(
            hour=open_time.hour, minute=open_time.minute, second=0, microsecond=0
        )
        close_dt = current.replace(
            hour=close_time.hour, minute=close_time.minute, second=0, microsecond=0
        )

        if current < open_dt:
            current = open_dt
            continue
        if current >= close_dt:
            current = _next_open(current + timedelta(days=1), open_time, work_days, BUCHAREST)
            continue

        # current is within business hours — count to min(close_dt, end_local)
        count_until = min(close_dt, end_local)
        minutes = int((count_until - current).total_seconds() / 60)
        total_minutes += minutes
        current = count_until

    return total_minutes
```

**Edge cases that MUST be handled:**
1. Lead created outside business hours → start counting from next open window, NOT from creation time
2. Lead created during business hours, first touch after business hours → count only up to close on creation day, then from next open to first touch
3. Lead created Friday 18:59, first touch Saturday 09:30 → 1 minute (Fri) + 30 min (Sat) = 31 minutes (Mon-Sun schedule means Saturday is a work day for Sofa Belle)
4. `end_utc <= start_utc` (first touch before creation — data quality issue) → return 0
5. No history rows at all → return None per D-05

### Pattern 3: Source Categorization with Designer Detection

Designer detection requires a JOIN on `mefi_lead_history`. A lead is classified as `designer` if it has ever had `to_status_id = 24` in its history, regardless of its current `source_id`.

```python
# [ASSUMED] — illustrative SQL structure
# Step 1: Get designer lead external_ids from mefi_lead_history
designer_subq = (
    select(MefiLeadHistory.lead_external_id)
    .where(
        MefiLeadHistory.tenant_id == tenant_id,
        MefiLeadHistory.to_status_id == 24,
    )
    .distinct()
    .subquery()
)

# Step 2: When categorizing sources, check designer flag first
source_category = case(
    (v.c.external_id.in_(select(designer_subq.c.lead_external_id)), "designer"),
    (v.c.source_id == 1, "google"),
    (v.c.source_id.in_([2, 11]), "mail_fb_ig"),
    (v.c.source_id == 10, "telefon"),
    (v.c.source_id == 9, "whatsapp"),
    (v.c.source_id == 6, "site"),
    else_="alte",
)
```

Note: `source_id` values come from `funnel_config.source_categories` JSONB, not hardcoded. The service should read the mapping from `tenants.funnel_config` at task start.

### Pattern 4: WoW/MoM Delta Calculation

Read prior-period row from `daily_kpi` within the same query using a scalar subquery per metric, or in two sequential async reads. Null-safe: returns NULL if no prior row exists.

```python
# [ASSUMED] — two-read approach (simpler, proven in this codebase pattern)
async def compute_delta(
    current_val: Decimal | None,
    prior_val: Decimal | None,
) -> Decimal | None:
    """Compute (current - prior) / prior as decimal fraction.
    Returns None if either value is None or prior is zero (D-11).
    """
    if current_val is None or prior_val is None or prior_val == 0:
        return None
    return (current_val - prior_val) / prior_val
```

### Pattern 5: Celery Chain Extension

`daily_pipeline()` in `sync_mefi_leads.py` currently returns `chain(sync_mefi_leads.si(tenant_id))`. Phase 3 extends it to:

```python
# Source: backend/app/tasks/etl/sync_mefi_leads.py — daily_pipeline() function
# Phase 3 extends this function (D-18, PIPE-01)
def daily_pipeline(tenant_id: str) -> object:
    from celery import chain
    from app.tasks.etl.calculate_daily_kpis import calculate_daily_kpis

    return chain(
        sync_mefi_leads.si(tenant_id),
        calculate_daily_kpis.si(tenant_id),
    )
```

`calculate_daily_kpis` uses `.si()` (immutable signature) — it does NOT use the ETL result as input. The task accepts `tenant_id` and `calculation_date: str | None = None` separately (D-12).

### Anti-Patterns to Avoid

- **Querying `raw_mefi_*` tables directly:** Always use `v_mefi_leads_active` (D-14). The view encapsulates lifecycle filtering and AT TIME ZONE logic.
- **Hardcoding source_id → category mapping:** Read from `tenants.funnel_config.source_categories` JSONB. Status 24 = designer is a status check, not a source_id mapping.
- **Float arithmetic for revenue/rates:** Use `Decimal` throughout. `NUMERIC(5,4)` maps to `Decimal` in SQLAlchemy with asyncpg. Never cast to `float`.
- **Raw UTC date grouping:** Always apply `AT TIME ZONE 'Europe/Bucharest'` before grouping by date (D-15, DATA-03).
- **Imputing zero for missing prior period:** NULL delta is correct. Zero would mislead Phase 4 anomaly detection.
- **Calling `asyncio.run()` from an already-running loop:** The Celery task uses `asyncio.run(_calc_async(...))` at the sync entry point — same pattern as Phase 2. All async code runs inside `_calc_async`.
- **Module-level `app.db.session` import in task file:** Keep all DB/model imports inside the `_calc_async` coroutine body (fork-safety, INFRA-05). Same discipline as `sync_mefi_leads.py`.
- **Using `SELECT *` in aggregation queries:** Specify explicit columns per CLAUDE.md and project conventions.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Timezone-aware datetime comparison | Manual UTC offset arithmetic | `zoneinfo.ZoneInfo("Europe/Bucharest")` | DST transitions (EET→EEST) shift offset by 1h; manual arithmetic will be wrong twice a year |
| PostgreSQL UPSERT | Custom SELECT-then-INSERT logic | `pg_insert(...).on_conflict_do_update()` | Race condition between SELECT and INSERT; ON CONFLICT is atomic |
| Decimal division guard | `try: a/b except ZeroDivisionError` | `NULLIF(b, 0)` in SQL or `if b == 0: return None` | The SQL form is cleaner and runs where the data lives |
| Task scheduling | Manual cron in Python | Celery chain + existing redbeat schedule | Chain halt-on-failure semantics (PIPE-02) and beat registration already exist |
| Source category lookup | Hardcoded `if source_id == 2` chains | Read `funnel_config.source_categories` from DB | Tenant-configurable; avoids deploy needed to change a client's mapping |

---

## Schema Gap Analysis (Critical Finding)

### Gap 1: WoW/MoM delta columns not in SPEC.md §7 DDL

**Finding:** SPEC.md §7 DDL for `daily_kpi` does NOT include WoW/MoM delta columns. The requirements (METR-05) and ROADMAP SC#5 require `wow_delta_pct` and `mom_delta_pct` per numeric KPI. [VERIFIED: grepped SPEC.md — "wow", "mom", "_delta" appear 0 times in §7 DDL]

**Resolution:** Phase 3 migration extends SPEC.md §7 schema with delta columns. Example additions to `daily_kpi`:
```sql
-- WoW / MoM deltas (METR-05) — not in SPEC.md §7, added by Phase 3 migration
leads_total_wow_delta  NUMERIC(8,4),  -- (current - D-7) / D-7
leads_total_mom_delta  NUMERIC(8,4),  -- (current - D-30) / D-30
conversion_l_to_v_wow_delta  NUMERIC(8,4),
conversion_l_to_v_mom_delta  NUMERIC(8,4),
-- ... one pair per numeric KPI ...
```
[ASSUMED] The exact column list (which numeric KPIs get deltas) needs a planner decision. Reasonable scope: all 5 conversion rates + leads_total + revenue + avg_deal_size.

### Gap 2: `data_completeness_pct` not in SPEC.md §7 `salesperson_daily_kpi` DDL

**Finding:** SPEC.md §7 DDL for `salesperson_daily_kpi` does NOT include `data_completeness_pct`. METR-06 and ROADMAP SC#3 require it. [VERIFIED: grepped SPEC.md]

**Resolution:** Phase 3 migration adds `data_completeness_pct NUMERIC(5,2)` to `salesperson_daily_kpi`.

### Gap 3: ROADMAP SC#1 says "6 source categories" but CONTEXT D-04 locks in 7

**Finding:** ROADMAP SC#1 reads "source_daily_kpi (6 rows for 6 source categories)". CONTEXT.md D-04 locks in 7 categories: `mail_fb_ig | telefon | whatsapp | site | designer | alte | google`. [VERIFIED: ROADMAP.md line 79 vs CONTEXT.md D-04]

**Resolution:** CONTEXT.md takes precedence as the most recent decision artifact. The ROADMAP SC#1 count (6) is a stale number that predates the CONTEXT discussion. The migration and task must produce 7 rows per day. The success criterion test should assert 7 rows, not 6.

### Gap 4: `business_hours` key missing from existing `funnel_config` seed

**Finding:** Migration 003 seeds `funnel_config` with `funnel_stages`, `source_categories`, `offer_sent_flag_field`, `showroom_field`, `junk_statuses`, `lifecycle_filter`. D-07 requires a new `business_hours` key. [VERIFIED: 003_mefi_schema.py FUNNEL_CONFIG dict]

**Resolution:** Phase 3 migration 004 must UPDATE `funnel_config` with the new key:
```sql
UPDATE tenants
SET funnel_config = funnel_config || '{"business_hours": {"days": [0,1,2,3,4,5,6], "open": "09:00", "close": "19:00", "tz": "Europe/Bucharest"}}'::jsonb
WHERE slug = 'sofa-belle'
  AND (funnel_config->>'business_hours') IS NULL
```
The idempotency guard `AND (funnel_config->>'business_hours') IS NULL` prevents overwriting manual edits on re-run.

### Gap 5: `v_mefi_leads_active` uses current-status funnel logic, Phase 3 needs history-based "ever reached"

**Finding:** Migration 003 comments explicitly: "reached_* columns use current status_id only (Phase 2 limitation). True 'ever reached' requires mefi_lead_history join — planned for Phase 3." [VERIFIED: 003_mefi_schema.py line 149-151]

**Resolution:** Two options:
1. **Update the view in migration 004** to JOIN mefi_lead_history and add correct `reached_*` booleans. This keeps the view as the single source of truth. Preferred.
2. **Compute in service code** by querying both view and history table separately.

Option 1 is architecturally cleaner. The updated view should:
```sql
-- reached_visit: current status IN (17,3,1) OR ever had status 17 in history
-- reached_offer: current status IN (3,1) OR offer_sent_flag=true OR ever had status 3 in history
-- reached_contract: current status = 1
```
Note: The view still reads from `raw_mefi_leads r` + LEFT JOIN `mefi_lead_history h ON h.lead_external_id = r.external_id AND h.tenant_id = r.tenant_id`.

---

## Common Pitfalls

### Pitfall 1: DST Boundary on TIMESTAMPTZ → Local Date Conversion

**What goes wrong:** A lead created at 23:30 UTC maps to either 01:30 EEST+2 (summer) or 01:30 EET+2 (winter) depending on DST. If you apply a fixed offset instead of `AT TIME ZONE 'Europe/Bucharest'`, some late-night leads are attributed to the wrong day during DST transitions.

**Why it happens:** Romania uses EET (UTC+2) in winter and EEST (UTC+3) in summer. The DST transition occurs twice a year (last Sunday of March/October). A fixed `+02:00` offset is wrong for half the year.

**How to avoid:** Always `AT TIME ZONE 'Europe/Bucharest'` in SQL (already enforced by D-15) and `ZoneInfo("Europe/Bucharest")` in Python business-hours code. Never use a fixed offset.

**Warning signs:** Lead counts differ by 1–2 between your metric table and a manual Excel count taken on a DST transition day.

### Pitfall 2: `asyncio.run()` Inside Celery Task Creates New Event Loop — Must Use NullPool

**What goes wrong:** If metric service code creates a SQLAlchemy engine with connection pooling at module level, calling `asyncio.run()` in the Celery task creates a new event loop. Pooled connections from the previous loop attach to the old loop's Futures, causing `asyncpg.InterfaceError: cannot perform operation: another operation is in progress` or `Task got Future attached to a different loop`.

**Why it happens:** Celery's sync entrypoint wraps async code in `asyncio.run()`, creating a fresh event loop on each task call. Connection pool connections reference the old loop.

**How to avoid:** Use `NullPool` per task call, exactly as `sync_mefi_leads.py` does (already documented in Phase 2 — `task_engine = create_async_engine(..., poolclass=NullPool)`). All DB imports stay inside `_calc_async` body.

**Warning signs:** Intermittent `asyncpg.InterfaceError` in the metric task but not in isolation testing.

### Pitfall 3: Designer Detection Missing Leads Currently at Non-Designer Status

**What goes wrong:** A lead is currently at status `3` (Ofertat) but at some earlier point had status `24` (DESIGNER). If you only check `raw_mefi_leads.status_id == 24`, you miss this lead and it falls into `alte` instead of `designer`.

**Why it happens:** The DESIGNER category is a lifecycle stage a lead passes through, not a permanent classification. D-02 explicitly requires history-based detection.

**How to avoid:** Query `mefi_lead_history` for `to_status_id = 24` (OR check `raw_mefi_leads.status_id = 24` for leads currently in designer status). Use the subquery pattern in Pattern 3 above.

**Warning signs:** The `designer` row in `source_daily_kpi` shows 0 leads on days when you know there were designer appointments.

### Pitfall 4: Integer Division Silently Truncating Conversion Rates

**What goes wrong:** `COUNT(visits) / COUNT(leads)` in SQLAlchemy with integer columns returns an integer (e.g., 49/200 = 0 not 0.245).

**Why it happens:** PostgreSQL integer division truncates. SQLAlchemy passes the types through.

**How to avoid:** Cast the numerator to NUMERIC before dividing: `func.count(...).cast(Numeric) / NULLIF(func.count(...), 0)`. Alternatively use `func.count(...) * 1.0` to force float promotion. NUMERIC(5,4) is the target type per SPEC.md §7.

**Warning signs:** All conversion rates are 0 despite having leads, visits, offers in the DB.

### Pitfall 5: UPSERT on Composite Key Missing `source` in source_daily_kpi Conflict Target

**What goes wrong:** `source_daily_kpi` UNIQUE constraint is on `(tenant_id, source, date)` — three columns. If you only specify `(tenant_id, date)` as the conflict target, the UPSERT fails with a constraint violation on insert of the second source category.

**Why it happens:** `source_daily_kpi` has a 3-column unique key unlike `daily_kpi` (2 columns) and `salesperson_daily_kpi` (3 columns with salesperson_external_id). Easy to miss.

**How to avoid:** Set `index_elements=["tenant_id", "source", "date"]` in the `on_conflict_do_update()` call for `SourceDailyKpi`. Verify the actual UNIQUE constraint in the migration matches.

**Warning signs:** `asyncpg.exceptions.UniqueViolationError` on second source category insert.

### Pitfall 6: `with_loader_criteria` Tenant Filter Fires on SELECT But Not Core INSERT

**What goes wrong:** The session-level `_add_tenant_filter` event listener (session.py) only fires on ORM SELECT statements (`execute_state.is_select`). Core `pg_insert().on_conflict_do_update()` bypasses it. If `tenant_id` is not explicitly included in the row dict, metric rows are inserted without a tenant.

**Why it happens:** Core INSERT/UPDATE statements skip the ORM criteria machinery. Phase 2 MefiRepository validates this explicitly, and the same discipline is required here.

**How to avoid:** `MetricsRepository` must validate `tenant_id` in every row dict before executing INSERT, exactly like `MefiRepository.bulk_upsert_leads` does. Fail loudly (`raise ValueError`) rather than silently inserting unscoped rows.

---

## Code Examples

### SPEC.md §7 Schema — Verbatim Column Reference (daily_kpi)

These are the exact column names from SPEC.md §7 DDL — the Alembic migration must match:

```sql
-- Source: SPEC.md §7 (verified by grepping lines 744–803)
daily_kpi:
  spend_meta, spend_google, spend_tiktok, spend_digital_total  -- NUMERIC(10,2) NULLABLE
  web_sessions, web_conversion_rate                              -- INT, NUMERIC(5,4) NULLABLE
  leads_mail_fb_ig, leads_telefon, leads_whatsapp, leads_site,
  leads_designer, leads_alte, leads_total                        -- INT NULLABLE
  cpl_overall, cpl_by_channel                                    -- NUMERIC(8,2), JSONB NULLABLE
  visits_count, offers_count, contracts_count                    -- INT
  conversion_l_to_v, conversion_v_to_o, conversion_l_to_o,
  conversion_o_to_c, conversion_l_to_c                          -- NUMERIC(5,4)
  revenue, avg_deal_size, avg_deal_size_per_day,
  cost_acquisition_contract                                      -- NUMERIC(12,2), NUMERIC(10,2)
  cac, roas                                                      -- NUMERIC(10,2), NUMERIC(8,2) NULLABLE
  calls_total, calls_answered, calls_missed,
  avg_call_duration_seconds, avg_sentiment_score                 -- INT/NUMERIC NULLABLE
  calculated_at  -- TIMESTAMPTZ DEFAULT NOW()
  UNIQUE(tenant_id, date)

salesperson_daily_kpi:
  salesperson_external_id  -- TEXT
  leads_assigned, leads_contacted, avg_time_to_first_touch_minutes  -- INT
  visits_conducted, offers_sent, deals_won, deals_lost  -- INT
  revenue  -- NUMERIC(12,2)
  conversion_l_to_v, conversion_v_to_o, conversion_o_to_c, conversion_l_to_c  -- NUMERIC(5,4)
  avg_deal_size  -- NUMERIC(10,2)
  calls_made, calls_answered, avg_call_duration_seconds  -- INT NULLABLE
  avg_sentiment_score  -- NUMERIC(3,2) NULLABLE
  calculated_at  -- TIMESTAMPTZ DEFAULT NOW()
  UNIQUE(tenant_id, salesperson_external_id, date)

source_daily_kpi:
  source  -- TEXT (7 categories per D-04)
  leads  -- INT
  ad_spend, cpl, cac, roas  -- NUMERIC NULLABLE
  visits, offers, deals_won  -- INT
  revenue  -- NUMERIC(12,2)
  conversion_rate  -- NUMERIC(5,4)
  calculated_at  -- TIMESTAMPTZ DEFAULT NOW()
  UNIQUE(tenant_id, source, date)
```

**Phase 3 migration 004 must ADD beyond SPEC.md §7:**
- `data_completeness_pct NUMERIC(5,2)` to `salesperson_daily_kpi` (METR-06, SC#3)
- One `_wow_delta NUMERIC(8,4)` + `_mom_delta NUMERIC(8,4)` pair per numeric KPI in `daily_kpi` (METR-05, SC#5)
- `business_hours` key in `tenants.funnel_config` JSONB seed (D-07)
- Updated `v_mefi_leads_active` with history-based `reached_*` logic (Gap 5)

### Funnel Conversion Rate SQL Pattern

```python
# Source: SPEC.md §7 + REQUIREMENTS METR-02 — zero-division guard is mandatory (SC#2)
# [ASSUMED] — illustrative, concrete column names verified from model definition
from sqlalchemy import func, case
from sqlalchemy.types import Numeric

leads_total = func.count(v.c.id).label("leads_total")
visits_count = func.count(
    case((v.c.reached_visit == True, v.c.id))
).label("visits_count")

conversion_l_to_v = (
    (visits_count.cast(Numeric(12, 4)) / func.nullif(leads_total, 0))
    .label("conversion_l_to_v")
)
```

### Task Skeleton (Fork-Safe Pattern)

```python
# Source: backend/app/tasks/etl/sync_mefi_leads.py — established pattern
from __future__ import annotations
import asyncio
from datetime import date as date_type
from uuid import UUID

from app.tasks.celery_app import celery_app

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
    calculation_date: str | None = None,  # ISO date string or None → yesterday
) -> dict:
    try:
        return asyncio.run(_calc_async(UUID(tenant_id), calculation_date))
    except Exception as exc:
        raise self.retry(exc=exc) from exc


async def _calc_async(tenant_id: UUID, calculation_date: str | None) -> dict:
    # All DB/model imports deferred here — fork-safety (INFRA-05, Pitfall 2)
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool
    from app.core.config import settings
    from app.core.tenancy import set_tenant_id
    # ... rest of implementation
    set_tenant_id(tenant_id)
    task_engine = create_async_engine(settings.database_url, poolclass=NullPool)
    # ...
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `pytz` for timezone handling | `zoneinfo` (Python 3.9+ stdlib) | Python 3.9 release | zoneinfo is authoritative IANA database; pytz still works but is legacy |
| Celery `apply_async()` chains | `celery.chain()` with `.si()` immutable signatures | Celery 3.x+ | `.si()` prevents passing results between chain links; required for independent tasks |
| ORM-level INSERT | `pg_insert().on_conflict_do_update()` Core insert | SQLAlchemy 1.4+ | Atomic UPSERT; ORM equivalent is more verbose |

**Deprecated/outdated:**
- `from typing import Optional, List`: Use `T | None`, `list[T]` — Python 3.10+ union syntax already enforced in this codebase
- Fixed UTC offset for Romania: Replaced by AT TIME ZONE 'Europe/Bucharest' — DST-correct

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Delta columns naming convention (`{metric}_wow_delta`, `{metric}_mom_delta`) — exact suffix not locked in CONTEXT.md | Schema Gap Analysis | Column names could differ from what Phase 5/6 expects; planner should pick convention and lock it |
| A2 | Exact set of numeric KPIs that get WoW/MoM deltas — "all 5 conversion rates + leads_total + revenue + avg_deal_size" suggested but not locked | Schema Gap Analysis | Missing a delta column that Phase 6/7 tries to read causes AttributeError at runtime |
| A3 | `data_completeness_pct` stored as NUMERIC(5,2) (0.00 to 100.00 range) | Schema Gap Analysis | If stored as NUMERIC(5,4) fraction (0.0000–1.0000) instead, Phase 7 UI must multiply by 100 |
| A4 | Business-hours loop implementation — minute-by-minute iteration is fast enough for Sofa Belle data volumes (≤ 100 new leads/day, first-touch typically same day) | Architecture Patterns | For large backfills (1000 leads × multi-day time spans), consider vectorized numpy approach instead |
| A5 | Designer detection queries `to_status_id = 24` in `mefi_lead_history` — `from_status_id = 24` not needed (a lead transitioning FROM designer to another status is still designer-sourced) | Source Categorization | If designer attribution requires bidirectional history check, counts could be low |
| A6 | `v_mefi_leads_active` view update (Gap 5) is migration 004's responsibility — the planner will include a view DDL update task | Architecture Patterns | If view is not updated, funnel counts may be inaccurate for leads that changed status between syncs |

---

## Open Questions

1. **WoW/MoM delta column naming convention**
   - What we know: METR-05 and SC#5 require deltas; SPEC.md §7 has no delta columns
   - What's unclear: Exact suffix and which metrics get deltas
   - Recommendation: Planner picks `{metric}_wow_delta` / `{metric}_mom_delta` for all 5 conversion rates + leads_total + revenue. Lock in PLAN.md.

2. **Updated `v_mefi_leads_active` view — migration 004 or separate plan?**
   - What we know: The current view uses current-status-only funnel logic; Phase 3 metrics need history-based "ever reached"
   - What's unclear: Whether updating the view should be Wave 0 (schema) or integrated with service implementation
   - Recommendation: Include view update in the Alembic migration 004 task (Wave 0). This ensures metric service tests can rely on correct funnel booleans from the start.

3. **`salesperson_daily_kpi` rows: filter to only active salespeople or emit NULL rows for inactive?**
   - What we know: D-17 says filter on `mefi_salespeople.is_active = true` for per-salesperson metrics
   - What's unclear: Sofa Belle has 11 MEFI users but only 6 confirmed salespeople; `is_active` is NULL for unconfirmed
   - Recommendation: Only emit rows where `is_active = true` (not NULL). This matches D-17. ROADMAP SC#1 says "6 rows for Sofa Belle" which aligns with 6 active salespeople.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11 | zoneinfo stdlib, type hints | ✓ | 3.11.15 | — |
| PostgreSQL | Metric table UPSERT | ✓ (Docker) | 16 | — |
| Redis | Celery broker | ✓ (Docker) | 7 | — |
| SQLAlchemy asyncpg | Async DB queries | ✓ | 2.0.49 / 0.31.0 | — |
| zoneinfo | Business-hours DST | ✓ | stdlib (Python 3.9+) | pytz 2.9.0 available |
| factory-boy | Test fixtures | ✓ | 3.3.3 | — |

**Missing dependencies with no fallback:** None.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.4.2 + pytest-asyncio 1.2.0 |
| Config file | `backend/pytest.ini` or `backend/pyproject.toml [tool.pytest]` |
| Quick run command | `pytest tests/unit/test_metrics*.py -x` |
| Full suite command | `pytest --cov=app --cov-report=term-missing` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| METR-01 | calculate_daily_kpis task writes to all 3 tables | unit (mocked DB) | `pytest tests/unit/test_calculate_daily_kpis.py -x` | ❌ Wave 0 |
| METR-02 | 5 conversion rates computed with zero-division guard | unit | `pytest tests/unit/test_daily_kpi_service.py::test_conversion_rates_zero_denominator -x` | ❌ Wave 0 |
| METR-03 | 7 source categories produced per day, designer detected | unit | `pytest tests/unit/test_source_kpi_service.py::test_designer_detection -x` | ❌ Wave 0 |
| METR-04 | Per-salesperson metrics including time_to_first_touch | unit | `pytest tests/unit/test_salesperson_kpi_service.py -x` | ❌ Wave 0 |
| METR-05 | WoW/MoM deltas NULL when prior data absent | unit | `pytest tests/unit/test_daily_kpi_service.py::test_wow_delta_null_on_missing_prior -x` | ❌ Wave 0 |
| METR-06 | data_completeness_pct correct calculation | unit | `pytest tests/unit/test_salesperson_kpi_service.py::test_data_completeness_pct -x` | ❌ Wave 0 |

**Critical edge case tests required:**

| Test Name | Coverage |
|-----------|---------|
| `test_business_hours_lead_created_outside_hours` | Lead created 20:00 → first touch 09:30 next day → correct business minutes |
| `test_business_hours_lead_created_at_close` | Lead created at 19:00 → first touch 09:01 next day → 1 minute |
| `test_business_hours_dst_spring_forward` | Lead created night before spring-forward → first touch after → correct |
| `test_conversion_rate_zero_denominator` | 0 leads in a category → conversion = NULL (not ZeroDivisionError) |
| `test_designer_category_overrides_source_id` | Lead source_id=2 (mail_fb_ig) but has status_24 in history → categorized as designer |
| `test_upsert_idempotent_same_date` | Running task twice for same date → same row count (no duplicates) |
| `test_wow_delta_null_on_missing_row` | No D-7 row in daily_kpi → wow_delta = NULL |
| `test_delta_precision_numeric` | Decimal precision preserved end-to-end (SC#4 — within 1 RON) |
| `test_inactive_salesperson_excluded` | is_active=False or NULL salespeople → no row in salesperson_daily_kpi |
| `test_seven_source_rows_per_day` | All 7 source categories emitted even when some have 0 leads |

### Wave 0 Gaps (ALL — no Phase 3 test files exist yet)

- [ ] `backend/tests/unit/test_calculate_daily_kpis.py` — task-level unit tests (mocked services)
- [ ] `backend/tests/unit/test_daily_kpi_service.py` — conversion rates, WoW/MoM deltas, zero-division
- [ ] `backend/tests/unit/test_salesperson_kpi_service.py` — per-rep metrics, time_to_first_touch, data_completeness_pct
- [ ] `backend/tests/unit/test_source_kpi_service.py` — source categorization, designer detection
- [ ] `backend/tests/unit/test_business_hours.py` — business-hours arithmetic edge cases
- [ ] `backend/tests/unit/test_metrics_repository.py` — UPSERT idempotency, tenant_id validation
- [ ] `backend/tests/unit/test_migration_004.py` — AST-based migration validation (follows 003 pattern)
- [ ] `backend/tests/factories/metrics_factory.py` — extend Phase 2 factories with metric row builders

### Sampling Rate
- **Per task commit:** `pytest tests/unit/test_metrics*.py -x`
- **Per wave merge:** `pytest --cov=app --cov-report=term-missing` (full suite, ≥ 70% coverage on services/metrics/)
- **Phase gate:** Full suite green + SC#1–SC#6 manually verified before `/gsd:verify-work`

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Not applicable — task runs within Celery worker, no HTTP auth |
| V3 Session Management | No | Not applicable |
| V4 Access Control | Yes | Tenant isolation — every INSERT row must contain tenant_id; validated in MetricsRepository (same pattern as MefiRepository) |
| V5 Input Validation | Yes | `calculation_date` parameter — validate as ISO date string, reject non-date inputs; `tenant_id` validated as UUID at task entry point (same as sync_mefi_leads.py) |
| V6 Cryptography | No | Not applicable |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Metric row missing tenant_id | Information Disclosure | MetricsRepository validates tenant_id in every row dict before INSERT; raises ValueError on missing |
| Calculation date injection (SQL) | Tampering | Parse `calculation_date` as Python `date` object before constructing query — never interpolate raw string into SQL |
| Cross-tenant funnel config read | Information Disclosure | `tenants.funnel_config` read by tenant_id with set_tenant_id() context active — covered by with_loader_criteria |
| Designer subquery reading other tenant's history | Information Disclosure | `mefi_lead_history` query must include `WHERE tenant_id = :tid` — NOT covered by with_loader_criteria for Core queries |

---

## Sources

### Primary (HIGH confidence)
- `backend/app/tasks/etl/sync_mefi_leads.py` — established NullPool, deferred-import, asyncio.run pattern verified in this codebase
- `backend/alembic/versions/003_mefi_schema.py` — existing FUNNEL_CONFIG structure, view DDL, current funnel logic limitation documented inline
- `backend/app/services/repositories/mefi_repository.py` — pg_insert UPSERT pattern proven
- `SPEC.md §7` lines 744–858 — authoritative schema DDL
- `.planning/phases/03-metrics-engine/03-CONTEXT.md` — all locked decisions
- Python docs: `zoneinfo` is stdlib in Python 3.9+ [CITED: docs.python.org/3/library/zoneinfo.html]

### Secondary (MEDIUM confidence)
- `docs/api-references/mefi/enums.md` — status_id 24 = DESIGNER, source_id mappings
- `docs/api-references/mefi/custom-fields.md` — form-cf-20 ofertat flag logic
- `.planning/phases/02-mefi-etl/02-01-SUMMARY.md` and `02-03-SUMMARY.md` — Phase 2 artifacts confirmed complete

### Tertiary (LOW confidence)
- Business-hours algorithm implementation (Pitfall 1 mitigation) — [ASSUMED] based on training knowledge; verified DST behavior using zoneinfo available in Python 3.11 stdlib

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages verified via pip show + slopcheck; no new packages required
- Architecture: HIGH — patterns directly derived from working Phase 2 code in this codebase
- Schema: HIGH — SPEC.md §7 read verbatim; gaps identified by grepping authoritative files
- Business-hours algorithm: MEDIUM — zoneinfo verified as stdlib; algorithm is [ASSUMED] illustrative
- Pitfalls: HIGH — derived from actual code comments in Phase 2 artifacts (NullPool issue documented in sync_mefi_leads.py docstring)

**Research date:** 2026-05-25
**Valid until:** 2026-06-25 (stable stack — no fast-moving dependencies)
