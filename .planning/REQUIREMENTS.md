# Requirements: Sales & Marketing AI Analyst

**Defined:** 2026-05-19
**Core Value:** Every morning, Sofa Belle gets a clear answer to "where are we losing money?" and 5–7 specific tasks for the day — not raw charts, but decisions ready to act on.

---

## v1 Requirements (Iteration 1: MEFI-only MVP)

### Foundation & Infrastructure

- [ ] **INFRA-01**: Docker Compose dev stack runs all services (PostgreSQL 16, Redis 7, FastAPI backend, Celery worker, Celery beat, Next.js frontend) with a single command
- [ ] **INFRA-02**: PostgreSQL schema uses TIMESTAMPTZ for all timestamps and tenant_id on every table
- [ ] **INFRA-03**: SQLAlchemy async session factory with `with_loader_criteria` tenant isolation seam (hardcoded Sofa Belle tenant for MVP — one-line swap in Iteration 4)
- [ ] **INFRA-04**: Celery + celery-redbeat configured with Europe/Bucharest timezone and visibility timeout ≥ 8h
- [ ] **INFRA-05**: Per-worker async SQLAlchemy engine initialized via `worker_process_init` signal (fork-safe pattern)
- [ ] **INFRA-06**: structlog JSON logging with tenant_id, task_id — no PII (no customer names, phones, emails, call content)

### Authentication

- [ ] **AUTH-01**: User can log in with email and password (single Sofa Belle account, no self-registration)
- [ ] **AUTH-02**: Authenticated session persists across browser refresh via JWT (HttpOnly cookie or Authorization header)
- [ ] **AUTH-03**: All dashboard routes require authentication; unauthenticated requests redirect to login

### MEFI Integration (ETL)

- [ ] **MEFI-01**: MEFI API client reads leads from `/leads/search` using `MEFI_API_KEY` from environment
- [ ] **MEFI-02**: Nightly ETL Celery task syncs all leads to `raw_mefi_leads` table via idempotent UPSERT on `(tenant_id, external_id)`
- [ ] **MEFI-03**: Incremental sync uses `date_from = last_sync_at`; initial backfill uses `date_to = sync_start_at` upper bound to prevent page-shift during long runs
- [ ] **MEFI-04**: Lead lifecycle junk filtering: `lifecycle IN ('active', 'lost')` only — junk leads excluded from all metrics
- [ ] **MEFI-05**: Funnel stage derived as "ever reached" from status sets (not "currently in"): Vizita if `status_id IN (17, 3, 1)`, Oferta if `status_id IN (3, 1)`, Contract if `status_id = 1`
- [ ] **MEFI-06**: Best-effort lead history: detect status changes between syncs and emit rows to `mefi_lead_history` with timestamp, from_status, to_status
- [ ] **MEFI-07**: Tenant-specific status/source/salesperson IDs stored in `tenants.funnel_config JSONB` — no hardcoded enum ID constants in code
- [ ] **MEFI-08**: Sync run writes to `sync_runs` log (status, records_synced, duration, error) — both success and failure recorded
- [ ] **MEFI-09**: Liveness probe per sync: if MEFI returns total=0 with no date filter, emit alert (liveness, not empty-result)
- [ ] **MEFI-10**: Rate limit respect: max 50 req/min, read `X-RateLimit-Remaining` header, honor `Retry-After` on 429
- [ ] **MEFI-11**: Celery sync task acquires a Redis lock (`SET NX EX`) keyed on `sync:mefi:{tenant_id}` to prevent duplicate concurrent execution
- [ ] **MEFI-12**: Initial 12-month backfill runs in a dedicated `backfill` Celery queue — separate from daily `default` queue, chunked by month

### Conformed Data Layer

- [ ] **DATA-01**: SQL views (`v_mefi_leads`, `v_mefi_leads_active`) provide clean interface between raw tables and metrics — metric services never query `raw_mefi_*` tables directly
- [ ] **DATA-02**: Critical custom fields promoted to dedicated columns at sync time: showroom ID (`form-cf-14`), UTM source/medium/campaign/content (`form-cf-38..41`)
- [ ] **DATA-03**: All date grouping in views and queries uses `AT TIME ZONE 'Europe/Bucharest'` — no raw UTC grouping by day
- [ ] **DATA-04**: Revenue amounts stored as `NUMERIC(12,2)`, never `float`; API responses serialize as decimal strings

### Metrics Calculation

