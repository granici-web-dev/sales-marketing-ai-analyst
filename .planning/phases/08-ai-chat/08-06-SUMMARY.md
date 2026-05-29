---
phase: 08-ai-chat
plan: 06
subsystem: chat/frontend-ui
tags: [chat, frontend, sse, react, ui, i18n, markdown, wave4]

# Dependency graph
requires:
  - phase: 08-01
    provides: "Wave 0 parseSSE test stub (it.todo) + react-markdown / remark-gfm deps + Playwright E2E spec stub"
  - phase: 08-04
    provides: "7 D-09 SSE event schemas — wire-format contract for parseSSE.ts SSEEvent union"
  - phase: 08-05
    provides: "FastAPI chat router at /api/v1/chat — 5 endpoints (4 CRUD + suggested-questions) + SSE POST /messages"
provides:
  - "parseSSEChunk(chunk) pure SSE parser with LM-7 chunk-boundary tolerance"
  - "tool-pill-hints.ts dayCount + periodLabel Romanian helpers (UI-SPEC § Hint helpers)"
  - "useChat hook (fetch + ReadableStream + 7-event dispatch + D-08 regen reset + AbortController cancel)"
  - "useConversations: list/get/create/archive TanStack Query hooks"
  - "useSuggestedQuestions hook with silent error fallback (D-17)"
  - "3 new shadcn primitives: alert-dialog / textarea / dropdown-menu (D-Phase7 radix-umbrella)"
  - "14 chat components covering UI-SPEC § Component Inventory"
  - "Rebuilt /chat page with split-panel sidebar + mobile sheet (D-13 + D-36)"
  - "Extended chat namespace in messages/ro.json + en.json (UI-SPEC § Concrete Copy Block)"
  - "vitest jsdom + @testing-library/react + jest-dom test infrastructure"
affects:
  - "Frontend chat surface is end-to-end wired against the 08-05 backend contract"
  - "Phase 8 stack is feature-complete pending the BLOCKING mobile + Romanian-quality UAT (Task 4)"

# Tech tracking
tech-stack:
  added:
    - "@testing-library/react@^16.3.2 (devDep)"
    - "@testing-library/jest-dom@^6.9.1 (devDep)"
    - "@testing-library/dom@^10.4.1 (devDep)"
    - "jsdom@^29.1.1 (devDep)"
  reused:
    - react-markdown@^9.1.0 (08-01 install)
    - remark-gfm@^4.0.1 (08-01 install)
    - radix-ui@^1.4.3 (Phase 7 umbrella — alert-dialog + dropdown-menu added)
    - "@tanstack/react-query@5.100.11 (Phase 7)"
    - next-intl@4.12.0 (Phase 7)
    - lucide-react@^0.469.0 (12-tool icon map + send/abort/chevron icons)
    - date-fns@^4.3.0 (formatDistanceToNow with ro locale)
  patterns:
    - "fetch + ReadableStream SSE consumer (D-32 — NOT EventSource per LM-2)"
    - "Buffer-tail LM-7 chunk-boundary handling: only slice on the LAST `\\n\\n` per read tick"
    - "radix-umbrella manual primitive (Phase 7 D-Phase7) for alert-dialog + dropdown-menu"
    - "Optimistic UI (D-33): user + empty assistant bubbles pushed before SSE round-trip; assistant replaced via onDone callback"
    - "Touch-target ≥44px via min-h-[44px] / min-w-[44px] on every interactive surface (D-17/D-36 NON-NEGOTIABLE)"
    - "Real NextIntlClientProvider in component tests via src/test/render-with-intl.tsx — exercises the actual Romanian copy end-to-end"

