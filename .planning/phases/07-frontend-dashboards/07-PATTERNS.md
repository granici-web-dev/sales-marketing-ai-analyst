# Phase 7: Frontend Dashboards - Pattern Map

**Mapped:** 2026-05-28
**Files analyzed:** 22 new/modified files
**Analogs found:** 18 / 22 (4 are net-new with no codebase analog — use RESEARCH.md patterns)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `frontend/postcss.config.mjs` | config | — | `frontend/next.config.ts` | config-match |
| `frontend/src/app/(dashboard)/layout.tsx` | provider/layout | request-response | `frontend/src/app/layout.tsx` | role-match (Server→Client upgrade) |
| `frontend/src/components/sidebar.tsx` | component | event-driven | self (existing, modify) | exact — MODIFY |
| `frontend/src/components/topbar.tsx` | component | event-driven | self (existing, modify) | exact — MODIFY |
| `frontend/src/lib/formatters.ts` | utility | transform | `frontend/src/lib/utils.ts` | role-match |
| `frontend/src/hooks/useSalesDashboard.ts` | hook | request-response | no analog — see RESEARCH.md | no-analog |
| `frontend/src/hooks/useSalespeopleDashboard.ts` | hook | request-response | `useSalesDashboard.ts` (create first) | role-match |
| `frontend/src/hooks/useMarketingDashboard.ts` | hook | request-response | `useSalesDashboard.ts` (create first) | role-match |
| `frontend/src/hooks/useInsights.ts` | hook | request-response | `useSalesDashboard.ts` (create first) | role-match |
| `frontend/src/hooks/useHealthData.ts` | hook | request-response | `useSalesDashboard.ts` (create first) | role-match |
| `frontend/src/components/data-freshness-banner.tsx` | component | request-response | `frontend/src/app/(auth)/login/page.tsx` (inline error pattern) | partial-match |
| `frontend/src/components/date-range-picker.tsx` | component | event-driven | no analog — see RESEARCH.md | no-analog |
| `frontend/src/components/dashboards/sales/kpi-cards.tsx` | component | transform | `frontend/src/components/ui/button.tsx` (shadcn pattern) | partial-match |
| `frontend/src/components/dashboards/sales/funnel-chart.tsx` | component | transform | no analog — see RESEARCH.md | no-analog |
| `frontend/src/components/dashboards/sales/source-breakdown.tsx` | component | transform | `funnel-chart.tsx` (create first) | role-match |
| `frontend/src/components/dashboards/sales/revenue-trend.tsx` | component | transform | `funnel-chart.tsx` (create first) | role-match |
| `frontend/src/components/dashboards/sales/stuck-offers.tsx` | component | transform | `kpi-cards.tsx` (create first) | role-match |
| `frontend/src/components/dashboards/salespeople/leaderboard-table.tsx` | component | transform | `frontend/src/components/ui/separator.tsx` (shadcn Radix pattern) | partial-match |
| `frontend/src/components/dashboards/marketing/source-volume-chart.tsx` | component | transform | `revenue-trend.tsx` (create first) | role-match |
| `frontend/src/components/dashboards/marketing/junk-pct-table.tsx` | component | transform | `leaderboard-table.tsx` (create first) | role-match |
| `frontend/src/components/dashboards/marketing/ad-spend-placeholder.tsx` | component | — | stub pages (existing) | exact |
| `frontend/src/components/dashboards/insights/insight-summary.tsx` | component | transform | stub pages (existing) | partial-match |
| `frontend/src/components/dashboards/insights/problem-card.tsx` | component | event-driven | no analog — see RESEARCH.md | no-analog |
| `frontend/src/components/dashboards/insights/generation-failed-banner.tsx` | component | — | `frontend/src/app/(auth)/login/page.tsx` (error banner) | partial-match |
| `frontend/src/app/(dashboard)/sales/page.tsx` | page/route | request-response | self (existing stub, replace) | exact — REPLACE |
| `frontend/src/app/(dashboard)/salespeople/page.tsx` | page/route | request-response | self (existing stub, replace) | exact — REPLACE |
| `frontend/src/app/(dashboard)/marketing/page.tsx` | page/route | request-response | self (existing stub, replace) | exact — REPLACE |
| `frontend/src/app/(dashboard)/insights/page.tsx` | page/route | request-response | self (existing stub, replace) | exact — REPLACE |
| `frontend/messages/ro.json` | config/i18n | — | self (existing, expand) | exact — EXPAND |
| `frontend/messages/en.json` | config/i18n | — | self (existing, expand) | exact — EXPAND |

