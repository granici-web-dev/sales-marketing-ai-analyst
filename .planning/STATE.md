# Project State

**Project:** Sales & Marketing AI Analyst
**Initialized:** 2026-05-19
**Current Phase:** Phase 7 — Frontend Dashboards
**Milestone:** Iteration 1 (MVP1: MEFI-only)

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-19)

**Core value:** Every morning, Sofa Belle gets a clear answer to "where are we losing money?" and 5–7 specific tasks for the day.
**Current focus:** Phase 7 — Frontend Dashboards

## Phase Progress

| Phase | Name | Status | Plans |
|-------|------|--------|-------|
| 1 | Foundation | ✓ Complete (2026-05-21) | 7/7 |
| 2 | MEFI ETL | ✓ Complete (2026-05-23) | 5/5 |
| 3 | Metrics Engine | ✓ Complete (2026-05-28) | 4/4 |
| 4 | Anomaly Detection | ✓ Complete (2026-05-28) | 5/5 |
| 5 | AI Insights | ✓ Complete (2026-05-28) | 4/4 |
| 6 | Backend HTTP API | ✓ Complete (2026-05-28) | 4/4 |
| 7 | Frontend Dashboards | ◆ In progress (2026-05-28) | 3/5 complete |
| 8 | AI Chat | ○ Pending | — |
| 9 | Polish & Deploy | ○ Pending | — |

## Blockers

None currently.

## Key Decisions Made

- Single-tenant first (MVP1-3): tenant_id in schema, enforcement seam in Phase 1
- claude-sonnet-4-5 for AI insights and chat (per SPEC.md)
- shadcn/ui chart (Recharts v3) replacing Tremor
- Next.js 16.2, React 19.2, Tailwind v4.3
- celery-redbeat replacing default Beat file scheduler
- Celery chain() for daily pipeline (not 4 independent cron jobs)
- "Ever reached" funnel stage logic (not "currently in")
- AI Chat (Phase 8): FastAPI StreamingResponse + Anthropic async client + Tool Use — documented exception to batch-only Claude rule; reuses Phase 6 metric services as tool backends
- claude-sonnet-4-5 for both batch insights (Phase 5) and interactive chat (Phase 8) — per SPEC.md and docs/CHAT.md
- Phase 1 auth: HttpOnly cookie + interceptor-based refresh + Next.js middleware route protection
- Phase 1 tenancy: hardcoded Sofa Belle UUID at startup (context var), with_loader_criteria seam, Alembic data migration for seed data
- Phase 1 Docker: separate worker + beat + flower containers, depends_on with service_healthy
- Phase 1 frontend: full shell layout with all 8 nav items from SPEC §13.1, next-intl with Romanian strings from day 1
- Phase 4 detect_* methods: optional pre-fetched data params (None triggers DB fetch) — testable without DB, AsyncMock-friendly
- Phase 4 close rate fallback: CLOSE_RATE_FALLBACK=0.15 when no trailing conversion_o_to_c data
- Phase 4 underperforming salesperson loss: conservative proxy count × avg_deal_size × 0.30 (contracts_closed not available per day)
- Phase 5 AsyncAnthropic: imported at module level in insight_service.py for test patchability; instantiated inside run() body only (INFRA-05 fork safety)
- Phase 5 NUMBER_PATTERN: greedy \b(\d[\d.,]*\d|\d)\b — handles Romanian thousands (23.400→23400) and 4+ digit integers (5050 not truncated to 505)
- Phase 5 anthropic_api_key in Settings: optional empty default — tests mock AsyncAnthropic; production needs real ANTHROPIC_API_KEY in .env
- Phase 7 QueryClientProvider: getQueryClient() singleton in layout.tsx (NOT useState) — server gets new instance per request, browser reuses single instance
- Phase 7 KI-01 fix: postcss.config.mjs (ESM .mjs extension) with @tailwindcss/postcss plugin; transpilePackages: ["radix-ui"] in next.config.ts for Radix UI ESM resolution
- Phase 7 formatters.ts: Intl.NumberFormat('ro-RO') for all monetary/percentage formatting; formatWowDelta returns {label, positive} shape; no .toFixed() anywhere
- Phase 7 tooltip.tsx + popover.tsx: created manually via radix-ui umbrella package (same pattern as sheet.tsx/collapsible.tsx) — shadcn CLI unavailable (pnpm not on PATH)
- Phase 7 RevenueTrend: AreaChart (vs LineChart) — gradient fill more visually informative for daily revenue data
- Phase 7 date URL validation: isNaN(new Date(param).getTime()) check before use per T-7-01 threat mitigation