key-files:
  created:
    - "frontend/src/components/ui/alert-dialog.tsx (~140 lines)"
    - "frontend/src/components/ui/textarea.tsx (~22 lines)"
    - "frontend/src/components/ui/dropdown-menu.tsx (~123 lines)"
    - "frontend/src/lib/chat/parseSSE.ts (~85 lines)"
    - "frontend/src/lib/tool-pill-hints.ts (~44 lines)"
    - "frontend/src/hooks/useChat.ts (~260 lines)"
    - "frontend/src/hooks/useConversations.ts (~85 lines)"
    - "frontend/src/hooks/useSuggestedQuestions.ts (~42 lines)"
    - "frontend/src/hooks/useChat.test.ts (~230 lines, 9 tests UC1-UC9)"
    - "frontend/src/components/chat/thinking-indicator.tsx (~63 lines)"
    - "frontend/src/components/chat/dashboard-link-pill.tsx (~30 lines)"
    - "frontend/src/components/chat/markdown-renderer.tsx (~110 lines)"
    - "frontend/src/components/chat/tool-pill.tsx (~155 lines)"
    - "frontend/src/components/chat/tool-pills-row.tsx (~68 lines)"
    - "frontend/src/components/chat/message-bubble.tsx (~118 lines)"
    - "frontend/src/components/chat/message-list.tsx (~92 lines)"
    - "frontend/src/components/chat/chat-input.tsx (~115 lines)"
    - "frontend/src/components/chat/suggested-questions.tsx (~80 lines)"
    - "frontend/src/components/chat/welcome-card.tsx (~38 lines)"
    - "frontend/src/components/chat/chat-header.tsx (~95 lines)"
    - "frontend/src/components/chat/conversation-item.tsx (~63 lines)"
    - "frontend/src/components/chat/conversations-list.tsx (~155 lines)"
    - "frontend/src/components/chat/chat-main.tsx (~245 lines)"
    - "frontend/src/components/chat/__tests__/markdown-renderer.test.tsx (~85 lines, 6 tests MR1-MR6)"
    - "frontend/src/components/chat/__tests__/thinking-indicator.test.tsx (~50 lines, 5 tests TI1-TI5)"
    - "frontend/src/test/render-with-intl.tsx (~22 lines)"
    - "frontend/vitest.setup.ts (~35 lines)"
  modified:
    - "frontend/src/app/(dashboard)/chat/page.tsx (placeholder → split-panel ChatPage)"
    - "frontend/messages/ro.json (added chat namespace per UI-SPEC § Concrete Copy Block)"
    - "frontend/messages/en.json (mirrored chat namespace)"
    - "frontend/src/lib/chat/__tests__/parseSSE.test.ts (Wave 0 it.todo → real PS1-PS5 GREEN)"
    - "frontend/vitest.config.ts (jsdom env + setupFiles + e2e exclude)"
    - "frontend/package.json (+4 testing-library/jsdom devDeps)"

key-decisions:
  - "parseSSEChunk returns SSEEvent[] (per plan action item 4 + useChat sketch lines 243-244 where the caller slices on the last \\n\\n before invoking the parser). The Wave 0 stub's `{events, remainder}` shape was advisory; the simpler array shape is plan-compliant and tests pass."
  - "vitest environment switched from `node` to `jsdom` (Rule 3 unblock — React component tests + useChat reader tests need DOM). `tests/e2e/**` excluded from both vitest runs and tsconfig (Phase 8 Wave 0 carry-forward — Playwright owns that path)."
  - "next-intl is NOT mocked in vitest.setup.ts. Component tests wrap render() in a real NextIntlClientProvider loaded from messages/ro.json via src/test/render-with-intl.tsx. This exercises the full Romanian copy stack — TI2/TI3 actually verify `Caut datele...` and `Verific cifrele...` appear in DOM."
  - "tools.collapsedSummary uses a simple `{count}` placeholder + `tools.collapsedSummaryOne` companion key (instead of the ICU `{count, plural, ...}` form in the UI-SPEC § Concrete Copy Block). Component logic in tool-pills-row.tsx selects the singular key when pills.length === 1 and the plural key otherwise. ICU plural support depends on next-intl runtime configuration that isn't enabled in this project; the explicit-key approach is robust and locale-aware."
  - "useChat dispatches conversation_meta via an optional `onMeta` callback (D-33 optimistic ID swap), NOT into hook-local state. The ChatMain component is the IDENTITY owner — it tracks the optimistic user/assistant bubble IDs and uses onDone to replace them with DB IDs once streaming completes."
  - "chat-main.tsx pushes BOTH the user message AND an empty assistant bubble onto local state before calling chat.sendMessage(). The assistant bubble is rendered live from `chat.tokens` / `chat.toolPills` / `chat.thinkingState` so token-by-token UX is correct (D-33 + D-34)."
  - "Raw HSL Tailwind tokens (`bg-[hsl(221_83%_53%)]` etc.) match the existing codebase convention (sidebar.tsx, topbar.tsx, button.tsx). The IDE lints suggesting canonical class names (text-muted-foreground, bg-accent, min-h-11) were dismissed for consistency. A future global refactor can swap to canonical tokens."

