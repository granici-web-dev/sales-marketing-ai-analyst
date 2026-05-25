# Phase 3: Metrics Engine - Context

**Gathered:** 2026-05-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Daily KPIs computed deterministically from conformed MEFI views and persisted to three metric tables: `daily_kpi`, `salesperson_daily_kpi`, `source_daily_kpi`. Includes funnel conversion rates, per-salesperson breakdowns (with business-hours-adjusted time_to_first_touch), per-source breakdowns (7 categories), and WoW/MoM deltas.

This phase produces: Alembic migration for all three metric tables (full SPEC.md §7 schema), SQLAlchemy models, metric service layer, and `calculate_daily_kpis` Celery task wired into the existing ETL chain.

**Does NOT include:** anomaly detection rules (Phase 4), AI insights generation (Phase 5), API endpoints (Phase 6), frontend dashboards (Phase 7). Ad-spend fields (CPL, CAC, ROAS) are created as nullable columns — populated in Iteration 2.

</domain>

<decisions>
## Implementation Decisions

### Source Categorization

- **D-01:** Google (source_id=1) stored as a single **`google`** row in `source_daily_kpi` — no UTM-based Ads vs Organic split in Phase 3. UTM split deferred to Iteration 2 when ad spend data is available.
- **D-02:** Designer leads derived from **status_id=24** in `mefi_lead_history` — if a lead ever had status 24, its source category is `designer`, regardless of `source_id`. (Designer is a MEFI status, not a source in `raw_mefi_leads`.)
- **D-03:** TikTok has no dedicated source_id in MEFI — TikTok leads fall under Meta source IDs (2 or 11) and are folded into **`mail_fb_ig`** for Phase 3. Separate `tiktok` category deferred to Iteration 2.
- **D-04:** `source_daily_kpi.source` values use **funnel_config category names** (not SPEC.md generic names). Seven rows per day per tenant:
  `mail_fb_ig` | `telefon` | `whatsapp` | `site` | `designer` | `alte` | `google`

### time_to_first_touch Calculation

- **D-05:** "First touch" = **first row in `mefi_lead_history`** for that lead (earliest recorded status change after creation). Leads with no `mefi_lead_history` rows get `time_to_first_touch = NULL` — incomplete history, not imputed.
- **D-06:** `avg_time_to_first_touch_minutes` is **business-hours-adjusted** — only working minutes count. A lead arriving Friday 19:00 with first touch Saturday 09:00 counts as 0 minutes over-hours penalty (first touch is within the next working window).
- **D-07:** Sofa Belle business hours for adjustment: **Mon–Sun 09:00–19:00 Europe/Bucharest** (7 days/week, 10-hour window). Store the schedule in `tenants.funnel_config` JSONB as `business_hours` so it is tenant-configurable.

### Schema Scope

- **D-08:** Phase 3 Alembic migration creates the **full SPEC.md §7 schema** for all three tables with all ad-spend/GA4/calls columns as `NULLABLE`. Phase 3 populates only what MEFI data provides; future phases UPDATE the same rows. No schema additions needed in Phases 4–9 for columns already defined in SPEC.md §7.
- **D-09:** `source_daily_kpi.source` uses funnel_config category names (see D-04), not SPEC.md generic names (`meta`, `organic`). Phase 3 schema uses `TEXT` for the `source` column — enum constraint deferred until multi-tenant onboarding (Iteration 4).

### Metrics Date Window & Deltas

- **D-10:** `calculate_daily_kpis` calculates KPIs for **yesterday** (the previous full calendar day in `Europe/Bucharest`). At 04:00 Bucharest, the previous day is always complete. This is the default behavior.
- **D-11:** WoW and MoM deltas store **NULL** when prior data doesn't exist (no row for D-7 or D-30). Phase 7 dashboard renders NULL as "N/A" — not zero. Never impute zero for a missing comparison point.
- **D-12:** Task signature: `calculate_daily_kpis(date: date | None = None)`. When `None`, defaults to yesterday. When called with an explicit date, calculates for that date (backfill support). UPSERT on `(tenant_id, date)` handles idempotent re-runs safely.

### Locked Decisions (from Phase 1 / Phase 2)