- [ ] **METR-01**: Celery task calculates daily KPIs after ETL and writes to `daily_kpi`, `salesperson_daily_kpi`, `source_daily_kpi`
- [ ] **METR-02**: Funnel conversion rates calculated: L→V, V→O, L→O, O→C, L→C — with zero-divisor guards
- [ ] **METR-03**: Lead volume by source (6 Sofa Belle categories) tracked per day
- [ ] **METR-04**: Per-salesperson metrics: leads assigned, visits scheduled, offers sent, contracts closed, time-to-first-touch
- [ ] **METR-05**: WoW and MoM delta calculated for each KPI (current period vs same period prior)
- [ ] **METR-06**: `estimated_value` null tracked as data-completeness metric per salesperson (% leads with value filled)

### Anomaly Detection

- [x] **ANOM-01**: Anomaly detection runs after metrics calculation and writes findings to `detected_problems` with severity, metric, current_value, expected_value, estimated_loss_ron
- [x] **ANOM-02**: Rule: leads with no contact attempt > 4 hours during business hours → "slow first touch"
- [x] **ANOM-03**: Rule: offers with no activity > 14 days → "stuck offer"
- [x] **ANOM-04**: Rule: L→V conversion rate drops > 30% vs 30-day baseline → "showroom traffic problem"
- [x] **ANOM-05**: Rule: O→C conversion rate drops > 20% vs baseline → "closing problem"
- [x] **ANOM-06**: Rule: specific salesperson KPI 30%+ below team average → "underperforming salesperson"
- [x] **ANOM-07**: Anomaly detection skips junk leads; flags if junk % > 20% as a marketing quality issue

### AI Insights Generation

- [ ] **AI-01**: Celery task runs at 06:00 Europe/Bucharest, reads `detected_problems` for the day, generates daily insights via Claude Sonnet 4.6
- [ ] **AI-02**: Uses `client.messages.parse(output_format=DailyInsightResponse)` with Pydantic schema — no hand-rolled JSON parsing
- [ ] **AI-03**: `DailyInsightResponse` schema: `{problems: [{title, description, severity, estimated_loss_ron, recommended_actions: [{action, owner, deadline}]}], summary_ro, generated_at}`
- [ ] **AI-04**: System prompt includes Sofa Belle domain context: industry, deal size, cycle length, mandatory showroom visit, 4h response-time target, tone (Romanian, business, no fluff)
- [ ] **AI-05**: `temperature=0.2`; system prompt + tenant context block uses prompt caching (`cache_control`)
- [ ] **AI-06**: Post-generation validation: extract all numbers from narrative text via regex, cross-check against input metrics ±2% tolerance; regenerate (up to 2 retries) on mismatch
- [ ] **AI-07**: On 3 failed generations: save raw response, set `daily_insights.status='failed'`, surface "algorithmic anomalies only" fallback in UI
- [ ] **AI-08**: Log `usage.input_tokens`, `usage.output_tokens`, cost per call to enable budget tracking
- [ ] **AI-09**: Claude API called ONLY from Celery tasks — never from HTTP handlers

### AI Chat

- [ ] **CHAT-01**: User can type a question in Romanian in a chat interface and receive a grounded, data-backed answer from Claude Sonnet 4.6
- [ ] **CHAT-02**: Claude uses Tool Use (function calling) with tools that query the metrics DB: `get_kpi(date_range, metric_name)`, `get_funnel_data(date_range)`, `get_salesperson_performance(salesperson_id, date_range)`, `compare_periods(period_a, period_b)`, `get_loss_reasons(date_range)`, `get_insight_history(date_range)`
- [ ] **CHAT-03**: Conversation history stored in DB per user and persists across browser sessions
- [ ] **CHAT-04**: System prompt includes full Sofa Belle business context (industry, funnel stages, metrics definitions, 4h response-time target, tone)
- [ ] **CHAT-05**: Number cross-check: all numeric values in chat responses are verified against actual DB values; Claude states uncertainty when queried data is unavailable (e.g., asks about ad spend before Iteration 2)
- [ ] **CHAT-06**: Chat responses include inline deep-links to the relevant dashboard section (e.g., "Conversie a scăzut → Sales Dashboard")
- [ ] **CHAT-07**: "Se gândește..." (thinking) indicator shown while Claude is processing / calling tools
- [ ] **CHAT-08**: FastAPI streaming endpoint with `StreamingResponse` and Anthropic async client — responses stream token-by-token to the frontend (exception to the batch-only Claude rule, documented)
- [ ] **CHAT-09**: Typical query response time < 2 seconds to first token; tool call round-trips complete in < 500ms each (DB queries via pre-computed metric tables)
- [ ] **CHAT-10**: Zero hallucinated salesperson names, funnel stage names, or KPI values — all entity references resolved from DB before passing to Claude

### Sales Dashboard