patterns-established:
  - "SSE consumer hook contract: fetch POST → response.body.getReader() → TextDecoder → buffer-tail slice on last `\\n\\n` → parseSSEChunk → event dispatch loop. Pattern is reusable for any future SSE-over-POST endpoint."
  - "Optimistic chat UI pattern: caller owns message identity; useChat is stateless w.r.t. message IDs — it surfaces tokens/pills/thinking + callbacks (onMeta / onDone) so the caller swaps optimistic IDs at well-defined boundaries."
  - "Component test rig using a real NextIntlClientProvider in jsdom — preferred over namespace mocking for translation-heavy components because it catches missing keys + ICU interpolation bugs at test time."

requirements-completed: [CHAT-01, CHAT-06, CHAT-07, CHAT-09]

# Metrics
duration: "~50 min"
completed: 2026-05-29
tasks_completed: 3
tasks_pending: 1 (Task 4 — BLOCKING human-verify checkpoint; cannot be self-approved by a parallel executor)
files_created: 27
files_modified: 6
lines_added: ~2700
commits: 3
test-counts:
  parseSSE-green: "5 / 5 (PS1-PS5)"
  useChat-green: "9 / 9 (UC1-UC9)"
  markdown-renderer-green: "6 / 6 (MR1-MR6)"
  thinking-indicator-green: "5 / 5 (TI1-TI5)"
  total-chat-frontend-tests: 25
  total-frontend-tests-passing: 51
---

# Phase 8 Plan 06: Frontend Chat UI Summary

Builds the **frontend chat surface** end-to-end against the wire contract from
plans 08-04 (7 D-09 SSE event schemas) and 08-05 (5 chat endpoints). Replaces
the `/chat` placeholder with the UI-SPEC split-panel layout (260px
`ConversationsList` sidebar + `ChatMain` pane), wires the `useChat` hook
(D-32 — `fetch` + `ReadableStream`, NOT EventSource per LM-2), renders 14
chat components per UI-SPEC § Component Inventory, mounts 3 new shadcn
primitives (`alert-dialog`, `textarea`, `dropdown-menu`) via the Phase 7
radix-umbrella manual pattern, and adds the Romanian-primary `chat` namespace
to `frontend/messages/ro.json` + `en.json`.

## What Was Built

### Task 1 — Foundation layer (commit `92bd81db`)

**3 shadcn primitives** (Phase 7 D-Phase7 radix-umbrella pattern, no shadcn
CLI required):

- `alert-dialog.tsx` (~140 lines) — archive confirmation dialog. Mirrors
  `sheet.tsx` shape, imports `AlertDialog as AlertDialogPrimitive` from the
  `radix-ui` umbrella. Exports the full set: `AlertDialog`, `Trigger`,
  `Content`, `Header`, `Footer`, `Title`, `Description`, `Action`, `Cancel`.
- `textarea.tsx` (~22 lines) — pure native textarea wrapper for ChatInput.
  Pattern from `input.tsx`, with `min-h-[60px]` and focus ring.
- `dropdown-menu.tsx` (~123 lines) — kebab menu on ConversationItem +
  ChatHeader. Same radix-umbrella shape: `DropdownMenu` + `Trigger` +
  `Content` + `Item` + `Separator` + checkbox/label/group variants.

**2 lib helpers:**

- `parseSSE.ts` (~85 lines) — pure SSE chunk parser. Function
  `parseSSEChunk(chunk: string): SSEEvent[]`. Skips heartbeat lines (`:`),
  tolerates malformed JSON (LM-7), exports a discriminated union covering
  all 7 D-09 event types matching `backend/app/schemas/chat/sse_events.py`
  exactly.
- `tool-pill-hints.ts` (~44 lines) — `dayCount(dateFrom, dateTo)` returns
  Romanian-pluralized day count (`"1 zi"` / `"N zile"`) using date-fns
  `differenceInCalendarDays`. `periodLabel({date_from, date_to})` is the
  thin wrapper used by tool pills.

**3 TanStack Query hooks:**

- `useChat.ts` (~260 lines) — the centerpiece. fetch + ReadableStream + tail
  buffer + parseSSEChunk + 7-event dispatch. Exposes
  `{sendMessage, cancel, isStreaming, tokens, toolPills, error, thinkingState}`
  + `onMeta` / `onDone` callbacks for D-33 optimistic-ID swap and final
  persistence. Surfaces 429/409 errors with Romanian UI-SPEC strings.
