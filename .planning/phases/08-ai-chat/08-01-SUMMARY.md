---
phase: 08-ai-chat
plan: 01
subsystem: chat/test-infra
tags: [chat, test-infra, wave0, sse, anthropic, adversarial]
requires:
  - Phase 5 (anthropic SDK pinned ≥0.30,<1 — reused, not rebumped)
  - Phase 5 insight_factory.py dict-builder pattern
  - Phase 5 AI-09 grep gate (INVERSE source for CHAT-08)
provides:
  - reusable chat unit + integration test packages
  - mock-AsyncAnthropic fixtures + sse_collector + mock_anthropic_stream factory
  - recorded streaming cassettes (basic_turn, multi_tool) for CHAT-02 SC#2
  - CHAT-08 grep gate (PASSING — vacuous; activates strictly when 08-05 lands chat.py)
  - adversarial fixture YAML (15 questions × 5 categories) + RUN_ADVERSARIAL gate
  - frontend SSE parser test contract + Playwright E2E stub
  - react-markdown@^9.1.0 + remark-gfm@^4.0.1 frontend deps
affects:
  - frontend/package.json (deps added)
  - frontend/tsconfig.json (tests/e2e/** excluded from typecheck)
tech-stack:
  added:
    - react-markdown@^9.1.0 (frontend dependency — D-19)
    - remark-gfm@^4.0.1 (frontend dependency — D-19, GFM tables)
  reused:
    - respx>=0.21,<1 (already pinned in backend/pyproject.toml line 33 — Phase 5)
    - anthropic>=0.30,<1 (already pinned — Phase 5)
    - pyyaml (installed into dev venv for adversarial YAML loading)
  patterns:
    - dict-builder factory (mirrors insight_factory.py)
    - INVERSE grep gate (mirrors AI-09)
    - module-level pytest.skip env gate (cost-spike protection)
key-files:
  created:
    - backend/tests/unit/chat/__init__.py
    - backend/tests/unit/chat/conftest.py (212 lines)
    - backend/tests/unit/chat/test_anthropic_scope.py (108 lines)
    - backend/tests/integration/chat/__init__.py
    - backend/tests/integration/chat/conftest.py (105 lines)
    - backend/tests/fixtures/chat_factory.py (124 lines)
    - backend/tests/fixtures/anthropic_responses/__init__.py
    - backend/tests/fixtures/anthropic_responses/basic_turn.py (88 lines)
    - backend/tests/fixtures/anthropic_responses/multi_tool.py (191 lines)
    - backend/tests/adversarial/__init__.py
    - backend/tests/adversarial/adversarial_chat_questions.yaml (143 lines, 15 entries)
    - backend/tests/adversarial/test_chat_adversarial.py (97 lines)
    - backend/tests/adversarial/README.md (77 lines)
    - frontend/src/components/chat/__tests__/.gitkeep
    - frontend/src/lib/chat/__tests__/parseSSE.test.ts (55 lines)
    - frontend/tests/e2e/chat.spec.ts (71 lines)
  modified:
    - frontend/package.json (+2 deps)
    - frontend/tsconfig.json (+1 exclude entry)
decisions:
  - "Patch target ORCHESTRATOR_ANTHROPIC_PATCH_TARGET centralized as a single constant in chat unit conftest so future renames in plan 08-04 require updating one string, not N test sites (T-08 tampering mitigation)."
  - "CHAT-08 grep gate uses inverted logic: chat.py absent → vacuous pass; chat.py present → strict-inclusion + strict-exclusion. Gate stays green throughout the phase by design."
  - "Adversarial runner uses module-level pytest.skip(allow_module_level=True) instead of per-test skips so collection itself avoids importing yaml/orchestrator when RUN_ADVERSARIAL!=1."
  - "Vitest contract spec uses `it.todo()` (not `it.fails`) so Wave 0 exits 0 cleanly — production parseSSE.ts arrives in plan 08-06."
  - "Playwright spec uses `test.skip()` and excludes itself from tsconfig.json so the project's `pnpm typecheck` passes without @playwright/test installed."
metrics:
  duration: "~10 minutes"
  completed: 2026-05-29
  tasks_completed: 5
  files_created: 16
  files_modified: 2
  lines_added: ~1271
  commits: 5
---

# Phase 8 Plan 01: Wave 0 Test Infrastructure Summary

Build out every test scaffold, fixture, and gate that plans 08-02..08-06 need to satisfy their per-task `<automated>` verification blocks — without writing any production code. The plan installs the two new frontend markdown deps, creates reusable mock-AsyncAnthropic fixtures + recorded streaming cassettes, installs the CHAT-08 grep gate (inverse of Phase 5 AI-09), and ships an adversarial YAML + env-gated runner so CI cost stays bounded.

## What Was Built

### Task 1 — Package Legitimacy Gate (resolved by user before this agent ran)

User approved `react-markdown@^9`, `remark-gfm@^4` (npm: `remarkjs` org), and `respx>=0.21,<1` (PyPI: `lundberg`, already pinned in pyproject) before the agent resumed. Zero commits on this task (verification only).

### Task 2 — Install BLOCKING dependencies (commit `51675fec`)

- Ran `corepack pnpm add react-markdown@^9 remark-gfm@^4` from the worktree's `frontend/` directory.
- Resolved versions: `react-markdown@9.1.0`, `remark-gfm@4.0.1`. Both landed under `dependencies` (NOT devDependencies — they ship to the browser).
- `backend/pyproject.toml` line 33 already pinned `respx>=0.21,<1` (Phase 5 carry-forward) — no manifest mutation. Existing dev venv contained `respx==0.23.1`; importable.
- **Project convention discovered:** `frontend/pnpm-lock.yaml` is in `frontend/.gitignore` line 41 — the lockfile is intentionally NOT tracked in this project. Only `package.json` was committed. The plan must-have wording ("added to package.json + pnpm-lock.yaml") is interpreted as "lockfile updated on disk during the install" — true — but the lockfile is correctly excluded from git per project convention. Reproducibility is preserved via the `^9` / `^4` version ranges in `package.json`.

### Task 3 — Backend chat test scaffolding (commit `fab5bcfe`)

Eight files (3 package markers + 5 substantive modules, ~720 LOC):

| File | Purpose | Lines |
|------|---------|-------|
| `backend/tests/unit/chat/conftest.py` | tenant_id / user_id / mock_session / mock_anthropic_client / mock_anthropic_class (lazy patch — inert until 08-04) / sse_collector / mock_anthropic_stream factory | 212 |
| `backend/tests/integration/chat/conftest.py` | streaming_client AsyncClient fixture, seeded_conversation dict, integration_skip helper | 105 |
| `backend/tests/fixtures/chat_factory.py` | make_chat_conversation / make_chat_message / make_chat_tool_call / make_chat_turn_pair | 124 |
| `backend/tests/fixtures/anthropic_responses/basic_turn.py` | BASIC_TURN_EVENTS — single-turn Romanian text reply, no tools | 88 |
| `backend/tests/fixtures/anthropic_responses/multi_tool.py` | MULTI_TOOL_EVENTS — 3 distinct tool_use blocks (CHAT-02 SC#2: get_funnel_data + get_salesperson_performance + compare_periods) | 191 |

The conftest exposes `ORCHESTRATOR_ANTHROPIC_PATCH_TARGET = "app.services.chat.orchestrator.AsyncAnthropic"` as a module-level constant. When plan 08-04 lands the orchestrator at a different name, only this one string changes — preventing silent no-op patches across N test sites (T-08 register: tampering mitigation).

### Task 4 — CHAT-08 grep gate (commit `5e1edcc4`)

`backend/tests/unit/chat/test_anthropic_scope.py` (108 lines). Inverted logic from Phase 5 AI-09:

- **Before 08-05** (current state): `chat.py` absent → strict-inclusion clause guarded by `if chat_file.exists()` is skipped; strict-exclusion clause runs against every other `app/api/v1/*.py` file — currently all six pass vacuously (none of them import `AsyncAnthropic` or `client.messages`).
- **After 08-05**: strict-inclusion activates (chat.py MUST contain `AsyncAnthropic`); strict-exclusion still enforces no sibling has it.

Docstring cites CHAT-08, D-25, D-39 explicitly. Verification: `pytest tests/unit/chat/test_anthropic_scope.py` → 1 PASSED.

### Task 5 — Adversarial fixture + env-gated runner (commit `20cc10d4`)

Four files (~317 LOC):

- `backend/tests/adversarial/adversarial_chat_questions.yaml` — 15 trap questions in EXACTLY the 5 required categories × 3:
  - `out_of_scope`: `oos_meta_cac`, `oos_google_roas`, `oos_tiktok_ctr`
  - `date_bounded`: `date_2024_q1`, `date_2025_summer`, `date_2027_forecast`
  - `entity_hallucination`: `entity_maria_popescu`, `entity_ion_ionescu`, `entity_andrei_test`
  - `prompt_injection`: `injection_ignore_previous`, `injection_role_override`, `injection_reveal_tools`
  - `chat05_honesty`: `chat05_meta_cac`, `chat05_google_spend`, `chat05_tiktok_impressions`
- `backend/tests/adversarial/test_chat_adversarial.py` — module-level `pytest.skip(allow_module_level=True)` when `RUN_ADVERSARIAL != "1"`. Bodies raise `NotImplementedError` until plan 08-04 wires the ChatOrchestrator. Loader asserts the exact `len == 15` and category-set distribution at collection time, so YAML drift surfaces immediately.
- `backend/tests/adversarial/README.md` — cost-protection rationale, RUN_ADVERSARIAL=1 + nightly cron documentation.
- `backend/tests/adversarial/__init__.py`

Verification: `pytest tests/adversarial/` → 1 skipped (module-level skip). `RUN_ADVERSARIAL=1 pytest tests/adversarial/ --collect-only` → 15 tests collected.

### Task 6 — Frontend SSE parser test + Playwright stub (commit `ab834557`)

Four files + 1 tsconfig edit:

- `frontend/src/lib/chat/__tests__/parseSSE.test.ts` (55 lines) — Vitest contract spec with 5 `it.todo()` entries (single-event, partial-chunk buffer, heartbeat skip, malformed-JSON tolerance, multi-event chunk). Vitest discovers the file; reports 5 todo, exits 0.
- `frontend/tests/e2e/chat.spec.ts` (71 lines) — Playwright spec with `test.skip(...)` body documenting the CHAT-09 happy-path contract (login → /chat → input visible <5s → assistant bubble <5s → first text <8s).
- `frontend/src/components/chat/__tests__/.gitkeep` — preserves dir for plan 08-06 component tests.
- **Rule 3 fix:** `frontend/tsconfig.json` `exclude` array gained `"tests/e2e/**/*"` so `pnpm typecheck` ignores the Playwright spec (the project doesn't have `@playwright/test` installed yet; install happens in plan 08-06). Playwright specs conventionally live outside the Next.js tsconfig anyway.

Verification: `pnpm vitest --run src/lib/chat/__tests__/parseSSE.test.ts` → `Test Files 1 skipped (1), Tests 5 todo (5)`; `pnpm typecheck` → exit 0; `pnpm lint` → exit 0.

## Overall Verification

All six commands from the plan's `<verification>` block pass:

| # | Command | Result |
|---|---------|--------|
| 1 | `pytest tests/unit/chat/ tests/adversarial/ --collect-only -q` | 1 collected (CHAT-08 gate) + 1 skipped (adversarial module-level) — zero errors |
| 2 | `pytest tests/unit/chat/test_anthropic_scope.py -x` | 1 PASSED |
| 3 | `python -c "import respx, yaml; from tests.fixtures.chat_factory import make_chat_conversation; from tests.fixtures.anthropic_responses.basic_turn import BASIC_TURN_EVENTS"` | exit 0 |
| 4 | `pnpm vitest --run src/lib/chat/__tests__/parseSSE.test.ts` | Test Files 1 skipped, Tests 5 todo |
| 5 | `pnpm typecheck` | exit 0 |
| 6 | `cat package.json \| grep -E '"react-markdown"\|"remark-gfm"'` | both present at `^9.1.0` / `^4.0.1` |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] tsconfig.json must exclude `tests/e2e/**/*` to keep `pnpm typecheck` green**
- **Found during:** Task 6 verification.
- **Issue:** `frontend/tests/e2e/chat.spec.ts` imports from `@playwright/test`, which is intentionally NOT a Wave 0 dependency (added by plan 08-06 per the plan's own `<read_first>` note). With the file in the default tsconfig include glob `**/*.ts`, `tsc --noEmit` failed with `TS7031: Binding element 'page' implicitly has an 'any' type` (line 44).
- **Fix:** Added `"tests/e2e/**/*"` to the `exclude` array in `frontend/tsconfig.json`. This matches the standard Playwright convention (Playwright specs use a separate test runner with its own typing).
- **Files modified:** `frontend/tsconfig.json` (1 line added in `exclude` array).
- **Commit:** `ab834557` (folded into the Task 6 commit since it's the same task scope — the typecheck failure surfaced only after the spec file was written).
- **Why Rule 3, not Rule 4:** No architectural change. This is the standard Next.js + Playwright tsconfig split — the Playwright spec was always meant to live outside the app's tsconfig.

### Project-convention adjustments (no rule needed)

**2. `frontend/pnpm-lock.yaml` is gitignored — not committed**
- **Found during:** Task 2 pre-commit check.
- **Plan wording:** "Frontend has react-markdown@^9 + remark-gfm@^4 installed (added to package.json + pnpm-lock.yaml)". The lockfile IS regenerated on disk during install, but `frontend/.gitignore:41` excludes it from tracking. No commit of pnpm-lock.yaml.
- **Reproducibility:** preserved via the `^9.1.0` / `^4.0.1` ranges in `package.json` plus per-developer `pnpm install`.

## Authentication / Human Gates

Task 1 was a `checkpoint:human-verify` Package Legitimacy Gate. The user reviewed both npm packages on npmjs.com and confirmed `react-markdown` and `remark-gfm` are maintained by the `remarkjs` org with multi-million weekly downloads. `respx` was already pre-approved (existing Phase 5 dev dep). The user responded "approved" and this continuation agent resumed from Task 2.

## Known Stubs (intentional — resolved by future plans)

The following stubs are documented in-code and resolved by named future plans — none of them block the Wave 0 must-haves:

| Stub | File | Reason | Resolved by |
|------|------|--------|-------------|
| `mock_anthropic_class` fixture catches `ModuleNotFoundError` | `backend/tests/unit/chat/conftest.py:104-114` | `app.services.chat.orchestrator` doesn't exist yet | Plan 08-04 |
| `streaming_client` fixture yields `None` if `app.main` not importable | `backend/tests/integration/chat/conftest.py:62-72` | Same — Wave 0 contract | Plan 08-05 |
| Adversarial test bodies raise `NotImplementedError` | `backend/tests/adversarial/test_chat_adversarial.py:84-96` | ChatOrchestrator not yet built | Plan 08-04 |
| `parseSSE.test.ts` uses `it.todo()` | `frontend/src/lib/chat/__tests__/parseSSE.test.ts` | `src/lib/chat/parseSSE.ts` doesn't exist yet | Plan 08-06 |
| `chat.spec.ts` uses `test.skip()` | `frontend/tests/e2e/chat.spec.ts` | Chat UI + login wire-up not yet built; `@playwright/test` not yet a dep | Plan 08-06 |
| `frontend/src/components/chat/__tests__/.gitkeep` empty | (the file itself) | Component tests for MarkdownRenderer / ThinkingIndicator / ToolPill | Plan 08-06 |

Each of these stubs is the EXPLICIT Wave 0 contract per the plan's `<objective>`: "Empty/skeleton test files (RED until later plans fill the production code)". None of them stub a behavior the chat-must-haves require to be live today.

## Threat Flags

None. Wave 0 introduces only test scaffolding. The threat register entries (T-08-01..T-08-SC) are all addressed by design in this plan: per-tenant fixture isolation (T-08-01), env-gated adversarial runner with documented cost-spike landmine (T-08-02 / T-08-04), placeholder PII-free factory data (T-08-05), single-source patch-target constant for cross-plan tampering resistance (T-08).

## Commits (in order)

| Hash | Subject |
|------|---------|
| `51675fec` | `build(08-01): install react-markdown@^9 + remark-gfm@^4 for chat markdown rendering` |
| `fab5bcfe` | `test(08-01): scaffold chat unit + integration test packages with reusable fixtures` |
| `5e1edcc4` | `test(08-01): add CHAT-08 grep gate — AsyncAnthropic only in chat.py` |
| `20cc10d4` | `test(08-01): scaffold adversarial chat fixture + env-gated runner` |
| `ab834557` | `test(08-01): scaffold frontend SSE parser test + Playwright E2E stub` |

A 6th commit follows with this SUMMARY.md.

## Wave 0 Unblocks

Every later plan in Phase 8 now has its scaffolding pre-laid:

- **08-02 (tools registry + handlers)** — uses `chat_factory.py` builders + `mock_session` fixture for unit tests of each of the 12 tools (D-02).
- **08-03 (chat tables + models + repositories)** — uses `chat_factory.py` dict shapes to assert UPSERT behavior against the future SQLAlchemy models.
- **08-04 (orchestrator + hallucination guard + title generator)** — `mock_anthropic_client` + `mock_anthropic_stream` factory + `BASIC_TURN_EVENTS` + `MULTI_TOOL_EVENTS` + adversarial YAML all become live targets.
- **08-05 (chat router + SSE endpoint)** — `sse_collector` + integration `streaming_client` exercise the SSE event schema (D-09); CHAT-08 grep gate activates strict-inclusion mode automatically.
- **08-06 (frontend UI)** — `parseSSE.test.ts` `.todo`s become real assertions; `chat.spec.ts` `test.skip` is lifted; component tests land in `src/components/chat/__tests__/`.

## Self-Check: PASSED

All claimed files exist on disk and every commit is present in the worktree's git log. Spot-checks:

- `[ -f backend/tests/unit/chat/conftest.py ]` → FOUND
- `[ -f backend/tests/unit/chat/test_anthropic_scope.py ]` → FOUND
- `[ -f backend/tests/adversarial/adversarial_chat_questions.yaml ]` → FOUND (15 entries, 5 categories)
- `[ -f frontend/src/lib/chat/__tests__/parseSSE.test.ts ]` → FOUND
- `[ -f frontend/tests/e2e/chat.spec.ts ]` → FOUND
- `git log --oneline | grep 51675fec` → FOUND
- `git log --oneline | grep fab5bcfe` → FOUND
- `git log --oneline | grep 5e1edcc4` → FOUND
- `git log --oneline | grep 20cc10d4` → FOUND
- `git log --oneline | grep ab834557` → FOUND
