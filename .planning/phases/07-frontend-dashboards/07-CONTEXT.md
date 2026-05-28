# Phase 7: Frontend Dashboards - Context

**Gathered:** 2026-05-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace all 4 placeholder dashboard stubs with fully functional Next.js 16 pages connected to the Phase 6 backend API. Deliver Sales, Salespeople, Marketing, and Insights pages with proper loading/empty/error states, date range picker, Romanian locale, and full responsive layout from 360px (mobile) through 1280px+ (desktop).

This phase also closes KI-01 (CSS/Tailwind not loading) before building any content.

**Does NOT include:** Phase 8 AI Chat (keep `/chat` route as stub), advertising integrations (CPL/CAC/ROAS — placeholder "coming soon" only), PDF export, real-time data.

</domain>

<decisions>
## Implementation Decisions

### KI-01: CSS/Tailwind Infrastructure Fix (Plan 01 — before any content)

- **D-01:** Fix approach: keep Turbopack, add PostCSS pipeline. Install `@tailwindcss/postcss`, add `postcss.config.mjs` with `{ plugins: { '@tailwindcss/postcss': {} } }`. This lets Turbopack delegate CSS processing to PostCSS, restoring the `@import "tailwindcss"` directive in `globals.css`.
- **D-02:** Plan 01 is a **dedicated infrastructure plan** covering exactly: PostCSS config + `@tailwindcss/postcss` install + `recharts` install + `react-day-picker` install + TanStack QueryClientProvider wired into `(dashboard)/layout.tsx` + shared formatter utilities (`formatRON`, `formatDate`). Nothing else. Plan 01 is done when CSS renders and the dev server runs without errors.
- **D-03:** After the CSS fix, Plan 01 includes a **visual audit** of existing components: sidebar, topbar, login page, and shadcn Button must all render with correct colors, spacing, and hover states before any dashboard content is built.

### Charts & Component Patterns

- **D-04:** **Funnel visualization** (SALE-01): Horizontal Recharts `BarChart` with 4 bars (Lead, Vizita, Oferta, Contract) showing count. Between each pair of bars, show conversion percentage with directional arrow (e.g. `28% →`). WoW delta shown as a colored badge below each bar. No custom SVG funnel — use Recharts for maintainability.
- **D-05:** **KPI cards** (SALE-03, SALES-01): shadcn `Card` with large metric number, WoW delta badge (green `▲+N%` or red `▼-N%`), and a small trend arrow icon. Stacked layout: number on top, delta badge + arrow below. `avg_time_to_first_touch_minutes` uses a red background highlight when value > 240 minutes (4h threshold, SALES-02).
- **D-06:** **Source breakdown** (SALE-04): Recharts horizontal `BarChart` (lead count per source category, sorted descending) + a summary table below it showing source, leads, conversion rate. Marketing page lead-volume chart uses a Recharts `LineChart` (one line per source over time).
- **D-07:** **Salespeople leaderboard** (SALES-01..04): shadcn `Table` with sortable columns. Columns: rank, name, leads, visits, offers, contracts, revenue (RON string), win-rate (%), avg_time_to_first_touch_minutes (red cell when > 240), data_completeness_pct (%). Default sort: contracts descending.

### Data Fetching & Date Range State

- **D-08:** **QueryClientProvider** placed in `src/app/(dashboard)/layout.tsx` (NOT root layout). The layout must be a Client Component wrapper (`"use client"`) that wraps children with `<QueryClientProvider client={queryClient}>`. Login page stays a clean Server Component.
- **D-09:** **Default date range**: last 30 days (today minus 29 days → today). **Preset shortcuts**: "Ultima săptămână" (7d), "Ultima lună" (30d), "Ultimele 90 zile" (90d), "Luna curentă" (this calendar month), + a custom date range picker. No YoY toggle in Phase 7 (deferred to Phase 9 polish).
- **D-10:** **Date state in URL query params**: `?from=YYYY-MM-DD&to=YYYY-MM-DD`. Each dashboard page reads these via `useSearchParams()`. Bookmarkable, persists on page refresh, works with browser back/forward. DateRangePicker component updates URL on selection.
- **D-11:** **TanStack Query cache policy**: `staleTime: 5 * 60 * 1000` (5 minutes), `refetchOnWindowFocus: false`. Data is pre-computed nightly — intraday changes don't happen. Manual refresh available via Insights page Reîmprospătează button (triggers pipeline, not just a client-side refetch).