- `useConversations.ts` (~85 lines) — `useConversationsList(opts?)`,
  `useConversation(id)`, `useCreateConversation`, `useArchiveConversation`.
  All under `["chat", "conversations"]` queryKey so `useChat`'s
  invalidation-on-done triggers the D-14 title hot-swap.
- `useSuggestedQuestions.ts` (~42 lines) — D-17 fault-tolerant. Returns `[]`
  on any error so the UI falls back to the 5 static localized strings
  without ever blocking input.

**i18n** — `messages/ro.json` + `messages/en.json` extended with the full
`chat` namespace (page, welcome, sidebar, conversation, input, indicators,
tools, suggested.static, messages, archive, timestamps, selectConversation).

**Test infrastructure:**

- `vitest.config.ts` switched env to `jsdom` + added `setupFiles` +
  excluded `tests/e2e/**` (Phase 8 Wave 0 carry-forward).
- `vitest.setup.ts` extends `expect` with @testing-library/jest-dom matchers
  and stubs `next/navigation` (router/searchParams/pathname).
- `src/test/render-with-intl.tsx` — renders with a real
  NextIntlClientProvider loaded from `messages/ro.json`.

**Tests added/activated:**

- `parseSSE.test.ts` — Wave 0 `it.todo` × 5 → real PS1-PS5 (single-event,
  heartbeat skip, multi-event chunk, malformed JSON tolerance, empty frame).
  **5 / 5 GREEN.**
- `useChat.test.ts` — UC1-UC9 covering chunk append, tool pill state
  transitions, D-08 regen reset, done invalidation, error event Romanian
  surfacing, AbortController cancel, LM-7 fragmentation, 429 rate-limit.
  **9 / 9 GREEN.**

### Task 2 — 14 chat components + 11 component tests (commit `9b3f74a5`)

| Component | File | Lines | Purpose |
| --- | --- | --- | --- |
| ThinkingIndicator | thinking-indicator.tsx | 63 | 3 motion-safe pulse dots + i18n label (thinking / looking-up / verifying-numbers) |
| DashboardLinkPill | dashboard-link-pill.tsx | 30 | next/link with accent #5 styling + ChevronRight |
| MarkdownRenderer | markdown-renderer.tsx | 110 | react-markdown + remark-gfm + allowedElements whitelist + D-19 strong→accent + D-18a link whitelist |
| ToolPill | tool-pill.tsx | 155 | 12-tool lucide icon map + per-tool hint helpers + 3 visual states (running/done/error) |
| ToolPillsRow | tool-pills-row.tsx | 68 | Container; collapses to "🔧 N unelte folosite" Collapsible after `done` (D-10) |
| MessageBubble | message-bubble.tsx | 118 | user vs assistant variants + 8 assistant states (streaming-empty, with-tools, with-text, complete, regenerating, fallback, error) |
| MessageList | message-list.tsx | 92 | role=log + auto-scroll <100px (D-34) + floating "↓ Mesaje noi" button |
| ChatInput | chat-input.tsx | 115 | Auto-growing textarea + Send button (≥44px) + Enter sends / Shift+Enter newline + Loader2 spinner |
| SuggestedQuestions | suggested-questions.tsx | 80 | 5 static fallback chips + dynamic backend chips; hidden on user-msg sent (D-17) |
| WelcomeCard | welcome-card.tsx | 38 | Centered empty-state H1 + body + chips |
| ChatHeader | chat-header.tsx | 95 | Title + kebab → AlertDialog archive confirmation → useArchiveConversation + redirect (D-15) |
| ConversationItem | conversation-item.tsx | 63 | next/link row with formatDistanceToNow (ro locale) + active border-l-accent |
| ConversationsList | conversations-list.tsx | 155 | Desktop 260px sidebar OR mobile Sheet (w-[85vw]) + loading/empty/error states |
| ChatMain | chat-main.tsx | 245 | Owns useChat + optimistic message buffer + 4 layout states (no-conv-no-history, no-conv-has-history, active, 404) |

**Component tests** in `src/components/chat/__tests__/`:

