# Phase 7: Frontend Dashboards - Research

**Researched:** 2026-05-28
**Domain:** Next.js 16 App Router, shadcn/ui, Recharts v3, TanStack Query v5, react-day-picker v10, Tailwind v4 PostCSS
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Fix approach: keep Turbopack, add PostCSS pipeline. Install `@tailwindcss/postcss`, add `postcss.config.mjs` with `{ plugins: { '@tailwindcss/postcss': {} } }`. This lets Turbopack delegate CSS processing to PostCSS, restoring the `@import "tailwindcss"` directive in `globals.css`.
- **D-02:** Plan 01 is a **dedicated infrastructure plan** covering exactly: PostCSS config + `@tailwindcss/postcss` install + `recharts` install + `react-day-picker` install + TanStack QueryClientProvider wired into `(dashboard)/layout.tsx` + shared formatter utilities (`formatRON`, `formatDate`). Nothing else. Plan 01 is done when CSS renders and the dev server runs without errors.
- **D-03:** After the CSS fix, Plan 01 includes a **visual audit** of existing components: sidebar, topbar, login page, and shadcn Button must all render with correct colors, spacing, and hover states before any dashboard content is built.
- **D-04:** **Funnel visualization** (SALE-01): Horizontal Recharts `BarChart` with 4 bars (Lead, Vizita, Oferta, Contract). Between each pair of bars, conversion percentage with directional arrow. WoW delta badge below each bar. No custom SVG funnel.
- **D-05:** **KPI cards** (SALE-03, SALES-01): shadcn `Card` with large metric number, WoW delta badge (green `▲+N%` or red `▼-N%`). `avg_time_to_first_touch_minutes` uses red background when > 240 minutes.
- **D-06:** **Source breakdown** (SALE-04): Recharts horizontal `BarChart` + summary table. Marketing page: Recharts `LineChart` (one line per source over time).
- **D-07:** **Salespeople leaderboard** (SALES-01..04): shadcn `Table`, sortable columns. Default sort: contracts descending.
- **D-08:** **QueryClientProvider** in `src/app/(dashboard)/layout.tsx` (NOT root layout). Must be Client Component wrapper (`"use client"`).
- **D-09:** **Default date range**: last 30 days. **Presets**: Ultima săptămână (7d), Ultima lună (30d), Ultimele 90 zile (90d), Luna curentă + custom.
- **D-10:** **Date state in URL**: `?from=YYYY-MM-DD&to=YYYY-MM-DD`. Each dashboard reads via `useSearchParams()`.
- **D-11:** **TanStack Query**: `staleTime: 5 * 60 * 1000`, `refetchOnWindowFocus: false`.
- **D-12:** **Loading states**: shadcn `Skeleton` matching final layout dimensions.
- **D-13:** **Error states**: inline Romanian message + retry button. 401 handled globally by apiClient.
- **D-14:** **Empty states**: section-specific Romanian copy + lucide icon. Zero-count charts replaced entirely.
- **D-15:** **Insights page layout**: `summary_ro` headline + up to 3 collapsed problem cards.
- **D-16:** **Generation failure fallback** (INSI-05): Romanian notice banner + algorithmic anomaly cards.
- **D-17..D-24:** **Mobile responsiveness — CRITICAL** (primary user = CEO on phone, 360px minimum).
- **D-25:** All strings in `ro.json`/`en.json`. `Intl.NumberFormat` for RON.

### Claude's Discretion

- Revenue trend line chart type (area vs line)
- Specific Recharts color palette (draw from CSS variables in `globals.css`)
- Conversion rate delta display exact format
- Specific Romanian copy for edge cases beyond D-13/D-14
- Chart height values (responsive)
- Whether to add `react-query-devtools` in development mode

### Deferred Ideas (OUT OF SCOPE)

- YoY overlay toggle (Phase 9 polish)
- Chat page implementation (Phase 8)
- Grafana/Prometheus (Phase 9)
- Sentry frontend error tracking (Phase 9)
- PDF/print export (out of v1 scope)
- Per-salesperson photo/avatar
- Configurable funnel stages
- Dark mode

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SALE-01 | Funnel viz: Lead→Vizita→Oferta→Contract with stage counts for date range | Backend: `SalesDashboardResponse.funnel` (FunnelCounts). UI: horizontal BarChart (D-04) |
| SALE-02 | L→V, V→O, L→O, O→C, L→C rates with WoW/MoM deltas | Backend: `SalesDashboardResponse.conversion_rates` (ConversionRates with 15 Decimal fields serialized as string) |
| SALE-03 | KPI cards: leads, visits, offers, contracts, revenue with delta indicators | Backend: `SalesDashboardResponse.kpi_cards` (KpiCards). UI: shadcn Card grid (D-05, D-19) |
| SALE-04 | Lead volume by source as chart + table | Backend: `SalesDashboardResponse.source_breakdown` (list[SourceBreakdownItem]). UI: horizontal BarChart (D-06) |
| SALE-05 | Revenue trend over time (line chart) | Backend: `SalesDashboardResponse.revenue_series` (list[RevenueSeries] with date+revenue). UI: LineChart/AreaChart |
| SALE-06 | Date range switching: 7d, 30d, 90d, custom | URL query params `?from=&to=` via useSearchParams (D-09, D-10) |
| SALE-07 | Stuck offers widget: count + list of offers >14 days no activity | Backend: `SalesDashboardResponse.stuck_offers` (list[StuckOffer] with external_id, days_stuck, salesperson_name) |
| SALES-01 | Leaderboard: 6 reps with leads/visits/offers/contracts/revenue/win-rate | Backend: `SalespeopleDashboardResponse.salespeople` (list[SalespersonRow]). UI: shadcn Table (D-07) |
| SALES-02 | Time-to-first-touch per rep, red highlight when >4h | Backend: `SalespersonRow.avg_time_to_first_touch_minutes` (int or None). UI: red cell when >240 |
| SALES-03 | Per-rep funnel for date range | Backend: same SalespersonRow (leads_assigned, visits_conducted, offers_sent, deals_won) |
| SALES-04 | `data_completeness_pct` per salesperson | Backend: `SalespersonRow.data_completeness_pct` (Decimal as string). UI: leaderboard column |
| MARK-01 | Lead volume by source over time (line chart) | Backend: `MarketingDashboardResponse.lead_volume_by_source` (list[LeadVolumeBySource] with series[]). UI: LineChart |
| MARK-02 | Site conversion rate | Backend: `MarketingDashboardResponse.site_conversion_rate` (Decimal as string, no GA4) |
| MARK-03 | Placeholder sections for CPL/CAC/ROAS | Backend: ad_spend/cpl/cac/roas always `null`. UI: "Coming in next update" placeholder |
| MARK-04 | Junk lead % by source | Backend: `MarketingDashboardResponse.junk_by_source` (list[JunkBySource] with junk_pct). UI: table |
| INSI-01 | Today's insights: top-3 problems with all fields | Backend: `GET /api/v1/insights/today` → InsightEnvelope{status, generation_failed, payload{summary, problems[]}}. NOTE: `summary` field (not `summary_ro`) |
| INSI-02 | Historical insights by date | Backend: `GET /api/v1/insights?date=YYYY-MM-DD` → 404 if absent. UI: historical date picker (D-15) |
| INSI-03 | Manual refresh, rate-limited 1/hr | Backend: `POST /api/v1/insights/refresh` → 202 or 429 with Retry-After. UI: Reîmprospătează button (D-15) |
| INSI-04 | Each problem links to triggering metric | Backend: `Problem.id = rule_id`. UI: display rule_id as source trace label |
| INSI-05 | Generation failure → algorithmic fallback | Backend: `InsightEnvelope.generation_failed=true`. UI: Romanian notice banner (D-16) |
| INSI-06 | generated_at + data freshness status | Backend: `InsightEnvelope.generated_at`. Health: `GET /api/v1/health/data` → HealthDataResponse |
| UI-01 | Romanian-first UI with English secondary | next-intl already wired. Phase 7 adds 6 new namespaces to ro.json/en.json |
| UI-02 | Currency: `1.234,56 RON` | `Intl.NumberFormat('ro-RO', {style:'currency', currency:'RON'})` — `formatRON()` in formatters.ts |
| UI-03 | Dates: `DD.MM.YYYY` | `Intl.DateTimeFormat('ro-RO', ...)` — `formatDate()` in formatters.ts |
| UI-04 | Timestamps in Europe/Bucharest timezone | `{timeZone: 'Europe/Bucharest'}` in Intl.DateTimeFormat — `formatTimestamp()` in formatters.ts |
| UI-05 | Loading, empty, error states on every chart/table | Skeleton (D-12), inline error+retry (D-13), Romanian empty copy (D-14) |
| UI-06 | Data freshness banner when >26h or sync failed | Shared `<DataFreshnessBanner>` in layout.tsx driven by `useHealthData()` hook |
| UI-07 | Responsive at desktop (1280px+) and tablet (768px+) | Grid responsive classes + hamburger sidebar for <768px. Primary target: mobile 360px (D-17..D-24) |
| UI-08 | Zero @tremor/react imports; use shadcn chart (Recharts v3) | `npx shadcn add chart` installs chart component. Import from `@/components/ui/chart` |

