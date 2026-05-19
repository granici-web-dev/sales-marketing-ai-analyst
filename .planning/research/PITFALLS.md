# Pitfalls — Sales & Marketing AI Analyst

**Domain:** B2B SaaS analytics on MEFI CRM + ad platforms + GA4/GSC, Claude-generated daily insights, single-tenant pilot (Sofa Belle).

---

## 1. MEFI API Integration Pitfalls

### CRITICAL — 1.1: Funnel derived from current status, not history

Current `status_id` only shows WHERE a lead is now. A lead that moved Lead→Vizita→Oferta no longer appears in Vizita counts — L→V conversion collapses, AI generates a false showroom crisis.

**Prevention:** Define funnel stage as "ever reached" not "currently in":
- Reached Vizita: `status_id IN (17, 3, 1)`
- Reached Oferta: `status_id IN (3, 1)`
- Reached Contract: `status_id = 1`

Build best-effort history by detecting status changes between syncs: compare previous stored `status_id`, emit a `mefi_lead_history` row on change. Document that history is approximate (granularity = sync frequency).

**Phase:** Phase 1 (MEFI ETL). Must be fixed before any sales KPI is computed.

---

### CRITICAL — 1.2: Pagination sort instability during long syncs

New leads created during a multi-hour initial sync shift pages — you skip rows or duplicate them.

**Prevention:**
- Incremental syncs: `sort=status_changed_at, order=asc` with `date_from = last_sync_at`
- Initial sync: `sort=created_at, order=asc` with upper bound `date_to = sync_start_at` to freeze the working set
- UPSERT by `(tenant_id, external_id)` makes duplicates harmless; skipped rows are the real risk

**Phase:** Phase 1.

---

### HIGH — 1.3: Tenant-specific enum IDs hardcoded in code

Status IDs (1, 3, 17, …), source IDs, and salesperson IDs are **per-tenant** (stated explicitly in `enums.md`). Hardcoding `STATUS_OFERTA = 3` silently breaks for any second MEFI client.

**Prevention:**
- Store funnel-status mapping in `tenants.funnel_config JSONB` from day one
- `FunnelStageResolver(tenant)` service — single seam for all status→stage logic
- Log warning on sync when unknown `status_id`/`source_id`/`assigned_to_id` detected

**Phase:** Phase 1.

---

### HIGH — 1.4: Including `lifecycle="junk"` in lead totals

Junk = spam/invalid. Including it inflates total leads, collapses conversion rates, distorts CPL/CAC.

**Prevention:**
- Filter `WHERE lifecycle != 'junk'` (or `IN ('active','lost')`) in every metric query
- Track junk volume separately as a marketing-hygiene metric (`% spam leads`)
- Create SQL view `mefi_leads_clean` — never query `mefi_leads` directly from metric code

**Phase:** Phase 1.

---

### HIGH — 1.5: `estimated_value` null silently zeroes revenue forecasts

`estimated_value` is null when not filled by salesperson. `SUM(estimated_value)` treats null as 0 — pipeline value KPI permanently under-reports.

**Prevention:**
- Add `data_completeness_pct` metric per salesperson (% leads with `estimated_value` filled)
- Use `AVG(estimated_value)` over non-null for trends, not SUM
- Feed AI both the value AND completeness rate so it can flag "ambiguous data"

**Phase:** Phase 1 (metrics layer).

---

### MEDIUM — 1.6: MEFI is a smaller Romanian vendor — undocumented breaking changes

API was released 2026-05-18, explicitly limited to `/leads` only. Smaller vendors ship undocumented schema changes.

**Prevention:**
- Store full `raw_payload JSONB` on every entity (keep per SPEC §7)
- Schema-drift check on every sync: compare top-level keys vs recorded baseline, log diffs
- Maintain `docs/api-references/mefi/CHANGELOG.md`

**Phase:** Phase 1 (raw layer), revisit each iteration.

---