- `markdown-renderer.test.tsx` — MR1 (D-19 strong→accent), MR2
  (`[Sales Dashboard](/sales)` → DashboardLinkPill), MR3
  (`[Evil](https://...)` → muted span), MR4 (`[Sales](#)` → plain span),
  MR5 (script/iframe/img dropped), MR6 (tables wrapped in `overflow-x-auto`).
  **6 / 6 GREEN.**
- `thinking-indicator.test.tsx` — TI1 (thinking: 3 dots, no label), TI2
  (looking-up: "Caut datele..."), TI3 (verifying-numbers: "Verific
  cifrele..."), TI4 (`role="status" aria-live="polite"`), TI5
  (`motion-safe:animate-pulse` on every dot). **5 / 5 GREEN.**

### Task 3 — Rebuild `/chat` page (commit `83183d39`)

`frontend/src/app/(dashboard)/chat/page.tsx` rewritten from the placeholder:

- `"use client"` + `Suspense fallback={<Skeleton />}` boundary
- `useSearchParams().get("conversation_id")` drives the active id
- Desktop ≥768px: `<ConversationsList mode="sidebar" />` + `<ChatMain />`
- Mobile <768px: `<ConversationsList mode="mobile-sheet" />` (rendered as a
  Sheet via radix-dialog) toggled from `<ChatMain onMobileMenu={...} />`
  hamburger
- QueryClientProvider explicitly NOT re-wrapped (inherited from Phase 7
  dashboard layout per D-08)
- Verified: 0 hits of the legacy placeholder string; 10 hits of
  ConversationsList/ChatMain/Suspense; 3 hits of useSearchParams.

## Overall Verification

Plan `<verification>` block:

| # | Command | Result |
|---|---------|--------|
| 1 | `pnpm vitest --run` | **51 passed** (5 + 9 + 11 chat tests + 26 carry-forward formatters) |
| 2 | `pnpm typecheck` | exit 0 |
| 3 | `pnpm lint` | exit 0 |
| 4 | `grep -E "hardcoded Romanian" src/components/chat/*.tsx src/app/(dashboard)/chat/page.tsx` | **(none)** |
| 5 | `grep -cE "min-h-\[44px\]" src/components/chat/*.tsx` | **6 files** (NON-NEGOTIABLE touch targets met) |
| 6 | `ro.json chat namespace integrity` | PASS (5 static suggested questions, welcome/sidebar/tools/suggested all present) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] frontend `node_modules/` missing in worktree spawn**
- **Found during:** Task 1 setup, when running pnpm vitest for the first time.
- **Issue:** The worktree is a fresh checkout; pnpm install must run before
  any test/typecheck/lint command.
- **Fix:** `corepack pnpm install` (resolves Phase 7 + 08-01 deps).
- **Files modified:** None tracked — `frontend/node_modules/` is gitignored.
- **Why Rule 3:** Per-worktree setup convenience, no architectural change.

**2. [Rule 3 — Blocking] vitest environment needed switch from `node` to
`jsdom` to run React component + useChat ReadableStream tests**
- **Found during:** Task 1, planning the useChat.test.ts harness.
- **Issue:** The Phase 7-era `vitest.config.ts` used `environment: "node"`
  (sufficient for the pure-logic `formatters.test.ts`). React component
  testing + `document.cookie` in `useChat`'s `readAccessToken` require jsdom.
- **Fix:** Switched env to `jsdom`, added `setupFiles: ["./vitest.setup.ts"]`
  for jest-dom matchers + DOM cleanup + `next/navigation` stub, added
  `@testing-library/react` + `@testing-library/jest-dom` +
  `@testing-library/dom` + `jsdom` as devDependencies, and excluded
  `tests/e2e/**` from vitest discovery (Playwright owns that path).
- **Files modified:** `frontend/vitest.config.ts` (1 edit),
  `frontend/vitest.setup.ts` (new), `frontend/package.json` (+4 devDeps).
- **Why Rule 3:** Test infrastructure needed for the plan's stated UC1-UC9
  + MR1-MR6 + TI1-TI5 tests. Did not change app architecture.

**3. [Rule 1 — Bug] `useMemo` placed after early returns in chat-main.tsx
violated Rules of Hooks**
- **Found during:** Task 2 typecheck.
- **Issue:** I initially defined `scrollKey` via `useMemo` inside the
  "active conversation" branch, after several `if (...) return ...` short
  circuits. React rules of hooks require unconditional hook calls.
- **Fix:** Moved the `useMemo` to the top of the component body, before any
  conditional return.