**Last session:** 2026-05-28 — Phase 7 Plan 03 complete ✓. Salespeople dashboard fully implemented: useSalespeopleDashboard hook (avg_time_to_first_touch_minutes as number|null), LeaderboardTable (sortable, overflow-x-auto, sticky rank+name, red TTFT > 240min), full /salespeople page with Suspense+date range picker. pnpm-workspace.yaml allowBuilds fix for pnpm v11. Plan 07-04 (Marketing) ready to execute.

**2026-05-21 session:** Phase 2 context gathered. Key decisions: store all lifecycle states (active/lost/junk) in raw_mefi_leads, two conformed views (v_mefi_leads_active + v_mefi_leads_junk), auto-detect backfill on first sync, auto-upsert salespeople, new Alembic migration 003 for funnel_config JSONB.

**2026-05-23 session:** Phase 2 APPROVED COMPLETE. 1000/1155 leads ingested (KI-02: burst rate limit on initial backfill — remaining 155 will be picked up by nightly syncs over a few days; deferred fix to Phase 9). All success criteria met: UPSERT idempotent, rate-limit detection+retry working, async event loop bug fixed, custom fields extracted. Advancing to Phase 3 — Metrics Engine.

**2026-05-25 session:** Phase 3 context gathered. Key decisions: 7 source categories (funnel_config names + google), time_to_first_touch from mefi_lead_history first status change with business-hours adjustment (Mon–Sun 09:00–19:00 Bucharest), full SPEC.md §7 schema with nullable ad-spend columns, calculate for yesterday with NULL deltas on missing prior data, date-parameterizable task for backfill. Resume file: .planning/phases/03-metrics-engine/03-CONTEXT.md

**2026-05-25 session (continued):** Phase 3 planning complete. 4 plans in 4 waves: Wave 0 (test stubs), Wave 1 (migration 004 + models), Wave 2 (metric services + MetricsRepository), Wave 3 (calculate_daily_kpis Celery task + chain). All 6 METR requirements covered. Status: Ready to execute.

**2026-05-25 session (03-01 executed):** Phase 3 Plan 01 (Wave 0 test stubs) COMPLETE. 9 files created: 8 RED-state test files + metrics factory. All acceptance criteria met.

**2026-05-26 session (03-02 executed):** Phase 3 Plan 02 (schema foundation) COMPLETE. Migration 004 + 3 SQLAlchemy models + metrics package. 24 Wave 0 model/migration tests GREEN.

**2026-05-26 session (03-03 executed):** Phase 3 Plan 03 (service layer) COMPLETE. 6 files: business_hours util, DailyKpiService, SalespersonKpiService, SourceKpiService, MetricsRepository, services/metrics/__init__.py. 40/40 service layer tests GREEN.

**2026-05-26 session (03-04 executed):** Phase 3 Plan 04 (Celery task) COMPLETE. calculate_daily_kpis task + daily_pipeline chain extension + celery_app registration. 71/71 Phase 3 tests GREEN. All METR requirements covered. Phase 3 execution complete — running verification.

**2026-05-28 session (Phase 3 post-execution fixes):** Three bugs found and fixed during backfill run: (1) UUID vs VARCHAR type mismatch — str(tenant_id) passed to text() bindparams; fixed by passing UUID object directly. (2) NUMERIC(5,4) overflow on conversion rates > 9.9999 — migration 005 widens 10 columns across 3 tables to NUMERIC(8,4). (3) KI-03 visits metric unavailable — migration 006 makes daily_kpi.visits_count nullable; all three services set visits to NULL. Also added: backfill_daily_kpis task (date range loop), docker-compose worker now listens to celery,backfill queues.

**2026-05-28 session (Phase 3 VERIFIED COMPLETE):** Source categorization rewritten to match real MEFI source_ids verified from 1219 ingested leads. Visits metric now correctly = COUNT(source_id=5) Showroom walk-ins (resolves KI-03 — "Vizita" in Sofa Belle Excel IS the Showroom source, not a funnel stage). MEFI throttle bumped to 0.35s (was 0.15s) to clear burst-limit wall at page 11. All 1219/1222 leads synced (99.8%). Metrics backfilled 148 days (2026-01-23 to 2026-05-06). EXACT MATCH against MEFI Clienți report: total contracts 71 = 71 ✓; per-salesperson contracts all match (Raileanu 22, Roibu 16, Godja 10, Dragoi 10, Zagrian 9, Moaca 3). Funnel: 1219 leads → 360 visits → 417 offers → 71 contracts (5.8% L→C). Sources: showroom 360, mail 335, telefon 208, whatsapp 153, site 124, colaborare 17, meta 9, recomandare 6, arhitect 4, client_fidel 2, other 1. Advancing to Phase 4 — Anomaly Detection.