---

## Pattern Assignments

### `frontend/postcss.config.mjs` (config)

**Analog:** `frontend/next.config.ts` — same ESM export default pattern, same `.mjs`/`.ts` file extension convention

**Current state of `next.config.ts`** (lines 1–10):
```typescript
import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

const config: NextConfig = {
  turbopack: {},
};

export default withNextIntl(config);
```

**New file pattern** — mirror the ESM `export default` shape:
```javascript
// frontend/postcss.config.mjs
const config = {
  plugins: {
    "@tailwindcss/postcss": {},
  },
};

export default config;
```

**Why this works:** `@tailwindcss/postcss` is already in `package.json` devDependencies at `^4`. Only the config file is missing. Next.js 16 Turbopack delegates CSS to PostCSS when `postcss.config.mjs` is present.

---

### `frontend/src/app/(dashboard)/layout.tsx` (provider/layout — MODIFY)

**Analog:** `frontend/src/app/layout.tsx` — the root layout is the established pattern for wrapping children in providers

**Current root layout** (lines 1–26 of `frontend/src/app/layout.tsx`):
```typescript
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { NextIntlClientProvider } from "next-intl";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ro">
      <body className={inter.className}>
        <NextIntlClientProvider>{children}</NextIntlClientProvider>
      </body>
    </html>
  );
}
```

**Current dashboard layout** (lines 1–18 of `frontend/src/app/(dashboard)/layout.tsx`):
```typescript
import Sidebar from "@/components/sidebar";
import Topbar from "@/components/topbar";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
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

**What must change:**
1. Add `"use client"` at top (currently a Server Component — no directive present)
2. Import and wire `QueryClientProvider` with module-level singleton pattern (not `useState`)
3. Change `ml-[240px]` → `ml-0 md:ml-[240px]` (mobile fix, Pitfall 7)
4. Change `p-8` → `p-4 md:p-8` (mobile padding)
5. Add `<DataFreshnessBanner />` inside `<main>` before `{children}`

**Modified layout pattern** (from RESEARCH.md Pattern 2 — verified against existing code):
```typescript
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
  if (isServer) return makeQueryClient();
  if (!browserQueryClient) browserQueryClient = makeQueryClient();
  return browserQueryClient;
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const queryClient = getQueryClient();
  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen">
        <Sidebar />
        <Topbar />
        <main className="ml-0 md:ml-[240px] mt-14 p-4 md:p-8 bg-white min-h-[calc(100vh-56px)]">
          <DataFreshnessBanner />
          {children}
        </main>
      </div>
    </QueryClientProvider>
  );
}
```

---

### `frontend/src/components/sidebar.tsx` (component — MODIFY)

**Analog:** self — read current file before modifying

**Current state** (full file, 85 lines):

Imports (lines 1–16):
```typescript
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import {
  LayoutDashboard, TrendingUp, Briefcase, Users, Lightbulb,
  MessageSquare, Plug, Settings, type LucideIcon,
} from "lucide-react";
```

`<aside>` element (line 47):
```typescript
<aside className="fixed left-0 top-0 h-screen w-[240px] bg-[hsl(240_5%_96%)] border-r border-[hsl(240_6%_90%)] flex flex-col">
```

**What must change:**
1. `<aside className="fixed left-0 top-0 h-screen w-[240px] ...flex flex-col">` → add `hidden md:flex` so sidebar is hidden on mobile
2. Add `Menu` icon import from `lucide-react` (for hamburger state — actually hamburger lives in topbar; sidebar only needs the `hidden md:flex` change)
3. The Sheet mobile overlay renders the same `navItems` array — export `navItems` so `topbar.tsx` can import it, OR duplicate the nav JSX inside the Sheet in `topbar.tsx`

**Active link pattern** (lines 62–76) — copy this exact CSS logic into the mobile Sheet nav:
```typescript
className={[
  "flex items-center gap-2 rounded-md py-[12px] px-3 text-sm transition-colors",
  active
    ? "bg-[hsl(221_83%_95%)] text-[#2563EB] font-semibold border-l-[3px] border-[#2563EB]"
    : "text-[#71717A] hover:bg-[hsl(240_5%_92%)] hover:text-[#09090B]",
].join(" ")}
```

---

### `frontend/src/components/topbar.tsx` (component — MODIFY)

**Analog:** self — read current file before modifying

**Current state** (full file, 52 lines):

Header element (line 38):
```typescript
<header className="fixed top-0 left-[240px] right-0 h-14 bg-[hsl(240_5%_96%)] border-b border-[hsl(240_6%_90%)] flex items-center justify-between px-6 z-10">
```

**What must change:**
1. `left-[240px]` → `left-0 md:left-[240px]` (Pitfall 7 fix — mobile dead zone)
2. Add hamburger button before `<span>` page title — visible only on mobile (`md:hidden`):
```typescript
<button
  className="md:hidden mr-3 min-h-[44px] min-w-[44px] flex items-center justify-center"
  aria-label={t("common.openMenu")}
  onClick={() => setMobileMenuOpen(true)}