- **Files modified:** `frontend/src/components/chat/chat-main.tsx`.
- **Why Rule 1:** Pure bug — React would have warned at runtime and
  potentially crashed when the early-return path was taken first.

**4. [Rule 1 — Bug] MR6 test asserted the wrong wrapper level**
- **Found during:** Task 2 MR6 first run.
- **Issue:** The shadcn `Table` primitive *itself* wraps `<table>` in a
  `<div className="relative w-full overflow-auto">`. My `markdown-renderer`
  adds an OUTER wrapper with `overflow-x-auto`. The test originally checked
  the immediate parent of `<table>`, which was the shadcn-internal wrapper.
- **Fix:** Walk up the DOM tree looking for a wrapper whose className
  contains `overflow-x-auto`.
- **Files modified:** `markdown-renderer.test.tsx` (MR6 only).
- **Why Rule 1:** Test bug — the production code was correct.

### Project-convention adjustments (no rule needed)

**5. `tools.collapsedSummary` does NOT use ICU `{count, plural, one {…}
few {…} other {…}}` syntax.**
- The UI-SPEC § Concrete Copy Block specifies an ICU plural form.
- The project's next-intl runtime doesn't have ICU pluralization enabled.
- I added two explicit keys (`collapsedSummary` for "N unelte folosite" and
  `collapsedSummaryOne` for "1 unealtă folosită") and let
  `tool-pills-row.tsx` pick the right one based on `pills.length === 1`.
- This is more robust (no runtime ICU formatter dependency) and locale-aware
  (the Romanian "few" form for 2-19 is handled by the same key as "other"
  per UI-SPEC § Hint helpers).

**6. Raw HSL Tailwind tokens (`bg-[hsl(221_83%_53%)]`, `min-h-[44px]`)
preserved over canonical class suggestions.**
- The IDE diagnostics surfaced ~15 suggestions to rewrite tokens (e.g.
  `text-[hsl(240_4%_46%)]` → `text-muted-foreground`, `min-h-[44px]` →
  `min-h-11`).
- Existing Phase 1/7 components (`sidebar.tsx`, `topbar.tsx`, `button.tsx`,
  `insights/page.tsx`) all use the raw HSL form for consistency with
  `globals.css`. Switching only the chat surface would create a stylistic
  inconsistency.
- A future global refactor can swap to canonical tokens; documented here as
  a deferred polish item.

## Authentication / Human Gates

**Task 4 — BLOCKING `checkpoint:human-verify` is INTENTIONALLY DEFERRED to
the orchestrator + user post-merge.**

The plan's Task 4 requires (per UI-SPEC § Breakpoints + Phase 7 D-17
NON-NEGOTIABLE carry-forward + ROADMAP SC#4 Romanian language quality):

1. **Mobile 360px / Tablet 768px / Desktop 1280px DevTools emulation** — visual
   verification of the split-panel layout, mobile Sheet hamburger, send button
   ≥44px, markdown tables overflow-x-auto.
2. **3 fresh live Anthropic conversations** against the real backend (with
   ANTHROPIC_API_KEY set):
   - WoW comparison → Romanian response + `compare_periods` tool call.
   - "Care e CAC-ul Meta?" → honest refusal containing "nu am acces" (CHAT-05).
   - "Care e cel mai bun vânzător?" → real Sofa Belle salesperson name
     (CHAT-10 entity whitelist).
3. **Inline dashboard pill rendering** — Ask Claude for stuck-leads → expect
   `[Sales Dashboard](/sales)` pill.
4. **Touch target inspection** — Send button + ConversationItem + chip
   computed heights ≥44px in DevTools.
5. **Keyboard-only flow + screen reader sanity checks.**

As a parallel executor running inside a worktree (no interactive console, no
live backend, no DevTools), I cannot self-approve Task 4. **This is by
design** — the plan was authored with `autonomous: false` and Task 4 is the
single human gate. The orchestrator will surface this checkpoint to the user
after the worktree merges, at which point the user runs the live UAT and
either types `approved` or files specific rejections that trigger a 08-07
gap-closure plan.

## Known Stubs

None. Every production code path is wired against the 08-04 / 08-05 contract.