- [ ] **SALE-01**: User can view funnel visualization showing total counts at each stage (Lead → Vizita → Oferta → Contract) for selected date range
- [ ] **SALE-02**: User can view L→V, V→O, L→O, O→C, L→C conversion rates with WoW/MoM delta indicators
- [ ] **SALE-03**: User can view total leads, visits, offers, contracts, revenue (Încasări) as KPI cards with delta vs prior period
- [ ] **SALE-04**: User can view lead volume breakdown by source category (Mail/FB/IG, Telefon, WhatsApp, Site, Designer, Alte) as chart and table
- [ ] **SALE-05**: User can view revenue trend over time (line chart, selected date range)
- [ ] **SALE-06**: User can switch between date ranges: 7d, 30d, 90d, custom; toggle YoY overlay
- [ ] **SALE-07**: User can see "stuck offers" widget: offers with no activity > 14 days, count and list

### Salespeople Dashboard

- [ ] **SALES-01**: User can view leaderboard of all salespeople with: leads assigned, visits scheduled, offers sent, contracts closed, revenue generated, win-rate
- [ ] **SALES-02**: User can view time-to-first-touch distribution per salesperson (target: < 4h), with highlight when target breached
- [ ] **SALES-03**: User can view per-salesperson funnel (leads → visits → offers → contracts) for selected date range
- [ ] **SALES-04**: User can view `data_completeness_pct` per salesperson (% leads with estimated_value filled)

### Marketing Dashboard

- [ ] **MARK-01**: User can view total lead volume by source over time (line chart, date range picker)
- [ ] **MARK-02**: User can view site conversion rate (leads from site / sessions approximation from MEFI — note: GA4 not yet connected in Iteration 1)
- [ ] **MARK-03**: Marketing dashboard has placeholder sections for ad spend data (CPL, CAC, ROAS) clearly labeled "Coming in next update" — structure is ready, data is not
- [ ] **MARK-04**: User can see junk lead percentage by source (marketing hygiene metric)

### AI Insights Page

- [ ] **INSI-01**: User can view today's AI insights: top-3 problems with titles, descriptions, severity, estimated loss (RON), and recommended actions with owner and deadline
- [ ] **INSI-02**: User can view insights for past dates by selecting a date
- [ ] **INSI-03**: User can trigger a manual insights refresh (rate-limited: max 1 per hour; triggers the full pipeline if data is fresh)
- [ ] **INSI-04**: Each insight problem links to the underlying metric that triggered it (source traceability)
- [ ] **INSI-05**: On insights generation failure, user sees algorithmic anomaly list (fallback) with a "Generation failed" notice
- [ ] **INSI-06**: Page shows when insights were generated (`generated_at`) and data freshness status

### UI & Localization

- [ ] **UI-01**: All UI text defaults to Romanian; English secondary (via next-intl locale switching)
- [ ] **UI-02**: Currency formatted as `1.234,56 RON` (`Intl.NumberFormat('ro-RO', {style:'currency', currency:'RON'})`)
- [ ] **UI-03**: Dates formatted as `DD.MM.YYYY` (Romanian convention)
- [ ] **UI-04**: All timestamps displayed in Europe/Bucharest timezone
- [ ] **UI-05**: Every chart and table has loading, empty, and error states
- [ ] **UI-06**: Data freshness banner shown when last sync > 26h ago or a sync failed
- [ ] **UI-07**: Responsive layout for desktop (1280px+) and tablet (768px+)
- [ ] **UI-08**: Charts use shadcn/ui chart components (Recharts v3) — no `@tremor/react` imports

### Daily Pipeline

- [ ] **PIPE-01**: Single Celery `chain()` pipeline triggered at 04:00 Europe/Bucharest: ETL → metrics → anomaly detection → AI insights
- [ ] **PIPE-02**: Each stage runs only if the previous succeeded; failed stage halts the chain and logs the failure
- [ ] **PIPE-03**: Pipeline health check: after ETL completes, verify data exists for today before proceeding to metrics — abort if empty
- [ ] **PIPE-04**: `pipeline_runs` table logs each run with stage, status, duration, records processed

---

## v2 Requirements (Iteration 2+)

### Advertising Integrations (Iteration 2)
- **ADS-01**: Meta Ads (Facebook + Instagram) CPL, CAC, ROAS by campaign
- **ADS-02**: Google Ads integration (requires Developer Token approval — submit application in Phase 1)
- **ADS-03**: TikTok Ads integration (pending confirmation with Sofa Belle on actual TikTok attribution)
- **ADS-04**: Marketing Dashboard: full CPL/CAC/ROAS by channel with trend charts
- **ADS-05**: AI insights enriched with ad spend performance and channel ROI