>
  <Menu size={24} />
</button>
```
3. Add `useState` for `mobileMenuOpen`
4. Add `Sheet` import and mobile nav overlay after `</header>`
5. Import `Menu` and `X` from `lucide-react`
6. The locale toggle button already exists — keep it, it's the right pattern

**Locale toggle pattern to preserve** (lines 41–49):
```typescript
<Button
  variant="ghost"
  size="sm"
  onClick={handleLocaleToggle}
  className="text-[#71717A] hover:text-[#09090B]"
>
  {tLocale(locale)}
</Button>
```

---

### `frontend/src/lib/formatters.ts` (utility — NEW)

**Analog:** `frontend/src/lib/utils.ts` — same directory, same export pattern (named exports, no default)

**Current `utils.ts`** (lines 1–6):
```typescript
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

**Pattern to follow:** Single-responsibility named export functions, no classes, `from __future__`-equivalent is `"use client"` NOT needed (pure compute, no hooks). Copy the exact function signatures from RESEARCH.md Code Examples section — they are verified against the backend schema.

**Key functions to implement** (from RESEARCH.md Code Examples):
```typescript
// frontend/src/lib/formatters.ts
// NO "use client" — pure utilities, no hooks

export function formatRON(value: string | number | null | undefined, compact = false): string
export function formatPct(value: string | number | null | undefined): string
export function formatDate(dateStr: string | Date | null | undefined): string
export function formatTimestamp(dateStr: string | Date | null | undefined): string
export function formatDuration(minutes: number | null | undefined): string
export function formatWowDelta(delta: string | null | undefined): { label: string; positive: boolean | null }
export function getDefaultDateRange(): { from: string; to: string }
```

All `formatRON`/`formatPct` use `Intl.NumberFormat('ro-RO', ...)`. All `formatDate`/`formatTimestamp` use `Intl.DateTimeFormat('ro-RO', { timeZone: 'Europe/Bucharest', ... })`. Never `.toFixed()`.

---

### `frontend/src/hooks/useSalesDashboard.ts` (hook — NEW, no codebase analog)

**No existing hook analog** — this is the first TanStack Query hook in the codebase. Use RESEARCH.md Pattern 3 exactly.

**Required imports pattern** (modeled on `api-client.ts` usage in login page):
```typescript
"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
```

