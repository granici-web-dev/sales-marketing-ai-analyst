# Roadmap: Sales & Marketing AI Analyst

**Created:** 2026-05-19
**Milestone:** Iteration 1 (MVP1 — MEFI-only)
**Granularity:** Standard (5-8 phases)
**Mode:** YOLO (auto-execute)
**Parallelization:** Enabled
**Coverage:** 78/78 v1 requirements mapped (incl. 10 AI Chat requirements added after initial roadmap)

---

## Phases

- [x] **Phase 1: Foundation** *(completed 2026-05-21 — KI-01: CSS/Tailwind unstyled, fix in Phase 7)* — Docker stack, FastAPI async skeleton, Celery+RedBeat, Next.js 16+shadcn UI scaffold, JWT auth, next-intl i18n, multi-tenancy seam
- [ ] **Phase 2: MEFI ETL** — MEFI API client, raw tables, conformed views, "ever reached" funnel logic, idempotent nightly sync with rate limits and backfill
- [ ] **Phase 3: Metrics Engine** — Daily KPI calculation, funnel conversion rates, salesperson and source KPIs, WoW/MoM deltas
- [x] **Phase 4: Anomaly Detection** *(completed 2026-05-28)* — Rule-based anomaly engine writing detected_problems with severity and estimated_loss_ron
- [x] **Phase 5: AI Insights** *(completed 2026-05-28)* — Claude Sonnet 4.5 integration with structured Pydantic schema, prompt caching, post-validation, daily insights table
- [x] **Phase 6: Backend HTTP API** *(completed 2026-05-28)* — FastAPI endpoints for all dashboards and insights with Pydantic response schemas
- [ ] **Phase 7: Frontend Dashboards** — Next.js UI pages (Sales → Salespeople → Marketing → Insights) with Romanian locale
- [ ] **Phase 8: AI Chat** — Interactive Romanian AI chat with Tool Use, conversation history, streaming responses, and number cross-check validation
- [ ] **Phase 9: Polish & Deploy** — E2E tests, Sentry, healthcheck task, Hetzner deployment with Caddy

---

## Phase Details

### Phase 1: Foundation
**Goal:** Working development environment where all infrastructure pieces (web, worker, scheduler, database, cache, frontend) start with one command and a user can log in to a protected route.
**Depends on:** Nothing (first phase)
**Requirements:** INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, INFRA-06, AUTH-01, AUTH-02, AUTH-03, UI-01 (i18n scaffold), PIPE-04 (pipeline_runs table)
**Success Criteria:**
1. Running `docker compose up -d` from project root starts all services (postgres, redis, backend, worker, beat, frontend) and `curl http://localhost:8000/healthz` returns 200 within 30 seconds.
2. `alembic upgrade head` creates all base tables (`tenants`, `users`, `sync_runs`, `pipeline_runs`) with `tenant_id NOT NULL` and `TIMESTAMPTZ` columns; verified via `\d+` in psql.
3. User can POST email and password to `/api/v1/auth/login`, receive a JWT, and the Next.js frontend stores it; subsequent navigation to `/dashboard` succeeds while an unauthenticated request to `/dashboard` redirects to `/login`.
4. `celery -A app.tasks.celery_app inspect ping` returns `pong` from the worker, and `celery-redbeat` shows the scheduler is alive in Redis (`KEYS redbeat::*` is non-empty).
5. A test job logged via `structlog` produces JSON output with `tenant_id`, `task_id`, no PII fields; grepping logs for sample customer name/email/phone returns nothing.
6. SQLAlchemy session factory rejects a query without a tenant context — `with_loader_criteria` seam present in `app/db/session.py` (verified via failing test for "missing tenant").
**Plans:** 7 plans
Plans:
- [ ] 01-01-PLAN.md — Wave 0 test stubs (D-06 failing test, conftest, all unit + integration test files)
- [ ] 01-02-PLAN.md — Docker Compose stack (7 services, healthchecks, Dockerfiles, .env.example)
- [ ] 01-03-PLAN.md — Python core modules (Pydantic Settings, PyJWT security, structlog, ContextVar tenancy, exceptions)
- [ ] 01-04-PLAN.md — SQLAlchemy models, Alembic migrations, tenant isolation seam (with_loader_criteria)
- [ ] 01-05-PLAN.md — Celery + celery-redbeat config with Europe/Bucharest timezone and worker_process_init fork-safety
- [ ] 01-06-PLAN.md — FastAPI app, auth endpoints (login/refresh), health check, ASGI middleware
- [ ] 01-07-PLAN.md — Next.js 16 frontend scaffold, shadcn, next-intl, proxy.ts auth guard, sidebar shell, login page
**UI hint:** yes

