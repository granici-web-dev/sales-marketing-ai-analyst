---
phase: 07-frontend-dashboards
plan: 04
subsystem: ui
tags: [nextjs, tanstack-query, recharts, shadcn, marketing-dashboard, line-chart, i18n, mobile-scroll]

# Dependency graph
requires:
  - phase: 07-frontend-dashboards
    plan: 01
    provides: formatters.ts (formatPct/getDefaultDateRange), QueryClientProvider, shadcn card/chart/skeleton/table, 6 i18n namespaces, recharts installed
  - phase: 07-frontend-dashboards
    plan: 02
    provides: DateRangePicker shared component, InlineError pattern, Suspense+content page pattern
  - phase: 06-backend-api
    provides: GET /api/v1/dashboards/marketing endpoint with MarketingDashboardResponse schema

provides:
  - useMarketingDashboard TanStack Query hook with complete MarketingDashboardData TypeScript interface
  - SourceVolumeChart: multi-series LineChart with pivoted data transformation, dynamic ChartConfig, desktop (260px+legend) and mobile (200px, day-only) layouts
  - JunkPctTable: overflow-x-auto table showing source/junk_count/total_leads/junk_pct with formatPct
  - AdSpendPlaceholder: always-rendered MARK-03 coming-soon card with TrendingUp icon
  - Full /marketing page with Suspense wrapper, DateRangePicker, per-section loading/error/empty states

affects:
  - 07-05-PLAN.md (Insights Dashboard — can reuse Suspense+content page pattern, InlineError)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - pivotData() transformation: per-source series[] arrays → flat { date, [sourceKey]: value } rows for Recharts multi-series
    - toSafeKey(): source name sanitization (replace \W with _) for safe object property keys (T-7-11 mitigation)
    - Dynamic ChartConfig from source array with indexed color palette from CSS variables
    - Mobile/desktop ChartContainer split: hidden sm:block / block sm:hidden pattern for different chart heights and legend visibility

key-files:
  created:
    - frontend/src/hooks/useMarketingDashboard.ts
    - frontend/src/components/dashboards/marketing/source-volume-chart.tsx
    - frontend/src/components/dashboards/marketing/junk-pct-table.tsx
    - frontend/src/components/dashboards/marketing/ad-spend-placeholder.tsx
  modified:
    - frontend/src/app/(dashboard)/marketing/page.tsx (replaced placeholder stub with full implementation)

key-decisions:
  - "pivotData() collects all unique dates across all source series, sorts ascending, creates flat Recharts rows — handles variable series lengths across sources"
  - "Mobile chart split (hidden sm:block / block sm:hidden): desktop at 260px with CartesianGrid+Legend, mobile at 200px with day-number x-axis only and no grid/legend"
  - "AdSpendPlaceholder always rendered unconditionally at bottom of page — MARK-03 compliance (ad_spend always null from backend)"
  - "site_conversion_rate null displayed as N/A string, not empty — clear placeholder per plan requirement"

patterns-established:
  - "Pattern: multi-series line chart data pivot — collect unique dates, sort, map each date to flat object with source keys"
  - "Pattern: toSafeKey() for sanitizing dynamic object property keys from user-visible source names (security per T-7-11)"
  - "Pattern: dynamic ChartConfig from source list — forEach source → key=toSafeKey, color from indexed palette array"

requirements-completed: [MARK-01, MARK-02, MARK-03, MARK-04, UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, UI-07, UI-08]

# Metrics
duration: ~20min
completed: 2026-05-28
---

# Phase 7 Plan 04: Marketing Dashboard Summary

**Multi-series lead volume LineChart with source pivot transformation, junk % table, site conversion card, and MARK-03 ad-spend placeholder — full /marketing page with per-section loading/error/empty states**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-05-28T
- **Completed:** 2026-05-28
- **Tasks:** 2 (+ 1 auto-fix deviation)
- **Files created/modified:** 5

## Accomplishments

- `useMarketingDashboard(from, to)` TanStack Query hook exports complete `MarketingDashboardData` TypeScript interface. Critical type correctness: `junk_by_source[].junk_count` and `total_leads` are `number|null` (integers, not Decimal strings), `junk_pct` is `string|null` (Decimal serialized per DATA-04). `ad_spend/cpl/cac/roas` all typed as `null` (MARK-03 explicit).
- `SourceVolumeChart` pivots per-source `series[]` arrays into a flat Recharts data format using `pivotData()` (collects unique dates across all sources, sorts ascending, merges to flat objects). Dynamic `ChartConfig` built from source list with indexed color palette. Source names sanitized via `toSafeKey()` before use as object property keys (T-7-11 mitigation). Desktop layout (260px + CartesianGrid + ChartLegend) and mobile layout (200px, no grid, day-number x-axis, no legend) via `hidden sm:block` / `block sm:hidden`. Empty state when no source data.
- `JunkPctTable` with `overflow-x-auto` wrapper and `min-w-[400px]` Table. Columns: Source | Junk Count | Total Leads | Junk %. `junk_pct` formatted via `formatPct()` (not raw decimal string). Integers (`junk_count`, `total_leads`) displayed directly with `?? "—"` for null. Empty state with PieChart icon.
- `AdSpendPlaceholder` Card (MARK-03) always rendered unconditionally at the bottom of the page regardless of loading state — never gated on data.
- Full `/marketing` page: `Suspense` outer + `MarketingPageContent` inner pattern. URL date param validation with `isNaN` check (T-7-10 mitigation). Per-section independent loading/error states. `site_conversion_rate` displayed as N/A when null.