**TanStack Query v5 hook shape** (RESEARCH.md Pattern 3):
```typescript
export function useSalesDashboard(from: string, to: string) {
  return useQuery<SalesDashboardData>({
    queryKey: ["sales", from, to],   // array — invalidates when from/to change
    queryFn: async () => {
      const res = await apiClient.get(`/api/v1/dashboards/sales?from=${from}&to=${to}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    enabled: Boolean(from && to),    // don't fetch if params missing
  });
}
```

**Critical:** `staleTime` and `refetchOnWindowFocus` are set at the QueryClient level in layout.tsx — do NOT set them per-query unless overriding.

**TypeScript interface** — all Decimal backend fields come as `string | null` (DATA-04). Non-Decimal integers come as `number | null`. Key field types:
- `funnel.*`: `number | null`
- `conversion_rates.*`: `string | null` (Decimal serialized)
- `kpi_cards.revenue`, `avg_deal_size`: `string | null`
- `kpi_cards.leads_total`, `visits_count`, etc.: `number | null`

---

### `frontend/src/hooks/useSalespeopleDashboard.ts` / `useMarketingDashboard.ts` / `useInsights.ts` / `useHealthData.ts` (hooks — NEW)

**Analog:** `useSalesDashboard.ts` (create that first)

**Pattern:** identical hook shape, different `queryKey`, different endpoint, different TypeScript interface. Special cases:

`useInsights.ts` — two query functions needed:
```typescript
// Today's insights
export function useInsightsToday() {
  return useQuery<InsightEnvelope>({
    queryKey: ["insights", "today"],
    queryFn: async () => {
      const res = await apiClient.get("/api/v1/insights/today");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
  });
}

// Historical insights by date
export function useInsightsByDate(date: string | null) {
  return useQuery<InsightEnvelope>({
    queryKey: ["insights", date],
    queryFn: async () => {
      const res = await apiClient.get(`/api/v1/insights?date=${date}`);
      if (res.status === 404) return null;  // 404 = no insight for that date
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    enabled: Boolean(date),
  });
}
```

`useHealthData.ts` — override `staleTime` to 60 seconds (freshness banner needs more frequent check):
```typescript
export function useHealthData() {
  return useQuery<HealthDataResponse>({
    queryKey: ["health", "data"],
    queryFn: async () => {
      const res = await apiClient.get("/api/v1/health/data");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    staleTime: 60 * 1000,  // override layout default — freshness needs 1min check
  });
}
```

---

### `frontend/src/app/(dashboard)/sales/page.tsx` (page — REPLACE stub)

**Analog:** existing stub at same path (lines 1–20 of current file):
```typescript
"use client";

import { useTranslations } from "next-intl";
import { Briefcase } from "lucide-react";

export default function SalesPage() {
  const t = useTranslations("placeholder");

  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-56px-64px)]">
      <Briefcase size={48} className="text-[#71717A] mb-4" aria-hidden="true" />
      <h1 className="text-xl font-semibold mb-2 text-[hsl(240_10%_4%)]">
        {t("comingSoon")}
      </h1>
      <p className="text-sm text-[#71717A] max-w-sm text-center">
        {t("sales")}
      </p>
    </div>
  );
}
```

**Replace with pattern** (preserve `"use client"` + `useTranslations` pattern, replace body):
```typescript
"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useSalesDashboard } from "@/hooks/useSalesDashboard";
import { getDefaultDateRange } from "@/lib/formatters";
import { DateRangePicker } from "@/components/date-range-picker";
import { KpiCards } from "@/components/dashboards/sales/kpi-cards";
import { FunnelChart } from "@/components/dashboards/sales/funnel-chart";
import { SourceBreakdown } from "@/components/dashboards/sales/source-breakdown";
import { RevenueTrend } from "@/components/dashboards/sales/revenue-trend";
import { StuckOffers } from "@/components/dashboards/sales/stuck-offers";
import { Skeleton } from "@/components/ui/skeleton";

function SalesPageContent() {
  const t = useTranslations("sales");
  const searchParams = useSearchParams();
  const defaults = getDefaultDateRange();
  const from = searchParams.get("from") ?? defaults.from;
  const to = searchParams.get("to") ?? defaults.to;

  const { data, isLoading, isError, refetch } = useSalesDashboard(from, to);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-xl font-semibold text-[hsl(240_10%_4%)]">{t("title")}</h1>
        <DateRangePicker />
      </div>
      {/* sections follow with isLoading/isError/data conditionals */}
    </div>
  );
}

export default function SalesPage() {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <SalesPageContent />
    </Suspense>
  );
}
```

**All 4 dashboard pages follow the same outer pattern:** `Suspense` wrapper + inner Content component that uses `useSearchParams`.

---

### `frontend/src/app/(dashboard)/salespeople/page.tsx` / `marketing/page.tsx` / `insights/page.tsx` (pages — REPLACE stubs)

**Analog:** `sales/page.tsx` pattern above. All stubs are structurally identical (confirmed by reading all 4).

Differences:
- `salespeople/page.tsx`: uses `useSalespeopleDashboard`, renders `<LeaderboardTable>`
- `marketing/page.tsx`: uses `useMarketingDashboard`, renders `<SourceVolumeChart>`, `<JunkPctTable>`, `<AdSpendPlaceholder>`
- `insights/page.tsx`: uses `useInsightsToday`, no date range picker (uses historical date picker instead), renders `<InsightSummary>`, `<ProblemCard>` list, Reîmprospătează button

---

### `frontend/src/components/dashboards/sales/kpi-cards.tsx` (component — NEW)

**Analog:** `frontend/src/components/ui/button.tsx` — the shadcn component pattern (Radix-based, `cn()` utility, forwardRef where needed)

**shadcn Card pattern** (to be installed via `npx shadcn add card`):
```typescript
// After install, import from:
import { Card, CardHeader, CardContent } from "@/components/ui/card";
```

**KPI card component pattern:**
```typescript
"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatRON, formatWowDelta } from "@/lib/formatters";
import { useTranslations } from "next-intl";

