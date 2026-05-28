# Phase 7: Frontend Dashboards - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-28
**Phase:** 7-frontend-dashboards
**Areas discussed:** KI-01: Tailwind CSS fix, Charts & component patterns, Data fetching & date range state, UX states & insights page rendering

---

## KI-01: Tailwind CSS fix

| Option | Description | Selected |
|--------|-------------|----------|
| PostCSS + keep Turbopack | Install @tailwindcss/postcss, add postcss.config.mjs. Minimal change, keeps fast HMR. | ✓ |
| Switch to webpack + PostCSS | Remove turbopack:{}, add PostCSS config. More stable, slightly slower HMR. | |
| Turbopack native CSS (no PostCSS) | Keep turbopack:{}, add tailwind.config.ts for Turbopack's built-in support. Experimental. | |

**User's choice:** PostCSS + keep Turbopack (Recommended)
**Notes:** None.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated Plan 01: CSS fix + infra | Fix Tailwind, add PostCSS config, QueryClientProvider, install recharts + react-day-picker. | ✓ |
| Fold into first content plan | CSS fix happens alongside first dashboard page. | |

**User's choice:** Dedicated Plan 01: CSS fix + infra (Recommended)
**Notes:** None.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Audit existing components visually | Confirm sidebar, topbar, login, button render correctly after CSS fix. | ✓ |
| Trust the globals.css vars | If PostCSS loads CSS vars, all hsl(var(--...)) components will just work. | |

**User's choice:** Audit existing components visually
**Notes:** KI-01 was a silent failure — better to confirm explicitly.

---

| Option | Description | Selected |
|--------|-------------|----------|
| CSS fix + QueryClientProvider + package installs only | Minimal scope for Plan 01. | ✓ |
| Add i18n message expansion too | Also expand ro.json / en.json in Plan 01. | |
| Add global error boundary too | Add React error boundary in dashboard layout. | |

**User's choice:** CSS fix + QueryClientProvider + package installs only (Recommended)
**Notes:** Keep Plan 01 focused. i18n expansion happens in the relevant dashboard plans.

---

## Charts & Component Patterns

| Option | Description | Selected |
|--------|-------------|----------|
| Horizontal stage bars with conversion % arrows | Recharts BarChart, 4 bars, percentage arrows between stages. | ✓ |
| Vertical funnel steps (custom CSS) | Trapezoid shapes narrowing downward. Custom CSS/SVG. | |
| Simple stat cards in a row | 4 cards with large number + conversion label. No chart library. | |

**User's choice:** Horizontal stage bars with conversion % arrows (Recommended)
**Notes:** None.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Metric + WoW delta badge + trend arrow | Large number, colored badge ▲/▼%, shadcn Card. | ✓ |
| Metric + sparkline mini-chart | Number + 7-day Recharts LineChart per card. | |
| Metric only, deltas in separate table | Clean cards, WoW/MoM in separate table. | |

**User's choice:** Metric + WoW delta badge + trend arrow (Recommended)
**Notes:** None.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Horizontal bar chart + summary table below | Recharts horizontal BarChart + table with source, leads, conversion. | ✓ |
| Donut/pie chart with legend | Recharts PieChart. Better for proportions, worse for 7+ categories. | |
| Data table only (no chart) | shadcn Table only. Most dense, least visual. | |

**User's choice:** Horizontal bar chart + summary table below (Recommended)
**Notes:** None.

---

| Option | Description | Selected |
|--------|-------------|----------|
| shadcn Table with sortable columns | Full data table with all metrics. Time-to-first-touch cell red when > 4h. | ✓ |
| Cards per rep with mini-stats | 6 cards in a grid per rep. | |
| Leaderboard rank list | Ranked 1-6, 3 metrics only. | |

**User's choice:** shadcn Table with sortable columns (Recommended)
**Notes:** None.

---

## Data Fetching & Date Range State

| Option | Description | Selected |
|--------|-------------|----------|
| Dashboard layout only | QueryClientProvider in (dashboard)/layout.tsx. Login stays clean Server Component. | ✓ |
| Root layout (app/layout.tsx) | Wraps everything. Causes Client Component root complexity. | |

**User's choice:** Dashboard layout only (Recommended)
**Notes:** None.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Default last 30 days, presets: 7d / 30d / 90d / this month | Covers a full business month. | ✓ |
| Default current month, presets: this month / last month / last 90d / YoY | Current month may be thin early in month. | |
| Default last 7 days, presets: 7d / 30d / 90d / custom | Shows most recent data. May feel sparse. | |

