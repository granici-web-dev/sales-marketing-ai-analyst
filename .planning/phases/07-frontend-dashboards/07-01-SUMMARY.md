---
phase: 07-frontend-dashboards
plan: 01
subsystem: ui
tags: [nextjs, tailwind, postcss, tanstack-query, shadcn, recharts, react-day-picker, date-fns, i18n, next-intl, vitest]

# Dependency graph
requires:
  - phase: 06-backend-api
    provides: /api/v1/health/data endpoint consumed by useHealthData() hook
  - phase: 01-foundation
    provides: Next.js 16 frontend scaffold, shadcn config, next-intl setup, sidebar/topbar shell

provides:
  - PostCSS pipeline fix (KI-01 resolved) — @tailwindcss/postcss config enabling CSS in dev server
  - formatters.ts — 7 pure formatter functions (formatRON, formatPct, formatDate, formatTimestamp, formatDuration, formatWowDelta, getDefaultDateRange) with 26 passing unit tests
  - useHealthData() TanStack Query hook (staleTime 60s) polling /api/v1/health/data
  - DataFreshnessBanner component with amber stale-data alert, localStorage dismissal, and Romanian i18n
  - Dashboard layout as Client Component with QueryClientProvider singleton (getQueryClient pattern) and DataFreshnessBanner slot
  - Mobile-responsive sidebar (hidden md:flex) and topbar (left-0 md:left-[240px]) with hamburger Sheet overlay
  - 6 new i18n namespaces in both ro.json and en.json: sales, salespeople, marketing, insights, common, errors
  - 7 shadcn UI components: card, skeleton, badge, table, chart, collapsible, sheet
  - recharts, react-day-picker, date-fns installed

affects:
  - 07-02-PLAN.md (Sales Dashboard — depends on formatters.ts, QueryClientProvider, shadcn card/chart/skeleton)
  - 07-03-PLAN.md (Salespeople Dashboard — depends on formatters.ts, shadcn table, i18n salespeople namespace)
  - 07-04-PLAN.md (Marketing Dashboard — depends on formatters.ts, recharts, i18n marketing namespace)
  - 07-05-PLAN.md (Insights Dashboard — depends on DataFreshnessBanner, i18n insights namespace, formatRON)

# Tech tracking
tech-stack:
  added:
    - recharts (Recharts v3 via shadcn chart abstraction)
    - react-day-picker (date range picker component)
    - date-fns (date arithmetic utilities)
    - @tailwindcss/postcss (CSS pipeline fix for Tailwind v4.3 + Next.js 16)
    - 7 shadcn components: card, skeleton, badge, table, chart, collapsible, sheet
  patterns:
    - getQueryClient singleton pattern (NOT useState) for QueryClientProvider in layout.tsx
    - useTranslations(ns) for all i18n strings — no hardcoded Romanian in JSX
    - apiClient.get(url) as queryFn base for all TanStack Query hooks
    - "use client" directive on hooks, layout wrapper, and interactive components
    - postcss.config.mjs (ESM .mjs extension required for Next.js 16 + ESM compatibility)
    - Vitest for formatter unit tests (relative import path for @/ alias compatibility)

key-files:
  created:
    - frontend/postcss.config.mjs
    - frontend/src/lib/formatters.ts
    - frontend/src/lib/__tests__/formatters.test.ts
    - frontend/src/hooks/useHealthData.ts
    - frontend/src/components/data-freshness-banner.tsx
    - frontend/src/components/ui/card.tsx
    - frontend/src/components/ui/skeleton.tsx
    - frontend/src/components/ui/badge.tsx
    - frontend/src/components/ui/table.tsx
    - frontend/src/components/ui/chart.tsx
    - frontend/src/components/ui/collapsible.tsx
    - frontend/src/components/ui/sheet.tsx
  modified:
    - frontend/src/app/(dashboard)/layout.tsx (replaced Server Component with Client Component + QueryClientProvider)
    - frontend/src/components/sidebar.tsx (added hidden md:flex for mobile collapse)
    - frontend/src/components/topbar.tsx (left-0 md:left-[240px], hamburger button, mobile Sheet nav)
    - frontend/messages/ro.json (added 6 new top-level namespaces)
    - frontend/messages/en.json (added 6 new top-level namespaces)
    - frontend/next.config.ts (added transpilePackages: ["radix-ui"] fix)
    - frontend/package.json (recharts, react-day-picker, date-fns added)