---

### Phase 2: MEFI ETL
**Goal:** Nightly sync pulls all Sofa Belle leads from MEFI into PostgreSQL with idempotent UPSERTs, derives a "ever reached" funnel, and exposes clean conformed views for downstream consumption.
**Depends on:** Phase 1
**Requirements:** MEFI-01, MEFI-02, MEFI-03, MEFI-04, MEFI-05, MEFI-06, MEFI-07, MEFI-08, MEFI-09, MEFI-10, MEFI-11, MEFI-12, DATA-01, DATA-02, DATA-03, DATA-04, PIPE-01, PIPE-02, PIPE-03
**Success Criteria:**
1. Triggering the MEFI sync task manually (`celery call app.tasks.etl.sync_mefi_leads`) populates `raw_mefi_leads` with the actual production lead count; running the same task again produces zero duplicate rows (idempotent UPSERT on `(tenant_id, external_id)`).
2. Query `SELECT * FROM v_mefi_leads_active LIMIT 5` returns rows with `funnel_stage` set to one of `lead | vizita | oferta | contract` (derived "ever reached" from status sets), `showroom_id` and `utm_*` columns populated from promoted custom fields, and `lifecycle` filtered to active/lost (no junk).
3. After scheduled run at 03:00 Europe/Bucharest, `sync_runs` shows a row with `status='success'`, `records_synced > 0`, `duration_ms > 0`; a forced 429 in tests results in a row with `status='retried'` honoring the `Retry-After` header.
4. Running two MEFI sync tasks concurrently in tests: the second exits with "lock held" log line within 1s — verified via `SET NX EX` Redis lock on `sync:mefi:{tenant_id}`.
5. The 12-month backfill task enqueued onto the `backfill` queue runs chunked by month without blocking the `default` queue (verified by inspecting both queues during a backfill run; daily sync still completes in `default`).
6. Status change between two consecutive syncs (status_id 17 → 3) writes a row to `mefi_lead_history` with `from_status=17, to_status=3, changed_at` within the inter-sync window.
7. Pipeline chain `etl → metrics → anomaly → insights` halts at ETL failure: forced exception in `sync_mefi_leads` produces `pipeline_runs.status='failed'` for that stage and downstream tasks are not enqueued.
**Plans:** 5 plans
Plans:
- [ ] 02-01-PLAN.md — Alembic migration 003: raw_mefi_leads + mefi_lead_history + mefi_salespeople tables, v_mefi_leads_active + v_mefi_leads_junk views, funnel_config JSONB column + seed; SQLAlchemy models
- [ ] 02-02-PLAN.md — MefiClient(BaseIntegration) HTTP client, Pydantic v2 response schemas, Settings.mefi_api_key
- [ ] 02-03-PLAN.md — MefiRepository (bulk UPSERT, history detection, salesperson upsert), sync_mefi_leads Celery task, pipeline chain + beat schedule
- [ ] 02-04-PLAN.md — backfill_mefi_leads Celery task (12-month chunked historical sync on backfill queue)
- [ ] 02-05-PLAN.md — Full test suite: unit tests (respx mocks) + integration tests (test DB + migration), factory-boy fixtures

---

