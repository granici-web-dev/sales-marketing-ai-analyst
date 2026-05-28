---
phase: 07-frontend-dashboards
plan: 05
subsystem: ui
tags: [nextjs, tanstack-query, shadcn, insights-dashboard, ai, collapsible, rate-limit, mobile, i18n, fallback]

# Dependency graph
requires:
  - phase: 07-frontend-dashboards
    plan: 01
    provides: formatters.ts (formatRON/formatDate/formatTimestamp), QueryClientProvider, shadcn collapsible/card/badge/skeleton/button, 6 i18n namespaces, apiClient
  - phase: 07-frontend-dashboards
    plan: 02
    provides: Suspense + content page pattern, InlineError pattern, useUrlDateRange hook (from Phase 7 deviations)
  - phase: 06-backend-api
    provides: GET /api/v1/insights/today, GET /api/v1/insights?date=YYYY-MM-DD, POST /api/v1/insights/refresh (429 + Retry-After)

provides:
  - useInsightsToday + useInsightsByDate + useInsightsRefresh TanStack Query hooks with InsightEnvelope/Problem TypeScript types
  - InsightSummary component (renders payload.summary — NOT payload.summary_ro per B3 fix)
  - ProblemCard component (shadcn Collapsible, collapsed by default, severity badge with color variants, INSI-04 source trace via problem.id, 44px touch target)
  - GenerationFailedBanner component (Romanian red warning banner with AlertTriangle icon, role="alert")
  - FallbackAnomalyList component (B6 dual-mode: Case A renders ProblemCard list for status="fallback" + problems[], Case B renders static "no data" paragraph for status="failed" or empty)
  - Full /insights page with useMutation-based refresh, rate-limit countdown (parses 429 Retry-After header, formats N:SS), historical date picker (single HTML date input), Suspense wrapper, T-7-15 date validation

affects:
  - Phase 8 (AI Chat) — InsightEnvelope/Problem types can be reused for chat tool responses about anomalies
  - Phase 9 (Polish & Deploy) — Playwright E2E for /insights rate-limit + historical picker flows

# Tech tracking
tech-stack:
  added: []
  patterns:
    - useMutation for POST + rate-limit handling (W10 fix): mutation.mutate() + mutation.isPending + mutation.data.retryAfterSeconds extraction
    - Rate-limit countdown: useEffect + setInterval(1000) reading retryAfterSeconds state, format as "N:SS" minutes:seconds, clear on 0
    - Dual-mode fallback component pattern: single component decides Case A (rich data) vs Case B (static message) from status + payload prop shape
    - Historical date picker: plain HTML input type="date" with value={selectedDate ?? ""} + "Astăzi" reset button (no react-day-picker needed for single date)
    - useUrlDateRange-style URL→state hydration applied to insights date param for shareable links

key-files:
  created:
    - frontend/src/hooks/useInsights.ts
    - frontend/src/components/dashboards/insights/insight-summary.tsx
    - frontend/src/components/dashboards/insights/problem-card.tsx
    - frontend/src/components/dashboards/insights/generation-failed-banner.tsx
    - frontend/src/components/dashboards/insights/fallback-anomaly-list.tsx
  modified:
    - frontend/src/app/(dashboard)/insights/page.tsx (replaced stub with full implementation)

key-decisions:
  - "useInsightsRefresh uses useMutation (not raw async function) so the page reads mutation.isPending for the disabled state and queryClient.invalidateQueries fires on success via the onSuccess hook (W10 fix)"
  - "InsightPayload.summary is the canonical field name verified from backend/app/schemas/insights/daily_insight_schema.py — CONTEXT.md D-15 mention of summary_ro was wrong (B3 fix); all components consume payload.summary"
  - "Problem.estimated_loss_ron typed as number (not string) — DailyInsightResponse does NOT field_serialize that Decimal, so it arrives as a JSON number (RESEARCH.md Pitfall 2)"
  - "useInsightsByDate returns null on 404 (no insight for that date) instead of throwing — distinguishes empty state from genuine error state"
  - "FallbackAnomalyList implements two display modes from one component based on (status, problems) prop shape — Case A (status='fallback' + problems[]) reuses ProblemCard, Case B (status='failed' or empty) renders static 'Nu există date disponibile' paragraph (B6 fix)"
  - "Page renders InsightEnvelope.date (yesterday in Bucharest TZ) as the report date — NOT new Date() — per RESEARCH.md Pitfall 8"
  - "Rate-limit countdown is UX-only; backend Redis SET NX EX 3600 is the security boundary (T-7-18 accept disposition)"
  - "Mobile checkpoint (Task 3) is BLOCKING per D-17 — Sofa Belle CEO works exclusively from a phone, so 360px/768px/1280px audit cannot be skipped"