## Task Commits

Each task was committed atomically:

1. **Task 1: useMarketingDashboard hook + AdSpendPlaceholder component** — `09f83801` (feat)
2. **Task 2: SourceVolumeChart, JunkPctTable, and Marketing page** — `e60d5863` (feat)

## Files Created/Modified

- `frontend/src/hooks/useMarketingDashboard.ts` — TanStack Query v5 hook, MarketingDashboardData interface with LeadVolumeBySource, LeadVolumeBySourcePoint, JunkBySource sub-interfaces; junk_count/total_leads as number|null, junk_pct as string|null
- `frontend/src/components/dashboards/marketing/ad-spend-placeholder.tsx` — MARK-03 Card with TrendingUp icon, Romanian strings from useTranslations("marketing")
- `frontend/src/components/dashboards/marketing/source-volume-chart.tsx` — Multi-series LineChart: pivotData() transformation, toSafeKey() sanitization, dynamic ChartConfig, desktop/mobile split layouts
- `frontend/src/components/dashboards/marketing/junk-pct-table.tsx` — Junk % by source table: overflow-x-auto, formatPct, direct integer display, empty state
- `frontend/src/app/(dashboard)/marketing/page.tsx` — Full Marketing dashboard (replaced placeholder stub): Suspense pattern, DateRangePicker, 4 sections with loading/error/data states, AdSpendPlaceholder always rendered

## Decisions Made

- `pivotData()` collects all unique dates across all source series arrays and sorts them ascending before building flat row objects. This handles the case where different sources have different date ranges within the queried period.
- Mobile chart split uses `hidden sm:block` / `block sm:hidden` Tailwind classes to render two separate `ChartContainer` instances at different heights — avoids the complexity of dynamically configuring a single chart based on viewport.
- `AdSpendPlaceholder` is rendered unconditionally at the bottom of the page (not wrapped in loading/error guards) because it has no dynamic data — it is a static coming-soon notice that MARK-03 requires always visible.
- `site_conversion_rate` null is displayed as the string "N/A" in the conversion rate card — provides a clear, explicit placeholder instead of an empty value that might look like a rendering failure.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] pnpm-workspace.yaml allowBuilds values were placeholders (not `true`)**
- **Found during:** Task 1 verification (`corepack pnpm typecheck`)
- **Issue:** `frontend/pnpm-workspace.yaml` contained placeholder text ("set this to true or false") instead of actual `true` values, causing `pnpm install` to fail with `ERR_PNPM_IGNORED_BUILDS`. The file was committed in Plan 03 with `true` values in git, but the working tree somehow had stale placeholder content when read.
- **Fix:** Rewrote `pnpm-workspace.yaml` with `true` for all 4 packages. Git confirmed the committed version was already correct — working tree state was the issue.
- **Files modified:** `frontend/pnpm-workspace.yaml`
- **Verification:** `corepack pnpm typecheck` exits 0.

---

**Total deviations:** 1 auto-fixed (1 Rule 3 blocking)
**Impact on plan:** Working tree state correction only; no code changes needed. No scope creep.

## Known Stubs

**1. AdSpendPlaceholder (intentional — MARK-03)**
- **File:** `frontend/src/components/dashboards/marketing/ad-spend-placeholder.tsx`
- **Stub type:** Feature placeholder card (always shown, no data wired)
- **Reason:** MARK-03 explicit — ad_spend/cpl/cac/roas are always null from the backend. Advertising platform integrations deferred to Iteration 2.
- **Resolution plan:** Phase 9 (or a future iteration) will wire actual CPL/CAC/ROAS data when ad platform integrations are connected.

## Threat Flags

No new threat surface beyond what was analyzed in the plan's `<threat_model>`:
- T-7-10: from/to URL params validated with `isNaN` check before use.
- T-7-11: Source names sanitized via `toSafeKey()` before use as object property keys; rendered as React text nodes (auto-escaped) in legend/tooltip.
- T-7-12: Source names in `JunkPctTable` rendered as React text nodes; no `dangerouslySetInnerHTML`.
- T-7-13: `ad_spend` always null from backend; frontend shows static placeholder only (no data exposure).

## Self-Check: PASSED

Files verified on disk:
- `frontend/src/hooks/useMarketingDashboard.ts` — FOUND
- `frontend/src/components/dashboards/marketing/ad-spend-placeholder.tsx` — FOUND
- `frontend/src/components/dashboards/marketing/source-volume-chart.tsx` — FOUND
- `frontend/src/components/dashboards/marketing/junk-pct-table.tsx` — FOUND
- `frontend/src/app/(dashboard)/marketing/page.tsx` — FOUND (modified)

Commits verified:
- `09f83801` (Task 1) — FOUND
- `e60d5863` (Task 2) — FOUND

Verification checks:
- `pnpm typecheck` exits 0 — PASS
- `pnpm lint` exits 0 — PASS
- No `@tremor/react` imports in marketing components — PASS
- `AdSpendPlaceholder` count in page.tsx >= 1 — PASS (count: 2)
- `overflow-x-auto` in junk-pct-table.tsx >= 1 — PASS (count: 1)
- `formatPct` in junk-pct-table.tsx >= 1 — PASS (count: 2)

---
*Phase: 07-frontend-dashboards*
*Completed: 2026-05-28*