### Phase 3: Metrics Engine
**Goal:** Daily KPIs computed deterministically from conformed views and persisted to metric tables, with funnel conversion rates, per-salesperson and per-source breakdowns, and WoW/MoM deltas.
**Depends on:** Phase 2
**Requirements:** METR-01, METR-02, METR-03, METR-04, METR-05, METR-06
**Success Criteria:**
1. Running `calculate_daily_kpis` Celery task for date D populates `daily_kpi`, `salesperson_daily_kpi` (6 rows for Sofa Belle), and `source_daily_kpi` (7 rows for 7 source categories per CONTEXT D-04); re-running for the same date does not duplicate rows (UPSERT on `(tenant_id, date, ...)`).
2. `SELECT l_to_v_pct, v_to_o_pct, l_to_o_pct, o_to_c_pct, l_to_c_pct FROM daily_kpi WHERE date = CURRENT_DATE` returns five rates between 0 and 1 with zero-division guards (no NULL/error when a denominator is 0).
3. `salesperson_daily_kpi` for each rep contains `leads_assigned`, `visits_scheduled`, `offers_sent`, `contracts_closed`, `time_to_first_touch_minutes`, and `data_completeness_pct` (% leads with `estimated_value IS NOT NULL`).
4. Computed values for a sample day match a hand-rolled SQL aggregation of `v_mefi_leads_active` within 1 RON (Decimal precision preserved end-to-end; no float drift).
5. `daily_kpi` for date D contains `wow_delta_pct` and `mom_delta_pct` for every numeric KPI, computed as `(current - prior) / prior` against the same weekday 7d ago and same date 30d ago.
6. All date grouping in metric queries uses `AT TIME ZONE 'Europe/Bucharest'` (verified by SQL inspection); a lead created at 23:30 EEST on day D is attributed to day D in `daily_kpi`, not day D+1.
**Plans:** 4 plans
Plans:
- [x] 03-01-PLAN.md — Wave 0 test stubs: 8 unit test files + metrics_factory.py (RED contracts for services, repository, models, migration, task, business_hours util)
- [x] 03-02-PLAN.md — Alembic migration 004 (3 metric tables full SPEC.md §7 + WoW/MoM delta cols + data_completeness_pct + business_hours seed + v_mefi_leads_active history-join update) + SQLAlchemy models
- [x] 03-03-PLAN.md — business_hours util (zoneinfo, DST-correct) + DailyKpiService + SalespersonKpiService + SourceKpiService (7 categories, designer detection) + MetricsRepository (2-col and 3-col UPSERT)
- [x] 03-04-PLAN.md — calculate_daily_kpis Celery task (NullPool, yesterday default per D-10, ISO-date backfill per D-12) + daily_pipeline chain extension (sync_mefi_leads → calculate_daily_kpis per D-18) + celery_app include registration

---

### Phase 4: Anomaly Detection
**Goal:** Rule-based engine consumes metrics and conformed lead views to write structured `detected_problems` rows with severity, current vs expected values, and an estimated loss in RON — these become Claude's input.
**Depends on:** Phase 3
**Requirements:** ANOM-01, ANOM-02, ANOM-03, ANOM-04, ANOM-05, ANOM-06, ANOM-07
**Success Criteria:**
1. `detect_anomalies` task run after metrics calculation writes rows to `detected_problems(date, rule_id, severity, metric, current_value, expected_value, estimated_loss_ron, context_json)` with one row per triggered rule.
2. Seeding a lead with no contact attempt for 5 hours during business hours produces a `slow_first_touch` row with `severity='high'`; outside business hours the same lead does NOT trigger the rule.
3. Seeding an offer in `oferta` stage with no status change for 15 days produces a `stuck_offer` row referencing the lead's external_id in `context_json`.
4. Forcing L→V conversion to drop 35% below the trailing 30-day baseline produces a `showroom_traffic_drop` row with `expected_value` = baseline rate and `current_value` = today's rate.
5. Forcing one salesperson's win rate to 30% below team average produces an `underperforming_salesperson` row identifying that salesperson by `salesperson_id`.
6. Seeding 25% of leads as `lifecycle='junk'` produces a `junk_lead_quality` row referencing source breakdown; junk leads themselves are excluded from all other rule evaluations (verified — no false-positive `slow_first_touch` on junk leads).
7. Each `detected_problems` row has a populated `estimated_loss_ron` computed deterministically from the rule (e.g., stuck_offer = sum(estimated_value of stuck offers) × historical close rate).
**Plans:** 4 plans
Plans:
- [x] 04-01-PLAN.md — Wave 0 test stubs (RED tests for service, repository, task + anomaly_factory)
- [x] 04-02-PLAN.md — Alembic migration 007 (detected_problems table) + DetectedProblem SQLAlchemy model
- [x] 04-03-PLAN.md — AnomalyService (5 rules + run_all_rules) + AnomalyRepository (UPSERT writer)
- [x] 04-04-PLAN.md — detect_anomalies Celery task + daily_pipeline chain extension + celery_app registration