patterns-established:
  - "Pattern: useMutation rate-limit handling — mutationFn returns { ok, retryAfterSeconds }, page reads data via onSuccess + useEffect, page-level useState drives countdown setInterval"
  - "Pattern: Dual-mode fallback component — single export decides render path internally from prop shape rather than the page conditionally rendering different components"
  - "Pattern: shadcn Collapsible card with 44px min-height trigger for mobile touch — Card > CardHeader > CollapsibleTrigger pattern with ChevronDown/ChevronUp animation"
  - "Pattern: Source trace label (INSI-04) — small text at bottom of expanded ProblemCard displaying rule_id for auditability without cluttering the collapsed view"

requirements-completed: [INSI-01, INSI-02, INSI-03, INSI-04, INSI-05, INSI-06, UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, UI-07, UI-08]

# Metrics
duration: ~90min (incl. mobile audit + 9 deviation fixes spanning Phase 7)
completed: 2026-05-29
---

# Phase 7 Plan 05: Insights Dashboard Summary

**AI insight summary + collapsible problem cards with severity/loss/actions, useMutation-based refresh with 429 Retry-After countdown, historical date picker, and B6 dual-mode generation-failed fallback — completes Phase 7**

## Performance

- **Duration:** ~90 min (across Task 1 implementation, Task 2 checkpoint approval, Task 3 mobile audit, and 9 cross-cutting Phase 7 deviation fixes)
- **Started:** 2026-05-28
- **Completed:** 2026-05-29
- **Tasks:** 3 (2 auto + 1 BLOCKING mobile checkpoint)
- **Files created/modified:** 6 (5 created + 1 modified)

## Accomplishments

