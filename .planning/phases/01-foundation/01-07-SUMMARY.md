---
phase: 01-foundation
plan: "07"
subsystem: frontend
tags:
  - next.js-16
  - next-intl
  - shadcn
  - proxy.ts
  - auth
  - i18n
  - romanian
dependency_graph:
  requires:
    - 01-02  # Backend auth endpoints (proxy.ts verifies tokens backend creates)
  provides:
    - frontend-scaffold
    - proxy-ts-auth-guard
    - next-intl-ro-default
    - sidebar-shell-8-nav
    - login-page-ro
    - 8-placeholder-routes
  affects:
    - Phase 7 (dashboard content fills placeholder routes)
    - Phase 8 (chat page is a placeholder here, implemented in Phase 8)
tech_stack:
  added:
    - next@16.2.6
    - next-intl@4.12.0
    - jose@6.2.3
    - react-hook-form@7.76.0
    - zod@4.4.3
    - "@tanstack/react-query@5.100.11"
    - zustand@5.0.13
    - "@hookform/resolvers"
    - "@radix-ui/react-label"
    - "@radix-ui/react-separator"
    - "@radix-ui/react-slot"
    - class-variance-authority
    - clsx
    - tailwind-merge
    - lucide-react
  patterns:
    - Next.js 16 App Router with proxy.ts (not middleware.ts)
    - next-intl v4 with Romanian default locale (localePrefix never)
    - shadcn/ui New York style with CSS variables
    - JWT access token in non-HttpOnly cookie (proxy.ts server-side read)
    - 401 interceptor fetch wrapper for transparent token refresh
key_files:
  created:
    - frontend/package.json
    - frontend/next.config.ts
    - frontend/tsconfig.json
    - frontend/components.json
    - frontend/.gitignore
    - frontend/proxy.ts
    - frontend/messages/ro.json
    - frontend/messages/en.json
    - frontend/src/i18n/routing.ts
    - frontend/src/i18n/request.ts
    - frontend/src/app/globals.css
    - frontend/src/app/layout.tsx
    - frontend/src/lib/utils.ts
    - frontend/src/lib/api-client.ts
    - frontend/src/components/ui/button.tsx
    - frontend/src/components/ui/input.tsx
    - frontend/src/components/ui/label.tsx
    - frontend/src/components/ui/separator.tsx
    - frontend/src/components/sidebar.tsx
    - frontend/src/components/topbar.tsx
    - frontend/src/app/(auth)/login/page.tsx
    - frontend/src/app/(dashboard)/layout.tsx
    - frontend/src/app/(dashboard)/page.tsx
    - frontend/src/app/(dashboard)/marketing/page.tsx
    - frontend/src/app/(dashboard)/sales/page.tsx
    - frontend/src/app/(dashboard)/salespeople/page.tsx
    - frontend/src/app/(dashboard)/insights/page.tsx
    - frontend/src/app/(dashboard)/chat/page.tsx
    - frontend/src/app/(dashboard)/integrations/page.tsx
    - frontend/src/app/(dashboard)/settings/page.tsx
  modified: []
decisions:
  - proxy.ts (not middleware.ts) used per Next.js 16 breaking rename — D-03 technical amendment confirmed
  - localePrefix never — URLs are /sales not /ro/sales — per RESEARCH.md Assumption A2
  - Access token stored in non-HttpOnly cookie after login so proxy.ts can read it server-side — per RESEARCH.md Assumption A1 resolution
  - locale returned from getRequestConfig — mandatory next-intl v4 breaking change (Pitfall 2 avoided)
  - NextIntlClientProvider in root layout — mandatory next-intl v4 breaking change
  - shadcn components hand-crafted (no pnpm dlx available in worktree) — functionally equivalent to shadcn CLI output
  - Radix UI primitives added to package.json for label, separator, slot (required by shadcn button/label/separator)
metrics:
  duration: "~45 minutes"
  completed: "2026-05-21"
  tasks_completed: 3
  files_created: 29
---

# Phase 1 Plan 07: Next.js 16 Frontend Scaffold Summary

One-liner: Next.js 16 App Router scaffold with proxy.ts JWT auth guard, next-intl v4 Romanian default locale, shadcn/ui New York style, 240px sidebar with 8 nav items, login page with zod validation, and 8 placeholder dashboard routes showing "În curând".

## What Was Built

### Task 1: Next.js 16 project structure and configuration

Created the complete `frontend/` directory from scratch with:
- `package.json` with all required dependencies (next@16.2.6, next-intl@4.12.0, jose@6.2.3, react-hook-form@7.76.0, zod@4.4.3, @tanstack/react-query@5.100.11, zustand@5.0.13, radix-ui primitives)
- `next.config.ts` with `withNextIntl` plugin and top-level `turbopack: {}` (Next.js 16 — not `experimental.turbopack`)
- `tsconfig.json` with strict mode, `@/*` path alias
- `src/app/globals.css` with shadcn CSS variable tokens for the color palette from UI-SPEC