### UX States (Loading / Error / Empty)

- **D-12:** **Loading states**: shadcn `Skeleton` components matching final layout dimensions (same height/width as the loaded content). One skeleton per chart, card, or table section. Prevents layout shift. No page-level spinners.
- **D-13:** **Error states**: Inline error message inside the failed section in Romanian + Retry button (via TanStack Query's `refetch`). **401** handled globally by existing `apiClient.ts` — refresh once, redirect to `/login` on second 401. **500/network errors** show inline: `"A apărut o eroare. Încearcă din nou."` + retry button in the affected card/chart area only. Other sections of the page still render.
- **D-14:** **Empty states**: Section-specific Romanian copy with a neutral `lucide-react` icon (not a sad face). Examples: `"Nu au fost înregistrate lead-uri în această perioadă."` for the funnel, `"Nu există oferte blocate în acest interval."` for stuck offers, `"Nu există date disponibile pentru perioada selectată."` for charts. Zero-count charts are NOT rendered — replace with empty state text.

### Insights Page Rendering

- **D-15:** **Insights page layout**: `summary` displayed as a headline paragraph at the top of the page (the daily AI summary in Romanian). **FIELD NAME CORRECTION (B3):** The backend field is `summary` (verified from `backend/app/schemas/insights/daily_insight_schema.py`). The field `summary_ro` does NOT exist in the DailyInsightResponse schema — always use `payload.summary`. Below it: up to 3 problem cards using shadcn `Card`. Each card header shows: severity badge (red = Critică, orange = Ridicată, yellow = Medie), problem title, and estimated_loss_ron formatted as RON. Cards are **collapsed by default** — click/tap to expand. Expanded state shows: description + flat bullet list of `recommended_actions` (`action`, `owner`, `deadline`). The "Reîmprospătează" refresh button appears at the top right; it is disabled and shows a countdown when rate-limited (429). Historical date picker at top-left for past insights (INSI-02).
- **D-16:** **Generation failure fallback** (INSI-05): when `InsightEnvelope.generation_failed === true`, show a Romanian notice banner. Two cases: (A) when `status='fallback'` and `payload.problems` is populated — banner + render `payload.problems[]` as ProblemCard components (the fallback payload IS generated by `InsightService._build_fallback()` from detected_problems rows); (B) when `status='failed'` or payload is null — banner + static "Nu există date disponibile pentru această perioadă." paragraph. See Plan 05 FallbackAnomalyList for full implementation.

### Mobile Responsiveness — CRITICAL REQUIREMENT

- **D-17:** **Full responsive down to 360px (mobile phone) — NON-NEGOTIABLE.** The primary user (CEO of Sofa Belle) works exclusively from a phone. The product does not work for the pilot if it does not work on mobile. This is not "nice to have" — it is a requirement equivalent to "the app must render".
- **D-18:** **Hamburger sidebar on mobile**: At < 768px, the fixed `240px` sidebar collapses behind a hamburger button in the topbar. Clicking it opens a slide-over or full-screen nav overlay. All 8 nav items remain accessible.
- **D-19:** **KPI card grid**: `grid-cols-1` on mobile (< 640px), `grid-cols-2` on tablet (640px–1023px), `grid-cols-4` on desktop (1024px+).
- **D-20:** **Funnel viz**: vertical stacked layout on mobile (stages top-to-bottom with conversion arrows pointing downward), horizontal on tablet/desktop.
- **D-21:** **Tables on mobile**: horizontal scroll (`overflow-x-auto`) for salespeople leaderboard and source breakdown table. Sticky first column (rep name / source name) so context is preserved while scrolling.
- **D-22:** **Date picker on mobile**: bottom sheet modal (full-screen) on `< 768px`, popover on `≥ 768px`.
- **D-23:** **Recharts responsive**: all charts wrapped in `<ResponsiveContainer width="100%" height={...}>`. On `< 640px`: hide gridlines, simplify x-axis labels (abbreviated), use compact tooltips.
- **D-24:** Touch targets ≥ 44px on all interactive elements (buttons, nav items, card click areas).

### Localization

- **D-25:** All new UI strings added to `messages/ro.json` and `messages/en.json` in Phase 7. Romanian strings are primary and must be complete; English strings can mirror Romanian with translations. Currency: `Intl.NumberFormat('ro-RO', { style: 'currency', currency: 'RON' })` → `1.234,56 RON`. Dates: `DD.MM.YYYY`. Timestamps: `Europe/Bucharest` timezone.

### Claude's Discretion

- Revenue trend line chart type (area chart vs pure line — open to what renders well with the data)
- Specific Recharts color palette (should draw from CSS variables in `globals.css` — `--color-accent` for primary, muted colors for secondary series)
- Conversion rate delta display (green/red badge, exact format — align with KPI card delta pattern once established)
- Specific Romanian copy for edge cases beyond those listed in D-13/D-14
- Chart height values (responsive — pick what looks good at each breakpoint)
- Whether to add a `react-query-devtools` devtools panel in development mode

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Roadmap
- `.planning/REQUIREMENTS.md` — Phase 7 covers: SALE-01..07, SALES-01..04, MARK-01..04, INSI-01..06, UI-01..08
- `.planning/ROADMAP.md` — Phase 7 success criteria (SC#1–SC#8) — all 8 must pass before phase is complete
- `.planning/STATE.md` — Key decisions (shadcn/ui + Recharts v3, Next.js 16.2, Tailwind v4.3, no Tremor)

### Architecture & Stack
- `docs/ARCHITECTURE.md` — System architecture, async/sync boundary
- `docs/STACK.md` — Technology choices (check STATE.md for overrides)
- `docs/CONVENTIONS.md` — Code style, naming, commit format — mandatory before writing any code

### Frontend Codebase (read before writing new code)
- `frontend/src/app/(dashboard)/layout.tsx` — Dashboard layout wrapper (add QueryClientProvider here)
- `frontend/src/components/sidebar.tsx` — Navigation structure (do not restructure; add hamburger toggle)
- `frontend/src/components/topbar.tsx` — Page title + locale switcher (add hamburger button)
- `frontend/src/lib/api-client.ts` — apiClient with 401/refresh interceptor (all API calls use this)
- `frontend/messages/ro.json` — Primary i18n strings (expand, don't restructure)
- `frontend/messages/en.json` — Secondary i18n strings (keep in sync with ro.json)
- `frontend/src/app/globals.css` — CSS variables (@theme block) — use these for chart colors
- `frontend/next.config.ts` — Turbopack config (Plan 01 adds PostCSS config here)
- `frontend/components.json` — shadcn config (new-york style, cssVariables: true)

### Phase 6 Backend API (consumed by this phase)
- `.planning/phases/06-backend-api/06-RESEARCH.md` — All endpoint specs, response schemas
- `backend/app/schemas/dashboards/sales.py` — SalesDashboardResponse fields
- `backend/app/schemas/dashboards/salespeople.py` — SalespeopleDashboardResponse fields
- `backend/app/schemas/dashboards/marketing.py` — MarketingDashboardResponse fields
- `backend/app/schemas/insights/daily_insight_schema.py` — DailyInsightResponse (problems, **summary** field — NOT summary_ro; verified B3 fix)
- `backend/app/schemas/health.py` — HealthDataResponse (stale flag, last_sync_at)

### Phase 1 Frontend Decisions
- `.planning/phases/01-foundation/01-CONTEXT.md` — D-01..D-13: JWT auth, i18n setup, sidebar structure, next-intl config — all carry forward to Phase 7

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `frontend/src/lib/api-client.ts` — `apiClient.get(url)` handles auth + refresh. All dashboard data fetches use this as the underlying fetcher for TanStack Query `queryFn`.
- `frontend/src/components/ui/button.tsx` — shadcn Button (variants: default, ghost, outline). Use for Retry, Reîmprospătează, mobile menu toggle.
- `frontend/src/components/ui/separator.tsx` — shadcn Separator for dividing dashboard sections.
- `frontend/messages/ro.json` — Has `nav`, `auth`, `placeholder`, `locale` keys already. Phase 7 adds `sales`, `salespeople`, `marketing`, `insights`, `common`, `errors` top-level keys.

### Established Patterns
- `"use client"` directive on all pages that use hooks (useTranslations, useSearchParams, etc.)
- `useTranslations("key")` pattern for all user-visible strings — no hardcoded Romanian in JSX
- TanStack Query v5 API uses `useQuery({ queryKey: [...], queryFn: ... })` (not v4 object syntax)
- Tailwind v4 `@theme` CSS variables — use `--color-accent`, `--color-border`, `--color-muted-foreground` etc., not hex values
- `localePrefix: "never"` in i18n routing — locale determined by `NEXT_LOCALE` cookie, not URL prefix
- Locale switcher already works in topbar (`handleLocaleToggle` sets cookie + router.refresh())

### Integration Points
- `frontend/src/app/(dashboard)/layout.tsx` — Add `QueryClientProvider` wrapper here (as Client Component)
- `frontend/src/app/(dashboard)/sales/page.tsx` — Replace stub with full implementation
- `frontend/src/app/(dashboard)/salespeople/page.tsx` — Replace stub
- `frontend/src/app/(dashboard)/marketing/page.tsx` — Replace stub
- `frontend/src/app/(dashboard)/insights/page.tsx` — Replace stub
- `frontend/src/components/topbar.tsx` — Add hamburger button for mobile sidebar
- `frontend/src/components/sidebar.tsx` — Add mobile collapse behavior
- New directory: `frontend/src/hooks/` — create for TanStack Query hooks (useSalesDashboard, etc.)
- New directory: `frontend/src/components/dashboards/` — chart and card components per dashboard

</code_context>

<specifics>
## Specific Ideas

- **Mobile-first reality check**: The CEO of Sofa Belle (primary user / pilot decision-maker) uses only a phone — no desktop, no tablet. If the product doesn't work on mobile, the pilot fails. Phase 7 must be tested on a phone before marking complete.
- **KI-01 was a silent failure**: CSS rendered as unstyled HTML. The fix must be validated by running the dev server and visually confirming the sidebar, topbar, and login page show correct colors/spacing.
- **Revenue formatting**: `Intl.NumberFormat('ro-RO', { style: 'currency', currency: 'RON', maximumFractionDigits: 2 })` — all revenue/money fields. The backend already returns revenue as decimal strings (not floats) per DATA-04; parse with `parseFloat()` before formatting.
- **Time-to-first-touch highlight**: `avg_time_to_first_touch_minutes > 240` → red cell background in the salespeople table. The 4h threshold is from ANOM-02 and SALES-02.
- **Data freshness banner** (UI-06): shown at the top of every dashboard page (not just insights) when `HealthDataResponse.stale === true`. One shared component, conditionally rendered based on health query result.
- **shadcn/ui chart**: install via `npx shadcn add chart` — this installs the chart component wrapper around Recharts. Don't import from `recharts` directly in page components — use the shadcn chart abstraction.
- **PostCSS config location**: `frontend/postcss.config.mjs` (not `.js` — Next.js 16 + ESM).

</specifics>

<deferred>
## Deferred Ideas

- **YoY overlay toggle** — mentioned by user as a preset shortcut option; deferred to Phase 9 polish (not in ROADMAP Phase 7 SC). A disabled placeholder button "Comparare An/An" is shown in DateRangePicker per SALE-06 shape (Plan 02).
- **Chat page implementation** — `/chat` route stays as a placeholder stub. Phase 8 will replace it. Do NOT implement chat in Phase 7.
- **Grafana / Prometheus** — Phase 9.
- **Sentry frontend error tracking** — Phase 9.
- **PDF/print export** — out of v1 scope per REQUIREMENTS.md Out of Scope table.
- **Per-salesperson photo/avatar** — MEFI API doesn't expose photos; show initials instead.
- **Configurable funnel stages** — out of scope (Sofa Belle-specific funnel is hardcoded for MVP1).
- **Dark mode** — not in scope.

</deferred>

---

*Phase: 7-frontend-dashboards*
*Context gathered: 2026-05-28*
