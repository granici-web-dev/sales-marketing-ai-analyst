---
phase: 07-frontend-dashboards
plan: 03
subsystem: ui
tags: [nextjs, tanstack-query, shadcn, table, salespeople, leaderboard, i18n, mobile-scroll, sticky-column]

# Dependency graph
requires:
  - phase: 07-frontend-dashboards
    plan: 01
    provides: formatters.ts (formatRON/formatPct/formatDuration/getDefaultDateRange), QueryClientProvider, shadcn table/skeleton/button, i18n salespeople namespace
  - phase: 07-frontend-dashboards
    plan: 02
    provides: DateRangePicker shared component, InlineError pattern, Suspense+content page pattern

provides:
  - useSalespeopleDashboard TanStack Query hook with SalespersonRow + SalespeopleDashboardData TypeScript interfaces
  - LeaderboardTable component: sortable, horizontal-scroll mobile, sticky rank+name columns, red TTFT highlight
  - Full /salespeople page with Suspense wrapper, date range picker, loading/error/empty states

affects:
  - 07-04-PLAN.md (Marketing Dashboard — can reuse same page pattern; junk-pct-table can follow leaderboard-table pattern)
  - 07-05-PLAN.md (Insights Dashboard — same Suspense+content page pattern)

# Tech tracking
tech-stack:
  added:
    - pnpm-workspace.yaml allowBuilds map (migrated from deprecated package.json pnpm field for pnpm v11)
  patterns:
    - useSalespeopleDashboard(from, to) — queryKey ["salespeople", from, to], enabled: Boolean(from && to)
    - LeaderboardTable: overflow-x-auto wrapper + min-w-[800px] Table for mobile horizontal scroll
    - Sticky first two columns: TableHead/TableCell className="sticky left-0 bg-background z-10"
    - TTFT red cell: cn() with conditional "bg-red-50 text-red-700 font-medium" when > 240
    - Sort state: SortField union type + useMemo for sorted array + cycle handler (desc → asc → reset to default)
    - Column header sort buttons: min-h-[44px] touch target with ChevronUp/ChevronDown icons

key-files:
  created:
    - frontend/src/hooks/useSalespeopleDashboard.ts
    - frontend/src/components/dashboards/salespeople/leaderboard-table.tsx
    - frontend/pnpm-workspace.yaml
  modified:
    - frontend/src/app/(dashboard)/salespeople/page.tsx (replaced placeholder stub with full implementation)

key-decisions:
  - "pnpm-workspace.yaml allowBuilds map created to migrate onlyBuiltDependencies from deprecated package.json pnpm field (pnpm v11 breaking change) — required for pnpm install / typecheck to work"
  - "Rank + name split into two sticky columns (left-0 and left-10) so both remain visible during mobile horizontal scroll"
  - "avg_time_to_first_touch_minutes typed as number|null (integer, not string) per verified backend schema — formatDuration takes number|null directly"

patterns-established:
  - "Pattern: sortable table with SortField union type, getSortValue() helper, useMemo sort, cycle handler (new field starts desc)"
  - "Pattern: double sticky columns — rank at left-0, name at left-10 (40px offset matching rank column width)"

requirements-completed: [SALES-01, SALES-02, SALES-03, SALES-04, UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, UI-07, UI-08]

# Metrics
duration: ~20min
completed: 2026-05-28
---

# Phase 7 Plan 03: Salespeople Dashboard Summary

**Sortable leaderboard table for 6 Sofa Belle reps with horizontal mobile scroll, sticky rank+name columns, red TTFT highlight for > 240min, and full /salespeople page with date range picker, loading/error/empty states**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-05-28T21:07:16Z
- **Completed:** 2026-05-28
- **Tasks:** 2 (+ 1 auto-fix deviation)
- **Files created/modified:** 4

## Accomplishments

- `useSalespeopleDashboard(from, to)` TanStack Query hook with complete `SalespersonRow` TypeScript interface. Critical: `avg_time_to_first_touch_minutes` typed as `number|null` (integer, not Decimal string), matching verified backend schema. All Decimal fields (`revenue`, `win_rate`, `data_completeness_pct`, `conversion_*`) typed as `string|null`.
- `LeaderboardTable` component with 10 columns, client-side sort (default `deals_won` descending), and horizontal mobile scroll (`overflow-x-auto` + `min-w-[800px]`). Rank and name columns are both sticky (`sticky left-0` and `sticky left-10` respectively) so they remain visible during horizontal scroll. Column header `<button>` elements with `min-h-[44px]` touch targets.
- Red TTFT cell: `bg-red-50 text-red-700 font-medium` applied to `avg_time_to_first_touch_minutes` cell when value `> 240` (4-hour threshold per D-05/SALES-02). Uses `cn()` utility for conditional class merging.
- `/salespeople` page replaces stub: `Suspense` outer + `SalespeoplePageContent` inner (useSearchParams pattern), `DateRangePicker`, 5 `Skeleton` rows during load, `InlineError` + Retry on error, `LeaderboardTable` on data. Date URL param `isNaN` validation per T-7-06 threat mitigation.