</phase_requirements>

---

## Summary

Phase 7 replaces four placeholder stub pages with full dashboard implementations. The backend API (Phase 6) is complete and documented — all endpoints, response shapes, and TypeScript-equivalent schemas are known exactly from the codebase. The primary frontend tech stack is already in `package.json` (Next.js 16.2, React 19.2, Tailwind v4.3, next-intl 4.12, TanStack Query 5.100.11) with one critical gap: `recharts` and `react-day-picker` are not yet installed, and the PostCSS config that makes Tailwind v4 work with Turbopack is missing (`postcss.config.mjs`).

The KI-01 issue (CSS not loading) has a confirmed fix: create `frontend/postcss.config.mjs` with `{ plugins: { "@tailwindcss/postcss": {} } }`. The `@tailwindcss/postcss` package is already listed as a devDependency in `package.json` at `^4` but the PostCSS config file simply does not exist yet. This is the only blocker for CSS rendering.

The existing codebase is well-structured with clear patterns: all pages are `"use client"` with `useTranslations`, `apiClient.get()` handles auth+refresh, and the shadcn component set already includes button, input, label, separator. The phase adds: card, skeleton, badge, table, chart, and the sheet component (via Radix — `@radix-ui/react-dialog` v1.1.15 already installed) for the mobile sidebar.

**Primary recommendation:** Execute Plan 01 (infrastructure only: PostCSS fix + package installs + QueryClientProvider + formatters) before any content plan. Plans 02-05 implement the four dashboard pages in parallel after Plan 01.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Date range state (presets, URL sync) | Browser / Client | — | `useSearchParams` + `router.push` — pure client state in URL |
| Dashboard data fetching | Browser / Client (TanStack Query) | API / Backend | `queryFn` calls `apiClient.get()` which hits backend; caching in browser |
| Loading/error/empty states | Browser / Client | — | Conditional rendering from `useQuery` status |
| KPI card rendering | Browser / Client | — | Reads from TanStack Query cache, computes display values client-side |
| Chart rendering | Browser / Client | — | Recharts runs only in browser (no SSR for canvas/SVG-heavy charts) |
| Revenue/date formatting | Browser / Client | — | `Intl.NumberFormat`/`Intl.DateTimeFormat` — locale-aware, client-side |
| i18n string lookup | Browser / Client + SSR | — | next-intl serves strings from server; `useTranslations` reads them |
| API data aggregation | API / Backend | — | Already pre-computed in metric tables; backend returns aggregated response |
| Rate limiting (insights refresh) | API / Backend (Redis) | — | `SET NX EX 3600` — enforced server-side |
| Auth token refresh | Browser / Client (apiClient) | API / Backend | `apiClient.ts` handles 401 refresh cycle |
| Mobile sidebar state (open/closed) | Browser / Client | — | `useState` in topbar/layout; CSS translate for show/hide |
| Data freshness detection | API / Backend | Browser / Client (banner) | Backend computes `stale` flag; banner reads it via `useHealthData()` |

---

## Standard Stack

### Core (already in package.json)

| Library | Version in package.json | Purpose | Why Standard |
|---------|------------------------|---------|--------------|
| next | 16.2.6 | Framework, App Router, Turbopack | Project standard [VERIFIED: package.json] |
| react | ^19.2.0 | UI rendering | Project standard [VERIFIED: package.json] |
| tailwindcss | ^4.3.0 | Utility CSS | Project standard [VERIFIED: package.json] |
| @tailwindcss/postcss | ^4 | PostCSS bridge for Tailwind v4 (KI-01 fix) | Required to enable PostCSS pipeline [VERIFIED: package.json devDependencies — already listed but missing postcss.config.mjs] |
| @tanstack/react-query | 5.100.11 | Server state, caching, loading/error states | Already installed [VERIFIED: package.json] |
| next-intl | 4.12.0 | i18n, `useTranslations`, locale routing | Already wired [VERIFIED: package.json] |
| lucide-react | ^0.469.0 | Icons (empty states, nav, buttons) | shadcn default [VERIFIED: package.json] |
| clsx + tailwind-merge | ^2.x | className utility (cn function) | Already in lib/utils.ts [VERIFIED: codebase] |

### Needs Installation

| Library | Current Latest | Purpose | Why Needed |
|---------|---------------|---------|------------|
| recharts | 3.8.1 | Chart rendering (BarChart, LineChart via shadcn chart wrapper) | Not installed; `npx shadcn add chart` will add it as a dependency [VERIFIED: npm registry] |
| react-day-picker | 10.0.1 | DateRangePicker calendar UI (D-09, D-22) | Not installed; direct npm package [VERIFIED: npm registry] |

### shadcn Components to Install

| Component | Install Command | Already Present |
|-----------|----------------|----------------|
| card | `npx shadcn add card` | No [VERIFIED: ui/ directory scan] |
| skeleton | `npx shadcn add skeleton` | No |
| badge | `npx shadcn add badge` | No |
| table | `npx shadcn add table` | No |
| chart | `npx shadcn add chart` | No — also installs recharts |
| collapsible | `npx shadcn add collapsible` | No — needed for insight problem cards (D-15) |
| button | already present | Yes [VERIFIED: ui/button.tsx] |
| separator | already present | Yes [VERIFIED: ui/separator.tsx] |
| input | already present | Yes [VERIFIED: ui/input.tsx] |

**Radix UI dialog/sheet:** `@radix-ui/react-dialog` v1.1.15 is already installed [VERIFIED: package.json]. The Sheet pattern for mobile sidebar uses `@radix-ui/react-dialog` under the hood — `npx shadcn add sheet` will add the component wrapper.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| react-day-picker | shadcn DatePicker (wraps react-day-picker) | shadcn DatePicker doesn't natively support range mode + bottom-sheet; direct react-day-picker gives more control |
| TanStack Query | SWR | Project decision locked (D-11). TanStack Query v5 already installed |
| shadcn Sheet (mobile) | custom CSS overlay | Sheet uses Radix Dialog (already installed) — no new heavy dependency |

**Installation (Plan 01):**

```bash
# From frontend/ directory
pnpm add recharts react-day-picker
npx shadcn add card skeleton badge table chart collapsible sheet
```

Note: `@tailwindcss/postcss` is already in devDependencies — only `postcss.config.mjs` needs to be created.

**Version verification:** [VERIFIED: npm registry 2026-05-28]
- `recharts`: 3.8.1 (npm registry) — peerDeps: react ^16-19, react-dom ^16-19
- `react-day-picker`: 10.0.1 (npm registry) — peerDeps: react >=16.8.0
- `@tanstack/react-query`: 5.100.14 on registry (5.100.11 already installed) — peerDeps: react ^18||^19

All three packages support React 19.2. No conflicts.

---

## Package Legitimacy Audit

> slopcheck defaults to PyPI. These are npm packages — cross-ecosystem check not applicable. npm registry verification performed instead.

