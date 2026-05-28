# Phase 4: Anomaly Detection - Context

**Gathered:** 2026-05-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Rule-based anomaly detection engine that runs as the third Celery task in the daily pipeline chain. Reads from `daily_kpi`, `salesperson_daily_kpi`, `v_mefi_leads_active`, and `v_mefi_leads_junk` to write structured `detected_problems` rows with severity, current vs expected values, and estimated loss in RON.

This phase produces: Alembic migration for `detected_problems` table, SQLAlchemy model, `AnomalyService` with 6 rule methods in `app/services/anomaly/`, `AnomalyRepository` for DB writes, and `detect_anomalies` Celery task wired into the existing chain.

**Does NOT include:** AI generation from problems (Phase 5), API endpoints to expose problems (Phase 6), frontend display (Phase 7). Rules and thresholds are fixed in Phase 4 — no dynamic rule configuration UI in this phase.

**Six rules in scope (ANOM-01..07):**
- `slow_first_touch` — lead with no contact attempt for 5+ business hours (ANOM-01, ANOM-02)
- `stuck_offer` — offer in `oferta` stage with no status change for 15+ days (ANOM-03)
- `showroom_traffic_drop` — L→V conversion drops 35%+ below trailing 30-day baseline (ANOM-04)
- `underperforming_salesperson` — win rate 30%+ below team average (ANOM-05)
- `junk_lead_quality` — junk lead rate reaches 25%+ of total (ANOM-06)
- (estimated_loss_ron populated deterministically for all 6 rules — ANOM-07)

</domain>

<decisions>
## Implementation Decisions

### Row Granularity

- **D-01:** `detected_problems` table uses **one aggregate row per rule per day per tenant** — UPSERT conflict target is `(tenant_id, date, rule_id)`. When a rule fires, it writes/updates exactly one row.
- **D-02:** `context_json` holds `count` (number of offending leads/salespeople) + list of `lead_ids` or `salesperson_ids` + a key metric value (e.g., `worst_hours_elapsed`, `max_days_stuck`). Example: `{"count": 3, "lead_ids": ["ext-001", "ext-002"], "worst_hours_elapsed": 8.5}`.
- **D-03:** Salesperson-based rules use the same aggregate model — `salesperson_ids` list in `context_json`. Example: `{"count": 2, "salesperson_ids": [7, 12], "details": [{"id": 7, "win_rate": 0.04, "team_avg": 0.06}]}`.

### estimated_loss_ron Formulas

- **D-04:** **Historical close rate** = trailing 30-day average of `daily_kpi.conversion_o_to_c` (offer-to-contract rate) read from `daily_kpi` table at rule execution time. Falls back to a 7-day window when fewer than 30 days of data exist (see D-11).
- **D-05:** **Trend-based rules** (`showroom_traffic_drop`, `underperforming_salesperson`) use a **lost-opportunity formula**:
  - `showroom_traffic_drop`: `(expected_visits - actual_visits) × avg_deal_size × trailing_close_rate`
  - `underperforming_salesperson`: `(team_avg_contracts - actual_contracts) × avg_deal_size` per day
  - Both read `avg_deal_size` and trailing rates from `daily_kpi` (trailing 30-day avg).