### MEDIUM — 1.7: Rate limit is global, not per-tenant (60 req/min per IP)

600 req/min per token, but only 60 req/min per IP. Two tenants on same egress IP share the IP quota.

**Prevention:**
- Per-source Celery semaphore, cap at 50 req/min (leave headroom for IP limit)
- Read `X-RateLimit-Remaining` header and back off at ≤50 remaining
- On 429, honor `Retry-After` — do NOT use blind exponential backoff

**Phase:** Phase 1 (single-tenant), Iteration 4 (multi-tenant egress routing).

---

## 2. External API Reliability Pitfalls

### CRITICAL — 2.1: Google Ads Developer Token requires 1–3 week review

Fresh dev token = "Test Account Access" only. Basic Access requires Google's formal review. Submit now, not when Iteration 2 starts.

**Prevention:**
- Submit Basic Access application **during Phase 1** as a non-coding deliverable
- Build Iteration 2 against the test MCC with mocked production responses
- Prepare submission artifacts: privacy policy URL, demo video, public landing page

**Phase:** Phase 1 (administrative kickoff).

---

### HIGH — 2.2: Meta long-lived tokens silently expire at 60 days

No clean error — sometimes returns partial/stale data instead of auth failure.

**Prevention:**
- Proactive refresh Celery Beat task every 30 days
- Check `expires_at` before every API call; refresh if < 5 days remain
- Distinguish error code 190 (token expiry) from 17/32/613 (rate limits)
- Recommend client enables System User tokens (don't expire)

**Phase:** Phase 2.

---

### HIGH — 2.3: Meta Insights API dynamic rate limits + async-only for large windows

Requests for >30 day windows can time out; rate limits are dynamic, not fixed.

**Prevention:**
- For >30-day requests: `is_async=True`, poll `AdReportRun.async_status` until completed
- Track `X-Business-Use-Case-Usage` header; throttle when any counter >75%
- Historical backfill: chunk by month, 12 async jobs spaced over an hour

**Phase:** Phase 2.

---

### MEDIUM — 2.4: TikTok Marketing API — no official Python SDK, thinner docs

Documentation is uneven (Chinese-translated sections, version skew). 200 HTTP doesn't always mean success — check `code` field.

**Prevention:**
- Treat TikTok as highest-risk integration; Meta and Google Ads must work without it
- Build a response normalizer: always parse `code`, raise `TikTokAPIError(code, message)` if non-zero
- Pin to specific API version (`v1.3`); daily CI health check on endpoint
- Confirm with Sofa Belle: `enums.md` warns TikTok leads land under `source_id=2 (Meta ADS)` — verify business need before building

**Phase:** Phase 2, confirm business need first.

---

### MEDIUM — 2.5: GA4 Property ID confusion + 2–3 day GSC data delay

GA4 uses numeric Property ID (not UA-style), wrong ID = silent empty results. GSC always has a 2–3 day lag.

**Prevention:**
- Onboarding: explicit "GA4 Property ID" field with format validation + smoke call test
- GSC queries always target `date <= today - 3`; mark last 3 days as "Pending" in UI
- Exclude pending dates from anomaly detection

**Phase:** Phase 3.

---

### HIGH — 2.6: Single broken integration takes down the morning report

If TikTok was down at 03:00, AI prompt has missing rows → malformed prompt → no report.

**Prevention:**
- Each sync writes a `sync_run` log row with status, error, records_synced
- AI prompt receives structured data-availability block: `{mefi: ok, meta: ok, tiktok: down}`
- Prompt instruction: "When source is down/stale, do not infer trends for it; note the gap in warnings"
- UI shows "Data freshness" banner on every dashboard

**Phase:** Phase 2 (multi-source), but contract must be designed in Phase 1.

---

## 3. ETL Pipeline Pitfalls

### CRITICAL — 3.1: Redis visibility timeout < task runtime = duplicate execution

Default Redis visibility timeout is 1 hour. MEFI initial sync runs 1–3 hours → Redis redelivers mid-execution → two workers sync the same tenant simultaneously.

**Prevention:**
- Set `visibility_timeout` to at least 2× the longest task runtime (6–8h for initial sync)
- Redis lock keyed on `sync:mefi:{tenant_id}` with TTL ≥ expected runtime (Redis `SET NX EX`)
- All DB writes must be true UPSONFLICTs (already planned — critical to enforce)
- Use `acks_late=True` on long-running tasks

**Phase:** Phase 1 (first Celery task written).

---

### HIGH — 3.2: "Zero new leads" vs "API returned error" — indistinguishable

Both log "0 records synced." Dashboard goes quiet; no one notices until Sofa Belle owner asks.

**Prevention:**
- Daily liveness probe: `GET /leads` with no date filter, `per_page=1` — total must be > 0
- Rolling 30-day mean of `records_synced` baseline; flag if sync returns 0 when baseline ≥5/day
- Health check task after ETL, before metrics: abort metrics calc if no data for today
- Distinguish "nothing new since last_sync_at" (OK) from "zero total leads in MEFI" (alarm)

**Phase:** Phase 1.

---

### CRITICAL — 3.3: Timezone — MEFI returns UTC, Sofa Belle thinks Europe/Bucharest

MEFI returns `"2026-04-23T06:19:45Z"`. Grouping by `DATE(created_at_source)` without TZ conversion = leads in wrong day. DST transitions (last Sundays March/October) silently shift 1h of leads.

**Prevention:**
- Store `TIMESTAMPTZ` in Postgres (always UTC internally)
- Every "group by day" query: `DATE(created_at_source AT TIME ZONE 'Europe/Bucharest')`
- Read `tenants.timezone` in metrics layer — never hardcode `'Europe/Bucharest'`
- Celery Beat: `timezone='Europe/Bucharest'` AND `enable_utc=True`
- CI test: lead created at 23:45 Europe/Bucharest → assert it lands in day N for all dashboards

**Phase:** Phase 1 (foundational).

---

### HIGH — 3.4: `autoretry_for` retrying non-idempotent DB writes

If sync task is partially through writing when network blips, autoretry runs the whole task again. Non-UPSERT inserts create duplicates.

**Prevention:**
- Every write in a retryable task must be a true UPSERT or `INSERT … ON CONFLICT DO NOTHING`
- Wrap task body in single DB transaction — atomic commit or full rollback
- Chain multi-step tasks via Celery `.chain()` so each step has its own idempotency boundary
- `max_retries=3`; on final failure mark `integration.last_sync_status='failed'` + Sentry event
- `acks_late=True` on long-running tasks

**Phase:** Phase 1.

---

### MEDIUM — 3.5: Multiple Celery Beat instances = duplicate scheduled tasks

Two Beat containers → every task fires twice → double API calls, double Claude spend.

**Prevention:**
- Run exactly one Beat instance; `--pidfile` to enforce
- Use `celery-redbeat` (Redis-backed) for HA — implements leader election
- Defense-in-depth: "last scheduled at" check inside each task

**Phase:** Phase 1 (development), hardening before production.

---

### MEDIUM — 3.6: Initial backfill starves daily sync workers

Initial sync (1–3h) consumes a worker. Only 1 worker → daily tasks queue behind it → no insights on day 1.

**Prevention:**
- Backfill goes to dedicated `backfill` queue with its own worker pool
- Chunk by month: 12 separate tasks (~5–15 min each), cancelable mid-flight
- Daily ETL at highest priority on `default` queue

**Phase:** Phase 1 (when first backfill runs).

---

## 4. AI Insights Generation Pitfalls

### CRITICAL — 4.1: Claude hallucinating numbers in narrative text

Even when exact KPIs are passed in input JSON, Claude may write "vânzările au scăzut cu 23%" when the actual drop was 17%. Trust-killing bug for an analytics product.

**Prevention:**
- Use `client.messages.parse(output_format=PydanticModel)` — structured output, SDK-enforced
- Every numeric claim is a typed field computed by us; Claude writes narrative *around* our numbers
- System prompt: "Niciun fapt inventat — folosește doar datele din input"
- Post-generation validation: extract all numbers from narrative via regex, cross-check against input metrics ±2% tolerance; reject and regenerate on mismatch
- Set `temperature=0.2` for insights call
- UI: every metric in the report links back to the raw KPI it came from

**Phase:** Phase 1 (insights MVP).

---

### HIGH — 4.2: Malformed JSON breaks parsing — no fallback

Even with JSON schema in prompt, Claude occasionally returns invalid JSON (trailing comma, unescaped quote from Romanian text with diacritics, markdown code fence).

**Prevention:**
- Use SDK's `output_config={"format": {"type": "json_schema", "schema": {...}}}` — server-side schema enforcement
- Or `messages.parse(..., output_format=PydanticModel)` — SDK handles the round-trip
- On `JSONDecodeError`: regenerate up to 2 times with "Răspunsul precedent nu era JSON valid. Returnează doar JSON conform schemei."
- Sentinel: if all 3 attempts fail, save raw response, surface "Insight failed — algorithmic anomalies only" in UI
- Test fixtures: leads with names containing quotes, newlines, diacritics

**Phase:** Phase 1.

---

### HIGH — 4.3: Token budget exceeded as data grows

SPEC estimates ~3,000 input tokens. With 12 months YoY + 10 salespeople + anomaly list + future transcripts, easily 20K+ tokens. Cost escalates; may hit context limits.

**Prevention:**
- Input to Claude = aggregated metrics only, never raw rows (hard rule)
- Pre-summarize anomalies before LLM call (anomaly detection runs first)
- Use **prompt caching**: `cache_control={"type":"ephemeral"}` on system prompt + tenant context block (90% cost reduction on cached blocks)
- Log `usage.input_tokens` + `usage.output_tokens` per call; alert if input >10K tokens
- Monthly spend cap per tenant: refuse Claude call if exceeded, fall back to algorithmic report

**Phase:** Phase 1 (design), monitor Phase 2+.

---

### MEDIUM — 4.4: Generic e-commerce reasoning for premium furniture sales cycle

Claude will default to generic patterns: "respond in 5 minutes," "increase ad frequency" — wrong for a 2-week to 2-month premium consultative sales cycle where every deal requires a showroom visit.

**Prevention:**
- Domain context block in system prompt: industry, deal size, cycle length, mandatory showroom visit
- Few-shot examples from Sofa Belle's Excel ground truth (style of expected recommendations)
- Negative constraints: "DO NOT recommend: discount campaigns, generic email blasts"
- 👍/👎 feedback buttons on each insight; store feedback; iterate prompt monthly

**Phase:** Phase 1, iterative refinement in every later phase.

---

### MEDIUM — 4.5: Daily Claude run — DST + Celery Beat skew

Same as Pitfall 3.3. On DST transition night, the 06:00 task may fire at 05:00 local time or twice.

**Phase:** Phase 1 (same fix as timezone pitfall).

---

## 5. Database Schema Pitfalls

### CRITICAL — 5.1: `tenant_id` deferred enforcement — guaranteed cross-tenant leak

Every query written in Phases 1–3 without tenant filtering becomes a data leak risk when Iteration 4 adds a second tenant. Routes that bypass `with_loader_criteria`: raw `text()` queries, Core `select()` not via ORM Session, Celery tasks creating sessions without the event listener, direct asyncpg connections, Postgres views.

**Prevention:**
- Install `with_loader_criteria` event listener seam in Phase 1 — filter by hardcoded constant for MVP, swap in dynamic tenant for Iteration 4 (one-line change)
- CI check: scan codebase for `.execute(text(` and `select(` without tenant filter — fail PR
- CI test: 2-tenant isolation test, assert Session from tenant 1 returns zero tenant-2 rows
- Postgres Row-Level Security as defense-in-depth: `CREATE POLICY tenant_isolation ON ... USING (tenant_id = current_setting('app.current_tenant')::uuid)`

**Note:** `PROJECT.md` states enforcement is deferred; `CLAUDE.md` mandates it. The recommended resolution: install the *seam* now (cheap), defer the *second tenant* to Iteration 4.

**Phase:** Phase 1 (architecture decision).

---

### HIGH — 5.2: `*_daily_kpi` time-series tables grow unbounded

100 tenants × 5 years × ~50 KPI rows/day = ~9M rows. Single-table scans for "last 90 days" get slow.

**Prevention:**
- Partition `daily_kpi` by month (`PARTITION BY RANGE (date)`) from day one
- Composite indexes: `(tenant_id, date)` on every `*_daily_kpi` table
- After 90 days: roll up daily → weekly; drop dailies older than 1 year
- Align with GDPR retention: "data stored while subscription active + 90 days" (SPEC §13)

**Phase:** Phase 1 (partitioning), Phase 3+ (rollup).

---

### HIGH — 5.3: Missing indexes for common dashboard queries

SPEC indexes `mefi_leads (tenant_id, created_at_source DESC)` but dashboards filter by `status`, `salesperson_id`, `source` — sequential scans on 100K+ rows → page loads 200ms → 5s.

**Prevention:**
- EXPLAIN every dashboard query during dev
- Add: `(tenant_id, lifecycle, created_at_source)`, `(tenant_id, salesperson_id, lifecycle)`, `(tenant_id, source, created_at_source)`
- Partial index: `CREATE INDEX ON mefi_leads (tenant_id, created_at_source) WHERE lifecycle = 'active'`
- Periodic `pg_stat_statements` review

**Phase:** Phase 1 (initial set), Phase 2 (after first dashboards).

---

### MEDIUM — 5.4: JSONB `raw_payload` queried at runtime instead of normalized

Querying `raw_payload->'custom_fields'` is slow and breaks if MEFI changes JSON shape.

**Prevention:**
- Promote critical custom fields to dedicated columns at sync time (showroom `form-cf-14`, UTMs `form-cf-38..41`)
- `raw_payload` stays for debugging only — never referenced from API endpoints
- CI lint rule: API endpoints may not reference `raw_payload` in query path

**Phase:** Phase 1.

---

### MEDIUM — 5.5: NUMERIC precision drift on RON amounts

Python `Decimal` round-trip via FastAPI defaults to `float` → loses cents on aggregation.

**Prevention:**
- Pydantic schema fields: `amount: Decimal` (not `float`), `decimal_places=2`
- SQLAlchemy reads to `Decimal`, never `float`
- JSON serialization: emit decimals as strings (`"1234.56"`), not floats
- Frontend: `Intl.NumberFormat('ro-RO', {style:'currency', currency:'RON'})`

**Phase:** Phase 1.

---

## 6. Frontend Dashboard Pitfalls

### HIGH — 6.1: Chart components require `"use client"` — hydration boundary mistakes

Tremor/shadcn chart components use `"use client"`. Importing in Server Component without a Client wrapper = build failure or hydration mismatch. Passing Decimal/Date objects across the boundary = serialization errors.

**Prevention:**
- Every chart in its own Client Component file
- Server Component: data fetch, auth check, layout — passes plain JSON-serializable props (strings/numbers/ISO dates)
- Pre-serialize Decimals to strings and Dates to ISO strings server-side
- `next/dynamic` with `ssr: false` for charts that don't need SEO

**Phase:** Phase 1 (first chart component).

---

### MEDIUM — 6.2: Recharts performance with 365-day series × multiple metrics

YoY mode: 365 points × 2 series × 5 metrics = 3,650 datapoints. Recharts re-renders all on every hover → sluggish on tablet.

**Prevention:**
- Downsample server-side: date ranges >90 days → return weekly aggregates not daily
- `useMemo` keyed on date range for chart data
- `isAnimationActive={false}` for charts with >100 points

**Phase:** Phase 2 (when YoY ships).

---

### HIGH — 6.3: Romanian locale — server vs client timezone divergence

next-intl without explicit `timeZone` and `locale` config → SSR renders UTC, browser renders Europe/Bucharest → hydration mismatch.

**Prevention:**
- Pin `timeZone: 'Europe/Bucharest'` and `locale: 'ro'` in `src/i18n/request.ts`
- Define global formats once: `dateTime`, `number.currency` (RON), `percent` — use `useFormatter()` everywhere
- Docker container `TZ=Europe/Bucharest`
- Romanian specifics: thousands separator `.`, decimal `,` (`1.234,56 RON`); dates `DD.MM.YYYY`; DB collation `ro_RO.utf8`

**Phase:** Phase 1 (next-intl setup), Phase 2 (full localization).

---

### MEDIUM — 6.4: AI insights rendering — markdown vs structured JSON + XSS risk

If AI returns plain text and frontend uses `dangerouslySetInnerHTML` → XSS risk. If stripped of formatting → wall of text.

**Prevention:**
- AI output is structured JSON (SPEC §10) — render with semantic React components, no markdown parsing needed
- If markdown ever creeps in: use `react-markdown` + `rehype-sanitize`, never `dangerouslySetInnerHTML`
- Set `lang="ro"` on insights container for accessibility

**Phase:** Phase 1 (Insights UI).

---

## Phase-Specific Quick Reference

| Phase | Pitfall | Mitigation |
|-------|---------|------------|
| Phase 1 — MEFI ETL | Funnel from current status, not history | 1.1 |
| Phase 1 — MEFI ETL | Tenant enum IDs hardcoded | 1.3 |
| Phase 1 — Celery | Redis visibility timeout < task runtime | 3.1 |
| Phase 1 — Timezone | DST + UTC vs Europe/Bucharest | 3.3, 4.5, 6.3 |
| Phase 1 — Schema | tenant_id discipline deferred → future leak | 5.1 |
| Phase 1 — AI Insights | Hallucination + JSON parse failure | 4.1, 4.2 |
| Phase 1 — Frontend | Server/Client boundary + locale | 6.1, 6.3 |
| Phase 1 (admin) | Submit Google Ads dev token NOW (3-week lead) | 2.1 |
| Phase 2 — Meta | Token expiry at 60d, dynamic rate limits | 2.2, 2.3 |
| Phase 2 — Multi-source | No graceful degradation when one source down | 2.6 |
| Phase 2 — TikTok | No official SDK, weaker error surface | 2.4 |
| Phase 3 — GA4/GSC | Property-ID confusion + 2–3 day data delay | 2.5 |
| Phase 3+ — DB | Unbounded daily_kpi growth | 5.2 |
| Iteration 4 — Tenancy | Retrofit is high-risk; install the seam in Phase 1 | 5.1 |

---

## Key Contradictions to Resolve

1. **`PROJECT.md` says "no tenant_id enforcement in MVP1-3" but `CLAUDE.md` mandates filtering on every query.** Recommended resolution: install the `with_loader_criteria` event-listener seam in Phase 1 with a hardcoded tenant constant. Enforcement is present but the second tenant doesn't exist yet. Iteration 4 = change one line.

2. **`PROJECT.md` says `claude-sonnet-4-6` but `CLAUDE.md` and `docs/STACK.md` still reference `claude-sonnet-4-5`.** Update `CLAUDE.md` and `docs/STACK.md` in Phase 1.

3. **`docs/STACK.md` specifies Tremor for charts but Tremor is effectively abandoned.** Replace with `shadcn/ui chart` (Recharts v3). Update `CLAUDE.md` and `docs/STACK.md`.

---
*Research completed: 2026-05-19*
