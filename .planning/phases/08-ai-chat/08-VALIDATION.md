---
phase: 8
slug: ai-chat
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-29
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: `08-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework (backend)** | pytest 7.x + pytest-asyncio + respx (Anthropic mock) |
| **Framework (frontend)** | Vitest 1.x + React Testing Library + Playwright (E2E) |
| **Config file (backend)** | `backend/pyproject.toml` (pytest section) |
| **Config file (frontend)** | `frontend/vitest.config.ts` |
| **Quick run command (backend)** | `cd backend && pytest tests/unit/chat -q` |
| **Quick run command (frontend)** | `cd frontend && pnpm vitest --run src/components/chat` |
| **Full suite command (backend)** | `cd backend && pytest --cov=app.api.v1.chat --cov=app.services.chat --cov=app.models.chat` |
| **Full suite command (frontend)** | `cd frontend && pnpm vitest --run && pnpm test:e2e -- chat.spec.ts` |
| **Estimated runtime (quick)** | ~25 seconds |
| **Estimated runtime (full)** | ~3 minutes (excludes adversarial nightly fixture) |

---

## Sampling Rate

- **After every task commit:** Run quick command for the touched layer (backend or frontend).
- **After every plan wave:** Run full backend suite (and full frontend suite if any frontend task in the wave).
- **Before `/gsd:verify-work`:** Both full suites must be green.
- **Max feedback latency:** 30 seconds (quick), 180 seconds (full).
- **Adversarial fixture** (`tests/adversarial_chat_questions.yaml`) is NIGHTLY only — not per-commit (real Claude API cost). Tracked separately from the green-bar gate.

---

## Per-Task Verification Map

> Filled by the planner during PLAN.md generation. Each task gets one row here, mapped to its REQ-ID and threat ref. Status updated by execute-phase.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| _to be filled by planner_ | | | | | | | | | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Test infrastructure that must exist before any later wave can run its tests. Per `08-RESEARCH.md`:

- [ ] `backend/tests/unit/chat/__init__.py` — chat unit test package marker
- [ ] `backend/tests/unit/chat/conftest.py` — shared chat fixtures (mock AsyncAnthropic via respx, tenant fixture, db session)
- [ ] `backend/tests/integration/chat/__init__.py` — chat integration test package marker
- [ ] `backend/tests/integration/chat/conftest.py` — SSE client fixture (httpx AsyncClient with streaming), seeded conversation/messages
- [ ] `backend/tests/fixtures/chat_factory.py` — factory_boy or plain functions building chat_conversation / chat_message / chat_tool_call records
- [ ] `backend/tests/fixtures/anthropic_responses/` — recorded Anthropic streaming response cassettes (named events) for deterministic replay
- [ ] `backend/tests/adversarial_chat_questions.yaml` — placeholder (5 categories × 3 questions stub per RESEARCH § Validation Architecture)
- [ ] `frontend/src/components/chat/__tests__/` — RTL test directory + shared render helpers
- [ ] `frontend/tests/e2e/chat.spec.ts` — Playwright E2E stub: open chat, send Romanian question, assert SSE chunks arrive
- [ ] `frontend/src/lib/chat/__tests__/parseSSE.test.ts` — SSE chunk-boundary parser unit test (LM-7 from RESEARCH)
- [ ] **Dependency installs:** `cd backend && uv pip install -e ".[dev]"` (adds `respx` if missing), `cd frontend && pnpm add react-markdown@^9 remark-gfm@^4` (per RESEARCH key finding #1)
- [ ] **CHAT-08 grep gate** — `backend/tests/unit/chat/test_anthropic_scope.py` that fails if any module outside `app/api/v1/chat.py` and `app/tasks/` imports `AsyncAnthropic` (D-25 / D-39)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Streaming feels responsive on real network (first token < 2s, no perceptible stutter) | CHAT-06 / SC#6 | Real-time perception cannot be unit-tested; requires real Anthropic API + browser | 1. `docker compose up -d` 2. Open `/chat` 3. Ask "Cum stăm comparativ cu săptămâna trecută?" 4. Observe first character appears within 2s, tokens stream continuously |
| Romanian language quality of generated titles (D-14) | CHAT-04 (UX) | Linguistic judgment | After 5 fresh conversations, manually verify sidebar titles are coherent, 4-6 words, Romanian, no quotes |
| Tool pill clarity for non-technical owner persona (D-10) | CHAT-07 (transparency) | Subjective UX | Run pilot session with Sofa Belle CEO; collect feedback whether pills "feel right" or noisy; iterate per D-10 humanized-hint heuristic |
| Honest "Nu am acces..." behavior when asking about Iteration-2 data | CHAT-05 / SC#3 | Open-ended phrasing; needs human judgment of honesty | Ask three variants: "Care e CAC-ul Meta?", "Cât am cheltuit pe Google Ads?", "Care e CTR-ul reclamelor TikTok?" — each must produce a refusal containing the phrase "nu am acces" or equivalent (no fabricated numbers) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (chat test packages, fixtures, cassettes, grep gate)
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s (quick), < 180s (full)
- [ ] CHAT-08 grep gate is part of the standing test suite (not nightly-only)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