interface KpiCardProps {
  label: string;
  value: string | number | null;
  delta?: string | null;
  format?: "ron" | "count";
  highlight?: boolean;  // red background for avg_time_to_first_touch > 240
}

export function KpiCard({ label, value, delta, format, highlight }: KpiCardProps) {
  const wow = formatWowDelta(delta?.toString());
  return (
    <Card className={highlight ? "bg-red-50 border-red-200" : ""}>
      <CardContent className="pt-4">
        <p className="text-xs text-[#71717A] mb-1">{label}</p>
        <p className="text-2xl font-bold text-[hsl(240_10%_4%)]">
          {format === "ron" ? formatRON(value) : value ?? "—"}
        </p>
        {wow.label && (
          <span className={`text-xs font-medium ${wow.positive ? "text-green-600" : wow.positive === false ? "text-red-600" : "text-[#71717A]"}`}>
            {wow.label}
          </span>
        )}
      </CardContent>
    </Card>
  );
}
```

**KPI card grid responsive pattern** (D-19):
```typescript
<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
  {/* KpiCard instances */}
</div>
```

---

### `frontend/src/components/dashboards/sales/funnel-chart.tsx` (component — NEW, no direct analog)

**No codebase analog** — first Recharts component. Use RESEARCH.md Pattern 5.

**Import pattern** (CRITICAL — always via shadcn chart, never direct recharts):
```typescript
"use client";

import { BarChart, Bar, XAxis, YAxis, Cell } from "recharts";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";  // NOT from "recharts"
import { useTranslations } from "next-intl";
```

**CSS variable pattern for colors** (from `globals.css`):
```typescript
const chartConfig = {
  count: {
    label: "Count",
    color: "var(--color-accent)",          // hsl(221 83% 53%) — blue
  },
} satisfies ChartConfig;
```

**ResponsiveContainer is handled by ChartContainer** — do not add `<ResponsiveContainer>` manually when using `ChartContainer`.

**Mobile funnel layout** (D-20) — use CSS to switch orientation:
```typescript
// Horizontal on tablet+, vertical on mobile
<div className="hidden sm:block">
  {/* horizontal BarChart */}
</div>
<div className="block sm:hidden">
  {/* vertical stacked layout */}
</div>
```

---

### `frontend/src/components/dashboards/salespeople/leaderboard-table.tsx` (component — NEW)

**Analog:** `frontend/src/components/ui/separator.tsx` — same Radix UI + shadcn pattern, same `cn()` usage

**shadcn Table pattern** (to be installed via `npx shadcn add table`):
```typescript
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
```

**Mobile scroll pattern** (D-21):
```typescript
<div className="overflow-x-auto">
  <Table className="min-w-[700px]">  {/* force minimum width so table scrolls rather than wraps */}
    <TableHeader>
      <TableRow>
        <TableHead className="sticky left-0 bg-white z-10">{/* name — sticky */}</TableHead>
        {/* other columns */}
      </TableRow>
    </TableHeader>
  </Table>
</div>
```

**Red cell for avg_time_to_first_touch** (D-07, SALES-02):
```typescript
<TableCell className={
  row.avg_time_to_first_touch_minutes != null && row.avg_time_to_first_touch_minutes > 240
    ? "bg-red-50 text-red-700 font-medium"
    : ""
}>
  {formatDuration(row.avg_time_to_first_touch_minutes)}
</TableCell>
```

---

### `frontend/src/components/dashboards/marketing/ad-spend-placeholder.tsx` (component — NEW)

**Analog:** existing stub pages (all 4 identical stubs) — the "coming soon" empty state pattern is already in the codebase

**Pattern to copy** (from `frontend/src/app/(dashboard)/marketing/page.tsx` lines 9–18):
```typescript
<div className="flex flex-col items-center justify-center min-h-[200px] rounded-lg border border-[hsl(240_6%_90%)] bg-[hsl(240_5%_96%)]">
  <TrendingUp size={32} className="text-[#71717A] mb-3" aria-hidden="true" />
  <p className="text-sm font-medium text-[hsl(240_10%_4%)]">{t("marketing.adSpendTitle")}</p>
  <p className="text-xs text-[#71717A] mt-1 text-center max-w-xs">{t("marketing.adSpendComingSoon")}</p>
