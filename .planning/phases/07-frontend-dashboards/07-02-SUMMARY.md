---
phase: 07-frontend-dashboards
plan: 02
subsystem: ui
tags: [nextjs, tanstack-query, recharts, shadcn, react-day-picker, date-fns, sales-dashboard, i18n]

# Dependency graph
requires:
  - phase: 07-frontend-dashboards
    plan: 01
    provides: formatters.ts, QueryClientProvider, shadcn card/chart/skeleton/badge/table, 6 i18n namespaces, recharts/react-day-picker installed

provides:
  - useSalesDashboard TanStack Query hook with complete SalesDashboardData TypeScript interface
  - DateRangePicker shared component with 4 presets, URL sync, mobile Sheet / desktop Popover, disabled YoY toggle (SALE-06 shape)
  - FunnelChart: horizontal BarChart (desktop sm:block) + vertical stacked layout (mobile sm:hidden) with conversion rates and WoW badges
  - KpiCards: 6-card responsive grid with WoW delta coloring (green/red) and RON formatting
  - SourceBreakdown: vertical layout BarChart + shadcn Table below with overflow-x-auto
  - RevenueTrend: AreaChart with gradient fill, parseFloat on string revenue
  - StuckOffers: list with red/amber Badge by days_stuck + CheckCircle empty state
  - Full /sales page with Suspense wrapper, per-section loading/error/empty states, date URL validation
  - tooltip.tsx and popover.tsx shadcn-style components via radix-ui umbrella

affects:
  - 07-03-PLAN.md (Salespeople Dashboard — can reuse DateRangePicker and inline error/loading patterns)
  - 07-04-PLAN.md (Marketing Dashboard — can reuse chart component patterns)
  - 07-05-PLAN.md (Insights Dashboard — can reuse Card/Badge/empty state patterns)

# Tech tracking
tech-stack:
  added:
    - tooltip.tsx (radix-ui Tooltip wrapper — shadcn style)
    - popover.tsx (radix-ui Popover wrapper — shadcn style)
  patterns:
    - useSalesDashboard(from, to) — TanStack Query v5 hook with queryKey ["sales", from, to]
    - DateRangePicker with useEffect-gated isMobile for SSR-safe viewport detection
    - Per-section loading/error/empty state gating (isLoading → Skeleton, isError → InlineError, data → component)
    - parseFloat(point.revenue ?? "0") before passing string Decimal to Recharts
    - Suspense outer + SalesPageContent inner (useSearchParams Pitfall 5 fix)
    - Date param validation: new Date(param) + isNaN check before use (T-7-01 mitigation)

key-files:
  created:
    - frontend/src/hooks/useSalesDashboard.ts
    - frontend/src/components/date-range-picker.tsx
    - frontend/src/components/ui/tooltip.tsx
    - frontend/src/components/ui/popover.tsx
    - frontend/src/components/dashboards/sales/funnel-chart.tsx
    - frontend/src/components/dashboards/sales/kpi-cards.tsx
    - frontend/src/components/dashboards/sales/source-breakdown.tsx
    - frontend/src/components/dashboards/sales/revenue-trend.tsx
    - frontend/src/components/dashboards/sales/stuck-offers.tsx
  modified:
    - frontend/src/app/(dashboard)/sales/page.tsx (replaced placeholder stub with full implementation)

key-decisions:
  - "tooltip.tsx and popover.tsx created manually using 'radix-ui' umbrella package (same pattern as sheet.tsx/collapsible.tsx) because shadcn CLI requires pnpm on PATH which is not globally installed"
  - "DateRangePicker uses useEffect + useState for isMobile (not window.innerWidth during render) — prevents SSR hydration mismatch"
  - "FunnelChart shows empty state when funnel.leads === 0 || null — not an empty chart with zero axes"
  - "RevenueTrend uses AreaChart (vs LineChart) for better visual with daily revenue data — fills area nicely"
  - "SalesPageContent wraps DateRangePicker in its own Suspense to handle useSearchParams SSR requirement independently"

patterns-established:
  - "Per-section error gating: each section independently shows loading/error/empty — one section error does not block others"
  - "InlineError component: flex flex-col items-center gap-2 py-8 with red text + outline Retry button"
  - "URL date validation: rawFrom → new Date(rawFrom) → isNaN check → fallback to defaults"
  - "parseFloat pattern for recharts: parseFloat(point.revenue ?? '0') before any chart data mapping"

requirements-completed: [SALE-01, SALE-02, SALE-03, SALE-04, SALE-05, SALE-06, SALE-07, UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, UI-07, UI-08]

# Metrics
duration: ~45min
completed: 2026-05-28
---

# Phase 7 Plan 02: Sales Dashboard Summary

**Full Sales dashboard page with useSalesDashboard hook, DateRangePicker (with disabled YoY SALE-06 shape), FunnelChart (responsive desktop/mobile), KpiCards grid, SourceBreakdown, RevenueTrend AreaChart, StuckOffers — all with loading/empty/error states and zero Tremor imports**

## Performance

- **Duration:** ~45 min
- **Completed:** 2026-05-28
- **Tasks:** 2
- **Files created/modified:** 11

## Accomplishments