| Package | Registry | Age | Source Repo | npm verify | Disposition |
|---------|----------|-----|-------------|-----------|-------------|
| recharts | npm | ~11 yrs (2015-08-07) | github.com/recharts/recharts | `npm view recharts version` = 3.8.1 | Approved [VERIFIED: npm registry] |
| react-day-picker | npm | ~10 yrs | github.com/gpbl/react-day-picker | `npm view react-day-picker version` = 10.0.1 | Approved [VERIFIED: npm registry] |
| @tanstack/react-query | npm | ~6 yrs | github.com/TanStack/query | `npm view @tanstack/react-query version` = 5.100.14 | Approved — already installed [VERIFIED: npm registry] |

slopcheck flagged all three as SLOP on PyPI (cross-ecosystem confusion — these are npm packages, not Python packages). All three pass npm registry verification with long publication history, millions of weekly downloads, and official source repos. **slopcheck verdict does not apply to npm ecosystem packages.**

**Packages removed:** none.
**Packages flagged as suspicious:** none.
**Postinstall scripts:** none found on any of the three packages [VERIFIED: npm view scripts.postinstall].

---

## Architecture Patterns

### System Architecture Diagram

```
User navigates to /sales?from=2026-05-01&to=2026-05-28
          │
          ▼
Next.js App Router
  (dashboard)/layout.tsx [Client Component]
    └─ QueryClientProvider (staleTime=5min, refetchOnWindowFocus=false)
    └─ DataFreshnessBanner (reads useHealthData — separate query, staleTime=60s)
          │
          ▼
SalesPage [Client Component]
  useSearchParams() → {from, to}  (defaults: today-29 → today)
  useSalesDashboard({from, to})
    └─ useQuery({queryKey: ['sales', from, to], queryFn: ...})
         └─ apiClient.get('/api/v1/dashboards/sales?from=...&to=...')
              └─ 401? → refresh → retry → redirect /login
                                    │
                   ┌────────────────┼──────────────────┐
                   ▼                ▼                   ▼
             isLoading           isError            data present
                │                  │                   │
           <Skeleton>        inline error          render content:
           (section-sized)   + retry button        ┌─ KpiCards grid
                                                   ├─ FunnelChart
                                                   ├─ SourceBreakdown
                                                   ├─ RevenueTrend
                                                   └─ StuckOffers

Date change:
  DateRangePicker → router.push('?from=...&to=...')
  → useSearchParams() re-reads → query key changes → refetch
```

### Recommended Project Structure

```
frontend/src/
├── hooks/                          # NEW — TanStack Query hooks
│   ├── useSalesDashboard.ts
│   ├── useSalespeopleDashboard.ts
│   ├── useMarketingDashboard.ts
│   ├── useInsights.ts
│   └── useHealthData.ts
├── lib/
│   ├── api-client.ts               # existing — DO NOT MODIFY
│   ├── utils.ts                    # existing (cn utility)
│   └── formatters.ts               # NEW — formatRON, formatDate, formatDuration, formatPct
├── components/
│   ├── ui/                         # shadcn primitives (existing + new via `npx shadcn add`)
│   ├── data-freshness-banner.tsx   # NEW — shared stale data banner (UI-06)
│   ├── date-range-picker.tsx       # NEW — react-day-picker + preset tabs + URL sync
│   └── dashboards/
│       ├── sales/
│       │   ├── kpi-cards.tsx
│       │   ├── funnel-chart.tsx
│       │   ├── source-breakdown.tsx
│       │   ├── revenue-trend.tsx
│       │   └── stuck-offers.tsx
│       ├── salespeople/
│       │   └── leaderboard-table.tsx
│       ├── marketing/
│       │   ├── source-volume-chart.tsx
│       │   ├── junk-pct-table.tsx
│       │   └── ad-spend-placeholder.tsx
│       └── insights/
│           ├── insight-summary.tsx
│           ├── problem-card.tsx
│           └── generation-failed-banner.tsx
├── app/(dashboard)/
│   ├── layout.tsx                  # MODIFY — add QueryClientProvider + DataFreshnessBanner
│   ├── sales/page.tsx              # REPLACE stub
│   ├── salespeople/page.tsx        # REPLACE stub
│   ├── marketing/page.tsx          # REPLACE stub
│   └── insights/page.tsx           # REPLACE stub
├── components/
│   ├── sidebar.tsx                 # MODIFY — add mobile collapse (D-18)
│   └── topbar.tsx                  # MODIFY — add hamburger button (D-18)
└── messages/
    ├── ro.json                     # EXPAND — add 6 new namespaces
    └── en.json                     # EXPAND — mirror new namespaces
```

### Pattern 1: KI-01 PostCSS Fix

**What:** Create `frontend/postcss.config.mjs` to enable PostCSS pipeline so Turbopack can process Tailwind v4's `@import "tailwindcss"` directive.

**Why it works:** Tailwind v4 changed from a PostCSS plugin shipped with the main package to `@tailwindcss/postcss`. Next.js 16 Turbopack delegates CSS to PostCSS when a postcss config is present. Without the config file, Turbopack doesn't invoke PostCSS, so the `@import "tailwindcss"` in globals.css produces no utility classes.

```javascript
// Source: tailwindcss.com/docs/guides/nextjs [CITED]
// File: frontend/postcss.config.mjs
const config = {
  plugins: {
    "@tailwindcss/postcss": {},
  },
};

export default config;
```

**Validation:** `pnpm dev` serves the app; sidebar shows gray background (`hsl(240 5% 96%)`), active nav item shows blue text, login button shows correct colors. [VERIFIED approach via Tailwind official docs]

### Pattern 2: QueryClientProvider in Dashboard Layout

**What:** Convert `(dashboard)/layout.tsx` to a Client Component that wraps children with `QueryClientProvider`. Use `getQueryClient()` helper (not `useState`) to avoid React dropping the client on suspense.

```typescript
// Source: tanstack.com/query/v5/docs/framework/react/guides/advanced-ssr [CITED]
// File: frontend/src/app/(dashboard)/layout.tsx
"use client";

import { isServer, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Sidebar from "@/components/sidebar";
import Topbar from "@/components/topbar";
import DataFreshnessBanner from "@/components/data-freshness-banner";

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 5 * 60 * 1000,     // 5 minutes — D-11
        refetchOnWindowFocus: false,   // D-11
      },
    },
  });
}

let browserQueryClient: QueryClient | undefined = undefined;

function getQueryClient() {
  if (isServer) {
    return makeQueryClient();        // new per request on server
  }
  if (!browserQueryClient) browserQueryClient = makeQueryClient();
  return browserQueryClient;         // singleton in browser
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const queryClient = getQueryClient();
  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen">
        <Sidebar />
        <Topbar />
        <main className="ml-[240px] mt-14 p-8 bg-white min-h-[calc(100vh-56px)]">
          <DataFreshnessBanner />
          {children}
        </main>
      </div>
    </QueryClientProvider>
  );
}
```

**Key gotcha:** Do NOT create the QueryClient with `useState`. If a child suspends before the client is used, React will discard the state and create a new client — this breaks cache. The `getQueryClient()` module-level singleton pattern is the TanStack official recommendation for Next.js App Router. [CITED: tanstack.com/query/v5 advanced-ssr guide]

**Mobile:** The `ml-[240px]` must become `ml-0 md:ml-[240px]` for mobile layout. The `p-8` padding should be `p-4 md:p-8`.

### Pattern 3: TanStack Query v5 Hook (Client Component)

**What:** `useQuery` with proper v5 object syntax, inferring TypeScript types from API response shape.