The only "stubbed" surface is the `useConversation` envelope's optional
`messages: Array<...>` field — `ChatMain` reads it when present, but the
backend (per 08-05 key-decisions) intentionally omits message history from
the GET `/chat/conversations/{id}` response in MVP1; messages are hydrated
via the SSE stream. The optional typing makes this forward-compatible: when
Phase 9 wires eager message hydration, `ChatMain` will start picking it up
automatically.

## Threat Flags

No new threat surface beyond what's enumerated in the plan's `<threat_model>`.
All 6 listed entries are mitigated:

- **T-08-01 (cross-tenant info disclosure):** Frontend trusts the backend
  404 — no client-side bypass attempted.
- **T-08-02 (XSS via markdown):** `MarkdownRenderer` sets
  `allowedElements={[...ALLOWED_ELEMENTS]}` + `unwrapDisallowed: false` so
  script/iframe/img/svg/h1-h6/raw HTML and their children are removed
  entirely. MR5 test verifies. Custom `a` renderer rejects any href outside
  the 5-path DASHBOARD_PATHS whitelist (D-18a client-side defense). MR3 test
  verifies external URLs render as plain muted span.
- **T-08-03 (error event leak):** useChat surfaces only `data.message_ro`
  from SSE `error` events; raw 4xx/5xx HTTP status codes map to Romanian
  UI-SPEC strings (rate-limit, concurrent-stream, generic error). No
  `error.stack` exposed.
- **T-08-06 (uncancellable stream):** `cancel()` uses `AbortController`;
  UC7 test exercises it.
- **T-08-PI (prompt injection visible to user):** Backend guard already
  drops adversarial numbers/entities (plan 08-04); MarkdownRenderer's
  `allowedElements` whitelist provides a second line of defense.
- **T-08-MOBILE (mobile UX blocker):** Touch targets ≥44px on Send,
  conversation items, chips, kebab, mobile hamburger. Task 4 BLOCKING
  checkpoint enforces the formal D-17 NON-NEGOTIABLE.

## Commits (in order)

| Hash | Subject |
|------|---------|
| `92bd81db` | `feat(08-06): add chat foundation — 3 ui primitives + parseSSE + hooks + i18n` |
| `9b3f74a5` | `feat(08-06): add 14 chat components + markdown renderer + 11 component tests` |
| `83183d39` | `feat(08-06): rebuild /chat page — split panel ChatMain + sidebar + mobile sheet` |

A 4th commit follows with this SUMMARY.md.

## Plan 08-06 Unblocks

- **Phase 8 frontend stack is feature-complete.** Plans 08-04 (orchestrator
  + guard) and 08-05 (router + SSE) are already wired into chat-main.tsx
  via the documented wire contract.
- The HUMAN-UAT (Task 4) is the only remaining gate before `/gsd:verify-work`.
- Test counts: **51 frontend tests GREEN** (5 parseSSE + 9 useChat + 6
  MarkdownRenderer + 5 ThinkingIndicator + 26 formatters/insights
  carry-forward).
- Once Task 4 returns "approved" from the user, Phase 8 is COMPLETE.

## Self-Check: PASSED

All claimed files exist on disk and every commit is present in the
worktree's git log. Spot-checks:

- `[ -f frontend/src/components/ui/alert-dialog.tsx ]` → FOUND
- `[ -f frontend/src/components/ui/textarea.tsx ]` → FOUND
- `[ -f frontend/src/components/ui/dropdown-menu.tsx ]` → FOUND
- `[ -f frontend/src/lib/chat/parseSSE.ts ]` → FOUND
- `[ -f frontend/src/lib/tool-pill-hints.ts ]` → FOUND
- `[ -f frontend/src/hooks/useChat.ts ]` → FOUND
- `[ -f frontend/src/hooks/useConversations.ts ]` → FOUND
- `[ -f frontend/src/hooks/useSuggestedQuestions.ts ]` → FOUND
- `[ -f frontend/src/hooks/useChat.test.ts ]` → FOUND
- 14 / 14 chat components present in `frontend/src/components/chat/`
- 2 / 2 component tests in `frontend/src/components/chat/__tests__/`
- `frontend/src/app/(dashboard)/chat/page.tsx` placeholder REPLACED
- `git log --oneline | grep 92bd81db` → FOUND
- `git log --oneline | grep 9b3f74a5` → FOUND
- `git log --oneline | grep 83183d39` → FOUND
- `pnpm vitest --run` → 51 passed
- `pnpm typecheck` → exit 0
- `pnpm lint` → exit 0