</div>
```

---

### `frontend/src/components/data-freshness-banner.tsx` (component — NEW)

**Analog:** `frontend/src/app/(auth)/login/page.tsx` — the inline error banner pattern (lines 131–138):
```typescript
{authError && (
  <div
    className="mt-4 border-l-4 border-[#DC2626] bg-[#FEF2F2] px-4 py-3 text-[#DC2626] text-xs"
    role="alert"
  >
    {authError}
  </div>
)}
```

**Adapted for freshness banner** (uses `useHealthData` hook, amber/yellow for warning vs. red for error):
```typescript
"use client";

import { useHealthData } from "@/hooks/useHealthData";
import { useTranslations } from "next-intl";
import { AlertTriangle } from "lucide-react";
import { formatTimestamp } from "@/lib/formatters";

export default function DataFreshnessBanner() {
  const { data } = useHealthData();
  const t = useTranslations("common");

  if (!data?.stale) return null;

  return (
    <div
      className="mb-4 flex items-center gap-2 border-l-4 border-amber-500 bg-amber-50 px-4 py-3 text-amber-800 text-xs rounded-r-md"
      role="alert"
    >
      <AlertTriangle size={14} aria-hidden="true" />
      <span>{t("dataStale", { lastSync: data.last_sync_at ? formatTimestamp(data.last_sync_at) : t("never") })}</span>
    </div>
  );
}
```

---

### `frontend/src/components/dashboards/insights/problem-card.tsx` (component — NEW, no direct analog)

**Analog:** No collapse/expand pattern exists. Use shadcn Collapsible (install via `npx shadcn add collapsible`).

**Collapsed-by-default pattern** (D-15):
```typescript
"use client";

import { useState } from "react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Card, CardHeader, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ChevronDown, ChevronUp } from "lucide-react";
import { formatRON } from "@/lib/formatters";
import { useTranslations } from "next-intl";

export function ProblemCard({ problem }: { problem: Problem }) {
  const [open, setOpen] = useState(false);  // collapsed by default
  const t = useTranslations("insights");

  const severityColors = {
    high: "bg-red-100 text-red-800 border-red-200",
    medium: "bg-orange-100 text-orange-800 border-orange-200",
    low: "bg-yellow-100 text-yellow-800 border-yellow-200",
  };

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <Card>
        <CardHeader className="pb-2">
          <CollapsibleTrigger className="flex items-center justify-between w-full min-h-[44px]">
            <div className="flex items-center gap-2 flex-wrap">
              <Badge className={severityColors[problem.severity]}>
                {t(`severity.${problem.severity}`)}
              </Badge>
              <span className="font-medium text-sm text-[hsl(240_10%_4%)]">{problem.title}</span>
              <span className="text-xs text-[#71717A]">{formatRON(problem.estimated_loss_ron)}</span>
            </div>
            {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </CollapsibleTrigger>
        </CardHeader>
        <CollapsibleContent>
          <CardContent className="pt-0">
            {/* description + action list */}
          </CardContent>
        </CollapsibleContent>
      </Card>
    </Collapsible>
  );
}
```

---

### `frontend/src/components/dashboards/insights/generation-failed-banner.tsx` (component — NEW)

**Analog:** `frontend/src/app/(auth)/login/page.tsx` error banner (lines 131–138) — same red border-left pattern.

```typescript
// Pattern: identical shape to login error banner, different text + icon
<div
  className="mb-4 border-l-4 border-[#DC2626] bg-[#FEF2F2] px-4 py-3 text-[#DC2626] text-sm rounded-r-md"
  role="alert"
>
  {t("insights.generationFailed")}
  {/* "Generarea automată a eșuat. Se afișează problemele detectate automat." */}