```typescript
// Source: package.json [@tanstack/react-query 5.100.11 — VERIFIED]
// File: frontend/src/hooks/useSalesDashboard.ts
"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export interface SalesDashboardData {
  period: { from: string; to: string };
  funnel: { leads: number | null; visits: number | null; offers: number | null; contracts: number | null };
  conversion_rates: {
    l_to_v: string | null; v_to_o: string | null; l_to_o: string | null;
    o_to_c: string | null; l_to_c: string | null;
    l_to_v_wow_delta: string | null; l_to_c_wow_delta: string | null;
    // ... all delta fields as string | null (DATA-04: Decimal serialized as string)
  };
  kpi_cards: {
    leads_total: number | null; visits_count: number | null;
    offers_count: number | null; contracts_count: number | null;
    revenue: string | null; avg_deal_size: string | null;
    revenue_wow_delta: string | null; leads_total_wow_delta: string | null;
  };
  source_breakdown: Array<{ source: string; leads: number | null; conversion_rate: string | null }>;
  revenue_series: Array<{ date: string; revenue: string | null }>;
  stuck_offers: Array<{ external_id: string; days_stuck: number; salesperson_name: string | null }>;
}

export function useSalesDashboard(from: string, to: string) {
  return useQuery<SalesDashboardData>({
    queryKey: ["sales", from, to],
    queryFn: async () => {
      const res = await apiClient.get(`/api/v1/dashboards/sales?from=${from}&to=${to}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    enabled: Boolean(from && to),
  });
}
```

**Important:** All Decimal fields come from the backend as strings (DATA-04). Parse with `parseFloat()` before formatting. Never use `.toFixed()` — use `Intl.NumberFormat` exclusively (D-25).

### Pattern 4: Date Range Picker with URL Sync

**What:** `react-day-picker` v10 `mode="range"` + URL state via `useSearchParams` + `router.push`.

```typescript
// Source: react-day-picker v10 range mode docs [CITED: daypicker.dev]
// File: frontend/src/components/date-range-picker.tsx
"use client";

import { useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { DayPicker, type DateRange } from "react-day-picker";
import { format, subDays, startOfMonth } from "date-fns"; // react-day-picker v10 uses date-fns

function getDefaultRange(): { from: string; to: string } {
  const to = new Date();
  const from = subDays(to, 29);
  return {
    from: format(from, "yyyy-MM-dd"),
    to: format(to, "yyyy-MM-dd"),
  };
}

export function DateRangePicker() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [open, setOpen] = useState(false);

  const defaults = getDefaultRange();
  const currentFrom = searchParams.get("from") ?? defaults.from;
  const currentTo = searchParams.get("to") ?? defaults.to;

  const [range, setRange] = useState<DateRange | undefined>({
    from: new Date(currentFrom),
    to: new Date(currentTo),
  });

  function applyRange(r: DateRange | undefined) {
    if (!r?.from || !r?.to) return;
    const params = new URLSearchParams(searchParams.toString());
    params.set("from", format(r.from, "yyyy-MM-dd"));
    params.set("to", format(r.to, "yyyy-MM-dd"));
    router.push(`?${params.toString()}`);
    setOpen(false);
  }

  return (
    // ... trigger button + DayPicker mode="range" + preset tabs
    <DayPicker
      mode="range"
      selected={range}
      onSelect={setRange}
      numberOfMonths={2} // show two months for range selection
    />
  );
}
```

**react-day-picker v10 range mode API:** [CITED: daypicker.dev]
- `mode="range"` — enables range selection
- `selected: DateRange | undefined` — controlled state, type `{ from?: Date; to?: Date }`
- `onSelect: (range: DateRange | undefined) => void` — called on each click
- Range is "open" (only `from` set) until user clicks second date
- `resetOnSelect` prop starts a new range on click when a full range is already selected

**Mobile bottom sheet (D-22):** Wrap `DayPicker` in a conditional: `< 768px` → full-screen `Sheet` from shadcn; `>= 768px` → `Popover`. Use `useMediaQuery` hook or CSS to toggle. Avoid `window.innerWidth` during SSR — use `useEffect` + `useState` for hydration-safe breakpoint detection.

### Pattern 5: shadcn Chart (ChartContainer + ChartTooltip)

**What:** `npx shadcn add chart` copies `components/ui/chart.tsx` (a thin wrapper around Recharts). This is NOT a re-export of Recharts — it adds `ChartContainer` with CSS variable support and `ChartTooltip`/`ChartTooltipContent` components.

```typescript
// Source: ui.shadcn.com/docs/components/chart [CITED]
// File: frontend/src/components/dashboards/sales/funnel-chart.tsx
"use client";

import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer } from "recharts";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";  // ← ALWAYS import from here, never directly from recharts

const chartConfig = {
  count: {
    label: "Leads",
    color: "var(--color-accent)",  // uses CSS variable from globals.css
  },
} satisfies ChartConfig;

export function FunnelChart({ data }: { data: FunnelData }) {
  return (
    <ChartContainer config={chartConfig} className="min-h-[200px] w-full">
      <BarChart data={data.horizontal}>
        <XAxis dataKey="stage" />
        <Bar dataKey="count" fill="var(--color-accent)" />
        <ChartTooltip content={<ChartTooltipContent />} />
      </BarChart>
    </ChartContainer>
  );
}
```

**Key insight:** `ChartContainer` sets up CSS variable context so `var(--color-accent)` works inside chart fill/stroke props. Always use `ChartContainer` — don't use `ResponsiveContainer` directly when using shadcn chart. ChartContainer handles responsive sizing internally via `ResponsiveContainer width="100%"`.

### Pattern 6: Mobile Sidebar (Sheet + Hamburger)

**What:** Hide sidebar on mobile, show hamburger button in topbar, open shadcn `Sheet` with full nav on tap.

**SSR hydration safety:** Do NOT check `window.innerWidth` during render. Use CSS classes exclusively:

```typescript
// In sidebar.tsx — hide on mobile with CSS, no JS breakpoint detection
<aside className="hidden md:flex fixed left-0 top-0 h-screen w-[240px] ...">
  {/* desktop sidebar content */}
</aside>

// In topbar.tsx — hamburger button visible only on mobile
<button className="md:hidden" aria-label={t("common.openMenu")} onClick={() => setMobileMenuOpen(true)}>
  <Menu size={24} />
</button>

// Mobile Sheet overlay
<Sheet open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
  <SheetContent side="left" className="w-full sm:w-[240px] p-0">
    {/* render same nav items as desktop sidebar */}
  </SheetContent>