### Web Analytics (Iteration 3)
- **WEB-01**: GA4 integration — sessions, conversion rate, traffic by source
- **WEB-02**: Google Search Console — keyword rankings, impressions, clicks
- **WEB-03**: Marketing Dashboard: full web traffic + search data

### Multi-tenancy & Production (Iteration 4)
- **MULT-01**: Full SQLAlchemy `with_loader_criteria` tenant isolation enforcement (seam exists from Phase A)
- **MULT-02**: PostgreSQL Row-Level Security as defense-in-depth layer
- **MULT-03**: JWT with `tenant_id` claim + middleware enforcement
- **MULT-04**: Tenant onboarding flow (self-service integration setup)
- **MULT-05**: Stripe billing integration
- **MULT-06**: GDPR audit log + DPA template
- **MULT-07**: Production deployment on Hetzner + Unihost with Caddy reverse proxy

### Future (backlog)
- **FUTR-01**: Showroom-level analytics (requires IP telephony deployment)
- **FUTR-02**: Email/Telegram digest
- **FUTR-03**: Forecasting (pipeline revenue, deal probability)
- **FUTR-04**: Anonymous cross-client benchmarks (after 5+ clients)
- **FUTR-05**: 👍/👎 feedback on insight items for prompt iteration

---

## Out of Scope

| Feature | Reason |
|---------|--------|
| Call transcription | DOTRO MonitorAI handles this; not our responsibility |
| Real-time dashboards | Data freshness is daily; real-time adds infrastructure complexity with no value |
| Custom report builder | High dev cost; low SMB demand; anti-feature that dilutes the daily-action-plan value prop |
| Free-form AI chat | Tempting in 2026 but contradicts the product thesis: structured daily output, not conversation |
| Lead scoring ML | Insufficient data volume for statistical significance at this scale |
| Editing CRM data from our UI | We are read-only analytics; MEFI is the source of truth |
| Per-salesperson logins | Single-tenant MVP has one owner/analyst user; multi-user is Iteration 4 scope |
| PDF export | Browser print is sufficient for MVP; implement only if pilot specifically requests |
| Configurable funnel stages | Design for Sofa Belle's specific funnel; generalize only after client #2 |
| Mobile app | Web-first; no mobile native app planned |
| Telegram/WhatsApp bot | Future backlog |

---

## Traceability

*Updated during roadmap creation (2026-05-19).*

