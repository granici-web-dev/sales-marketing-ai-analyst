# Phase 2: MEFI ETL - Context

**Gathered:** 2026-05-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Nightly sync pipeline that pulls all Sofa Belle leads from the MEFI CRM API into PostgreSQL with idempotent UPSERTs, derives a "ever reached" sales funnel from lead status transitions, and exposes clean conformed views for the downstream metrics engine.

This phase produces: `raw_mefi_leads` table + `mefi_lead_history` table + `mefi_salespeople` table, Alembic migration 003 (funnel_config seed), Celery ETL task (`sync_mefi_leads`), backfill task, MEFI API client class (`MefiClient`), conformed views (`v_mefi_leads_active`, `v_mefi_leads_junk`), and Redis-based sync lock.

**Does NOT include:** metrics calculation (Phase 3), anomaly detection (Phase 4), API endpoints (Phase 6), frontend (Phase 7). Metric services in later phases read from views — never from `raw_mefi_*` tables directly.

</domain>

<decisions>
## Implementation Decisions

### Raw Storage Scope

- **D-01:** Pull **all 3 lifecycle states** (active, lost, junk) from MEFI and store in `raw_mefi_leads`. No lifecycle filter in the API call. Views handle the filtering for metrics.
  > Rationale: Complete audit history. If MEFI reclassifies a junk lead to active, we have the full record. Storage cost is negligible vs. data completeness benefit.

- **D-02:** Two conformed views:
  - `v_mefi_leads_active` — filters `lifecycle IN ('active', 'lost')`, excludes junk. Used by all metric queries.
  - `v_mefi_leads_junk` — filters `lifecycle = 'junk'` only. Used by anomaly rule ANOM-07 (junk% > 20% alert).
  > Never query `raw_mefi_leads` directly from metric services — always go through views.

### Backfill Strategy

- **D-03:** **Auto-detect on first sync.** `sync_mefi_leads` checks if `raw_mefi_leads` is empty for the tenant (COUNT = 0). If yes, it enqueues the `backfill_mefi_leads` task before running today's incremental sync. Zero manual steps on first production deploy.

- **D-04:** Backfill chunks by **full calendar months** going 12 months back. The current (partial) month is handled by the regular incremental sync — no overlap. Date arithmetic: `month_start = date(today.year, today.month - n, 1)`, `month_end = last_day_of_month(month_start)`. Backfill task enqueued onto the `backfill` Celery queue (separate from the daily `default` queue).

### Salesperson List & Showroom Mapping

- **D-05:** Import **all salesperson IDs** encountered in `assigned_to` field during sync. The `sync_mefi_leads` task auto-upserts rows into `mefi_salespeople` via `INSERT ... ON CONFLICT (mefi_user_id) DO NOTHING`. Each row starts with `is_active = NULL` and `showroom = NULL`.

- **D-06:** After first sync, the `mefi_salespeople` table is populated with all observed user IDs. Sofa Belle / developer manually sets `is_active = true` and `showroom = 'Brașov'|'București'|'Cluj'` for the 6 active salespeople. Phase 3 metrics filter on `is_active = true`.
  > Known values from enums.md (ID → name): 2 Palega Andrei, 4 Potinga Dima, 6 Iordache Razvan, 7 Marketing Sofa (marketing, not salesperson), 8 Roibu Valeria, 9 Moaca Andreea, 10 Godja Adina Maria, 11 Zagrian Emilia, 12 Dragoi Mihaela, 13 Raileanu Leon, 14 Elena Ureche. Confirm the 6 active + showroom mapping with Sofa Belle after first sync.

### Funnel Config Migration

- **D-07:** Seed `funnel_config` via a **new Alembic migration 003** in Phase 2 (`003_seed_funnel_config.py`). Uses `UPDATE tenants SET funnel_config = '...' WHERE slug = 'sofabelle'`. Phase 1's `002_seed_sofabelle.py` is not touched.