---

### Phase 5: AI Insights
**Goal:** Claude Sonnet 4.5 transforms structured `detected_problems` into a Romanian daily report (top-3 problems + 5-7 action items with owner/deadline) using a typed Pydantic schema, prompt caching, and number-cross-check validation.
**Depends on:** Phase 4
**Requirements:** AI-01, AI-02, AI-03, AI-04, AI-05, AI-06, AI-07, AI-08, AI-09
**Success Criteria:**
1. `generate_daily_insights` Celery task triggered at 06:00 Europe/Bucharest reads `detected_problems` for the day and writes a row to `daily_insights(date, status='success', payload_json, generated_at, input_tokens, output_tokens, cost_usd)`.
2. `payload_json` validates against the `DailyInsightResponse` Pydantic schema: `problems[]` with `title, description, severity, estimated_loss_ron, recommended_actions[{action, owner, deadline}]`, plus `summary_ro` and `generated_at`; invalid structures are rejected by `messages.parse()` before reaching the DB.
3. Insight text is in Romanian (verified — `summary_ro` and `description` fields pass a basic Romanian-language sniff: contain "RON" and at least one of `vânzări|comenzi|oferte|clienți|magazin`).
4. Numbers extracted from narrative text via regex match input metrics within ±2% tolerance; injecting a deliberate number drift in tests triggers up to 2 regenerations, and on 3rd failure writes `status='failed'` with the raw response preserved.
5. `usage.input_tokens`, `usage.output_tokens`, and `cost_usd` are logged per call; second invocation with the same system prompt shows `cache_read_input_tokens > 0` (prompt caching active).
6. Grep of HTTP handler code (`app/api/`) for `anthropic.Anthropic` / `client.messages` returns zero matches — Claude is invoked exclusively from Celery task code.
7. With `daily_insights.status='failed'`, the Insights page query returns the algorithmic anomaly list (fallback) with the failure notice flag set.
**Plans:** 4 plans
Plans:
- [x] 05-01-PLAN.md — Wave 1 test stubs: insight_factory.py + 6 RED-state test files (schema, prompt_builder, insight_service, number_validator, repository, task)
- [x] 05-02-PLAN.md — Wave 2 migration 008 (daily_insights table, D-16 columns, UNIQUE tenant+date) + DailyInsight ORM model
- [x] 05-03-PLAN.md — Wave 3 DailyInsightResponse Pydantic schema + prompt_builder + number_validator + InsightService (Claude API, retry, fallback) + InsightRepository (UPSERT)
- [x] 05-04-PLAN.md — Wave 4 generate_daily_insights Celery task + chain extension (4th link) + beat entry 06:00 + anthropic SDK dependency + Settings.anthropic_api_key

---

### Phase 6: Backend HTTP API
**Goal:** Thin FastAPI endpoints expose dashboard data and insights via Pydantic response schemas — no business logic in handlers, all reads via services against metric tables and conformed views.
**Depends on:** Phase 3, Phase 4, Phase 5
**Requirements:** Thin HTTP layer supporting SALE-01..07, SALES-01..04, MARK-01..04, INSI-01..06, UI-06 (data freshness), PIPE-04 (pipeline_runs read)
**Success Criteria:**
1. `GET /api/v1/dashboards/sales?from=2026-05-01&to=2026-05-19` returns funnel counts, conversion rates with deltas, KPI cards, source breakdown, revenue series in <300ms p95 against pre-computed metric tables.
2. `GET /api/v1/dashboards/salespeople?from=...&to=...` returns leaderboard with 6 rep rows including time-to-first-touch and data_completeness_pct.
3. `GET /api/v1/dashboards/marketing?from=...&to=...` returns lead volume by source, site conversion approximation, junk % by source, and explicitly-null `ad_spend` placeholders.
4. `GET /api/v1/insights/today` returns `DailyInsightResponse` payload from `daily_insights`; `GET /api/v1/insights?date=YYYY-MM-DD` returns historical insights for that day or 404 if absent.
5. `POST /api/v1/insights/refresh` enqueues a pipeline run, is rate-limited to 1 per hour per user (subsequent call within the window returns 429), and returns a `pipeline_run_id` the client can poll.
6. `GET /api/v1/healthz` returns 200; `GET /api/v1/health/data` returns `last_sync_at`, `last_pipeline_status`, and a stale flag if `now - last_sync_at > 26h`.
7. All endpoints return Pydantic-validated responses; revenue fields serialize as decimal strings (not floats); endpoint OpenAPI schema visible at `/docs` matches actual responses.
**Plans:** 4 plans
Plans:
- [x] 06-01-PLAN.md — Wave 1: get_current_user dependency + all dashboard/insight Pydantic response schemas + dashboard factory + schema unit tests
- [x] 06-02-PLAN.md — Wave 1: DashboardReadService (sales, salespeople, marketing, stuck offers) + InsightReadService + HealthReadService + service unit tests
- [x] 06-03-PLAN.md — Wave 2: dashboards.py + insights.py + health/data routers + router registration + rate-limit unit tests + auth integration tests
- [x] 06-04-PLAN.md — Wave 3: Phase 6 integration test suite (all 7 success criteria) + full suite regression check