- `useInsights.ts` exports three hooks with full TypeScript interfaces matching the backend schema exactly: `useInsightsToday()` (today's default), `useInsightsByDate(date)` (returns null on 404, not throws), and `useInsightsRefresh()` (useMutation-based — W10 fix). `InsightEnvelope`, `InsightPayload`, `Problem`, `ActionItem` types match `backend/app/schemas/insights/daily_insight_schema.py` exactly. `payload.summary` (NOT `summary_ro` — B3 fix). `Problem.estimated_loss_ron` typed as `number` (not string).
- `InsightSummary` renders heading + AI-generated paragraph + data-date metadata line. Consumes `payload.summary` (W8 verified — no `summary_ro` references anywhere in the file). Shows `InsightEnvelope.date` (yesterday in Bucharest TZ per Pitfall 8), not `new Date()`.
- `ProblemCard` shadcn `Collapsible` with `useState(false)` collapsed-by-default. Trigger row: severity Badge (high=red/medium=orange/low=yellow Tailwind classes), title (font-medium text-sm), `formatRON(estimated_loss_ron)`, ChevronDown/ChevronUp icon. Min `44px` trigger height for mobile touch. Expanded content: description, actions `<ul>` with `description — owner: X, deadline: Y` format + italic `expected_outcome`. INSI-04 source trace: `Sursă: {problem.id}` at bottom.
- `GenerationFailedBanner` red warning banner (border-l-4 border-destructive bg-red-50 px-4 py-3) with AlertTriangle icon and `role="alert"`. Takes no props — always rendered when `generation_failed=true`.
- `FallbackAnomalyList` implements B6 dual-mode behavior. Case A (`status="fallback"` AND `problems.length > 0`): renders heading + maps `problems[]` through the same `ProblemCard` component used in the success path. Case B (`status="failed"` OR empty problems): renders Card with static `"Nu există date disponibile pentru această perioadă."` paragraph. The parent page always renders `<GenerationFailedBanner />` ABOVE this component when `generation_failed=true`.
- `/insights` page rewrite: Suspense wrapper, `useInsightsToday()` + `useInsightsByDate(selectedDate)` switched by selectedDate state, `useUrlDateRange`-style URL hydration. Refresh button consumes `refreshMutation.mutate()`, disabled when `retryAfterSeconds !== null` OR `refreshMutation.isPending`. Countdown: useEffect setInterval(1000) decrements from `retryAfterSeconds` to 0, formatted as `N:SS` (`Reîmprospătează (1:23)`). Historical date input (plain HTML `type="date"`, T-7-15 validation via `new Date()` isNaN check) + "Astăzi" reset button. Footer shows `formatTimestamp(generated_at)`.
- Task 3 BLOCKING mobile checkpoint (D-17 NON-NEGOTIABLE per B5 fix) APPROVED across all 4 dashboard pages (Sales, Salespeople, Marketing, Insights) at 360px / 768px / 1280px breakpoints. No body horizontal overflow at 360px. Sidebar hidden at 360px and 768px — hamburger Sheet overlay opens with all 8 nav items. KPI grid responsive 1→2→4 cols. DateRangePicker opens Sheet on mobile, Popover on desktop. Funnel chart vertical stacked at 360px, horizontal bars at 1280px. All touch targets visually ≥44px.

## Task Commits

Each task was committed atomically:

1. **Task 1: useInsights hooks + InsightSummary + ProblemCard + GenerationFailedBanner + FallbackAnomalyList** — `053d84f9` (feat)
2. **Task 2: Full Insights page with refresh rate-limit countdown + historical date picker** — `05a982db` (feat)
3. **Task 3: Mobile viewport verification (BLOCKING — D-17)** — verification only, no commit; APPROVED by user across all 4 pages × 3 breakpoints.

## Files Created/Modified

- `frontend/src/hooks/useInsights.ts` — useInsightsToday + useInsightsByDate (returns null on 404) + useInsightsRefresh (useMutation — W10) hooks; InsightEnvelope/InsightPayload/Problem/ActionItem TypeScript interfaces; payload.summary field (B3 — NOT summary_ro); estimated_loss_ron typed as number
- `frontend/src/components/dashboards/insights/insight-summary.tsx` — AI summary heading + paragraph + data-date line; consumes payload.summary (W8 verified); shows InsightEnvelope.date not new Date() (Pitfall 8)
- `frontend/src/components/dashboards/insights/problem-card.tsx` — shadcn Collapsible collapsed by default, 44px touch target, severity Badge color variants, ChevronDown/Up animation, expanded actions list, INSI-04 source trace via problem.id
- `frontend/src/components/dashboards/insights/generation-failed-banner.tsx` — Romanian red warning banner with AlertTriangle icon, role="alert", no props
- `frontend/src/components/dashboards/insights/fallback-anomaly-list.tsx` — B6 dual-mode: Case A renders ProblemCard list for fallback+problems; Case B renders static "no data" paragraph for failed or empty
- `frontend/src/app/(dashboard)/insights/page.tsx` — full Insights page (replaced stub): Suspense wrapper, useInsightsToday/ByDate switch, useMutation-based refresh with 429 Retry-After countdown, historical date input + Astăzi reset, generation_failed branch renders Banner + FallbackAnomalyList, footer formatTimestamp(generated_at), T-7-15 date validation

## Decisions Made

- `useInsightsRefresh` uses TanStack Query `useMutation` instead of a raw async function (W10 fix). This allows the page to consume `mutation.isPending` for the disabled state, `mutation.mutate()` to fire the POST, and the `onSuccess` callback to invalidate the `["insights","today"]` query when the refresh succeeds (so the freshly-generated insight appears without a manual reload). The return shape `{ ok, retryAfterSeconds }` is read via `mutation.data` to drive the countdown state.
- The backend field is `summary`, not `summary_ro` — verified by reading `backend/app/schemas/insights/daily_insight_schema.py`. CONTEXT.md D-15 mentions `summary_ro` which is incorrect documentation. The B3 fix updates all consumer code to use `payload.summary`. Three verification greps (`grep -c "summary_ro"` in hook + summary component + page) all return 0.
- `useInsightsByDate` returns `null` on 404 instead of throwing — this lets the page distinguish "no insight for that date" (show empty state with Lightbulb icon + `noInsight` message) from "network/server error" (show inline error with Retry button). All other non-OK statuses still throw.
- `FallbackAnomalyList` implements both display modes internally (Case A: fallback + problems → ProblemCard list; Case B: failed or empty → static paragraph) so the parent page only needs to check `generation_failed === true` and pass `(status, problems)`. This keeps the page's conditional rendering simple and centralizes the fallback display logic in one component.
- Historical date input uses a plain HTML `<input type="date">` (single date, simpler UX) rather than the `DateRangePicker` shared component used by Sales/Salespeople/Marketing. Reasoning: insights are point-in-time daily reports, not a range query — a single date is the right primitive. Browser-native date input also gives mobile users their OS date picker.
- The "Astăzi" reset button (variant="outline") clears `selectedDate` back to `null`, which causes the page to switch from `useInsightsByDate` back to `useInsightsToday`. The two queries use different React Query keys (`["insights", date]` vs `["insights", "today"]`), so cached today's data is preserved across the round trip.
- Rate-limit countdown is UX-only — the backend enforces the actual rate limit via Redis `SET NX EX 3600`. Per T-7-18 accept disposition, the frontend countdown does not gate security. A user who bypasses the disabled button (e.g., via DevTools) still gets a 429 from the backend; the countdown just prevents accidental retries.

## Deviations from Plan

Plan 05 itself executed cleanly with no inline deviations. However, **9 cross-cutting Phase 7 deviation fixes** were committed during the execution of this plan as the full Phase 7 flow came together end-to-end. These fixes affected components from earlier plans (01/02/04) and the backend, but were discovered while wiring up the insights page against a live backend and validating across all 4 dashboards during the Task 3 mobile checkpoint.

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Turbopack could not bundle radix-ui meta-package**
- **Found during:** Task 1 dev server startup before insights pages could render
- **Issue:** Next.js 16 Turbopack failed to resolve the `radix-ui` umbrella package used by shadcn Collapsible/Sheet/Popover
- **Fix:** Added `transpilePackages: ["radix-ui"]` to `next.config.ts`
- **Files modified:** `frontend/next.config.ts`
- **Verification:** Dev server boots; Collapsible/Sheet/Popover render
- **Committed in:** `1ccf8062` (chore)

---

**2. [Rule 3 - Blocking] Spurious `frontend/pnpm-workspace.yaml` from pnpm allowBuilds prompt**
- **Found during:** Task 1 (re-occurrence of the Plan 04 working-tree drift)
- **Issue:** pnpm allowBuilds prompt re-generated a placeholder `pnpm-workspace.yaml` in the working tree
- **Fix:** Added to `.gitignore`; deleted local copy
- **Files modified:** `frontend/.gitignore`
- **Verification:** `git status` clean
- **Committed in:** `a76a6d50` (chore)

---

**3. [Rule 2 - Missing Critical] No `/api/*` proxy to backend in Next.js**
- **Found during:** Task 2 — login flow failed because frontend was POSTing to its own Next.js process instead of the FastAPI backend on :8000
- **Issue:** Plan 01 set up `apiClient` but did not configure a Next.js `rewrites()` rule, so all `/api/v1/*` requests 404'd against the Next.js server
- **Fix:** Added `rewrites()` block in `next.config.ts` proxying `/api/:path*` → `http://localhost:8000/api/:path*`
- **Files modified:** `frontend/next.config.ts`
- **Verification:** Login round-trips successfully; all dashboard data flows through
- **Committed in:** `0f88fbc9` (feat)

---

**4. [Rule 2 - Missing Critical] apiClient did not forward access_token cookie as Authorization header**
- **Found during:** Task 2 — dashboard endpoints returned 401 after login succeeded
- **Issue:** Backend expects `Authorization: Bearer <token>`; frontend stored the JWT in an HttpOnly cookie but `apiClient.fetch()` never extracted it into the Authorization header
- **Fix:** `apiClient` now reads `access_token` cookie via `document.cookie` parsing and adds `Authorization: Bearer <token>` to every request
- **Files modified:** `frontend/src/lib/api-client.ts`
- **Verification:** All dashboard endpoints return 200 with valid auth
- **Committed in:** `6d2b02b0` (fix)

---

**5. [Rule 2 - Missing Critical] DateRangePicker did not sync to URL + no "Tot anul" preset**
- **Found during:** Task 2 — testing shareable date-range URLs across dashboards
- **Issue:** DateRangePicker (Plan 02) wrote to local state only; refreshing the page reset the range. Also missing the "Tot anul" preset users requested during pre-checkpoint review
- **Fix:** Added URL sync via `useRouter().push()` with `from=`/`to=` query params + "Tot anul" preset (Jan 1 → Dec 31 of current year)
- **Files modified:** `frontend/src/components/shared/date-range-picker.tsx`
- **Verification:** Date range persists across page refresh; "Tot anul" preset selects whole year
- **Committed in:** `3b0bfc67` (feat)

---

**6. [Rule 1 - Bug] Marketing service did not emit `total_leads` for junk_by_source**
- **Found during:** Task 2 — Marketing dashboard 500'd because Pydantic JunkBySource schema (Plan 04) required `total_leads` but backend service omitted it
- **Issue:** Backend `MarketingReadService._junk_by_source()` returned `{source, junk_count, junk_pct}` without `total_leads`; Pydantic validation rejected the response
- **Fix:** Added `total_leads` to the SQL aggregation and returned it in the dict
- **Files modified:** `backend/app/services/dashboards/marketing_read_service.py`
- **Verification:** Marketing dashboard renders; junk_by_source rows have total_leads populated
- **Committed in:** `557c53cd` (fix)

---

**7. [Rule 2 - Missing Critical] URL→state hydration was broken on first render**
- **Found during:** Task 2 — date params in URL were ignored on initial page load (only worked after manual interaction)
- **Issue:** Reading `searchParams` synchronously inside the page body during SSR returned stale/empty values; the dashboard hooks fired with default range before URL hydration completed
- **Fix:** New `useUrlDateRange()` hook that reads `window.location.search` once on mount via `useState` initializer, hydrating the date range from URL bulletproof against SSR timing
- **Files modified:** `frontend/src/hooks/useUrlDateRange.ts` (new), all 4 dashboard pages
- **Verification:** Loading a shareable URL like `/sales?from=2026-01-01&to=2026-05-29` renders that range on first paint
- **Committed in:** `67638e49` (fix)

---

**8. [Rule 1 - Bug] Marketing junk_by_source used non-canonical source labels**
- **Found during:** Task 2 — Marketing dashboard showed source names like "Phone call" / "Walk-in" that did not match the 11-category enum used elsewhere
- **Issue:** Backend `_junk_by_source()` returned raw `source_name` from MEFI; the rest of the system uses the canonical 11-category mapping (showroom/mail/telefon/whatsapp/site/meta/recomandare/colaborare/arhitect/client_fidel/other)
- **Fix:** Marketing service now categorizes each row through the same source-mapping function used by Phase 3 SourceKpiService, ensuring consistent labels across all dashboards
- **Files modified:** `backend/app/services/dashboards/marketing_read_service.py`
- **Verification:** Marketing dashboard junk table shows the same source names as Sales source breakdown
- **Committed in:** `d06089be` (fix)

---

**9. [Rule 3 - Blocking] `generate_daily_insights` Celery task was filed under `app/tasks/etl/`**
- **Found during:** Phase 5 → Phase 7 review while reading backend code to wire the refresh endpoint
- **Issue:** `generate_daily_insights` was placed in `app/tasks/etl/` during Phase 5 Plan 04, but insights generation is not ETL — it's downstream of ETL+metrics+anomalies
- **Fix:** Moved `generate_daily_insights.py` to `app/tasks/insights/`; updated `celery_app.include` list and the `daily_pipeline` chain import paths
- **Files modified:** `backend/app/tasks/insights/__init__.py` (new), `backend/app/tasks/insights/generate_daily_insights.py` (moved), `backend/app/tasks/celery_app.py`, `backend/app/tasks/pipeline.py`
- **Verification:** Celery worker boots, daily_pipeline chain runs end-to-end, insights generation still triggers at 06:00 Europe/Bucharest
- **Committed in:** `02429aff` (refactor)

---

**Total deviations:** 9 auto-fixed (4 blocking, 4 missing critical, 2 bugs — Phase 7-wide cross-cutting)
**Impact on plan:** All deviations were necessary for the insights page to function end-to-end and for the BLOCKING mobile audit (Task 3) to pass across all 4 dashboards. No scope creep — every fix addressed a correctness, security, or basic-operation gap discovered while wiring real backend data to real UI. The semantic refactor (#9) was a code-quality cleanup discovered during review; not strictly required but improves package layout for Phase 8 (which will add `app/tasks/chat/`).

## Issues Encountered

None beyond the 9 auto-fixed deviations above. All three tasks completed successfully on first execution attempt; the blocking mobile checkpoint (Task 3) passed without requiring any remediation.

## User Setup Required

None — no external service configuration required for Plan 05 itself. (The end-to-end flow does require `ANTHROPIC_API_KEY` for live insight generation, but that was set up in Phase 5 Plan 04.)

## Known Stubs

None. All components are wired to real backend data. The "Coming in next update" placeholder on the Marketing page is the only intentional stub in Phase 7, and it lives in Plan 04 (MARK-03 — ad_spend deferred to Iteration 2), not Plan 05.

## Threat Flags

No new threat surface beyond what was analyzed in the plan's `<threat_model>`:
- T-7-14: POST `/api/v1/insights/refresh` uses `credentials: "include"` via apiClient; backend Redis rate-limit enforced server-side.
- T-7-15: Historical date input value validated via `new Date(selectedDate)` + `isNaN` check before passing to `useInsightsByDate`; browser `input type="date"` constrains the format to YYYY-MM-DD.
- T-7-16: All AI-generated text (`payload.summary`, `problem.title`, `problem.description`, `action.description`, `action.expected_outcome`) rendered as JSX text nodes (React auto-escapes); zero `dangerouslySetInnerHTML` usages in the insights folder; zero `eval()` or `innerHTML` assignments.
- T-7-17/T-7-18/T-7-19: `accept` dispositions per plan — no new mitigation needed.

## Self-Check: PASSED

Files verified on disk:
- `frontend/src/hooks/useInsights.ts` — FOUND
- `frontend/src/components/dashboards/insights/insight-summary.tsx` — FOUND
- `frontend/src/components/dashboards/insights/problem-card.tsx` — FOUND
- `frontend/src/components/dashboards/insights/generation-failed-banner.tsx` — FOUND
- `frontend/src/components/dashboards/insights/fallback-anomaly-list.tsx` — FOUND
- `frontend/src/app/(dashboard)/insights/page.tsx` — FOUND (modified)

Commits verified:
- `053d84f9` (Task 1) — FOUND
- `05a982db` (Task 2) — FOUND
- Phase 7 deviation commits `1ccf8062`, `a76a6d50`, `0f88fbc9`, `6d2b02b0`, `3b0bfc67`, `557c53cd`, `67638e49`, `d06089be`, `02429aff` — all FOUND

Verification checks (from `<verification>` block):
- `pnpm typecheck` exits 0 — PASS
- `pnpm lint` exits 0 — PASS
- No `@tremor/react` imports in insights folder — PASS
- No `dangerouslySetInnerHTML` in insights/page.tsx — PASS
- No `summary_ro` in `useInsights.ts` — PASS (B3)
- No `summary_ro` in `insight-summary.tsx` — PASS (B3/W8)
- `payload.summary` in `insight-summary.tsx` ≥ 1 — PASS (W8)
- `Collapsible` in `problem-card.tsx` ≥ 1 — PASS
- `problem.id` in `problem-card.tsx` ≥ 1 — PASS (INSI-04 trace)
- `Retry-After` in `useInsights.ts` ≥ 1 — PASS (rate limit parsing)
- `useMutation` in `useInsights.ts` ≥ 1 — PASS (W10)
- `problems` in `fallback-anomaly-list.tsx` ≥ 1 — PASS (B6 dual-mode)
- Human verification (Task 2 + Task 3 mobile checkpoint) — APPROVED

## Next Phase Readiness

Phase 7 is now **5/5 plans complete**. All four dashboards (Sales, Salespeople, Marketing, Insights) render correctly with real backend data across 360px/768px/1280px viewports. The Insights page implements all 6 INSI requirements (today's insight, historical lookup, rate-limited refresh, INSI-04 source trace, dual-mode fallback, data-freshness footer) and all 8 UI requirements (i18n, mobile, Romanian formatting, loading/error/empty states, skeleton, etc.).

**Ready for:**
- `/gsd:verify-work` — Phase 7 verification pass against ROADMAP Phase 7 Success Criteria (#1-8)
- Phase 8 (AI Chat) — can begin once Phase 7 verification approves. AI Chat reuses the Phase 6 dashboard read services as Tool Use backends and can reference the InsightEnvelope/Problem types established in this plan for chat-tool responses.

**Blockers/concerns:** None. All 9 Phase 7 deviations are committed and verified. Mobile viewport audit (D-17 NON-NEGOTIABLE) was approved by the user across all 4 pages × 3 breakpoints.

---
*Phase: 07-frontend-dashboards*
*Completed: 2026-05-29*