| Requirement | Phase | Status |
|---|---|---|
| INFRA-01 | Phase 1: Foundation | Pending |
| INFRA-02 | Phase 1: Foundation | Pending |
| INFRA-03 | Phase 1: Foundation | Pending |
| INFRA-04 | Phase 1: Foundation | Pending |
| INFRA-05 | Phase 1: Foundation | Pending |
| INFRA-06 | Phase 1: Foundation | Pending |
| AUTH-01 | Phase 1: Foundation | Pending |
| AUTH-02 | Phase 1: Foundation | Pending |
| AUTH-03 | Phase 1: Foundation | Pending |
| MEFI-01 | Phase 2: MEFI ETL | Pending |
| MEFI-02 | Phase 2: MEFI ETL | Pending |
| MEFI-03 | Phase 2: MEFI ETL | Pending |
| MEFI-04 | Phase 2: MEFI ETL | Pending |
| MEFI-05 | Phase 2: MEFI ETL | Pending |
| MEFI-06 | Phase 2: MEFI ETL | Pending |
| MEFI-07 | Phase 2: MEFI ETL | Pending |
| MEFI-08 | Phase 2: MEFI ETL | Pending |
| MEFI-09 | Phase 2: MEFI ETL | Pending |
| MEFI-10 | Phase 2: MEFI ETL | Pending |
| MEFI-11 | Phase 2: MEFI ETL | Pending |
| MEFI-12 | Phase 2: MEFI ETL | Pending |
| DATA-01 | Phase 2: MEFI ETL | Pending |
| DATA-02 | Phase 2: MEFI ETL | Pending |
| DATA-03 | Phase 2: MEFI ETL | Pending |
| DATA-04 | Phase 2: MEFI ETL | Pending |
| METR-01 | Phase 3: Metrics Engine | Pending |
| METR-02 | Phase 3: Metrics Engine | Pending |
| METR-03 | Phase 3: Metrics Engine | Pending |
| METR-04 | Phase 3: Metrics Engine | Pending |
| METR-05 | Phase 3: Metrics Engine | Pending |
| METR-06 | Phase 3: Metrics Engine | Pending |
| ANOM-01 | Phase 4: Anomaly Detection | Complete |
| ANOM-02 | Phase 4: Anomaly Detection | Complete |
| ANOM-03 | Phase 4: Anomaly Detection | Complete |
| ANOM-04 | Phase 4: Anomaly Detection | Complete |
| ANOM-05 | Phase 4: Anomaly Detection | Complete |
| ANOM-06 | Phase 4: Anomaly Detection | Complete |
| ANOM-07 | Phase 4: Anomaly Detection | Complete |
| AI-01 | Phase 5: AI Insights | Pending |
| AI-02 | Phase 5: AI Insights | Pending |
| AI-03 | Phase 5: AI Insights | Pending |
| AI-04 | Phase 5: AI Insights | Pending |
| AI-05 | Phase 5: AI Insights | Pending |
| AI-06 | Phase 5: AI Insights | Pending |
| AI-07 | Phase 5: AI Insights | Pending |
| AI-08 | Phase 5: AI Insights | Pending |
| AI-09 | Phase 5: AI Insights | Pending |
| SALE-01 | Phase 6 (API) + Phase 7 (UI) | Pending |
| SALE-02 | Phase 6 (API) + Phase 7 (UI) | Pending |
| SALE-03 | Phase 6 (API) + Phase 7 (UI) | Pending |
| SALE-04 | Phase 6 (API) + Phase 7 (UI) | Pending |
| SALE-05 | Phase 6 (API) + Phase 7 (UI) | Pending |
| SALE-06 | Phase 6 (API) + Phase 7 (UI) | Pending |
| SALE-07 | Phase 6 (API) + Phase 7 (UI) | Pending |
| SALES-01 | Phase 6 (API) + Phase 7 (UI) | Pending |
| SALES-02 | Phase 6 (API) + Phase 7 (UI) | Pending |
| SALES-03 | Phase 6 (API) + Phase 7 (UI) | Pending |
| SALES-04 | Phase 6 (API) + Phase 7 (UI) | Pending |
| MARK-01 | Phase 6 (API) + Phase 7 (UI) | Pending |
| MARK-02 | Phase 6 (API) + Phase 7 (UI) | Pending |
| MARK-03 | Phase 6 (API) + Phase 7 (UI) | Pending |
| MARK-04 | Phase 6 (API) + Phase 7 (UI) | Pending |
| INSI-01 | Phase 6 (API) + Phase 7 (UI) | Pending |
| INSI-02 | Phase 6 (API) + Phase 7 (UI) | Pending |
| INSI-03 | Phase 6 (API) + Phase 7 (UI) | Pending |
| INSI-04 | Phase 6 (API) + Phase 7 (UI) | Pending |
| INSI-05 | Phase 6 (API) + Phase 7 (UI) | Pending |
| INSI-06 | Phase 6 (API) + Phase 7 (UI) | Pending |
| UI-01 | Phase 1 (i18n scaffold) + Phase 7 | Pending |
| UI-02 | Phase 7: Frontend Dashboards | Pending |
| UI-03 | Phase 7: Frontend Dashboards | Pending |
| UI-04 | Phase 7: Frontend Dashboards | Pending |
| UI-05 | Phase 7: Frontend Dashboards | Pending |
| UI-06 | Phase 6 (API) + Phase 7 (banner UI) | Pending |
| UI-07 | Phase 7: Frontend Dashboards | Pending |
| UI-08 | Phase 7: Frontend Dashboards | Pending |
| PIPE-01 | Phase 2: MEFI ETL | Pending |
| PIPE-02 | Phase 2: MEFI ETL | Pending |
| PIPE-03 | Phase 2: MEFI ETL | Pending |
| PIPE-04 | Phase 1 (table) + Phase 2 (writes) | Pending |
| CHAT-01 | Phase 8: AI Chat | Pending |
| CHAT-02 | Phase 8: AI Chat | Pending |
| CHAT-03 | Phase 8: AI Chat | Pending |
| CHAT-04 | Phase 8: AI Chat | Pending |
| CHAT-05 | Phase 8: AI Chat | Pending |
| CHAT-06 | Phase 8: AI Chat | Pending |
| CHAT-07 | Phase 8: AI Chat | Pending |
| CHAT-08 | Phase 8: AI Chat | Pending |
| CHAT-09 | Phase 8: AI Chat | Pending |
| CHAT-10 | Phase 8: AI Chat | Pending |

**Coverage:**
- v1 requirements: 78 total (68 original + 10 AI Chat)
- Mapped to phases: 78
- Unmapped: 0 ✓

---

*Requirements defined: 2026-05-19*
*Last updated: 2026-05-19 — traceability mapped to 8-phase roadmap*
