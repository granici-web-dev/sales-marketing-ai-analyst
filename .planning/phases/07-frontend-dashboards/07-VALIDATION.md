---
phase: 7
slug: frontend-dashboards
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-28
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | TypeScript compiler (typecheck) + ESLint (lint) + manual browser inspection |
| **Config file** | `frontend/tsconfig.json` (strict mode) |
| **Quick run command** | `cd frontend && pnpm typecheck` |
| **Full suite command** | `cd frontend && pnpm typecheck && pnpm lint` |
| **Estimated runtime** | ~15–30 seconds |

> Note: Playwright e2e is Phase 9. Phase 7 validation is TypeScript strict mode + manual visual verification.

---

## Sampling Rate

- **After every task commit:** Run `cd frontend && pnpm typecheck`
- **After every plan wave:** Run `cd frontend && pnpm typecheck && pnpm lint`
- **Before `/gsd:verify-work`:** Full suite must be green + manual browser verification at 360px, 768px, 1280px
- **Max feedback latency:** ~30 seconds (typecheck)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 0 | UI-02, UI-03, UI-04 | — | N/A | unit | `pnpm typecheck` + formatRON/formatDate/formatDuration tests | ❌ Wave 0 | ⬜ pending |
| 07-01-02 | 01 | 0 | KI-01 | — | N/A | visual | `pnpm dev` → sidebar/topbar/login render with correct colors | ❌ Wave 0 | ⬜ pending |
| 07-01-03 | 01 | 1 | UI-01 | — | N/A | type | `pnpm typecheck` | existing | ⬜ pending |
| 07-02-01 | 02 | 2 | SALE-01..07 | T-7-01 | URL params `?from=` validated as YYYY-MM-DD before API call | type+manual | `pnpm typecheck` + browser at 360px | ❌ | ⬜ pending |
| 07-03-01 | 03 | 2 | SALES-01..04 | — | N/A | type+manual | `pnpm typecheck` + browser at 360px | ❌ | ⬜ pending |
| 07-04-01 | 04 | 2 | MARK-01..04 | — | N/A | type+manual | `pnpm typecheck` + browser at 360px | ❌ | ⬜ pending |
| 07-05-01 | 05 | 2 | INSI-01..06 | T-7-02 | POST /insights/refresh uses credentials: include | type+manual | `pnpm typecheck` + browser at 360px | ❌ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `frontend/src/lib/__tests__/formatters.test.ts` — unit tests for `formatRON`, `formatDate`, `formatDuration`, `formatWowDelta`
- [ ] `frontend/postcss.config.mjs` — PostCSS config (KI-01 fix — CSS must render before Plan 02)

*Existing `@tanstack/react-query`, `next-intl`, `shadcn` infrastructure covers the rest of the phase.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| CSS renders (KI-01) | KI-01 | Visual only | Run `pnpm dev`, navigate to `/dashboard/sales`, confirm sidebar/topbar have correct shadcn colors and spacing |
| Romanian strings in all UI | UI-01 | i18n strings only testable in browser | Open `/dashboard/sales` with `NEXT_LOCALE=ro` cookie; verify all visible text is in Romanian |
| Loading skeleton states | UI-05 | Requires DevTools throttling | Open Network tab → Slow 3G → navigate to any dashboard page; all charts must show Skeleton before data |
| Error state (500) | UI-05 | Requires API mock | Block backend in `/etc/hosts` or mock 500; each dashboard section must show inline error + retry button |
| Empty state | UI-05 | Requires empty date range | Select a date range with no data; sections must show Romanian empty state copy, not blank whitespace |
| Mobile nav hamburger | UI-07 | Viewport simulation | DevTools → iPhone 12 (390px); tap hamburger → slide-over nav opens with all 8 items; tap any nav item → navigates and closes |
| Mobile 360px smoke | D-17 | Lowest supported viewport | DevTools → Galaxy S8 (360px); verify Sales, Salespeople, Marketing, Insights pages each load without horizontal overflow |
| Freshness banner | UI-06 | Requires backend state | When `HealthDataResponse.stale === true`, a banner appears at top of every dashboard page |
| Insights refresh rate-limit | INSI-03 | Requires triggering twice within 1h | Click Reîmprospătează → 429 response → button shows countdown timer in Romanian |

---

## Threat Model (ASVS L1)

| Threat | STRIDE | Mitigation |
|--------|--------|-----------|
| XSS via API data in JSX | Tampering | Never use `dangerouslySetInnerHTML`; all API strings rendered as JSX text nodes (auto-escaped) |
| CSRF on POST /insights/refresh | Spoofing | `credentials: "include"` + SameSite=Lax cookie (Phase 1 backend); no CSRF token needed for same-site |
| Open redirect via `?from=`/`?to=` param injection | Tampering | Parse with `new Date(param)` + `isNaN()` check; invalid values silently fall back to 30-day default |
| API base URL exposure | Info Disclosure | `apiClient.ts` uses relative paths (`/api/v1/...`) — no absolute URL in client bundle |

---

## Phase Gate Checklist (before VERIFICATION.md)

- [ ] `pnpm typecheck` exits 0
- [ ] `pnpm lint` exits 0
- [ ] Manual browser: SC#1 Sales page renders with funnel + KPI cards + source breakdown
- [ ] Manual browser: SC#2 Salespeople page renders with leaderboard + per-rep funnel
- [ ] Manual browser: SC#3 Marketing page renders with source charts + "Coming soon" placeholders
- [ ] Manual browser: SC#4 Insights page renders summary_ro + collapsed problem cards + date picker
- [ ] Manual browser: SC#5 Locale toggle switches RO/EN; RON format and dates unchanged
- [ ] Manual browser: SC#6 Slow 3G → skeleton states; 500 → inline error; empty range → empty state
- [ ] Manual browser: SC#7 Data freshness banner appears when stale
- [ ] `grep -r "@tremor" frontend/src` returns zero matches (SC#8)
- [ ] Manual mobile: 360px smoke test on all 4 dashboard pages (no horizontal overflow)

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