**User's choice:** Default last 30 days, presets: 7d / 30d / 90d / this month (Recommended)
**Notes:** No YoY overlay in Phase 7 — deferred to Phase 9 polish.

---

| Option | Description | Selected |
|--------|-------------|----------|
| URL query params (?from=...&to=...) | Bookmarkable, persists on refresh, useSearchParams(). | ✓ |
| Zustand global store | Shared in memory. Simpler component code but lost on refresh. | |

**User's choice:** URL query params (Recommended)
**Notes:** None.

---

| Option | Description | Selected |
|--------|-------------|----------|
| staleTime: 5 min, refetchOnWindowFocus: false | Data pre-computed nightly. Avoids redundant refetches. | ✓ |
| staleTime: 0, refetchOnWindowFocus: true | Always fresh but unnecessary API calls. | |
| staleTime: 1 hour | Aggressive caching. Users won't see post-refresh updates. | |

**User's choice:** staleTime: 5 minutes, refetchOnWindowFocus: false (Recommended)
**Notes:** None.

---

## UX States & Insights Page Rendering

| Option | Description | Selected |
|--------|-------------|----------|
| Skeleton cards matching final layout | shadcn Skeleton, prevents layout shift. | ✓ |
| Page-level spinner | Single centered spinner. Feels like loading screen. | |

**User's choice:** Skeleton cards matching final layout (Recommended)
**Notes:** None.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Inline error in affected section + global 401 redirect | TanStack Query error state, Romanian message + Retry. 401 → apiClient handles. | ✓ |
| Toast notifications for all errors | shadcn Sonner. Easy to miss. | |
| Full page error boundary | One failing query breaks whole page. | |

**User's choice:** Inline error in affected section + global 401 redirect (Recommended)
**Notes:** None.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Specific Romanian copy + neutral illustration | Section-specific text, neutral lucide icon. No sad faces. | ✓ |
| Zeros in the chart (always render chart) | Chart axes with zero values. Can look broken. | |
| Generic 'No data' message | Single generic message per page. Less helpful. | |

**User's choice:** Specific Romanian copy + neutral illustration (Recommended)
**Notes:** None.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Cards per problem, flat action list below each | shadcn Cards, collapsed by default, severity badge, expand to see description + action bullets. | ✓ |
| Accordion | shadcn Accordion. More compact, requires more interaction. | |
| Full flat layout (no collapsing) | All expanded by default. More scrolling. | |

**User's choice:** Cards per problem, flat action list below each (Recommended)
**Notes:** summary_ro shown as headline paragraph at page top. Refresh button disabled with countdown when rate-limited.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Full responsive down to 360px (mobile phone) | CRITICAL: CEO of Sofa Belle works only from a phone. | ✓ |
| Desktop + tablet (768px+) | Matches ROADMAP SC#7. No phone layout. | |
| Desktop only (1280px+) | Fastest to implement. | |

**User's choice:** Full responsive including mobile (360px+)
**Notes (verbatim from user):** "Critical context: the CEO of Sofa Belle (the primary user / decision-maker / person who will say 'yes I'll pay for this') works only from a phone — no desktop, no tablet. If the product doesn't work well on mobile, it doesn't work at all for our pilot customer." Specific requirements: hamburger sidebar, stacked KPI cards (1 col mobile / 2-3 tablet / 4+ desktop), vertical funnel on mobile, horizontal scroll tables, bottom sheet date picker on mobile, ResponsiveContainer Recharts, touch targets ≥ 44px. Also future-proofs Phase 8 AI Chat.

---

## Claude's Discretion

- Revenue trend line chart type (area vs pure line)
- Recharts color palette (use CSS variables from globals.css)
- Conversion rate delta display exact format
- Specific Romanian copy for edge cases beyond D-13/D-14
- Chart height values at each breakpoint
- Whether to add react-query-devtools in development

## Deferred Ideas

- YoY overlay toggle — Phase 9 polish
- Chat page implementation — Phase 8 (keep stub)
- Grafana / Prometheus — Phase 9
- Sentry frontend error tracking — Phase 9
- PDF/print export — out of v1 scope
- Per-salesperson photo/avatar — MEFI API has no photos; use initials
- Configurable funnel stages — out of scope
- Dark mode — out of scope