## Task Commits

Each task was committed atomically:

1. **Task 1: useSalespeopleDashboard hook** — `777e2756` (feat)
2. **Task 2: LeaderboardTable component + Salespeople page** — `0b90b18c` (feat)

## Files Created/Modified

- `frontend/src/hooks/useSalespeopleDashboard.ts` — TanStack Query v5 hook, SalespersonRow interface with avg_time_to_first_touch_minutes: number|null
- `frontend/src/components/dashboards/salespeople/leaderboard-table.tsx` — Sortable leaderboard: overflow-x-auto, double sticky columns, red TTFT cell, 44px sort buttons
- `frontend/src/app/(dashboard)/salespeople/page.tsx` — Full Salespeople page (replaced placeholder stub)
- `frontend/pnpm-workspace.yaml` — pnpm v11 allowBuilds migration (auto-fix)

## Decisions Made

- `pnpm-workspace.yaml` created with `allowBuilds` map to migrate from the deprecated `package.json` `pnpm.onlyBuiltDependencies` field (pnpm v11 breaking change). Without this fix, `pnpm install` fails and `pnpm typecheck` cannot run.
- Rank and name columns split into separate sticky columns (`sticky left-0` for rank, `sticky left-10` for name) so both are visible on mobile scroll. Rank column is `w-10` (40px) to match the `left-10` offset.
- `avg_time_to_first_touch_minutes` intentionally typed as `number|null` (not `string|null`) to match the integer field in the backend schema — this allows direct `> 240` comparison without parseFloat.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] pnpm-workspace.yaml created with allowBuilds for pnpm v11**
- **Found during:** Task 1 verification (`corepack pnpm typecheck`)
- **Issue:** `pnpm install` failed with `ERR_PNPM_IGNORED_BUILDS` because `pnpm@11.4.0` no longer reads the `pnpm` field from `package.json`. The `onlyBuiltDependencies` setting for `@parcel/watcher`, `@swc/core`, `sharp`, `unrs-resolver` needs to live in `pnpm-workspace.yaml` as `allowBuilds` boolean map. Without this, pnpm install refused to complete and typecheck could not run.
- **Fix:** Created `frontend/pnpm-workspace.yaml` with `allowBuilds` map setting each of the 4 packages to `true`.
- **Files modified:** `frontend/pnpm-workspace.yaml` (created)
- **Verification:** `corepack pnpm install` succeeds; `corepack pnpm typecheck` exits 0; `corepack pnpm lint` exits 0.
- **Committed in:** `777e2756` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 Rule 3 blocking)
**Impact on plan:** Auto-fix was necessary for pnpm to install and typecheck to run. No scope creep.

## Known Stubs

None — all data flows from the live `useSalespeopleDashboard` hook to `LeaderboardTable`. No placeholder values, no hardcoded arrays.

## Threat Flags

No new threat surface beyond what was analyzed in the plan's `<threat_model>`:
- T-7-06: from/to URL params validated with `isNaN` check before use.
- T-7-08: salesperson names rendered as React text nodes (auto-escaped), no `dangerouslySetInnerHTML`.

## Self-Check: PASSED

Files verified on disk:
- `frontend/src/hooks/useSalespeopleDashboard.ts` — FOUND
- `frontend/src/components/dashboards/salespeople/leaderboard-table.tsx` — FOUND
- `frontend/src/app/(dashboard)/salespeople/page.tsx` — FOUND (modified)
- `frontend/pnpm-workspace.yaml` — FOUND

Commits verified in git log:
- `777e2756` (Task 1) — FOUND
- `0b90b18c` (Task 2) — FOUND

Verification checks:
- `pnpm typecheck` exits 0 — PASS
- `pnpm lint` exits 0 — PASS
- No `@tremor/react` imports in salespeople components — PASS
- `overflow-x-auto` present in leaderboard-table.tsx — PASS (count: 1)
- `bg-red-50` present in leaderboard-table.tsx — PASS (count: 1)
- `> 240` condition present in leaderboard-table.tsx — PASS (count: 2)

---
*Phase: 07-frontend-dashboards*
*Completed: 2026-05-28*