- **D-08:** `funnel_config` is **one JSONB column** that stores all tenant-specific mappings:
  ```json
  {
    "funnel_stages": {
      "visit": [17],
      "offer": [3],
      "contract": [1]
    },
    "offer_sent_flag_field": "form-cf-20",
    "source_categories": {
      "mail_fb_ig": [2, 11],
      "telefon": [10],
      "whatsapp": [9],
      "site": [6],
      "designer": [],
      "alte": [3, 4, 5, 7, 12, 13]
    },
    "lifecycle_filter": ["active", "lost", "junk"],
    "showroom_field": "form-cf-14",
    "junk_statuses": [23]
  }
  ```
  > Note: `"designer"` source category has no source_id because DESIGNER is a status (24), not a source — verify with Sofa Belle if TikTok leads are tracked separately.
  > Google (source_id=1) is not in source_categories — needs UTM inspection to distinguish Google Ads vs. Google Organic. Handled in Phase 3.

### Locked Decisions (from Phase 1 / Requirements)

- **D-09:** "Ever reached" funnel logic (MEFI-05). Lead is in stage if it EVER had the status, not "currently in": Vizita if status_id ever was 17; Oferta if status_id ever was 3 OR `form-cf-20 = "✅DA"`; Contract if status_id ever was 1.
- **D-10:** Incremental sync uses `date_from = last_sync_at`, `date_to = sync_start_at` upper bound (MEFI-03) to prevent page-shift during long runs.
- **D-11:** Redis lock `SET NX EX` on key `sync:mefi:{tenant_id}` prevents duplicate concurrent execution (MEFI-11).
- **D-12:** Idempotent UPSERT on `(tenant_id, external_id)` for `raw_mefi_leads` (MEFI-02).
- **D-13:** Rate limit: 600 req/min for read keys (`lrd_*`). Read `X-RateLimit-Remaining`, honor `Retry-After` on 429 (MEFI-10). The 600/min limit gives substantial headroom — page at 100/req = 6 pages/sec before any throttling.
- **D-14:** Pipeline triggers downstream via Celery `chain()`: `etl → metrics → anomaly → insights`. ETL failure halts the chain (PIPE-01..03).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### MEFI API (primary source — read all 4 files)
- `docs/api-references/mefi/README.md` — base URL, auth, rate limits, available endpoints, critical limitations
- `docs/api-references/mefi/leads-read.md` — `/leads/search` pagination, filter params, full response schema
- `docs/api-references/mefi/enums.md` — Sofa Belle status/source/salesperson/showroom IDs (tenant-specific)
- `docs/api-references/mefi/custom-fields.md` — `form-cf-14` (showroom), `form-cf-20` (ofertat flag), `form-cf-38..41` (UTM fields), parsing patterns