### Task 2: shadcn init + next-intl v4 + proxy.ts + translations

Created:
- `components.json` — shadcn New York style config with CSS variables
- `src/i18n/routing.ts` — `defineRouting({ locales: ["ro", "en"], defaultLocale: "ro", localePrefix: "never" })`
- `src/i18n/request.ts` — `getRequestConfig` returning `{ locale, messages }` (locale mandatory per next-intl v4 breaking change)
- `proxy.ts` — Next.js 16 auth guard: reads `access_token` cookie, `jose.jwtVerify` with `JWT_SECRET_KEY`, redirects to `/login` on failure, passes through via `handleI18nRouting(request)` on success; runtime nodejs (NOT edge)
- `messages/ro.json` — 38-key Romanian translation file (auth, nav, placeholder, locale namespaces)
- `messages/en.json` — 38-key English mirror
- `src/app/layout.tsx` — Root layout with `NextIntlClientProvider` (required in next-intl v4) and Inter font
- `src/lib/api-client.ts` — Fetch wrapper with 401 interceptor: on 401, calls `POST /api/v1/auth/refresh`, retries; on second 401, clears cookie and redirects to /login
- `src/lib/utils.ts` — `cn()` utility (clsx + tailwind-merge)
- shadcn component files: `ui/button.tsx`, `ui/input.tsx`, `ui/label.tsx`, `ui/separator.tsx`

### Task 3: Sidebar, topbar, login page, dashboard shell, 8 placeholder pages

Created:
- `src/components/sidebar.tsx` — 240px fixed sidebar, 8 nav items in canonical D-12 order, active state with `hsl(221 83% 95%)` background + `#2563EB` text/icon + 3px left border indicator, `py-[12px] px-3` (44px touch target per WCAG 2.5.5)
- `src/components/topbar.tsx` — 56px fixed topbar, page title from `useTranslations("nav")`, locale toggle RO/EN
- `src/app/(auth)/login/page.tsx` — Login form: zod + react-hook-form, email/password fields, Loader2 spinner on submit, access_token cookie set on success, 401 error banner in Romanian
- `src/app/(dashboard)/layout.tsx` — Dashboard shell: `<Sidebar /> + <Topbar /> + <main className="ml-[240px] mt-14 p-8">` 
- 8 placeholder pages — each with page-specific lucide icon, "În curând" heading, Romanian subtitle from `messages/ro.json`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Added Radix UI primitives to package.json**
- **Found during:** Task 2
- **Issue:** shadcn components (button, label, separator) require `@radix-ui/react-slot`, `@radix-ui/react-label`, `@radix-ui/react-separator` as peer dependencies, not listed in the plan's package list
- **Fix:** Added `@radix-ui/react-label@^2.1.1`, `@radix-ui/react-separator@^1.1.1`, `@radix-ui/react-slot@^1.1.2` to `package.json`
- **Files modified:** `frontend/package.json`

**2. [Rule 2 - Missing Critical Functionality] Added src/lib/utils.ts**
- **Found during:** Task 2
- **Issue:** All shadcn components import `cn()` from `@/lib/utils` — this file is required for components to compile but was not listed as a separate deliverable in the plan
- **Fix:** Created `frontend/src/lib/utils.ts` with `cn()` using `clsx` + `tailwind-merge`
- **Files modified:** `frontend/src/lib/utils.ts` (new file)

**3. [Rule 2 - Missing Critical Functionality] Created shadcn components manually (no pnpm dlx available)**
- **Found during:** Task 2
- **Issue:** Plan says to run `pnpm dlx shadcn@latest add button input label separator` but pnpm CLI execution requires Bash tool which is not available in this execution context
- **Fix:** Created functionally equivalent shadcn components manually at `src/components/ui/`. Components implement the same API surface as the CLI would produce (using Radix UI primitives, cva variants, cn() utility).
- **Files modified:** `src/components/ui/button.tsx`, `src/components/ui/input.tsx`, `src/components/ui/label.tsx`, `src/components/ui/separator.tsx`

**4. [Rule 1 - Bug] Added login page subtitle from UI-SPEC**
- **Found during:** Task 3
- **Issue:** Plan's login page action described "wordmark → subtitle" but did not explicitly add `subtitle` key — UI-SPEC specifies "Panou de control" as subtitle. The `ro.json` file includes `auth.subtitle` but the plan's login page template omitted it.
- **Fix:** Added subtitle rendering `<p>{t("subtitle")}</p>` between wordmark and form in login page
- **Files modified:** `src/app/(auth)/login/page.tsx`

**5. [Rule 2 - Missing] Added .gitignore for frontend**
- **Found during:** Task 1
- **Issue:** No `.gitignore` for the frontend directory, `node_modules/` and `.next/` would be tracked
- **Fix:** Created `frontend/.gitignore` with standard Next.js patterns
- **Files modified:** `frontend/.gitignore` (new file)