</Sheet>
```

**Topbar layout:** Currently `left-[240px]` hardcoded. For mobile: `left-0 md:left-[240px]`. The hamburger button must be `left-0` area and visible only on mobile.

### Anti-Patterns to Avoid

- **Importing Recharts directly in page components:** Always `import { ChartContainer } from '@/components/ui/chart'` — never `import { BarChart } from 'recharts'` in page-level JSX.
- **`@tremor/react` imports:** Zero tolerance — zero Tremor. Grep check in Phase 7 SC#8.
- **Hardcoded hex colors in JSX:** Use `var(--color-accent)` or Tailwind semantic classes — never `text-[#2563EB]`.
- **Hardcoded Romanian strings:** Always `const t = useTranslations(ns); t('key')`.
- **`.toFixed(2)` for money:** Use `Intl.NumberFormat('ro-RO', {style:'currency', currency:'RON'})` exclusively.
- **`new Date().toLocaleDateString()`:** Use `Intl.DateTimeFormat('ro-RO', {timeZone:'Europe/Bucharest', ...})`.
- **Empty chart with zero-data:** Replace with empty state component — never render empty axes.
- **`queryClient` created with `useState`:** Use module-level `getQueryClient()` singleton pattern (see Pattern 2).
- **`window.innerWidth` during SSR:** Use CSS `hidden md:flex` or `useEffect`-gated breakpoint hook.
- **Calling backend in Server Components:** All dashboard data via TanStack Query hooks in Client Components.
- **`summary_ro` field name from insight:** The actual backend field is `summary` (not `summary_ro`) per `DailyInsightResponse` schema in `daily_insight_schema.py`. [VERIFIED: codebase]

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Auth token refresh | Custom 401 handler | `apiClient.ts` already handles refresh cycle | Existing, tested; re-implementing risks double-refresh bugs |
| Romanian number formatting | Custom string concat | `Intl.NumberFormat('ro-RO', ...)` | Handles dot-thousands, comma-decimal, RON symbol correctly per locale |
| Date range calendar | Custom calendar grid | `react-day-picker` v10 `mode="range"` | Handles keyboard nav, ARIA, month navigation, range highlighting |
| Chart tooltip | Custom HTML overlay | `ChartTooltip`/`ChartTooltipContent` from shadcn | Handles positioning, keyboard, theming with CSS vars |
| Loading skeletons | CSS animations from scratch | `shadcn add skeleton` (`Skeleton` component) | Consistent with design system, no layout shift |
| Collapsible insight cards | Custom open/close state + CSS | `shadcn add collapsible` (`Collapsible` component) | Handles ARIA, keyboard, animation with Radix Collapsible |
| Mobile sheet overlay | Custom drawer from scratch | `shadcn add sheet` (uses Radix Dialog) | Handles focus trap, escape key, backdrop, portal |

**Key insight:** Every "custom solution" above has been a source of a11y bugs in production apps. The shadcn/Radix ecosystem handles these edge cases. Never re-implement them.

---

## Common Pitfalls

### Pitfall 1: CSS Not Loading (KI-01) — the root cause is a missing file

**What goes wrong:** `globals.css` has `@import "tailwindcss"` which is a Tailwind v4 CSS import. Turbopack does not process it without a PostCSS config file — CSS classes are simply absent, all styling is unstyled HTML.

**Why it happens:** `@tailwindcss/postcss` is in `devDependencies` but `postcss.config.mjs` was never created in Phase 1.

**How to avoid:** Create `frontend/postcss.config.mjs` with content: `export default { plugins: { "@tailwindcss/postcss": {} } }`. Verify with `pnpm dev` before building any content (D-03 visual audit). [VERIFIED: official Tailwind v4 + Next.js guide — tailwindcss.com/docs/guides/nextjs]

**Warning signs:** All pages render as unstyled HTML; no colors, no spacing. The issue is silent — no error in console.

### Pitfall 2: `summary_ro` Field Name Mismatch

**What goes wrong:** The 07-CONTEXT.md and UI-SPEC.md refer to the insight summary as `summary_ro`. But the actual `DailyInsightResponse` Pydantic schema in `backend/app/schemas/insights/daily_insight_schema.py` has the field named `summary` (not `summary_ro`). The `InsightEnvelope.payload` dict will have `payload.summary`, not `payload.summary_ro`.

**Why it happens:** Design documentation used a different name than the implemented schema.

**How to avoid:** TypeScript interface for InsightEnvelope payload must use `summary: string`, not `summary_ro: string`. [VERIFIED: codebase — daily_insight_schema.py line: `summary: str  # one overview paragraph in Romanian`]

**Warning signs:** `payload.summary_ro` is undefined; insight headline renders as blank.

### Pitfall 3: Decimal Fields Are Strings From Backend

**What goes wrong:** `revenue`, `win_rate`, `conversion_rate`, `junk_pct`, etc. come from the backend as strings (e.g., `"85000.00"`), not numbers. Passing them directly to Recharts data props or doing arithmetic causes NaN.

**Why it happens:** DATA-04 compliance — backend uses `@field_serializer` on all Decimal fields to output strings.

**How to avoid:** Parse with `parseFloat(str ?? "0")` before: (1) passing to Recharts `dataKey` values, (2) arithmetic for derived values. Format with `Intl.NumberFormat`, never `.toFixed()`. [VERIFIED: codebase — all sales/salespeople/marketing schemas use field_serializer returning str | None]

**Warning signs:** Recharts bars all at height 0; `Intl.NumberFormat(undefined)` returns "NaN".

### Pitfall 4: QueryClient Created with useState

**What goes wrong:** Creating the QueryClient with `const [queryClient] = useState(() => new QueryClient())` in the layout causes React to drop the client instance when a child component suspends on the initial render, resulting in lost cache and potential infinite re-render.

**Why it happens:** React Suspense discards state on the initial render pass when suspension occurs.

**How to avoid:** Use the module-level `getQueryClient()` singleton pattern (Pattern 2). This is the TanStack official recommendation for Next.js App Router with v5. [CITED: tanstack.com/query/v5/docs/framework/react/guides/advanced-ssr]

**Warning signs:** Infinite re-fetching loop; React warns about "client was not provided".

### Pitfall 5: useSearchParams Requires Suspense Boundary

**What goes wrong:** `useSearchParams()` in Next.js App Router throws if not wrapped in a Suspense boundary during SSR. Page renders may suspend.

**Why it happens:** Next.js App Router's `useSearchParams()` requires the component to be in a client subtree that can suspend during SSR.

**How to avoid:** Wrap page content that uses `useSearchParams()` in `<Suspense fallback={<Skeleton />}>` or add `"use client"` + lazy boundary at the page level. Since all dashboard pages are already `"use client"`, the risk is lower — but the Suspense wrapper is still recommended.

**Warning signs:** "useSearchParams() should be wrapped in a suspense boundary" console error in production builds.

### Pitfall 6: react-day-picker v10 Breaking Changes from v8

**What goes wrong:** Existing examples online use `react-day-picker` v8 API (`DateRange`, `DayPickerRangeProps`). v10 has breaking changes: the component is now `DayPicker` (unchanged name) but some props and types have changed. v10 no longer requires `date-fns` as a separate peer dependency for basic use (it bundles date utilities).

**Why it happens:** npm latest is v10.0.1 — many blog posts and StackOverflow answers show v8 API.

**How to avoid:** Import `DateRange` from `react-day-picker` (not `react-day-picker/dist/types`). Use `mode="range"`, `selected: DateRange | undefined`, `onSelect: (range: DateRange | undefined) => void`. [CITED: daypicker.dev]

**Warning signs:** TypeScript errors on `DayPickerRangeProps` or missing `selected` prop type.

### Pitfall 7: Mobile Layout — Hardcoded `left-[240px]` in Topbar

**What goes wrong:** Current `topbar.tsx` has `left-[240px]` hardcoded. On mobile, with the sidebar hidden, this makes the topbar start at 240px from the left — leaving a dead zone on mobile.

**Why it happens:** Phase 1 built desktop-only layout. Mobile responsiveness is Phase 7.

**How to avoid:** Change topbar `left-[240px]` to `left-0 md:left-[240px]`. Change main content `ml-[240px]` to `ml-0 md:ml-[240px]`. [VERIFIED: topbar.tsx and layout.tsx — current hardcoded values]

**Warning signs:** On mobile, topbar has 240px left whitespace; main content is shifted 240px off-screen.

### Pitfall 8: Insights `today` Means Yesterday's Data

**What goes wrong:** `GET /api/v1/insights/today` actually queries `daily_insights WHERE date = yesterday` (Bucharest timezone `today - 1 day`). The pipeline generates insights at 06:00 for "yesterday's" data. If the frontend shows "Today" as a date label, it should show the `date` field from the response, not `new Date()`.

**Why it happens:** The insight generation is a daily morning batch job for prior day data — "today's insight" is the report generated this morning about yesterday's CRM activity.

**How to avoid:** Display the `InsightEnvelope.date` field as the insight date, not "today". Keep the nav label as "Analize AI" (already in `nav.insights`). [VERIFIED: insights.py — `svc.get_today()` queries for yesterday]

**Warning signs:** "Data pentru: 28.05.2026" when insight.date is "27.05.2026".

---

## Code Examples

### formatters.ts

```typescript
// File: frontend/src/lib/formatters.ts
// All formatters derived from UI-SPEC.md Number & Date Formatting Contract

export function formatRON(value: string | number | null | undefined, compact = false): string {
  if (value === null || value === undefined) return "N/A";
  const num = typeof value === "string" ? parseFloat(value) : value;
  if (isNaN(num)) return "N/A";
  return new Intl.NumberFormat("ro-RO", {
    style: "currency",
    currency: "RON",
    maximumFractionDigits: compact ? 0 : 2,
  }).format(num);
}

export function formatPct(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return "N/A";
  const num = typeof value === "string" ? parseFloat(value) : value;
  if (isNaN(num)) return "N/A";
  return new Intl.NumberFormat("ro-RO", {
    style: "percent",
    maximumFractionDigits: 1,
  }).format(num);
}

export function formatDate(dateStr: string | Date | null | undefined): string {
  if (!dateStr) return "";
  const d = typeof dateStr === "string" ? new Date(dateStr) : dateStr;
  return new Intl.DateTimeFormat("ro-RO", {
    day: "2-digit", month: "2-digit", year: "numeric",
  }).format(d);
}

export function formatTimestamp(dateStr: string | Date | null | undefined): string {
  if (!dateStr) return "";
  const d = typeof dateStr === "string" ? new Date(dateStr) : dateStr;
  return new Intl.DateTimeFormat("ro-RO", {
    timeZone: "Europe/Bucharest",
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  }).format(d);
}

export function formatDuration(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined) return "N/A";
  if (minutes < 60) return `${minutes}min`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m > 0 ? `${h}h ${m}min` : `${h}h`;
}

export function formatWowDelta(delta: string | null | undefined): {
  label: string; positive: boolean | null;
} {
  if (!delta) return { label: "", positive: null };
  const num = parseFloat(delta);
  if (isNaN(num)) return { label: "", positive: null };
  const pct = (num * 100).toFixed(1);
  if (num > 0) return { label: `▲ +${pct}%`, positive: true };
  if (num < 0) return { label: `▼ ${pct}%`, positive: false };
  return { label: "0%", positive: null };
}
```

### Default Date Range Utility

```typescript
// Shared utility — used in DateRangePicker and page defaultProps
export function getDefaultDateRange(): { from: string; to: string } {
  const to = new Date();
  const from = new Date();
  from.setDate(to.getDate() - 29); // last 30 days inclusive (D-09)
  const fmt = (d: Date) => d.toISOString().split("T")[0]; // YYYY-MM-DD
  return { from: fmt(from), to: fmt(to) };
}
```

### InsightEnvelope TypeScript type

```typescript
// Derived from backend/app/api/v1/insights.py InsightEnvelope + daily_insight_schema.py
export interface ActionItem {
  order: number;
  description: string;
  owner: string;
  deadline: "Azi" | "Mâine" | "Săptămâna aceasta" | "Luna aceasta";
  expected_outcome: string;
}

export interface Problem {
  id: string;           // = rule_id for source traceability (INSI-04)
  severity: "high" | "medium" | "low";
  category: "marketing" | "sales" | "team" | "funnel";
  title: string;
  description: string;
  estimated_loss_ron: number; // backend sends as number (Decimal but not field_serialized in DailyInsightResponse)
  actions: ActionItem[];
}

export interface InsightPayload {
  summary: string;      // NOTE: "summary" not "summary_ro" — verified in backend schema
  problems: Problem[];  // max 3
  positives: Array<{ title: string; description: string; recommendation: string }>;
  warnings: Array<{ title: string; description: string }>;
  weekly_action_plan: string[];
  generated_at: string; // ISO datetime
}

export interface InsightEnvelope {
  date: string;            // YYYY-MM-DD (= yesterday in Bucharest TZ)
  status: string;          // "success" | "failed" | "fallback" | "running"
  generation_failed: boolean;
  generated_at: string | null;
  payload: InsightPayload | null;
}
```

---

## Existing Codebase State — Critical Inventory

### What Currently Exists in Dashboard Pages

All 4 dashboard stubs are identical in structure — a centered "coming soon" placeholder with a lucide icon and `useTranslations("placeholder")`. Each file is `"use client"` with no data fetching. They are safe to completely replace.

### `(dashboard)/layout.tsx` Current State

```typescript
// CURRENT — Server Component (no "use client"), no QueryClientProvider
import Sidebar from "@/components/sidebar";
import Topbar from "@/components/topbar";

export default function DashboardLayout({ children }) {
  return (
    <div className="min-h-screen">
      <Sidebar />
      <Topbar />
      <main className="ml-[240px] mt-14 p-8 bg-white min-h-[calc(100vh-56px)]">
        {children}
      </main>
    </div>
  );
}
```

Must be modified to: (1) add `"use client"`, (2) add QueryClientProvider with getQueryClient pattern, (3) add DataFreshnessBanner, (4) fix mobile ML to `ml-0 md:ml-[240px]`.

### `sidebar.tsx` Current State

Fixed 240px sidebar with 8 nav items. Uses inline HSL values (`hsl(240_5%_96%)`) instead of CSS variables — this is fine, it will render correctly once PostCSS fix is applied. Mobile: needs `hidden md:flex` on the aside element. Currently always visible.

### `topbar.tsx` Current State

Fixed topbar `left-[240px]` — needs `left-0 md:left-[240px]`. Has locale toggle button. Needs hamburger `<Menu>` icon button added (mobile only: `md:hidden`). Must accept `onMenuOpen` callback prop or lift sidebar open state.

### `apiClient.ts` Current State

Clean and complete. `apiClient.get(url)` handles: (1) `credentials: "include"` for cookies, (2) 401 → refresh → retry once → redirect `/login` on second 401. No changes needed.

### `messages/ro.json` Current State

Has 4 top-level keys: `auth`, `nav`, `placeholder`, `locale`. Phase 7 adds 6 new keys: `sales`, `salespeople`, `marketing`, `insights`, `common`, `errors`. **Existing keys must NOT be restructured** — only append new top-level namespaces.

### `globals.css` Current State

Has `@import "tailwindcss"` (Tailwind v4 syntax — correct). Has `@theme` block with all CSS variables. Has `:root` block for shadcn compatibility. The file is correct — the only issue is missing `postcss.config.mjs`. [VERIFIED: globals.css — content confirmed]

### `components.json` Current State

`style: "new-york"`, `baseColor: "zinc"`, `cssVariables: true`. All `npx shadcn add <component>` commands will use this config automatically. [VERIFIED: components.json]

### shadcn Components Currently Installed

`button.tsx`, `input.tsx`, `label.tsx`, `separator.tsx`. Missing for Phase 7: card, skeleton, badge, table, chart, collapsible, sheet. [VERIFIED: ui/ directory listing]

### `src/lib/` Current State

`api-client.ts` + `utils.ts` (cn function). `formatters.ts` does not yet exist — create in Plan 01.

### `src/hooks/` Current State

Directory does not exist. Create in Plan 01.

---

## Phase 6 API — Complete Endpoint Reference

All endpoints require `Authorization: Bearer <token>` header (handled by `apiClient.ts` via HttpOnly cookie).

| Endpoint | Method | Query Params | Response Schema |
|----------|--------|-------------|----------------|
| `/api/v1/dashboards/sales` | GET | `from=YYYY-MM-DD&to=YYYY-MM-DD` | `SalesDashboardResponse` (see below) |
| `/api/v1/dashboards/salespeople` | GET | `from=...&to=...` | `SalespeopleDashboardResponse` |
| `/api/v1/dashboards/marketing` | GET | `from=...&to=...` | `MarketingDashboardResponse` |
| `/api/v1/insights/today` | GET | none | `InsightEnvelope` (date = yesterday in Bucharest TZ) |
| `/api/v1/insights` | GET | `date=YYYY-MM-DD` | `InsightEnvelope` or 404 |
| `/api/v1/insights/refresh` | POST | none | `RefreshResponse` or 429 with `Retry-After` header |
| `/api/v1/health/data` | GET | none | `HealthDataResponse` |

**Key field details for TypeScript types:**

`SalesDashboardResponse`:
- `funnel.visits` — nullable (KI-03: visits_count unreliable, may be null)
- `conversion_rates.*` — ALL Decimal serialized as `string | null`
- `kpi_cards.revenue`, `avg_deal_size` — `string | null`
- `stuck_offers` — `Array<{external_id: string; days_stuck: number; salesperson_name: string | null}>`

`SalespeopleDashboardResponse`:
- `salespeople[].avg_time_to_first_touch_minutes` — `number | null` (integer, not string — NOT a Decimal field)
- `salespeople[].revenue`, `win_rate`, `data_completeness_pct`, `avg_deal_size` — `string | null`
- `salespeople[].conversion_l_to_v` etc — `string | null`

`MarketingDashboardResponse`:
- `lead_volume_by_source[].series[].leads` — `number | null`
- `site_conversion_rate` — `string | null`
- `junk_by_source[].junk_pct` — `string | null`
- `ad_spend`, `cpl`, `cac`, `roas` — always `null` (MARK-03 explicit null placeholders)

`InsightEnvelope`:
- `payload.summary` — `string` (NOT `summary_ro`)
- `payload.problems[].estimated_loss_ron` — number (Decimal in schema but not field_serialized in DailyInsightResponse)
- `generation_failed: boolean` — `true` when status='failed'; render fallback banner

`HealthDataResponse`:
- `last_sync_at` — `string | null` (ISO datetime)
- `stale: boolean` — `true` when now - last_sync_at > 26h OR last_sync_at is null

**429 on `POST /insights/refresh`:**
Response has `Retry-After` header (seconds). Parse `parseInt(response.headers.get('Retry-After') ?? '0')`. Display countdown in "Reîmprospătează (N:SS)" button label. Disable button while rate-limited.

---

## Plan Structure Recommendation

### Dependency Graph

```
Plan 01: Infrastructure (KI-01 fix + packages + providers + formatters)
   │
   ├── Plan 02: Sales Dashboard (SALE-01..07) ──┐
   ├── Plan 03: Salespeople Dashboard (SALES-01..04) ─┤ (parallel Wave 2)
   ├── Plan 04: Marketing Dashboard (MARK-01..04) ────┤
   └── Plan 05: Insights Dashboard (INSI-01..06) ─────┘
                     │
              Plan 06: Mobile Responsiveness + Integration
                        (date picker bottom sheet, hamburger sidebar,
                         grid breakpoints verified, touch targets audit)
```

### Plan Descriptions

**Plan 01 — Infrastructure (Wave 1, BLOCKER for all)**
- Create `frontend/postcss.config.mjs` (KI-01 fix)
- Install recharts, react-day-picker (`pnpm add recharts react-day-picker`)
- Run `npx shadcn add card skeleton badge table chart collapsible sheet`
- Convert `(dashboard)/layout.tsx` to Client Component with QueryClientProvider (D-08)
- Create `src/lib/formatters.ts` (formatRON, formatDate, formatTimestamp, formatDuration, formatPct, formatWowDelta)
- Create `src/hooks/` directory
- Expand `messages/ro.json` and `messages/en.json` with all 6 new namespaces (skeleton strings)
- **Done when:** `pnpm dev` renders sidebar with colors, topbar with layout, login page styled correctly (D-03 visual audit)

**Plans 02, 03, 04, 05 — Dashboard Pages (Wave 2, parallel after Plan 01)**
Each plan: implement one dashboard page + its hooks + its component files + complete i18n strings + loading/error/empty states.

**Plan 06 — Mobile Responsiveness + Cross-Dashboard Integration (Wave 3)**
- Hamburger sidebar (sidebar.tsx + topbar.tsx modifications)
- Mobile layout fixes (`ml-0 md:ml-[240px]`, `left-0 md:left-[240px]`)
- DateRangePicker with bottom sheet on mobile
- Verify 360px minimum layout (D-17)
- DataFreshnessBanner wired to health endpoint (UI-06)
- Touch target audit (44px minimum — D-24)
- Grep for `@tremor/react` — must return zero results (SC#8)

Plans 02-05 can be parallelized because they share no state and write to distinct files.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Tremor charts | shadcn/ui chart (Recharts v3) | Phase 1 decision | `@tremor/react` is FORBIDDEN — zero imports allowed |
| Tailwind v3 postcss config (JS) | Tailwind v4 postcss config (ESM `.mjs`) | Tailwind v4 (2024) | Must use `.mjs` extension for Next.js 16 ESM compatibility |
| `react-day-picker` v8 API | `react-day-picker` v10 API | v10 (2024) | Breaking: import `DateRange` from `react-day-picker` directly; `mode="range"` unchanged |
| TanStack Query v4 `useQuery(key, fn)` | TanStack Query v5 `useQuery({queryKey, queryFn})` | v5 (2023) | Object-only API; no positional arguments |
| `useState` for QueryClient in providers | `getQueryClient()` singleton pattern | TanStack v5 SSR guide | Prevents client recreation on suspense |
| Next.js `<Image>` hydration issues | No images in Phase 7 | — | Not applicable |

**Deprecated/outdated:**
- `@tremor/react`: Explicitly banned per CLAUDE.md and Phase 1 decision. Zero imports.
- Tailwind v3 `tailwind.config.js` pattern: Project uses v4 `@theme` in CSS — no config file.
- TanStack Query v4 syntax: All hooks must use v5 object API (`{queryKey: [...], queryFn: ...}`).

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `DailyInsightResponse.summary` (not `summary_ro`) is the field displayed as headline | Code Examples — InsightEnvelope type, Pitfall 2 | If wrong: insight headline renders blank; requires TypeScript interface correction |
| A2 | `Problem.estimated_loss_ron` in payload JSON is a number (not string) — Decimal but not field_serialized in DailyInsightResponse | Phase 6 API section | If wrong: `formatRON(value)` receives already-a-number; parseFloat would still work but TypeScript type would need adjustment |
| A3 | All 4 Phase 6 API endpoints are live and returning data (Phase 6 is marked "Planned" in STATE.md, plans are ready but execution status unclear) | Phase 6 API Reference | If Phase 6 is not yet executed: dashboard data fetching will fail with 404; Plan 01 validation should test `/api/v1/health/data` |
| A4 | `pnpm` is used (not npm/yarn) — command `pnpm add recharts react-day-picker` | Installation commands | If wrong: use `npm install recharts react-day-picker` |
| A5 | `shadcn` CLI version resolves to `@latest` compatible with components.json new-york style | shadcn add commands | If wrong: CLI may prompt for initialization — run `npx shadcn@latest add` to ensure latest |
| A6 | `react-day-picker` v10 bundles date utilities — no separate `date-fns` install needed for basic use | Pattern 4 | If wrong: add `pnpm add date-fns` |
| A7 | Mobile hamburger sidebar uses `Sheet` component (Radix Dialog) — `@radix-ui/react-dialog` v1.1.15 already installed | Pattern 6 | Sheet component is confirmed as using react-dialog; npm install confirmed dialog is present |

---

## Open Questions (RESOLVED)

1. **Is Phase 6 executed (API endpoints live)?**
   - What we know: STATE.md says Phase 6 is "Planned (2026-05-28)" with "4 plans ready" but not "Executed". The plans are complete but execution state is unclear. The recent commits show Phase 6 plans created but no execution entry.
   - What's unclear: Whether `GET /api/v1/dashboards/sales?from=...&to=...` returns real data or 404.
   - Recommendation: Plan 01 should include a `curl http://localhost:8000/api/v1/health/data` verification step. If it fails, Phase 6 needs execution before Plan 02 can be tested end-to-end.

2. **`data-fns` peer dependency for `react-day-picker` v10?**
   - What we know: react-day-picker v10 peerDependencies list shows only `react` and `@types/react`.
   - What's unclear: v10 may have bundled its own date utilities or dropped date-fns dependency entirely vs v8 which required date-fns v2/v3.
   - Recommendation: Attempt install without date-fns; add only if TypeScript errors about date utilities appear.

3. **`@tanstack/react-query-devtools` — include in dev?**
   - What we know: CONTEXT.md lists this as Claude's discretion.
   - Recommendation: Include it — it's invaluable for debugging cache state during Phase 7 development. Conditional import with `process.env.NODE_ENV === 'development'`. Does not affect bundle in production.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | Frontend build | ✓ | 16.2.6 (via Next.js) | — |
| pnpm | Package manager | ✓ | (package.json pnpm config present) | npm |
| @tailwindcss/postcss | KI-01 CSS fix | ✓ | ^4 (in devDeps) | — |
| recharts | Charts | NOT installed | 3.8.1 on registry | Via `npx shadcn add chart` |
| react-day-picker | DateRangePicker | NOT installed | 10.0.1 on registry | — |
| @tanstack/react-query | Data fetching | ✓ | 5.100.11 installed | — |
| Backend API (Phase 6) | All dashboard hooks | Unclear | — | Plan 01 health check |

**Missing with no fallback:**
- `recharts` — must be installed (via shadcn add chart) before any chart component works
- `react-day-picker` — must be installed before DateRangePicker component is buildable
- `postcss.config.mjs` — must be created (file exists in package, config absent) before CSS renders

**Missing with fallback:**
- Phase 6 API data — dashboard pages can be built with mock data during development; connect to real API when Phase 6 is confirmed executed

---

## Validation Architecture

nyquist_validation: true (per config.json).

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Playwright (e2e, Phase 9) / manual visual inspection (Phase 7) |
| Config file | none — Phase 9 adds `playwright.config.ts` |
| Quick run command | `cd frontend && pnpm dev` + manual browser check |
| Full suite command | `cd frontend && pnpm typecheck && pnpm lint` |

Phase 7 has no automated test suite — Playwright e2e is Phase 9. The validation strategy for Phase 7 is:

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UI-01 | Romanian strings display in sidebar/topbar/pages | manual | locale toggle in browser | ❌ (manual) |
| UI-02 | Currency format `1.234,56 RON` | unit | `pnpm typecheck` + `formatRON` unit test | ❌ Wave 0 |
| UI-03 | Date format `DD.MM.YYYY` | unit | `formatDate` unit test | ❌ Wave 0 |
| UI-04 | Timestamps in Bucharest TZ | unit | `formatTimestamp` unit test | ❌ Wave 0 |
| UI-05 | Loading/empty/error states on charts | manual | Throttle network in DevTools | ❌ (manual) |
| UI-06 | Freshness banner appears | manual | Mock stale=true from backend | ❌ (manual) |
| UI-07 | Responsive at 768px+ | manual | Chrome DevTools responsive mode | ❌ (manual) |
| UI-08 | Zero @tremor/react imports | automated | `grep -r "@tremor" frontend/src` = 0 results | SC#8 grep check |
| SALE-01..07 | Sales page renders with data | manual | Browser + DevTools network | ❌ (manual) |
| INSI-03 | 429 shows countdown | manual | Trigger refresh twice within 1h | ❌ (manual) |
| KI-01 fix | CSS renders correctly | visual | `pnpm dev` + visual inspect | ❌ Plan 01 gate |

### Wave 0 Gaps (unit tests for formatters)

- [ ] `frontend/src/lib/__tests__/formatters.test.ts` — unit tests for formatRON, formatDate, formatDuration, formatWowDelta

### Sampling Rate

- **Per plan commit:** `pnpm typecheck` (TypeScript strict mode catches type errors immediately)
- **Per wave merge:** `pnpm typecheck && pnpm lint`
- **Phase gate:** Manual browser verification at 360px, 768px, 1280px + SC#1-SC#8 checklist from ROADMAP.md + `grep -r "@tremor" frontend/src` returns zero matches

---

## Security Domain

Phase 7 is a read-only frontend. No auth logic, no secrets, no server-side data handling.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | partially | JWT stored in HttpOnly cookie — handled by Phase 1 auth + `apiClient.ts` 401 interceptor; no new auth logic in Phase 7 |
| V3 Session Management | no | Stateless; session managed by existing cookie |
| V4 Access Control | no | All access control in backend; frontend is read-only display |
| V5 Input Validation | yes | `?from=` and `?to=` URL params: validate as `YYYY-MM-DD` format before passing to API; invalid dates silently fall back to defaults |
| V6 Cryptography | no | No new crypto in Phase 7 |

### Known Threat Patterns for Next.js App Router

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| XSS via unsanitized API data in dangerouslySetInnerHTML | Tampering | Never use `dangerouslySetInnerHTML`; React auto-escapes JSX expressions |
| CSRF on POST /insights/refresh | Spoofing | `credentials: "include"` + SameSite=Lax cookie on backend JWT (Phase 1) |
| Open redirect via `?from=` param injection | Tampering | Parse dates with `new Date(param)` + validity check; invalid dates fall back to default range |
| Leaking API base URL in client bundle | Info Disclosure | `apiClient.ts` uses relative paths (`/api/v1/...`) — not an absolute URL |

---

## Project Constraints (from CLAUDE.md)

- Async-first: all I/O through hooks (TanStack Query) — no direct fetch in render
- Type hints everywhere: TypeScript strict mode (`tsconfig` already strict)
- No hardcoded strings in JSX: always `useTranslations(ns)`
- No `@tremor/react` imports: explicitly banned
- No calling Claude API from frontend: insights are fetched from pre-computed DB (Phase 5/6)
- Conventional Commits: `feat:`, `fix:`, `chore:`, etc.
- structlog: N/A for frontend (backend concern)
- Formatter: Prettier (frontend) — already in eslint-config-next
- Component pattern: functional components with hooks only (no class components)
- CSS: Tailwind utility classes only; no inline style objects except where Recharts requires `fill={value}`

---

## Sources

### Primary (HIGH confidence)

- Codebase: `frontend/package.json` — all installed dependencies and versions [VERIFIED]
- Codebase: `frontend/src/app/(dashboard)/layout.tsx` — current layout state [VERIFIED]
- Codebase: `frontend/src/components/sidebar.tsx` — current sidebar structure [VERIFIED]
- Codebase: `frontend/src/components/topbar.tsx` — current topbar structure [VERIFIED]
- Codebase: `frontend/src/lib/api-client.ts` — 401 refresh interceptor [VERIFIED]
- Codebase: `frontend/src/app/globals.css` — CSS variable definitions [VERIFIED]
- Codebase: `frontend/components.json` — shadcn config (new-york / zinc / cssVariables:true) [VERIFIED]
- Codebase: `frontend/messages/ro.json` — existing i18n keys [VERIFIED]
- Codebase: `frontend/src/components/ui/` — only button, input, label, separator present [VERIFIED]
- Codebase: `backend/app/schemas/dashboards/sales.py` — SalesDashboardResponse exact fields [VERIFIED]
- Codebase: `backend/app/schemas/dashboards/salespeople.py` — SalespeopleDashboardResponse [VERIFIED]
- Codebase: `backend/app/schemas/dashboards/marketing.py` — MarketingDashboardResponse [VERIFIED]
- Codebase: `backend/app/schemas/insights/daily_insight_schema.py` — field names (summary not summary_ro) [VERIFIED]
- Codebase: `backend/app/schemas/health.py` — HealthDataResponse [VERIFIED]
- Codebase: `backend/app/api/v1/insights.py` — InsightEnvelope, 429 behavior, Retry-After [VERIFIED]
- Codebase: `backend/app/api/v1/dashboards.py` — endpoint routes confirmed [VERIFIED]
- npm registry: `recharts@3.8.1` — peerDeps React 19 compatible [VERIFIED: npm view]
- npm registry: `react-day-picker@10.0.1` — peerDeps react>=16.8.0 [VERIFIED: npm view]
- npm registry: `@tanstack/react-query@5.100.14` — peerDeps react^18||^19 [VERIFIED: npm view]

### Secondary (MEDIUM confidence)

- [Tailwind CSS v4 + Next.js guide](https://tailwindcss.com/docs/guides/nextjs) — PostCSS config pattern [CITED]
- [TanStack Query v5 Advanced SSR guide](https://tanstack.com/query/v5/docs/framework/react/guides/advanced-ssr) — getQueryClient pattern [CITED]
- [react-day-picker range mode docs](https://daypicker.dev/) — DateRange type and mode="range" API [CITED]
- [shadcn chart docs](https://ui.shadcn.com/docs/components/chart) — ChartContainer, ChartTooltip, import paths [CITED]

### Tertiary (LOW confidence)

- WebSearch results on Next.js mobile sidebar Sheet pattern — confirmed approach but not verified in single authoritative source [ASSUMED — CSS `hidden md:flex` pattern is standard Tailwind responsive practice]

---

## Metadata

**Confidence breakdown:**
- KI-01 PostCSS fix: HIGH — verified against official Tailwind v4+Next.js docs and package.json state
- Standard stack + versions: HIGH — all verified via npm view and package.json codebase
- API shapes: HIGH — verified directly against actual backend schema files
- Architecture patterns: HIGH — derived from existing codebase + official framework docs
- Mobile responsiveness patterns: MEDIUM — CSS patterns are standard; Sheet component behavior confirmed by Radix Dialog presence in package.json

**Research date:** 2026-05-28
**Valid until:** 2026-06-28 (stable stack — no fast-moving Next.js/React/Tailwind releases expected in 30 days)