key-decisions:
  - "D-01 applied: postcss.config.mjs with @tailwindcss/postcss fixes KI-01 CSS not loading — validated by visual audit (D-03 APPROVED)"
  - "D-08 applied: QueryClientProvider in dashboard layout.tsx as Client Component with getQueryClient singleton (NOT useState) for stable QueryClient identity across renders"
  - "transpilePackages: ['radix-ui'] added to next.config.ts to fix Radix UI SSR/ESM resolution error surfaced during layout conversion"
  - "D-17/D-18 applied: mobile sidebar hidden md:flex, topbar left-0 md:left-[240px], hamburger Sheet overlay with all 8 nav items for < 768px mobile use"

patterns-established:
  - "Pattern: getQueryClient() singleton in layout.tsx — if (isServer) return makeQueryClient(); use cached browserQueryClient otherwise"
  - "Pattern: postcss.config.mjs ESM format for Tailwind v4.3 + Next.js 16 PostCSS pipeline"
  - "Pattern: formatters.ts pure utility — no 'use client', uses Intl.NumberFormat('ro-RO') for all monetary/pct formatting"
  - "Pattern: DataFreshnessBanner reads useHealthData().data.stale, returns null when not stale, localStorage session dismissal"
  - "Pattern: useHealthData staleTime 60s (overrides 5-min layout default for freshness sensitivity)"

requirements-completed: [UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, UI-07, UI-08]

# Metrics
duration: ~90min
completed: 2026-05-28
---

# Phase 7 Plan 01: Infrastructure + Foundations Summary

**PostCSS/Tailwind KI-01 fix, QueryClientProvider singleton, 26-test formatters.ts, mobile-responsive layout, 6 i18n namespaces, and 7 shadcn components unblocking all Wave 2 dashboard plans**

## Performance

- **Duration:** ~90 min
- **Started:** 2026-05-28T (continuation executor)
- **Completed:** 2026-05-28
- **Tasks:** 2 (+ 1 auto-fix deviation)
- **Files modified:** 18

## Accomplishments

- KI-01 CSS/Tailwind infrastructure bug resolved: `postcss.config.mjs` with `@tailwindcss/postcss` plugin enables Tailwind v4.3 CSS pipeline under Next.js 16 + Turbopack. D-03 visual audit passed — sidebar, topbar, and login page all render with correct shadcn styles.
- `formatters.ts` ships 7 named exports (formatRON, formatPct, formatDate, formatTimestamp, formatDuration, formatWowDelta, getDefaultDateRange) using `Intl.NumberFormat('ro-RO')` for Romanian locale formatting. 26 unit tests pass (vitest).
- Dashboard layout converted from Server Component to Client Component with `getQueryClient()` singleton pattern (not useState), `DataFreshnessBanner` slot, and `QueryClientProvider` wrapping all dashboard pages.
- Full mobile responsiveness: sidebar collapses on `< 768px` (hidden md:flex), topbar adjusts offset (left-0 md:left-[240px]), hamburger Sheet overlay exposes all 8 nav items with 44px touch targets.
- 6 new i18n namespaces (sales, salespeople, marketing, insights, common, errors) in both ro.json and en.json, completing all Phase 7 translation strings needed by Wave 2 and Wave 3 plans.

## Task Commits

Each task was committed atomically:

1. **Task 1: PostCSS fix + packages + shadcn + formatters.ts with tests** - `78a56d9e` (feat)
2. **Task 2: Dashboard layout + sidebar + topbar mobile fixes + i18n namespaces** - `82bf6059` (feat)
3. **Auto-fix: transpilePackages radix-ui in next.config.ts** - `1ccf8062` (fix)

## Files Created/Modified