- `useSalesDashboard(from, to)` TanStack Query hook exports full `SalesDashboardData` TypeScript interface with all backend field types correctly matched (Decimal=string|null, integers=number|null per DATA-04).
- `DateRangePicker` shared component with 4 preset shortcuts (Ultima săptămână/Ultima lună/Ultimele 90 zile/Luna curentă), URL sync via `router.push`, mobile bottom Sheet / desktop Popover, and disabled "Comparare An/An" button with Tooltip "Disponibil în curând" (SALE-06 shape satisfaction).
- `FunnelChart` renders horizontal `BarChart` on `>=640px` (ChartContainer wrapper, LabelList, WoW delta badges) and vertical flex-column layout on `<640px` (stages top-to-bottom with downward conversion arrows). Empty state when leads === 0 || null.
- `KpiCards` 6-card grid with `grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4`, WoW delta coloring (green-600/red-600), `formatRON()` for revenue/avg_deal_size.
- `SourceBreakdown` vertical `BarChart` (layout="vertical") sorted descending by leads + shadcn `Table` below with `overflow-x-auto` for mobile.
- `RevenueTrend` AreaChart with gradient fill, `parseFloat(revenue ?? "0")` before Recharts consumption, Romanian date labels, empty state when all-zero.
- `StuckOffers` list with amber/red Badge coloring based on `days_stuck` (>30=red, 14-30=amber) and CheckCircle empty state.
- Full `/sales` page: `Suspense` outer wrapper + `SalesPageContent` inner component. Per-section independent loading/error/empty states. Date URL param validation (`isNaN` check) per T-7-01 threat mitigation.
- `tooltip.tsx` and `popover.tsx` created manually following the same `radix-ui` umbrella import pattern as `sheet.tsx` and `collapsible.tsx` (installed in Plan 01).

## Task Commits

1. **Task 1: useSalesDashboard hook + DateRangePicker** — `a0a73d1c`
2. **Task 2: Sales chart/card components + full Sales page** — `a886d68b`

## Files Created/Modified

- `frontend/src/hooks/useSalesDashboard.ts` — TanStack Query v5 hook, SalesDashboardData interface with 7 sub-interfaces
- `frontend/src/components/date-range-picker.tsx` — DateRangePicker: presets, URL sync, Sheet/Popover, disabled YoY toggle
- `frontend/src/components/ui/tooltip.tsx` — Tooltip/TooltipContent/TooltipProvider/TooltipTrigger (radix-ui umbrella)
- `frontend/src/components/ui/popover.tsx` — Popover/PopoverContent/PopoverTrigger/PopoverAnchor (radix-ui umbrella)
- `frontend/src/components/dashboards/sales/funnel-chart.tsx` — Responsive funnel: horizontal (desktop) + vertical (mobile)
- `frontend/src/components/dashboards/sales/kpi-cards.tsx` — 6-card responsive grid with WoW delta badges
- `frontend/src/components/dashboards/sales/source-breakdown.tsx` — Vertical BarChart + Table below
- `frontend/src/components/dashboards/sales/revenue-trend.tsx` — AreaChart with parseFloat on revenue strings
- `frontend/src/components/dashboards/sales/stuck-offers.tsx` — Offer list with days_stuck Badge coloring
- `frontend/src/app/(dashboard)/sales/page.tsx` — Full Sales dashboard page (replaced placeholder stub)

## Decisions Made

- Manually created `tooltip.tsx` and `popover.tsx` using the `radix-ui` umbrella package (same pattern as `sheet.tsx` and `collapsible.tsx` from Plan 01). The `shadcn` CLI failed with `Command failed with ENOENT: pnpm add radix-ui` because `pnpm` is not on `PATH` globally (only available via `corepack pnpm`). The radix-ui umbrella (`radix-ui@^1.4.3`) is already in `dependencies`, so creating the wrappers directly is functionally identical to shadcn CLI output.
- `RevenueTrend` uses `AreaChart` rather than `LineChart` — area chart with gradient fill renders more visually informative for daily revenue data (fills the space below the line providing better visual density at the daily granularity used in this project).
- `FunnelChart` desktop layout uses a single `BarChart` with 4 bars (not 4 separate bars with custom positioning) — simpler to maintain and ChartContainer handles responsive sizing.
- `SalesPageContent` wraps `DateRangePicker` in its own inner `<Suspense>` to handle the `useSearchParams` requirement independently from the outer Suspense boundary.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] tooltip.tsx and popover.tsx created manually (shadcn CLI pnpm unavailable)**
- **Found during:** Task 1 (attempting `npx shadcn@latest add tooltip popover`)
- **Issue:** shadcn CLI requires `pnpm` on `PATH` and failed with `Command failed with ENOENT: pnpm add radix-ui`. The `radix-ui` umbrella package (v1.4.3) is already in `dependencies` and provides `Tooltip` and `Popover` components.
- **Fix:** Created `frontend/src/components/ui/tooltip.tsx` and `frontend/src/components/ui/popover.tsx` manually, using the same `import { Tooltip as TooltipPrimitive } from "radix-ui"` pattern established by `sheet.tsx` and `collapsible.tsx` in Plan 01. The output is functionally identical to shadcn CLI output.
- **Files modified:** `frontend/src/components/ui/tooltip.tsx`, `frontend/src/components/ui/popover.tsx`
- **Verification:** `pnpm typecheck` exits 0, `pnpm lint` exits 0.

---

**Total deviations:** 1 auto-fixed (1 Rule 3 blocking)

## Known Stubs

**1. Disabled YoY toggle (intentional — SALE-06 shape)**
- **File:** `frontend/src/components/date-range-picker.tsx` line 196
- **Stub type:** Feature placeholder button (always disabled, no state/handler)
- **Reason:** Phase 9 feature (YoY comparison). The SALE-06 requirement shape is satisfied in Phase 7 by rendering the disabled button with tooltip "Disponibil în curând". The actual YoY data overlay is deferred to Phase 9 polish.
- **Resolution plan:** Phase 9 will wire YoY data from a new backend endpoint and enable this button.

## Self-Check: PASSED

All 8 created/modified files verified on disk. Both task commits (a0a73d1c, a886d68b) confirmed in git log. pnpm typecheck and pnpm lint both exit 0.