---

### Phase 7: Frontend Dashboards
**Goal:** Romanian-first Next.js 16 + shadcn/ui application renders Sales, Salespeople, Marketing, and Insights pages with proper loading/empty/error states, date range picker, and AI insight action plan as the headline view.
**Depends on:** Phase 6
**Requirements:** SALE-01, SALE-02, SALE-03, SALE-04, SALE-05, SALE-06, SALE-07, SALES-01, SALES-02, SALES-03, SALES-04, MARK-01, MARK-02, MARK-03, MARK-04, INSI-01, INSI-02, INSI-03, INSI-04, INSI-05, INSI-06, UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, UI-07, UI-08
**Success Criteria:**
1. User navigating to `/sales` sees a funnel visualization (Lead → Vizita → Oferta → Contract) with stage counts, conversion rates with WoW/MoM delta arrows, KPI cards (leads, visits, offers, contracts, revenue), source breakdown chart, revenue trend line, and a stuck-offers widget — all reflecting selected date range.
2. User navigating to `/salespeople` sees a leaderboard of 6 reps with leads/visits/offers/contracts/revenue/win-rate, time-to-first-touch with red highlight where > 4h, per-rep funnel view, and data_completeness_pct column.
3. User navigating to `/marketing` sees lead volume by source over time, site conversion approximation, junk % by source, and clearly-labeled "Coming in next update" placeholders for CPL/CAC/ROAS.
4. User navigating to `/insights` sees today's top-3 problems with title/description/severity/estimated loss (formatted as `1.234,56 RON`)/action items with owner+deadline, a date picker to view past insights, a "Reîmprospătează" refresh button (disabled while rate-limited), and a "Generation failed" notice + algorithmic anomaly fallback when applicable.
5. Switching the locale toggle from `ro` to `en` swaps all UI strings; currency stays formatted as `1.234,56 RON`, dates as `DD.MM.YYYY`, all timestamps shown in `Europe/Bucharest`.
6. Throttled-network test (slow 3G in DevTools) shows skeleton loading states on every chart/table; mocking 500 from API shows error state with retry; mocking empty-data returns empty state copy (not blank screen).
7. Data freshness banner appears at the top of every dashboard page when `last_sync_at > 26h ago` or the last pipeline run failed.
8. Layout renders correctly at 1280px (desktop) and 768px (tablet) widths; grep of frontend source returns zero `@tremor/react` imports.
**Plans:** 5 plans
Plans:
- [x] 07-01-PLAN.md — Infrastructure + Foundations (KI-01 fix, packages, QueryClientProvider, formatters, mobile layout, i18n namespaces) ← **Wave 1 — all others depend on this**
- [x] 07-02-PLAN.md — Sales Dashboard (funnel chart, KPI cards, source breakdown, revenue trend, stuck offers) ← Wave 2 (parallel with 03, 04)
- [x] 07-03-PLAN.md — Salespeople Dashboard (sortable leaderboard table, per-rep funnel, TTFT red highlight) ← Wave 2 (parallel with 02, 04)
- [ ] 07-04-PLAN.md — Marketing Dashboard (source volume line chart, junk % table, ad-spend placeholder) ← Wave 2 (parallel with 02, 03)
- [ ] 07-05-PLAN.md — Insights Dashboard (problem cards, refresh rate-limit, historical picker, fallback) ← **Wave 3 — depends on 01..04; contains blocking mobile checkpoint**
**Wave dependency:** 01 → {02, 03, 04} → 05 (02/03/04 parallelisable)
**Cross-cutting constraints:** All charts use `shadcn chart` abstraction (no direct `recharts` imports in pages); every component uses `useTranslations(ns)` (no hardcoded Romanian strings); `credentials: "include"` required on POST /insights/refresh (CSRF); date params validated as YYYY-MM-DD before API call (T-7-01). SC#8 grep gate (`grep -r "@tremor" frontend/src`) run in 07-01 verify block.
**UI hint:** yes