</div>
```

---

### `frontend/messages/ro.json` and `frontend/messages/en.json` (i18n — EXPAND)

**Analog:** self — current 4-key structure must be preserved exactly, new keys appended

**Current structure** (lines 1–41 of `ro.json`):
```json
{
  "auth": { ... },
  "nav": { ... },
  "placeholder": { ... },
  "locale": { ... }
}
```

**Pattern:** append 6 new top-level namespaces. Never restructure existing keys. Use `useTranslations("namespace")` — namespace maps to top-level JSON key. Must add same keys to both `ro.json` (Romanian primary, complete) and `en.json` (English mirror).

**New namespaces to add:**
```json
{
  "sales": { "title": "Vânzări", "funnel": {...}, "kpi": {...}, "sources": {...}, "stuckOffers": {...} },
  "salespeople": { "title": "Agenți de vânzări", "table": {...} },
  "marketing": { "title": "Marketing", "adSpendTitle": "...", "adSpendComingSoon": "..." },
  "insights": { "title": "Analize AI", "refresh": "...", "severity": { "high": "Critică", "medium": "Ridicată", "low": "Medie" }, "generationFailed": "Generarea automată a eșuat..." },
  "common": { "loading": "Se încarcă...", "error": "A apărut o eroare. Încearcă din nou.", "retry": "Reîncearcă", "noData": "Nu există date disponibile pentru perioada selectată.", "openMenu": "Deschide meniu", "dataStale": "Date vechi...", "never": "niciodată" },
  "errors": { "networkError": "Eroare de rețea.", "serverError": "Eroare server." }
}
```

---

## Shared Patterns

### "use client" Directive
**Source:** `frontend/src/components/sidebar.tsx` line 1, `frontend/src/components/topbar.tsx` line 1, all 4 stub pages line 1
**Apply to:** ALL new components in `components/dashboards/`, ALL new hooks, modified layout.tsx
```typescript
"use client";
```
Rule: any file using `useQuery`, `useTranslations`, `useSearchParams`, `useState`, `useRouter`, or any hook must be `"use client"`. Pure utility files (`formatters.ts`) do NOT need `"use client"`.

### useTranslations Pattern
**Source:** `frontend/src/components/sidebar.tsx` lines 5, 37 and `frontend/src/components/topbar.tsx` lines 4, 24–25
```typescript
import { useTranslations } from "next-intl";
// ...
const t = useTranslations("nav");  // namespace = top-level key in ro.json
// usage:
t("marketing")  // returns "Marketing" or "Marketing"
```
**Apply to:** ALL new components and pages. Never hardcode Romanian strings in JSX.

### cn() Utility for Conditional Classes
**Source:** `frontend/src/lib/utils.ts` + `frontend/src/components/ui/button.tsx` line 5
```typescript
import { cn } from "@/lib/utils";
// usage:
className={cn("base-classes", condition && "conditional-class", otherProp)}
```
**Apply to:** All components that have conditional className logic.

### apiClient Usage Pattern
**Source:** `frontend/src/lib/api-client.ts` lines 42–60 — the exported `apiClient` object
```typescript
import { apiClient } from "@/lib/api-client";
// usage in queryFn:
const res = await apiClient.get("/api/v1/dashboards/sales?from=...&to=...");
if (!res.ok) throw new Error(`HTTP ${res.status}`);
return res.json();
```
**Apply to:** All TanStack Query `queryFn` implementations in hooks. Never call `fetch()` directly in hooks — always go through `apiClient`.

### Loading State Pattern (Skeleton)
**Source:** Decision D-12; `Skeleton` component (install via `npx shadcn add skeleton`)
```typescript
import { Skeleton } from "@/components/ui/skeleton";

if (isLoading) {
  return <Skeleton className="h-[200px] w-full rounded-lg" />;
}
```
**Apply to:** Every chart, card grid, and table section. One skeleton per visual section, matching the final content height.

### Error State Pattern
**Source:** `frontend/src/app/(auth)/login/page.tsx` lines 131–138 (border-left alert pattern)
```typescript
if (isError) {
  return (
    <div className="flex flex-col items-center gap-2 py-8">
      <p className="text-sm text-[#DC2626]">{t("common.error")}</p>
      <Button variant="outline" size="sm" onClick={() => refetch()}>
        {t("common.retry")}
      </Button>
    </div>
  );
}
```
**Apply to:** Every section with a TanStack Query hook. Other sections of the page still render.

### Empty State Pattern
**Source:** current stub pages (`sales/page.tsx`, etc.) lines 9–18 — the centered icon + text pattern
```typescript
// When data is present but has zero items:
if (data.funnel.leads === 0 || data.funnel.leads === null) {
  return (
    <div className="flex flex-col items-center py-12 text-center">
      <SomeIcon size={32} className="text-[#71717A] mb-3" aria-hidden="true" />
      <p className="text-sm text-[#71717A]">{t("sales.noLeads")}</p>
    </div>
  );
}
// Do NOT render an empty chart — replace entirely with this pattern.
```
**Apply to:** Every chart and table section. Triggers when count is 0 or null.

### Touch Target Minimum
**Source:** Decision D-24
```typescript
// All interactive elements must have min 44px tap area:
className="min-h-[44px] min-w-[44px] flex items-center justify-center"
// For buttons that look smaller visually, add padding to hit the 44px requirement.
```
**Apply to:** Hamburger button, nav items in mobile Sheet, DateRangePicker trigger, Retry buttons, Collapsible triggers, table sort buttons.

### CSS Variables for Colors
**Source:** `frontend/src/app/globals.css` lines 3–15 (`@theme` block)
```typescript
// Use these CSS variables everywhere — never hex codes:
// --color-accent: hsl(221 83% 53%) — primary blue
// --color-border: hsl(240 6% 90%) — borders
// --color-muted-foreground: hsl(240 4% 46%) — secondary text
// --color-destructive: hsl(0 72% 51%) — red/errors
// --color-secondary: hsl(240 5% 96%) — light gray bg
// --color-foreground: hsl(240 10% 4%) — primary text