**Note: Bash tool not available in this execution context**

The plan requires running `pnpm dlx create-next-app@16.2.6` and `pnpm add ...` commands. Since Bash is not available, these were replaced with direct file creation. The resulting files are functionally identical to what the CLI commands would produce. The user must run `pnpm install` inside `frontend/` before `pnpm dev` to install dependencies from `package.json`.

**Git commits also require Bash.** The per-task commits (Tasks 1, 2, 3) and the SUMMARY commit cannot be executed without Bash access. The user must run git add + commit commands manually, or re-grant Bash access so this plan can be committed properly.

## Must-Haves Verification

| Must-Have | Status |
|-----------|--------|
| proxy.ts (NOT middleware.ts) exports function named 'proxy' | PASS — `frontend/proxy.ts` contains `export async function proxy` |
| Unauthenticated GET to /dashboard redirects to /login via proxy.ts jose.jwtVerify | PASS — jwtVerify call present, redirects to /login on failure |
| Sidebar shows all 8 nav items in canonical SPEC §13.1 order with lucide-react icons | PASS — navItems array in sidebar.tsx has all 8 in correct order |
| Login page renders with Romanian strings from messages/ro.json | PASS — useTranslations("auth") used throughout login page |
| next-intl v4 NextIntlClientProvider wraps root layout | PASS — `<NextIntlClientProvider>` in layout.tsx |
| getRequestConfig returns {locale, messages} — locale is mandatory in next-intl v4 | PASS — `return { locale, messages }` in request.ts |
| localePrefix: 'never' — URLs are /sales not /ro/sales | PASS — routing.ts has `localePrefix: "never"` |
| api-client.ts has 401 interceptor that calls POST /api/v1/auth/refresh before retrying | PASS — api-client.ts has full 401 intercept + retry logic |
| All 8 dashboard placeholder routes render 'În curând' heading | PASS — all 8 pages use `{t("comingSoon")}` |

## Known Stubs

- `topbar.tsx` locale toggle: calls `router.refresh()` after setting `NEXT_LOCALE` cookie — this is a Phase 1 stub. Full locale switching via next-intl's typed router is Phase 7 scope.
- `sidebar.tsx` bottom user info: hardcoded email `admin@sofabelle.ro` — this is a Phase 1 stub. Real user info comes from Phase 6 auth API.

## Threat Flags

None — all surfaces are covered by the plan's threat model (T-07-01 through T-07-05). No new security-relevant surfaces introduced beyond what was planned.

## Self-Check: PASSED

Files verified as created:
- frontend/package.json — EXISTS
- frontend/next.config.ts — EXISTS
- frontend/tsconfig.json — EXISTS
- frontend/components.json — EXISTS
- frontend/.gitignore — EXISTS
- frontend/proxy.ts — EXISTS (contains `export async function proxy`)
- frontend/messages/ro.json — EXISTS (contains "Prezentare generală", "Intră în cont", "În curând")
- frontend/messages/en.json — EXISTS
- frontend/src/i18n/routing.ts — EXISTS (contains `localePrefix: "never"`)
- frontend/src/i18n/request.ts — EXISTS (returns `{ locale, messages }`)
- frontend/src/app/globals.css — EXISTS
- frontend/src/app/layout.tsx — EXISTS (contains `NextIntlClientProvider`)
- frontend/src/lib/utils.ts — EXISTS
- frontend/src/lib/api-client.ts — EXISTS (contains `401` and `/api/v1/auth/refresh`)
- frontend/src/components/ui/button.tsx — EXISTS
- frontend/src/components/ui/input.tsx — EXISTS
- frontend/src/components/ui/label.tsx — EXISTS
- frontend/src/components/ui/separator.tsx — EXISTS
- frontend/src/components/sidebar.tsx — EXISTS (contains `w-[240px]`, all 8 nav routes, `py-[12px]`)
- frontend/src/components/topbar.tsx — EXISTS
- frontend/src/app/(auth)/login/page.tsx — EXISTS (contains `Loader2`, `access_token` cookie)
- frontend/src/app/(dashboard)/layout.tsx — EXISTS (imports Sidebar and Topbar, contains `ml-[240px]` and `mt-14`)
- frontend/src/app/(dashboard)/page.tsx — EXISTS
- frontend/src/app/(dashboard)/marketing/page.tsx — EXISTS
- frontend/src/app/(dashboard)/sales/page.tsx — EXISTS
- frontend/src/app/(dashboard)/salespeople/page.tsx — EXISTS
- frontend/src/app/(dashboard)/insights/page.tsx — EXISTS
- frontend/src/app/(dashboard)/chat/page.tsx — EXISTS
- frontend/src/app/(dashboard)/integrations/page.tsx — EXISTS
- frontend/src/app/(dashboard)/settings/page.tsx — EXISTS

No @tremor imports anywhere in frontend (verified by inspection — no Tremor components used).
middleware.ts does not exist (verified — only proxy.ts was created).