---

### Phase 8: AI Chat

**Goal:** Business owners and managers can ask questions about their data in plain Romanian and receive accurate, tool-grounded answers with inline dashboard links — turning the product from "dashboard + daily report" into an interactive AI consultant.
**Depends on:** Phase 6 (Backend HTTP API — chat tools reuse the same metric services)
**Requirements:** CHAT-01, CHAT-02, CHAT-03, CHAT-04, CHAT-05, CHAT-06, CHAT-07, CHAT-08, CHAT-09, CHAT-10
**Success Criteria:**
1. User can ask "Cum stăm comparativ cu săptămâna trecută?" and receive a Romanian-language answer with actual WoW delta values fetched via `compare_periods` tool call, displayed with a "Se gândește..." indicator during processing.
2. Claude successfully calls at least 3 distinct tools in a single conversation turn when answering a multi-part question (e.g., "Care e cel mai bun vânzător și de ce a scăzut conversia?"); all tool inputs and outputs are logged in the conversation history row.
3. Asking about data not yet available (e.g., Meta Ads CAC before Iteration 2 is built) produces an honest "Nu am acces la datele de reclamă în această versiune" response, not a hallucinated number.
4. All numeric values in a chat response match the corresponding `daily_kpi` / `salesperson_daily_kpi` DB values within ±1% — verified by a test that cross-checks response text against live DB query.
5. Conversation history for a user session persists after browser refresh: reopening the chat shows prior messages and allows follow-up questions in context.
6. Streaming: user sees first token within 2 seconds of submitting a question; subsequent tokens stream continuously without a loading pause; tool call round-trips (DB query) complete in < 500ms each.
7. Chat endpoint `/api/v1/chat/stream` exists as a `StreamingResponse` using the Anthropic async client; CLAUDE.md documents this as the documented exception to the batch-only rule.
**Plans:** TBD

---

### Phase 9: Polish & Deploy

**Goal:** Application is deployed to production on Hetzner behind Caddy with TLS, observability via Sentry, automated healthcheck, smoke tests passing, and Playwright E2E coverage on the core user flows.
**Depends on:** Phase 7, Phase 8
**Requirements:** All v1 requirements behind production gate; no new functional reqs (covers gaps: backup, monitoring, deployment readiness)
**Success Criteria:**
1. `pnpm test:e2e` Playwright suite passes covering: login → view sales dashboard → switch date range → view insights page → trigger refresh. All flows green in CI.
2. Sentry receives test exception from backend (`raise RuntimeError('sentry test')`) and from frontend (`throw new Error('sentry test')`); both appear in the Sentry project within 30s.
3. `healthcheck` Celery beat task runs every 15 minutes and writes a row to `pipeline_runs` with `stage='healthcheck'`; absence of a row in the last 30 min triggers a Sentry alert.
4. Production URL `https://analyst.sofabelle.ro` (or staging equivalent) serves the application over HTTPS with valid Caddy-issued TLS certificate; redirect from `http://` returns 301 to `https://`.
5. Smoke test script (`scripts/smoke.sh`) hits `/healthz`, logs in with the seed user, fetches `/api/v1/dashboards/sales?from=...&to=...`, and asserts 200 + non-empty body — runs green against production after each deploy.
6. Hetzner deployment via `docker compose -f docker-compose.prod.yml up -d --build` succeeds from a clean VM following `docs/DEPLOYMENT.md`; PostgreSQL data volume persists across `docker compose down && up`.
7. Backup of `pg_dump` runs nightly and the latest dump is restorable in <10 min into a clean PostgreSQL instance (verified once in a restore drill).
**Plans:** TBD

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 7/7 | Executed | 2026-05-21 |
| 2. MEFI ETL | 0/5 | Not started | — |
| 3. Metrics Engine | 1/4 | In progress | — |
| 4. Anomaly Detection | 3/4 | In progress | — |
| 5. AI Insights | 4/4 | Executed | 2026-05-28 |
| 6. Backend HTTP API | 3/4 | In progress | — |
| 7. Frontend Dashboards | 3/5 | In progress | — |
| 8. AI Chat | 0/? | Not started | — |
| 9. Polish & Deploy | 0/? | Not started | — |