// In Tailwind classes: bg-[hsl(240_5%_96%)] or use semantic Tailwind vars
// In Recharts fill props (JSX attr, not class): fill="var(--color-accent)"
// The sidebar uses raw HSL strings — that's fine, consistent with the theme
```
**Apply to:** All new components. Recharts `fill`/`stroke` props accept `var(--color-accent)`.

---

## No Analog Found

Files with no close match in the codebase (planner must use RESEARCH.md patterns exclusively):

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `frontend/src/hooks/useSalesDashboard.ts` | hook | request-response | No TanStack Query hooks exist anywhere in the codebase. This is the first. |
| `frontend/src/components/date-range-picker.tsx` | component | event-driven | No date picker exists. No URL-sync pattern exists. react-day-picker not yet installed. |
| `frontend/src/components/dashboards/sales/funnel-chart.tsx` | component | transform | No Recharts components exist. recharts not yet installed. |
| `frontend/src/components/dashboards/insights/problem-card.tsx` | component | event-driven | No Collapsible components exist. shadcn Collapsible not yet installed. |

For all four above: follow RESEARCH.md Patterns 3, 4, 5, 6 respectively (they are verified against the actual libraries and backend schemas).

---

## Critical Constraints (Extracted from Codebase Reading)

### package.json — What Is and Isn't Installed

**Already installed** (no install needed):
- `@tanstack/react-query` 5.100.11
- `next-intl` 4.12.0
- `lucide-react` ^0.469.0
- `clsx`, `tailwind-merge` (cn utility)
- `@radix-ui/react-dialog` v1.1.15 (Sheet uses this — already present)
- `@tailwindcss/postcss` ^4 (in devDeps — config file only missing)
- `zustand` 5.0.13 (not needed for Phase 7 but present)

**Must install before any chart/date work:**
```bash
# From frontend/ directory
pnpm add recharts react-day-picker
npx shadcn add card skeleton badge table chart collapsible sheet
```

### shadcn UI Components — Installed vs. Missing

**Currently installed** (confirmed by reading `frontend/src/components/ui/`):
- `button.tsx` — variants: default, destructive, outline, secondary, ghost, link; sizes: default, sm, lg, icon
- `input.tsx`
- `label.tsx`
- `separator.tsx`

**Not installed, must add in Plan 01:**
- `card` — needed for KPI cards, insight problem cards
- `skeleton` — needed for all loading states
- `badge` — needed for WoW deltas, severity indicators
- `table` — needed for salespeople leaderboard, source breakdown
- `chart` — needed for all Recharts charts (also installs recharts as dep)
- `collapsible` — needed for insight problem cards (collapse/expand)
- `sheet` — needed for mobile sidebar overlay

### components.json — shadcn Config (affects all `npx shadcn add` commands)

```json
{
  "style": "new-york",
  "tailwind": { "baseColor": "zinc", "cssVariables": true },
  "aliases": { "hooks": "@/hooks" }
}
```

All installed components use `hsl(var(--...))` CSS variable pattern (not hardcoded). The `@/hooks` alias is pre-configured — hooks created at `frontend/src/hooks/` are importable as `@/hooks/useSalesDashboard`.

### next.config.ts — Turbopack Enabled, No Custom Webpack

```typescript
const config: NextConfig = {
  turbopack: {},  // empty object = Turbopack enabled
};
```

PostCSS config file (`postcss.config.mjs`) is the ONLY change needed for CSS to work. Do not modify `next.config.ts`.

### i18n — `localePrefix: "never"` Means No URL Prefixes

Routes are `/sales`, `/marketing` (not `/ro/sales`). Locale is set by `NEXT_LOCALE` cookie (see topbar.tsx `handleLocaleToggle`). `useTranslations` works in all `"use client"` components via `NextIntlClientProvider` in root layout.

---

## Metadata

**Analog search scope:** `frontend/src/`, `frontend/messages/`, `frontend/package.json`, `frontend/components.json`, `frontend/next.config.ts`
**Files read:** 20
**Pattern extraction date:** 2026-05-28