- **D-06:** **`slow_first_touch`** formula: `count_affected_leads × avg_deal_size × 0.25`. The 0.25 drop factor represents a 25% reduced close probability from slow response — conservative and explainable to Sofa Belle.
- **D-07:** **`stuck_offer`** formula (per ROADMAP SC#7 example): `sum(estimated_value of stuck offers) × trailing_close_rate`. Use `raw_mefi_leads.estimated_value`; leads where `estimated_value IS NULL` contribute 0 to the sum (no imputation).
- **D-08:** **`junk_lead_quality`** formula: `junk_lead_count × avg_deal_size × trailing_close_rate`. Junk leads represent "would-have-been" pipeline if quality had been better.

### Rule Architecture

- **D-09:** **Single `AnomalyService` class** in `app/services/anomaly/anomaly_service.py`. Six methods: `detect_slow_first_touch()`, `detect_stuck_offer()`, `detect_showroom_traffic_drop()`, `detect_underperforming_salesperson()`, `detect_junk_lead_quality()`, plus a `run_all_rules()` orchestrator method called by the Celery task.
- **D-10:** **`AnomalyRepository`** in `app/services/repositories/anomaly_repository.py` — handles `INSERT ... ON CONFLICT DO UPDATE` on `detected_problems` table. Mirrors `MetricsRepository` pattern exactly.
- **D-11:** **`junk_lead_quality` is one of the 6 standard rules** — treated uniformly. Each non-junk rule fetches the junk lead set via a shared subquery (`SELECT external_id FROM v_mefi_leads_junk WHERE tenant_id = ?`) and excludes those IDs from its analysis. The subquery is computed once and passed to each rule method (not re-executed per rule).
- **D-12:** New **`app/services/anomaly/`** directory — parallel to `app/services/metrics/`. Not co-located with metric services; anomaly detection is a distinct concern.

### Baseline Window Fallback

- **D-13:** For trend-based rules requiring historical `daily_kpi` data: **use available data with a 7-day minimum**. If `>= 7 rows` exist: compute baseline from all available rows. If `< 7 rows`: skip that rule for the day (no `detected_problems` row written). Log at INFO level: `anomaly.rule_skipped, rule=showroom_traffic_drop, reason=insufficient_baseline, available_days=3`.
- **D-14:** **`slow_first_touch` checks yesterday-only leads** — leads where `created_date_local = kpi_date` AND business-hours-adjusted `time_to_first_touch > 300 minutes` (5 hours). Does not re-fire on chronically untouched leads from earlier days. Consistent with the daily-snapshot model.

### Locked Decisions (from Phase 1 / Phase 3)

- **D-15:** Chain position locked (Phase 3 D-18): `sync_mefi_leads → calculate_daily_kpis → detect_anomalies → generate_daily_insights`. `detect_anomalies` is third in the Celery `chain()`.
- **D-16:** Business hours for slow_first_touch: **Mon–Sun 09:00–19:00 Europe/Bucharest** from `tenants.funnel_config.business_hours` (Phase 3 D-07). Use existing `business_minutes_between()` utility.
- **D-17:** NullPool + deferred imports + autoretry + SyncRun pattern from Phase 3 `calculate_daily_kpis.py` — `detect_anomalies` task follows this exact structure. Source: `backend/app/tasks/etl/calculate_daily_kpis.py`.
- **D-18:** Metric services query **`v_mefi_leads_active` only** for active leads; junk leads are in `v_mefi_leads_junk` (Phase 2 D-02). Anomaly rules query `v_mefi_leads_active` and exclude junk IDs via subquery.
- **D-19:** All `estimated_value` and monetary columns as `NUMERIC(12,2)` / `Decimal`, never `float` (Phase 3 D-16).
- **D-20:** `slow_first_touch` 5-business-hour threshold, `stuck_offer` 15-day threshold, `showroom_traffic_drop` 35% drop threshold, `underperforming_salesperson` 30% below-average threshold — all fixed per ROADMAP success criteria.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Scope
- `.planning/REQUIREMENTS.md` — Phase 4 covers ANOM-01..07; confirm all 7 requirements are verifiable against success criteria
- `.planning/ROADMAP.md` — Phase 4 success criteria (7 items, SC#1–SC#7) — authoritative definition of all 6 rule behaviors and estimated_loss_ron requirement

### Sofa Belle Business Domain
- `docs/api-references/mefi/enums.md` — Status IDs for funnel stage derivation; `status_id=24` (Designer), `status_id=3` (Oferta/ever-offered), `status_id=1` (Contract), `status_id=17` (Showroom visit)
- `docs/SOFABELLE.md` — Business context: avg deal 20,000+ RON, 6 salespeople, 3 showrooms; use to validate rule thresholds and loss formula amounts against real business expectations

### Architecture & Conventions
- `docs/ARCHITECTURE.md` — Clean Architecture layers; anomaly service goes in `app/services/anomaly/`, task in `app/tasks/etl/`
- `docs/CONVENTIONS.md` — Code style, naming, commit format
- `CLAUDE.md` — Core principles: async-first, Celery-only, structlog no-PII, tenant_id on every query

### Phase 2 & 3 Artifacts (already built — build on top of these)
- `backend/app/tasks/etl/calculate_daily_kpis.py` — **Primary template** for `detect_anomalies` task: NullPool, deferred imports, SyncRun pattern, chain extension. Copy this structure exactly.
- `backend/app/services/metrics/daily_kpi_service.py` — Pattern for `AnomalyService` class constructor and method structure
- `backend/app/services/repositories/metrics_repository.py` — Pattern for `AnomalyRepository` (UPSERT with conflict target)
- `backend/app/services/metrics/business_hours.py` — `business_minutes_between()` utility — reuse directly in `slow_first_touch` rule
- `backend/app/models/metrics/daily_kpi.py` — Model pattern for `DetectedProblem` model
- `.planning/phases/03-metrics-engine/03-PATTERNS.md` — All established patterns: deferred imports, NullPool, tenant_id validation, UPSERT, structlog, pg_insert
- `.planning/phases/03-metrics-engine/03-CONTEXT.md` — Phase 3 locked decisions (D-07 business hours, D-14 metric service query scope, D-16 revenue as Decimal)

### Celery Chain
- `backend/app/tasks/etl/sync_mefi_leads.py` — `daily_pipeline()` function that must be extended to add `detect_anomalies.si(tenant_id)` as the third link

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/services/metrics/business_hours.py` — `business_minutes_between(start, end, business_hours_config)` utility. Used directly in `detect_slow_first_touch()` to check if time_to_first_touch > 300 business minutes.
- `backend/app/tasks/celery_app.py` — Celery app instance; `detect_anomalies` task routes to `default` queue (no `backfill` routing needed — anomaly detection is daily, not backfillable in the same way as metrics).
- `backend/app/db/base.py` — `TenantScopedMixin` and `TIMESTAMPTZ` type alias. `DetectedProblem` model inherits these.
- `backend/app/models/pipeline.py` — `SyncRun` model — `detect_anomalies` writes `SyncRun(source="anomaly")` for pipeline audit.

### Established Patterns
- **NullPool per task invocation** — `create_async_engine(settings.database_url, poolclass=NullPool)` inside `_detect_async()` coroutine body. Dispose in `finally`.
- **Deferred imports** — All `app.models.*`, `app.db.session`, `app.services.*` imports MUST be inside the `_detect_async()` function body (not module level). See `calculate_daily_kpis.py` for the exact pattern.
- **Stale SyncRun cleanup** — Before creating a new `SyncRun(status="running")`, mark any existing `running` rows with the same `source="anomaly"` as `failed` (WR-06 pattern from Phase 3 code review).
- **pg_insert UPSERT** — `INSERT INTO detected_problems ... ON CONFLICT (tenant_id, date, rule_id) DO UPDATE SET ...` via `sqlalchemy.dialects.postgresql.insert`.
- **task_routes** — `detect_anomalies` task must declare `name="tasks.etl.detect_anomalies"` in its `@celery_app.task` decorator to match any future routing (WR-07 pattern).
- **Autoretry** — `@celery_app.task(bind=True, autoretry_for=(Exception,), max_retries=3, default_retry_delay=60)`. No manual `try/except self.retry()` wrapper (CR-05 pattern from Phase 3 code review).

### Integration Points
- `backend/app/tasks/etl/sync_mefi_leads.py` — `daily_pipeline()` function: extend Celery chain to add `detect_anomalies.si(tenant_id)` after `calculate_daily_kpis.si(tenant_id)`.
- `backend/app/tasks/celery_app.py` — Add `"app.tasks.etl.detect_anomalies"` to the `include=` list.
- `backend/alembic/versions/` — New migration (number after 006) for `detected_problems` table. Existing migrations: 001-users, 002-tenants, 003-mefi_schema, 004-metrics_schema, 005-widen_conversion_columns, 006-visits_count_nullable.

</code_context>

<specifics>
## Specific Ideas

- **`detected_problems` UPSERT conflict target**: `(tenant_id, date, rule_id)` — 3-column unique constraint, same pattern as `source_daily_kpi` (3-column Pitfall 5 from Phase 3 PATTERNS.md). Must use `pg_insert().on_conflict_do_update(index_elements=["tenant_id", "date", "rule_id"], ...)`.
- **`rule_id` values** (string enum, not integer): `slow_first_touch`, `stuck_offer`, `showroom_traffic_drop`, `underperforming_salesperson`, `junk_lead_quality`. Store as TEXT in DB — no foreign key to a rules table (rules are code, not data).
- **`severity` values**: `low`, `medium`, `high` — TEXT column. Rule-specific severity assignment locked in ROADMAP SC#2 (`slow_first_touch` → `high`).
- **Junk exclusion subquery**: Computed once per `run_all_rules()` call using `SELECT external_id FROM v_mefi_leads_junk WHERE tenant_id = :tenant_id`. Pass the resulting set to each non-junk rule method as `junk_ids: set[str]` parameter.
- **Drop factor for slow_first_touch**: 0.25 (25% reduced close probability) — this is a business assumption, not a measured value. Document it clearly in the code so Sofa Belle can request adjustment after seeing the reports.
- **avg_deal_size source for loss formulas**: Read from trailing 30-day `daily_kpi.avg_deal_size` — same trailing window as close rate (D-04). If NULL (no contracts in window), fall back to the known Sofa Belle value `20000` RON (hardcoded fallback acceptable for MVP1).

</specifics>

<deferred>
## Deferred Ideas

- **Dynamic rule thresholds** — Allowing Sofa Belle to configure thresholds (e.g., change slow_first_touch from 5h to 4h) via `tenants.funnel_config`. Not needed for MVP1; thresholds are code constants in Phase 4.
- **Rule enable/disable toggle** — Per-tenant rule on/off switch. Phase 4 always runs all 6 rules. Deferred to multi-tenant iteration.
- **Historical anomaly trends** — Dashboard showing frequency of each rule firing over time (e.g., "stuck_offer fired 12 days this month"). Phase 7 shows today's problems only; historical trend is Phase 9 / Iteration 2.
- **Additional rules** — e.g., `missed_callback` (lead in `callback_requested` status > 24h), `evening_lead_response` (leads arriving after 19:00 with no morning follow-up). Not in ANOM-01..07 scope.
- **Backfill support** — A `backfill_anomalies` task analogous to `backfill_daily_kpis`. Not in scope for Phase 4; anomalies are point-in-time and less useful to retroactively compute.

</deferred>

---

*Phase: 4-Anomaly-Detection*
*Context gathered: 2026-05-28*