---

## Coverage Report

| Group | REQ-IDs | Count | Phase |
|---|---|---|---|
| INFRA | INFRA-01..06 | 6 | Phase 1 |
| AUTH | AUTH-01..03 | 3 | Phase 1 |
| MEFI | MEFI-01..12 | 12 | Phase 2 |
| DATA | DATA-01..04 | 4 | Phase 2 |
| PIPE | PIPE-01..04 | 4 | Phase 1 (PIPE-04 table) + Phase 2 (PIPE-01..03 chain) |
| METR | METR-01..06 | 6 | Phase 3 |
| ANOM | ANOM-01..07 | 7 | Phase 4 |
| AI | AI-01..09 | 9 | Phase 5 |
| SALE | SALE-01..07 | 7 | Phase 6 (API) + Phase 7 (UI) |
| SALES | SALES-01..04 | 4 | Phase 6 (API) + Phase 7 (UI) |
| MARK | MARK-01..04 | 4 | Phase 6 (API) + Phase 7 (UI) |
| INSI | INSI-01..06 | 6 | Phase 6 (API) + Phase 7 (UI) |
| UI | UI-01..08 | 8 | Phase 1 (UI-01 scaffold) + Phase 7 (UI-02..08) |
| CHAT | CHAT-01..10 | 10 | Phase 8 |
| **TOTAL** | | **78** | **All mapped** |

**Coverage: 78/78 v1 requirements mapped — no orphans.**

---

*Roadmap created: 2026-05-19*

---

## Iteration 2 Backlog

*Not in MVP1 scope. These items require Sofa Belle real-world validation before scheduling.*

### IT2-01: MEFI Status History Tracking (visits metric)

**Problem (KI-03):** MEFI API returns only the current lead status. The "ever reached SHOWROOM" signal needed for `visits_count` cannot be reconstructed for historical dates — computing it from current status produces cohort-contaminated numbers (~7 leads currently in showroom vs. ~180-200/month Sofa Belle reports from their own tracking).

**Impact:** `visits_count`, `conversion_l_to_v`, `conversion_v_to_o` are NULL in all KPI tables for MVP1. Offer- and contract-based metrics (`conversion_l_to_o`, `conversion_o_to_c`, `conversion_l_to_c`) are unaffected.

**Solution:** During each nightly sync (`sync_mefi_leads`), compare the incoming current status of each lead against its last-known status stored in `raw_mefi_leads`. When a status change is detected, write a row to a new `lead_status_history` table:

```
lead_status_history(
  tenant_id      UUID NOT NULL,
  external_id    TEXT NOT NULL,       -- lead external_id
  from_status_id INT,
  to_status_id   INT NOT NULL,
  observed_at    TIMESTAMPTZ NOT NULL  -- timestamp of the nightly sync that detected the change
)
```

After a few weeks of accumulated transitions, `reached_visit` can be computed as `BOOL_OR(to_status_id IN (17, 3, 1))` from `lead_status_history` — the same join already scaffolded in `v_mefi_leads_active` (the `h_agg` subquery in migration 004).

**Also unlocks:** time-in-stage metrics (how long a lead spent in each stage), per-salesperson average time from lead to visit, visit-to-offer lag analysis.

**Question for Sofa Belle:** How do they count "Vizita" in their Excel — manual tracking, or a MEFI UI report not exposed via the public API? This will determine whether IT2-01 is sufficient or whether a MEFI data-export endpoint needs to be negotiated.