### Requirements & Scope
- `.planning/REQUIREMENTS.md` — Phase 2 covers MEFI-01..12, DATA-01..04, PIPE-01..03
- `.planning/ROADMAP.md` — Phase 2 success criteria (7 items, SC#1–SC#7) — all must be verifiable
- `SPEC.md §7` — Full PostgreSQL schema: `raw_mefi_leads`, `mefi_lead_history`, conformed views

### Architecture & Conventions
- `docs/ARCHITECTURE.md` — Async/sync boundary, layer responsibilities (ETL task → service → repository)
- `docs/CONVENTIONS.md` — Code style, naming, commit format — mandatory before writing any code
- `docs/INTEGRATIONS.md` — Integration patterns including `BaseIntegration` class contract
- `CLAUDE.md` — Core principles: async-first, no sync in async, Celery-only for external APIs, structlog no-PII

### Phase 1 Artifacts (already built — build on top of these)
- `.planning/phases/01-foundation/01-04-SUMMARY.md` — SQLAlchemy models, TenantScopedMixin, `do_orm_execute` seam, Alembic migration 001+002
- `.planning/phases/01-foundation/01-05-SUMMARY.md` — Celery app, celery-redbeat, `backfill` queue config
- `backend/app/db/session.py` — AsyncSessionLocal, tenant isolation seam
- `backend/app/db/base.py` — Base, TenantScopedMixin, TimestampMixin (TIMESTAMPTZ = DateTime(timezone=True))
- `backend/app/models/pipeline.py` — SyncRun model (already built — write to it after each sync)
- `backend/app/tasks/celery_app.py` — Celery app instance to import from

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/db/base.py` — `TenantScopedMixin` provides `id` (UUID PK), `tenant_id` (UUID NOT NULL), `created_at`/`updated_at` (TIMESTAMPTZ). All new models inherit this.
- `backend/app/db/session.py` — `AsyncSessionLocal`, `get_session()` FastAPI dep, `do_orm_execute` tenant filter. ETL tasks use `AsyncSessionLocal` directly (not via FastAPI dependency).
- `backend/app/models/pipeline.py` — `SyncRun` model is already created. The ETL task writes to it: `status`, `records_synced`, `duration_ms`, `error_msg`, `started_at`, `completed_at`.
- `backend/app/core/config.py` — `settings.mefi_api_key` should be added (currently `.env.example` has `MEFI_API_KEY=`).
- `backend/app/core/tenancy.py` — `get_current_tenant_id()` for any SQLAlchemy queries in ETL tasks. Celery tasks must call `set_tenant_id()` at task start (not via ASGI middleware — that only runs in HTTP context).
- `backend/app/tasks/celery_app.py` — Celery app. `backfill` queue is separate from `default` — ensure it's registered.

### Established Patterns
- **BaseIntegration pattern (CLAUDE.md):** Each external integration inherits `BaseIntegration`. Phase 2 creates `MefiClient(BaseIntegration)` in `backend/app/services/integrations/mefi.py`. Methods: `authenticate()`, `sync()`, `health_check()`.
- **Celery autoretry:** ETL tasks use `@celery_app.task(bind=True, autoretry_for=(Exception,), max_retries=3, default_retry_delay=60)`. For 429 specifically, read `Retry-After` header and use `self.retry(countdown=int(retry_after))`.
- **Idempotent tasks:** All Celery tasks must be safe to re-run. UPSERTs via `INSERT ... ON CONFLICT DO UPDATE` for `raw_mefi_leads`.
- **No SQL in API layer, no HTTP in task layer without Celery:** ETL task → service (MefiClient, repo) → DB.

### Integration Points
- `backend/app/tasks/etl/sync_mefi_leads.py` (new) → calls `MefiClient` → writes to `raw_mefi_leads` via repository → writes to `SyncRun` → chains into metrics task
- `backend/app/services/integrations/mefi.py` (new) → `MefiClient(BaseIntegration)` → `httpx.AsyncClient`
- `backend/app/models/mefi.py` (new) → `RawMefiLead`, `MefiLeadHistory`, `MefiSalesperson` models
- `backend/alembic/versions/003_seed_funnel_config.py` (new) → UPDATE tenants SET funnel_config

</code_context>

<specifics>
## Specific Ideas

- **`form-cf-20` dual-signal for Oferta stage:** Custom field `form-cf-20 = "✅DA"` is an alternative offer-sent indicator (some leads have status IN PROCES but offer already sent). Funnel derivation must check EITHER `status_id = 3` OR `form-cf-20 = "✅DA"` to classify a lead as Oferta. Documented in `custom-fields.md`.
- **Google source ambiguity:** Source ID 1 (Google) cannot be cleanly split into Ads vs. Organic without UTM inspection. Phase 3 metrics will need a UTM-aware source categorization rule. Flag for Phase 3 researcher.
- **TikTok + Designer source gaps:** TikTok not in source list (lands under Meta ADS or Site). DESIGNER source category has no source_id (it's a status). Both need Sofa Belle verification before Phase 3 source breakdowns are finalized.
- **`mefi_salespeople.showroom` manual seed:** After first sync, developer or admin manually sets `is_active` + `showroom` for the 6 active sellers. Consider adding a simple admin endpoint or just documenting the SQL UPDATE as a runbook step.
- **Rate limit headroom:** Read keys get 600 req/min. At 100 leads/page and ~2,000 total Sofa Belle leads, a full sync is ~20 API calls — well within limits. Backfill (12 months × ~500 leads/month ÷ 100/page = ~60 pages) still well under 600/min.

</specifics>

<deferred>
## Deferred Ideas

- **Webhook ingestion:** Real-time lead updates via MEFI webhooks instead of nightly batch — deferred to future iteration when MEFI supports it.
- **Multi-tenant onboarding flow:** Configuring `funnel_config` for new MEFI clients via UI — deferred to Iteration 4.
- **Call data integration:** MEFI API doesn't expose calls/transcripts yet — deferred to future iteration once MEFI expands their API.

</deferred>

---

*Phase: 2-MEFI ETL*
*Context gathered: 2026-05-21*