**2026-05-28 session:** Phase 4 context gathered. Key decisions: one aggregate detected_problems row per rule per day (UPSERT on tenant_id+date+rule_id), context_json holds count+IDs, trailing 30-day close rate from daily_kpi for loss formulas, lost-opportunity formulas for trend rules, single AnomalyService in app/services/anomaly/ (Phase 3 pattern), 7-day minimum baseline window, slow_first_touch checks yesterday-only leads. Resume file: .planning/phases/04-anomaly-detection/04-CONTEXT.md

**2026-05-28 session (04-01 executed):** Phase 4 Plan 01 (Wave 0 test stubs) COMPLETE. 4 files created: anomaly_factory.py (GREEN) + 3 RED-state test files. 28 total tests: 23 unit (18 service + 5 repository) + 5 integration (2 non-DB RED + 3 skipped without TEST_DATABASE_URL). All tests collect cleanly with ModuleNotFoundError confirming RED state. Decision: 25% junk threshold (D-20/ROADMAP SC#6 overrides REQUIREMENTS.md 20% baseline).

**2026-05-28 session (04-02 executed):** Phase 4 Plan 02 (schema foundation) COMPLETE. Migration 007 creates detected_problems table with UNIQUE(tenant_id, date, rule_id), 2 performance indexes, FK to tenants.id. DetectedProblem ORM model with 8 domain columns (date, rule_id, severity, metric, current_value NUMERIC(12,4), expected_value NUMERIC(12,4), estimated_loss_ron NUMERIC(12,2), context_json JSONB) + detected_at TIMESTAMPTZ. app/models/anomaly package + app/models/__init__.py updated for Alembic autogenerate discovery.

**2026-05-28 session (04-03 executed):** Phase 4 Plan 03 (service layer) COMPLETE. AnomalyService (5 detect methods + run_all_rules orchestrator) + AnomalyRepository (3-col UPSERT). All 23 unit tests GREEN. Optional-params design: detect_*() methods accept pre-fetched data for testability, auto-fetch from DB when called from run_all_rules(). Key decisions: optional params pattern (AsyncMock-friendly), CLOSE_RATE_FALLBACK=0.15, underperforming sp loss = count × avg_deal_size × 0.30 proxy.

**2026-05-28 session (04-04 executed):** Phase 4 Plan 04 (Celery task wiring) COMPLETE. detect_anomalies task (NullPool, deferred imports, WR-06 stale SyncRun cleanup, PIPE-04 audit trail, WR-04 single commit, CR-05 autoretry). daily_pipeline() extended to 3-link chain: sync_mefi_leads → calculate_daily_kpis → detect_anomalies. celery_app.py include list updated. 45 tests passed (3 skipped live-DB integration). Phase 4 COMPLETE — advancing to Phase 5 AI Insights.

**2026-05-28 session (04-05 executed):** Phase 4 Plan 05 (Gap Closure CR-01, CR-02, INFO) COMPLETE. Two BLOCKER defects closed: (1) CR-01 — migration 007 now includes `detected_at TIMESTAMPTZ NOT NULL DEFAULT now()` between updated_at and date columns (13 columns match ORM model exactly); (2) CR-02 — `_get_junk_ids()` SQL now date-scoped via `AND created_date_local = :kpi_date` (no more all-time junk inflation). INFO closed: context_json keys renamed count→junk_count, total→total_leads per ORM model docstring. All 23 unit tests GREEN. Phase 4 gap-closure complete — Phase 4 FULLY COMPLETE.

**2026-05-28 session:** Phase 5 context gathered. Key decisions: rich SPEC.md schema (positives[], warnings[], weekly_action_plan[], expected_outcome), hard max 3 problems by estimated_loss_ron, problems[].id = rule_id for traceability, user message = anomalies + yesterday KPI snapshot, system prompt (cached) = instructions + Sofa Belle context (real salesperson names: Roibu Valeria/Raileanu Leon/Godja Adina Maria/Dragoi Mihaela/Zagrian Emilia/Moaca Andreea) + output schema, deadlines as relative Romanian labels, status machine: success|failed|fallback, zero-anomaly → positive-only report, anthropic SDK to add to pyproject.toml. Resume file: .planning/phases/05-ai-insights/05-CONTEXT.md

**2026-05-28 session (05-01 executed):** Phase 5 Plan 01 (Wave 0 test stubs) COMPLETE. 7 files created: insight_factory.py (GREEN) + 6 RED-state test files. 41 total tests: 36 unit tests (across schema, prompt_builder, insight_service, number_validator, insight_repository) + 5 integration tests (4 skipped without TEST_DATABASE_URL, 1 AI-09 grep gate PASSING immediately). Key decision: per-test @_integration_skip decorator instead of module-level pytestmark — allows AI-09 grep gate to run without TEST_DATABASE_URL. Advancing to Phase 5 Plan 02 (Wave 1: schema foundation + migration 008).

**2026-05-28 session (05-02 executed):** Phase 5 Plan 02 (schema foundation) COMPLETE. Migration 008 creates daily_insights table with all 12 D-16 columns (including cost_usd NUMERIC(10,6), raw_response TEXT), UNIQUE(tenant_id, date), FK to tenants.id. DailyInsight SQLAlchemy 2.x ORM model with all 8 domain columns. app/models/insights package + app/models/__init__.py updated for Alembic autogenerate discovery. All 4 plan verifications passed. Key decisions: status validation in application layer (no DDL CHECK constraint), 2-column UPSERT conflict target (tenant_id, date). Advancing to Phase 5 Plan 03 (Wave 2: Pydantic schema + services + repository).

**2026-05-28 session (05-03 executed):** Phase 5 Plan 03 (service layer) COMPLETE. 7 new files: DailyInsightResponse Pydantic schema, build_system_prompt() + build_user_message() with Sofa Belle roster and PII guard, extract_numbers_from_text() + cross_check() Romanian number validator, InsightService (run/fallback/cost/retry), InsightRepository (2-col UPSERT). anthropic>=0.30,<1 added to pyproject.toml (installed 0.104.1). anthropic_api_key added to Settings. 36/36 Wave 0 unit tests GREEN. Key deviations: NUMBER_PATTERN regex bug fixed (5050→505 truncation), anthropic_api_key missing from Settings added, anthropic package installed. Advancing to Phase 5 Plan 04 (Celery task wiring).

**2026-05-28 session (05-04 executed):** Phase 5 Plan 04 (Celery task wiring) COMPLETE. generate_daily_insights task created (NullPool + deferred imports + WR-06 + PIPE-04 + soft_time_limit=120 + time_limit=180). PIPE-01 chain fully closed: sync_mefi_leads → calculate_daily_kpis → detect_anomalies → generate_daily_insights. Beat entry 'daily-insights-generation' at 06:00 Europe/Bucharest registered. ANTHROPIC_API_KEY wired to backend + worker in docker-compose.yml. 37/37 tests pass (4 DB-dependent skipped). Phase 5 AI Insights COMPLETE — advancing to Phase 6 Backend HTTP API.

**2026-05-28 session (Phase 5 UAT + number_validator fix):** Live round-trip verified on real Sofa Belle data (2026-05-27). status=success, 668 input tokens, $0.044 per call. Romanian insight quality confirmed: all numbers grounded in real KPI data (17 leads, 85.000 RON, 80% V→O, 29.4%/45.8% showroom, 82 stuck offers). Prompt caching confirmed active: 1,051 tokens written on first call, 1,051 cache_read_input_tokens on second call. Number validator fixed: (1) added current_value/expected_value/context_json scalar values to reference set with minutes→hours and fraction→percent forms; (2) added date day-of-month to reference; (3) skip year range 1900-2100 in cross-check; (4) check summary text only (not problem descriptions which contain domain-knowledge figures). Phase 5 HUMAN-UAT complete (3/3 live tests passed, 1 deferred to Phase 6). Phase 5 FULLY COMPLETE.

**2026-05-28 session (07-01 executed):** Phase 7 Plan 01 (Wave 1 Infrastructure + Foundations) COMPLETE. KI-01 RESOLVED: postcss.config.mjs with @tailwindcss/postcss added; D-03 visual audit APPROVED by user (CSS renders correctly). 18 files created/modified: postcss.config.mjs, formatters.ts (26 unit tests GREEN), useHealthData.ts (staleTime 60s), DataFreshnessBanner, 7 shadcn components installed (card/skeleton/badge/table/chart/collapsible/sheet), recharts + react-day-picker + date-fns installed, dashboard layout.tsx converted to Client Component with getQueryClient singleton + QueryClientProvider, sidebar hidden md:flex, topbar left-0 md:left-[240px] + hamburger Sheet mobile nav, 6 i18n namespaces (sales/salespeople/marketing/insights/common/errors) added to ro.json and en.json. 1 auto-fix: transpilePackages: ["radix-ui"] in next.config.ts (Rule 3 blocking — Radix UI ESM resolution). pnpm typecheck + lint: exit 0. Wave 2 plans (07-02, 07-03, 07-04) now unblocked.

## Known Issues

| ID | Description | Workaround | Fix milestone |
|----|-------------|------------|---------------|
| KI-01 | ~~CSS/Tailwind not loading in frontend dev~~ | RESOLVED 2026-05-28: postcss.config.mjs with @tailwindcss/postcss; D-03 visual audit APPROVED | — |
| KI-02 | ~~Burst rate limit on initial MEFI backfill~~ | RESOLVED 2026-05-28: throttle bumped to 0.35s; 1219/1222 leads synced | — |
| KI-03 | ~~`visits_count` unreliable from `reached_visit`~~ | RESOLVED 2026-05-28: visits = COUNT(source_id=5) Showroom walk-ins; matches Sofa Belle Excel exactly | — |