- **D-13:** "Ever reached" funnel logic (Phase 2 D-09) — Vizita if status ever IN `[17]`, Oferta if status ever IN `[3]` OR `form-cf-20 = "✅DA"`, Contract if status ever `= 1`. Do not use "currently in" logic.
- **D-14:** Metric services query **`v_mefi_leads_active` only** — never `raw_mefi_*` tables directly (Phase 2 D-02).
- **D-15:** All date grouping uses `AT TIME ZONE 'Europe/Bucharest'` — no raw UTC grouping (DATA-03).
- **D-16:** Revenue amounts as `NUMERIC(12,2)`, never `float`; API responses serialize as decimal strings (DATA-04).
- **D-17:** Per-salesperson metrics filter on `mefi_salespeople.is_active = true` (Phase 2 D-06). Inactive or unconfirmed salespeople excluded from `salesperson_daily_kpi`.
- **D-18:** `calculate_daily_kpis` is second in the Celery `chain()`: `sync_mefi_leads → calculate_daily_kpis → detect_anomalies → generate_daily_insights`. ETL failure halts the chain (PIPE-01..03).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Scope
- `.planning/REQUIREMENTS.md` — Phase 3 covers METR-01..06; confirm all 6 requirements are verifiable against success criteria
- `.planning/ROADMAP.md` — Phase 3 success criteria (6 items, SC#1–SC#6) — all must be verifiable
- `SPEC.md §7` — Full PostgreSQL schema for `daily_kpi`, `salesperson_daily_kpi`, `source_daily_kpi` (authoritative column list — Phase 3 migration creates this exactly)

### Sofa Belle Business Domain
- `docs/api-references/mefi/enums.md` — Status IDs, source IDs, salesperson IDs for Sofa Belle (needed for funnel stage derivation and source categorization)
- `docs/api-references/mefi/custom-fields.md` — `form-cf-20` (ofertat flag for Oferta stage), `form-cf-38..41` (UTM fields)
- `docs/SOFABELLE.md` — Business context: showrooms, salespeople, deal cycle, average deal size; use to validate KPI logic against real business behavior

### Architecture & Conventions
- `docs/ARCHITECTURE.md` — Async/sync boundary, Clean Architecture layers; metric service goes in `app/services/metrics/`, task in `app/tasks/etl/`
- `docs/CONVENTIONS.md` — Code style, naming, commit format — mandatory before writing any code
- `CLAUDE.md` — Core principles: async-first, Celery-only for external APIs, structlog no-PII, no SELECT *, always filter by tenant_id

### Phase 2 Artifacts (already built — build on top of these)
- `.planning/phases/02-mefi-etl/02-01-SUMMARY.md` — Schema for `raw_mefi_leads`, `mefi_lead_history`, `mefi_salespeople`; conformed views `v_mefi_leads_active`, `v_mefi_leads_junk`
- `.planning/phases/02-mefi-etl/02-03-SUMMARY.md` — `sync_mefi_leads` Celery task and pipeline chain setup
- `backend/app/models/mefi.py` — `RawMefiLead`, `MefiLeadHistory`, `MefiSalesperson` models (column names to query)
- `backend/app/db/base.py` — `TenantScopedMixin`, `TimestampMixin` — new metric models inherit these
- `backend/app/db/session.py` — `AsyncSessionLocal`, `get_current_tenant_id()` — metric task uses these directly
- `backend/app/tasks/celery_app.py` — Celery app instance; `backfill` queue is separate from `default`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/db/base.py` — `TenantScopedMixin` (id, tenant_id, created_at/updated_at) and `TIMESTAMPTZ` type alias. New metric models (`DailyKpi`, `SalespersonDailyKpi`, `SourceDailyKpi`) inherit this.
- `backend/app/db/session.py` — `AsyncSessionLocal` for use in Celery tasks; `get_current_tenant_id()` for tenant-scoped queries. Call `set_tenant_id(sofabelle_uuid)` at task start (same pattern as Phase 2 ETL task).
- `backend/app/models/mefi.py` — `RawMefiLead.external_id`, `MefiLeadHistory.from_status`/`to_status`/`changed_at`, `MefiSalesperson.mefi_user_id`/`is_active`/`showroom` — the fields metric queries join against.
- `backend/app/models/pipeline.py` — `SyncRun` model for writing task run metadata (already used in Phase 2 pattern).
- `backend/app/tasks/celery_app.py` — Existing Celery app with `default` and `backfill` queues; `calculate_daily_kpis` goes into the `default` queue.

### Established Patterns
- **Repository pattern:** Phase 2 established `MefiRepository` in `backend/app/services/repositories/mefi_repository.py`. Create `MetricsRepository` in the same directory for metric table writes (INSERT ... ON CONFLICT DO UPDATE).
- **Celery autoretry:** `@celery_app.task(bind=True, autoretry_for=(Exception,), max_retries=3, default_retry_delay=60)`. Metric task uses same pattern.
- **Tenant context in tasks:** Celery tasks must call `set_tenant_id()` at task start — not available via ASGI middleware (only runs in HTTP context).
- **UPSERT pattern:** `INSERT ... ON CONFLICT (tenant_id, date) DO UPDATE SET ...` — same pattern used in `raw_mefi_leads` Phase 2.
- **No SQL in service layer / no HTTP in task layer:** Metric service queries DB via SQLAlchemy ORM only; task orchestrates service calls and writes `SyncRun`-style metadata.

### Integration Points
- `backend/app/tasks/etl/sync_mefi_leads.py` — Phase 2 chain: `sync_mefi_leads.s() | calculate_daily_kpis.s()`. Phase 3 adds `calculate_daily_kpis` as the second link; the Phase 2 task already has the chain setup placeholder.
- `backend/app/services/metrics/` (new directory) — `daily_kpi_service.py`, `salesperson_kpi_service.py`, `source_kpi_service.py` with calculation logic.
- `backend/app/tasks/etl/calculate_daily_kpis.py` (new) — Celery task entry point; calls metric services.
- `backend/alembic/versions/` — New migration for three metric tables (number sequentially after Phase 2's last migration).

</code_context>

<specifics>
## Specific Ideas

- **`funnel_config.business_hours` extension:** D-07 requires Mon–Sun 09:00–19:00 Bucharest for time_to_first_touch. Store this as a new key in `tenants.funnel_config` JSONB: `"business_hours": {"days": [0,1,2,3,4,5,6], "open": "09:00", "close": "19:00", "tz": "Europe/Bucharest"}`. This makes it tenant-configurable and avoids hardcoding. Phase 3 Alembic migration seeds this key (UPDATE tenants SET funnel_config = funnel_config || ...).
- **Designer source derivation:** Status_id=24 (Designer) check should happen against `mefi_lead_history` — a lead ever having `to_status=24` or `from_status=24` signals designer acquisition. Also check `raw_mefi_leads.status_id = 24` for leads currently in Designer status.
- **`data_completeness_pct` calculation (METR-06):** Per salesperson, `(COUNT(*) FILTER (WHERE estimated_value IS NOT NULL)) / COUNT(*) * 100`. Run against `v_mefi_leads_active` filtered by `assigned_to_id` and date range.
- **Zero-division guards (SC#2):** Every conversion rate calculation must use `NULLIF(denominator, 0)` in SQL or explicit `if denominator == 0: return None` in Python. All 5 conversion rates must handle denominator=0 cleanly.
- **Phase 2 known issue (KI-02):** 155 leads from the initial backfill are still being ingested via nightly syncs. Phase 3 metrics will show slightly incomplete numbers for the first few days — this is expected and acceptable. Historical KPI backfill (D-12) will reconcile once all leads are synced.

</specifics>

<deferred>
## Deferred Ideas

- **UTM-based Google Ads vs Organic split** — Deferred to Iteration 2 when ad spend data (Google Ads API) provides the authoritative signal. For now, all source_id=1 leads are `google`.
- **TikTok source category** — Deferred to Iteration 2. TikTok leads folded into `mail_fb_ig` for Phase 3.
- **CPL, CAC, ROAS calculation** — Schema columns created as nullable in Phase 3; values populated in Iteration 2 when ad spend APIs (Meta, Google, TikTok) are integrated.
- **GA4 web_sessions and web_conversion_rate** — Schema columns created as nullable; populated in Iteration 3.
- **Calls data (calls_total, avg_call_duration_seconds)** — Schema columns created as nullable; populated when DOTRO telephony integration is built (future iteration).
- **Intraday / real-time KPIs** — Phase 3 is batch/daily only. Real-time dashboards are out of v1 scope.

</deferred>

---

*Phase: 3-Metrics-Engine*
*Context gathered: 2026-05-25*