- `frontend/postcss.config.mjs` — PostCSS config: `{ plugins: { "@tailwindcss/postcss": {} } }` (KI-01 fix)
- `frontend/src/lib/formatters.ts` — 7 pure formatters using Intl.NumberFormat('ro-RO'): formatRON, formatPct, formatDate, formatTimestamp, formatDuration, formatWowDelta, getDefaultDateRange
- `frontend/src/lib/__tests__/formatters.test.ts` — 26 vitest unit tests covering all formatter behaviors including null/edge cases
- `frontend/src/hooks/useHealthData.ts` — TanStack Query hook for /api/v1/health/data with staleTime 60000ms
- `frontend/src/components/data-freshness-banner.tsx` — Amber stale-data banner with localStorage session dismissal; returns null when not stale
- `frontend/src/app/(dashboard)/layout.tsx` — Replaced Server Component; now Client Component with getQueryClient singleton, QueryClientProvider, Sidebar, Topbar, DataFreshnessBanner, mobile-responsive main margin (ml-0 md:ml-[240px])
- `frontend/src/components/sidebar.tsx` — aside element: added hidden md:flex for mobile collapse
- `frontend/src/components/topbar.tsx` — left-0 md:left-[240px] header offset; hamburger Menu button (md:hidden); Sheet overlay with all 8 nav items
- `frontend/messages/ro.json` — Added 6 top-level namespaces (sales, salespeople, marketing, insights, common, errors) with complete Romanian strings
- `frontend/messages/en.json` — Mirrored same 6 namespaces with English translations
- `frontend/next.config.ts` — Added transpilePackages: ["radix-ui"] (auto-fix for Radix UI ESM resolution)
- `frontend/package.json` — recharts, react-day-picker, date-fns added as dependencies
- `frontend/src/components/ui/card.tsx` — shadcn Card component
- `frontend/src/components/ui/skeleton.tsx` — shadcn Skeleton component
- `frontend/src/components/ui/badge.tsx` — shadcn Badge component
- `frontend/src/components/ui/table.tsx` — shadcn Table component
- `frontend/src/components/ui/chart.tsx` — shadcn Chart component (Recharts wrapper)
- `frontend/src/components/ui/collapsible.tsx` — shadcn Collapsible component
- `frontend/src/components/ui/sheet.tsx` — shadcn Sheet component (used for mobile nav overlay)

## Decisions Made

- `transpilePackages: ["radix-ui"]` added to `next.config.ts` to resolve a Next.js 16 ESM resolution error for Radix UI packages that surfaced when layout.tsx was converted to a Client Component. This was an auto-fix (Rule 3 - blocking) since it prevented the dev server from rendering.
- `getQueryClient()` singleton pattern (not `useState`) applied per D-08 — ensures stable QueryClient identity on the server (new instance per request) and in the browser (single instance reused). This is the canonical Next.js App Router TanStack Query pattern.
- Formatter tests use relative import (`../formatters`) rather than `@/lib/formatters` alias because the vitest config was not guaranteed to resolve the `@/` alias in all environments — confirmed 26/26 tests pass with relative path.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] transpilePackages: ["radix-ui"] added to next.config.ts**
- **Found during:** Task 2 (Dashboard layout conversion to Client Component)
- **Issue:** After converting `layout.tsx` to a Client Component with `"use client"` and importing shadcn components that depend on Radix UI, the Next.js 16 dev server threw an ESM resolution error for `@radix-ui/*` packages. The dev server failed to serve any page.
- **Fix:** Added `transpilePackages: ["radix-ui"]` to the `experimental` config block in `frontend/next.config.ts`, instructing Next.js to transpile Radix UI ESM packages during bundling.
- **Files modified:** `frontend/next.config.ts`
- **Verification:** `pnpm typecheck` exits 0; `pnpm lint` exits 0; dev server renders sidebar, topbar, and login page correctly (D-03 visual audit APPROVED by user).
- **Committed in:** `1ccf8062`

---

**Total deviations:** 1 auto-fixed (1 Rule 3 blocking)
**Impact on plan:** Auto-fix was necessary for the dev server to render. No scope creep.

## Issues Encountered

- D-03 visual audit (checkpoint) was required before Wave 2 plans. Audit passed: CSS renders correctly, sidebar shows gray background with blue active nav item, topbar full-width, login page correctly styled with shadcn components.

## User Setup Required

None — no external service configuration required. All changes are frontend infrastructure and utilities.

## Next Phase Readiness

Wave 2 plans (07-02, 07-03, 07-04) are unblocked and can execute in parallel:
- CSS pipeline is fixed and validated
- `formatters.ts` exports all functions needed by all 4 dashboard pages
- `QueryClientProvider` is wired — TanStack Query hooks can be created in any dashboard page
- `DataFreshnessBanner` is ready — plans 02-04 can import it directly
- All 6 i18n namespaces are populated — no missing translation keys expected in Wave 2
- `recharts`, `react-day-picker`, `date-fns` are installed
- All 7 shadcn components (card, skeleton, badge, table, chart, collapsible, sheet) are installed

No blockers for Wave 2.

---
*Phase: 07-frontend-dashboards*
*Completed: 2026-05-28*
