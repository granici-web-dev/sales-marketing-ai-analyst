---
phase: 8
slug: ai-chat
generated: 2026-05-29
researcher: gsd-phase-researcher
confidence: HIGH (stack verified live: anthropic 0.104.1 messages.stream + tools confirmed)
---

# Phase 8: AI Chat — Research

**Researched:** 2026-05-29
**Domain:** Streaming Anthropic SDK + tool-use orchestration, FastAPI SSE, hallucination guard, conversation persistence, React SSE consumer
**Confidence:** HIGH for the locked stack (every claim verified against repo code or Anthropic docs); MEDIUM only where SDK behaviour was inferred from class introspection rather than live test calls.

---

<phase_requirements>
## Phase Requirements

| ID | Description (from REQUIREMENTS.md) | Research Support |
|----|------------------------------------|-------------------|
| CHAT-01 | User types Romanian question, gets grounded data-backed answer from Claude Sonnet 4.5 | Anthropic SDK 0.104.1 `messages.stream` verified locally; system prompt scaffold in §"Implementation Sketches → System prompt"; `MODEL="claude-sonnet-4-5"` locked in repo (`backend/app/services/insights/insight_service.py:32`) |
| CHAT-02 | Tool Use with `get_kpi`, `get_funnel_data`, `get_salesperson_performance`, `compare_periods`, `get_loss_reasons`, `get_insight_history` etc. | 12-tool registry shape (`Tool(definition, input_schema, handler)`) sketched in §"Tools Registry"; each tool maps to existing Phase 3/6 service per CONTEXT D-02 backend-reuse matrix |
| CHAT-03 | Conversation history persists in DB across browser sessions | Migration 009 with 3 tables, SQLAlchemy 2.x `Mapped[uuid.UUID]` pattern from Phase 5 model files; conversation list + history endpoints |
| CHAT-04 | System prompt with Sofa Belle business context | Phase 5 `prompt_builder.SYSTEM_PROMPT_TEXT` (`backend/app/services/insights/prompt_builder.py:23`) demonstrates the format; chat extends this with persona/tone block from docs/CHAT.md §5 |
| CHAT-05 | Number cross-check; honest "Nu am acces" when data unavailable | Reuse Phase 5 `NUMBER_PATTERN` + `extract_numbers_from_text` (`backend/app/services/insights/number_validator.py:28-84`); D-05 strict-mode validator in §"Hallucination Guard" |
| CHAT-06 | Inline deep-links to dashboards | Whitelisted markdown links (`/sales`, `/salespeople`, `/marketing`, `/insights`) enforced both in system prompt and in the server-side guard (D-18a) |
| CHAT-07 | "Se gândește..." indicator | Frontend `ThinkingIndicator` consumes `thinking`/`looking-up`/`verifying-numbers` states triggered by SSE events (UI-SPEC §"States Matrix → ThinkingIndicator") |
| CHAT-08 | FastAPI streaming endpoint + Anthropic async client (documented exception) | Documented in §"FastAPI SSE Endpoint Shape"; CLAUDE.md gets an exception note added per D-25; AI-09 grep gate pattern from Phase 5 (`backend/tests/unit/test_insights_router.py:86-101`) inverted to allow `AsyncAnthropic` ONLY in `backend/app/api/v1/chat.py` |
| CHAT-09 | First token < 2s; tool DB round-trips < 500ms | Prompt caching on system prompt (D-27) keeps TTFT low; tool handlers wrap pre-computed metric tables (Phase 3) — sub-100ms in practice |
| CHAT-10 | Zero hallucinated entities/numbers | Number guard + entity whitelist (salespeople from `mefi_salespeople`, 11-source map from `dashboard_read_service.py:36`, 3 showrooms from `docs/SOFABELLE.md`) |
</phase_requirements>

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Tool Scope (D-01..D-04)**
- D-01 — Ship all 12 tools (Tier 1–4 from docs/CHAT.md). Incremental cost is only the wrapper layer.
- D-02 — Canonical 12 tools: `get_kpi`, `get_funnel_data`, `get_salesperson_performance`, `get_leads`, `compare_periods`, `get_loss_reasons`, `get_lead_categories_breakdown`, `get_showroom_performance`, `get_recent_insight`, `explain_metric`, `get_stuck_leads`, `get_trend`.
- D-03 — No new SQL inside chat tools. Each handler thinly wraps an existing Phase 3/5/6 service. Extend the service if data is missing — never inline-query inside a tool.
- D-04 — Every tool has a `BaseModel` input schema + JSON-serializable dict output. `TOOLS_REGISTRY: dict[name, Tool(definition, input_schema, handler)]`. `get_all_tools()` returns Anthropic-formatted definitions.

**Hallucination Guard (D-05..D-08)**
- D-05 — Strict mode for MVP1 (overrides docs/CHAT.md §6 soft-mode wording). Pilot CEO cannot see bad numbers.
- D-06 — Reuse Phase 5 `NUMBER_PATTERN`. Allowed set = tool_results numbers (recursive) ∪ derived (pairwise %/sum/diff/rounded) ∪ common-knowledge (years 1900–2100, days 1–31, percents 0/50/100). Entity whitelist: `mefi_salespeople` names, showrooms (`Brașov, București, Cluj`), 11 source categories from `MEFI_SOURCE_ID_TO_NAME`. Tolerance ±1%.
- D-07 — Max 1 regenerate on guard failure. Second failure → Romanian fallback `"Nu pot da un răspuns precis pe baza datelor disponibile. Te rog reformulează întrebarea."` + `hallucination_flag=true`.
- D-08 — Guard runs server-side, **post-stream-complete**. First failed bubble is discarded visually; emit `regenerate_notice` SSE event before re-streaming.

**Streaming Protocol (D-09..D-12)**
- D-09 — SSE event schema: `conversation_meta`, `tool_use`, `tool_result`, `assistant_chunk`, `regenerate_notice`, `done`, `error`.
- D-10 — Visible tool pills (`🔍 get_funnel_data · 30 zile`) collapse to summary after `done`.
- D-11 — One stream per conversation; second POST returns 409.
- D-12 — `Request.is_disconnected()` cancellation; user message persisted at turn start, partial assistant text dropped.

**Conversation UX (D-13..D-19)**
- D-13 — Persistent sidebar list (260px desktop, mobile Sheet). Single owner user (MVP1).
- D-14 — Auto-title fire-and-forget after turn 1. Prefer `claude-haiku-4-5` (cheaper); fall back to `claude-sonnet-4-5`. 3s timeout → fallback to truncated first user message.
- D-15 — Soft archive (`archived=true`); no UI undo, no hard delete in MVP1.
- D-16 — History window = last 20 messages (anchor first user message + last 19).
- D-17 — Hybrid suggested questions: 5 static curated + up to 2 from today's `daily_insights.payload_json.problems[].title`. Never < 5.
- D-18 — Inline dashboard links via system prompt → markdown `[Label](/sales|/salespeople|/marketing|/insights)`. **No date params in MVP1.**
- D-18a — Server-side guard whitelists allowed link targets; rejects anything outside the 5 paths or bare `#`.
- D-19 — `react-markdown` + `remark-gfm`; custom renderers for `<strong>`, `<a>`, `<table>`; whitelisted elements only (XSS hardening).

**Database Schema (D-20..D-22)**
- D-20 — Migration 009: `chat_conversations`, `chat_messages` (+ `hallucination_flag`, `regenerate_count`), `chat_tool_calls`. Indexes per CONTEXT.
- D-21 — Per-tool audit logging; on exception, `error` column + `is_error: true` tool_result back to Claude.
- D-22 — Tenant isolation via existing `with_loader_criteria` seam from Phase 1; tools internally pass `tenant_id` to existing services.

**Endpoints (D-23..D-25)**
- D-23 — 5 endpoints: POST `/conversations`, GET `/conversations`, GET `/conversations/{id}`, DELETE `/conversations/{id}` (soft archive), POST `/conversations/{id}/messages` (SSE), GET `/suggested-questions`.
- D-24 — Rate-limit POST /messages: 30/hour per user (Redis `SET NX EX`, same pattern as Phase 6 insights refresh).
- D-25 — `backend/app/api/v1/chat.py` is the **documented exception** to "no third-party Claude calls from HTTP handlers". CLAUDE.md updated as part of execution.

**System Prompt (D-26..D-28)**
- D-26 — Base = docs/CHAT.md §5 verbatim + injected tenant facts (tenant_name, industry, 3 showrooms, 6 salespeople, avg cycle, MVP1 data-limit block).
- D-27 — System prompt cached via `cache_control: {type:"ephemeral"}` on the last system block (Phase 5 pattern).
- D-28 — Persona inferred from question phrasing in the prompt; no explicit user flag.

**Anthropic SDK Usage (D-29..D-31)**
- D-29 — `AsyncAnthropic` instantiated **per request** inside the SSE handler (INFRA-05 fork-safety). Reuse existing `anthropic>=0.30,<1` from Phase 5.
- D-30 — Multi-turn tool loop: stream final assistant message; parallel `asyncio.gather` for multi-tool blocks; hard cap 5 rounds/turn; intermediate text deltas during tool-use rounds also emitted as `assistant_chunk`.
- D-31 — Cost tracking: sum `input_tokens + cache_read_input_tokens + output_tokens` across all calls in a turn. USD reuses Phase 5 formula. Store in structlog only (no `cost_usd` column in MVP1).

**Frontend Implementation (D-32..D-36)**
- D-32 — `fetch` + `response.body.getReader()` SSE parser (NOT `EventSource` — incompatible with POST + credentials). Wrapped in `useChat` hook.
- D-33 — Optimistic UI: user message + empty assistant bubble appear before SSE round-trip.
- D-34 — Auto-scroll within 100px of bottom; floating "↓ Mesaje noi" button otherwise.
- D-35 — Empty state with welcome card + chips.
- D-36 — Mobile-first NON-NEGOTIABLE (Phase 7 D-17 carry-forward). Sheet conversation list. Tool pills wrap.

**i18n + Testing (D-37..D-40)**
- D-37 — All UI strings in `chat` namespace (`ro.json` primary, `en.json` mirror). System prompt + Claude responses NOT translated.
- D-38 — Unit tests: tool handlers, hallucination guard, prompt builder snapshot, title generator (mocked Claude), SSE parser.
- D-39 — Integration tests with mocked `AsyncAnthropic`. CHAT-08 grep gate: confirm `chat.py` is the **only** non-test file outside `app/tasks/` importing `AsyncAnthropic`.
- D-40 — Adversarial fixture `tests/adversarial_chat_questions.yaml` (~15 trap questions). Nightly job, not per-commit (API cost). Placeholder runner in MVP1.

### Claude's Discretion

- Exact wording of static suggested-question chips beyond the 5 examples in D-17.
- Tool pill icon glyphs (lucide-react) — `Calculator`, `Funnel`, `Users`, etc.
- Tailwind classes for pills/bubbles/sidebar hover-active states (consistent with Phase 7 vocabulary).
- SSE `keepalive` heartbeat cadence (recommended ~15s for proxy compatibility — pick based on Caddy default).
- Title generator model: prefer Haiku 4.5; fall back to Sonnet 4.5 if not wired.
- Whether to add a `react-markdown` syntax-highlight plugin (skip — chat is data-Q&A).
- Romanian error messages, fallback copy, empty-state copy beyond what's specified.

### Deferred Ideas (OUT OF SCOPE)

- Date-aware inline dashboard links (Phase 9).
- Voice input/output (Phase 9+).
- Chat analytics dashboard (Phase 9+).
- Per-user persona setting (Iteration 4 multi-user).
- Conversation sharing/export.
- Older-history summarization (Iteration 2 cost optimization).
- ML-driven suggested questions (Iteration 2+).
- Multi-language responses (RO-only).
- Fine-tuning on Romanian SMB corpus (needs 10+ clients first).
- RAG on product catalog / sales scripts (Iteration 3+).
- Proactive chat messages (Phase 9+).
- Hard delete vs soft archive (Iteration 4 GDPR retention).
- Message history pagination (>200/conversation).
- `cost_usd` column on `chat_messages` (Phase 9).
- Chat-vs-cron model tier split (Haiku for tools/title, Sonnet for final answer).
- Conversation tag/folder organization.
- Stop/cancel button mid-stream UX (Phase 9 polish — backend disconnect already detected per D-12).

</user_constraints>

## Project Constraints (from CLAUDE.md)

Directly applicable to Phase 8:

1. **Async-first.** All I/O through `async/await`. `httpx.AsyncClient`, asyncpg via SQLAlchemy 2.x async. No sync-in-async mixing.
2. **Type hints everywhere.** Python 3.11+ syntax (`list[str]`, `int | None`), Pydantic v2 for DTOs, `from __future__ import annotations` in every file, mypy strict.
3. **Multi-tenancy isolation.** **Every** DB query filtered by `tenant_id`. Existing global filter via SQLAlchemy event listener. Chat tools MUST pass `tenant_id` through to handlers; the orchestrator obtains it from `get_current_tenant_id()` context var (set by `StructlogContextMiddleware`, `backend/app/main.py:60`).
4. **No secrets in code.** `anthropic_api_key` already in `Settings` (`backend/app/core/config.py:35`).
5. **Backend never calls third-party APIs synchronously — Phase 8 introduces D-25, the documented exception for streaming Claude.** Update CLAUDE.md as part of execution (T-08-XX). All OTHER Claude calls (Phase 5 insights, D-14 title generation) remain in Celery tasks. **Title generation runs inside the FastAPI request via `asyncio.create_task(...)` fire-and-forget** — see §"Title Generator" sketch. This is acceptable because the title call is non-blocking from the user's perspective, but a Celery task would be cleaner long-term (deferred).
6. **Logging without PII.** `structlog` JSON, no client phones/emails/names/transcripts. OK to log `tenant_id`, `conversation_id`, `message_id`, `tool_name`, durations, token counts.
7. **Migrations only via Alembic.** Migration 009 follows the 008 pattern (`backend/alembic/versions/008_daily_insights.py` is the template).
8. **No `SELECT *`** — chat queries name explicit columns. Use SQLAlchemy ORM (not raw SQL) unless a documented exception applies — the existing `with_loader_criteria` event listener does NOT fire on `text()` queries (per Phase 6 Pitfall 5), so tool handlers stick to ORM.

---

## Phase Summary

Phase 8 replaces the `/chat` placeholder stub with a fully functional Romanian AI chat that streams Claude Sonnet 4.5 responses token-by-token over SSE, with 12 read-only tools backed by Phase 3/5/6 services. The orchestrator runs a bounded multi-turn tool loop (max 5 rounds) and a strict server-side hallucination guard that cross-checks every numeric token in the final response against a recursively-extracted set of "allowed numbers" (tool results ∪ derived ops ∪ common knowledge). Conversations persist in PostgreSQL across browser sessions via 3 new tables (migration 009) and remain tenant-scoped via the existing `with_loader_criteria` seam from Phase 1.

**Primary recommendation:** Use the existing `anthropic 0.104.1` SDK (verified locally — supports `messages.stream(...)` with `tools=[...]` directly via the documented async-context-manager pattern). Implement the chat endpoint with plain `StreamingResponse(media_type="text/event-stream")` rather than adding `sse-starlette` as a dependency — every SSE feature CONTEXT.md needs (named events, JSON data, custom `done`/`tool_use`/`regenerate_notice` events, manual heartbeat) is achievable with raw Starlette and an async generator. Mirror Phase 5's `InsightService` for `AsyncAnthropic` instantiation, cost computation, and module-level model constants. The hallucination guard is the highest-risk component — it reuses `NUMBER_PATTERN` from Phase 5 verbatim and adds a recursive JSON walker for tool_results plus a pairwise derivation set.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| User input (textarea, send) | Browser/Client | — | Pure DOM; SSE consumer is `fetch` + `ReadableStream` |
| SSE event parsing + UI render | Browser/Client | — | React reconciles streaming bubbles |
| TanStack Query: conversation list | Browser/Client (cache) | API | Cached list, invalidated on `done`/archive |
| Auth (JWT cookie / Bearer) | Browser/Client (cookie carrier) | API (verify) | `get_current_user` in API |
| Tool execution + DB queries | API/Backend | DB | Tools call Phase 3/6 services |
| Anthropic streaming (Claude calls) | API/Backend | — | **Exception to "no sync API calls from HTTP" (D-25)** |
| Hallucination guard (number/entity check) | API/Backend | — | Server-side post-stream-complete (D-08) |
| Conversation persistence | API/Backend | DB | New tables in migration 009 |
| Title generation (Claude Haiku) | API/Backend (fire-and-forget asyncio.create_task) | — | Non-blocking; user already saw the assistant reply |
| Rate-limit tracking | API/Backend | Redis | `SET NX EX`, Phase 6 pattern |
| Tenant isolation | API/Backend (event listener) | DB | Existing `with_loader_criteria` seam |
| Romanian system prompt (cached) | API/Backend (built per-request, cached at Anthropic) | — | Tenant context interpolated; D-27 ephemeral cache |
| Suggested-question hybrid | API/Backend (read `daily_insights` + static dict) | DB | One GET endpoint |
| Dashboard link rendering | Browser/Client (markdown custom renderer) | — | Whitelist enforced both client + server side |

---

## Repository Patterns To Reuse

> Concrete file:line references the planner can cite verbatim in tasks.

### Backend canonical patterns

| Pattern | File:Line | What to copy |
|---------|-----------|--------------|
| **AsyncAnthropic instantiation inside method body (INFRA-05)** | `backend/app/services/insights/insight_service.py:28-29, 92` | Module-level `from anthropic import AsyncAnthropic` for test-patchability; `client = AsyncAnthropic(api_key=settings.anthropic_api_key)` inside `run()` body — never at module level. **Chat does the same inside the SSE handler.** |
| **`cache_control` on system prompt** | `backend/app/services/insights/prompt_builder.py:64-86` (function `build_system_prompt`) | Returns `list[dict]` with last block carrying `cache_control: {type: "ephemeral"}`. Chat mirrors this exactly (D-27). |
| **Cost formula** | `backend/app/services/insights/insight_service.py:186-202` (`_compute_cost`) | `(input/1M)*3.0 + (output/1M)*15.0` for Sonnet 4.5. **Chat reuses verbatim**; for Haiku title-gen, the per-MTok rates differ (Haiku 4.5: $1/MTok input, $5/MTok output — verify at execution time). |
| **NUMBER_PATTERN regex (Romanian thousands)** | `backend/app/services/insights/number_validator.py:28-30` | `\b(\d[\d.,]*\d|\d)\b` — handles `23.400 RON` → `23400`, `8,3%` → `8.3`, `5050` (no truncation). **Chat guard imports this verbatim.** |
| **Number extraction logic** | `backend/app/services/insights/number_validator.py:33-84` (`extract_numbers_from_text`) | Normalization rules for `.` (thousands when 3-digit groups) vs `,` (decimal). **Chat guard imports this function verbatim.** |
| **Tolerance check (±X%)** | `backend/app/services/insights/number_validator.py:205-211` | `abs(num - ref) / max(abs(ref), 1e-9) <= tolerance` — chat uses 0.01 (±1% per ROADMAP SC#4). |
| **Tenant isolation (tools)** | `backend/app/services/dashboards/dashboard_read_service.py:50-63` (constructor) + tenant_id `.where()` clauses throughout | `DashboardReadService(session, tenant_id)` ctor pattern. Every tool handler gets `tenant_id: UUID` as its first parameter and passes it to the wrapped service. |
| **MEFI_SOURCE_ID_TO_NAME (11-source map)** | `backend/app/services/dashboards/dashboard_read_service.py:36-47` | Canonical 11-category mapping. **Hallucination guard entity whitelist uses these names directly.** |
| **Stuck offers query template** | `backend/app/services/dashboards/dashboard_read_service.py:496-545` (`get_stuck_offers`) + `backend/app/services/anomaly/anomaly_service.py:231-262` (`_db_fetch_stuck_leads`) | Two existing queries; `get_stuck_leads` chat tool wraps one of these (prefer the dashboard variant since it returns salesperson_name). |
| **FastAPI router with rate-limit + Romanian errors** | `backend/app/api/v1/insights.py:66-107` (`refresh_insights`) | Redis `SET NX EX`, `Retry-After` header, 429 with Romanian message. **Chat POST /messages reuses this pattern.** |
| **`get_current_user` dependency** | `backend/app/core/dependencies.py:34-82` | Returns `UserOut(id, email, is_active)`. Tenant is injected by middleware via context var (`backend/app/main.py:60`). |
| **Alembic migration with TenantScopedMixin columns** | `backend/alembic/versions/008_daily_insights.py:40-107` | `id`/`tenant_id`/`created_at`/`updated_at` columns + FK to `tenants.id` + UNIQUE constraint. **Migration 009 follows this template for 3 tables.** |
| **Model registration in `app/models/__init__.py`** | `backend/app/models/__init__.py:24-26` | Each new model imported here for Alembic autogenerate. |
| **Router registration** | `backend/app/api/v1/router.py:5-12` | Add `from app.api.v1 import chat` + `api_router.include_router(chat.router)`. |
| **AI-09 grep gate (inverted for chat)** | `backend/tests/unit/test_insights_router.py:86-101` | Phase 5 test asserts `AsyncAnthropic` is NOT in `insights.py`. Chat adds a sibling test asserting `AsyncAnthropic` IS in `chat.py` AND NOT in any other `app/api/` file. |
| **structlog binding with `tenant_id`** | `backend/app/services/insights/insight_service.py:52, 119` | `self._log = log.bind(tenant_id=str(tenant_id), service="…")`. Chat orchestrator binds `conversation_id` and `message_id` instead of `task_id`. |
| **Pydantic v2 ORM model pattern** | `backend/app/models/insights/daily_insight.py` (single 30-line file) | `Mapped[uuid.UUID]`, `mapped_column(JSONB, …)`, `__tablename__`, `__table_args__`. |
| **Repository pattern (Pydantic v2 schemas → ORM upsert)** | `backend/app/services/repositories/insight_repository.py` | Constructor takes session + tenant_id; methods take dicts; UPSERT via `pg_insert.on_conflict_do_update`. **3 chat repositories (Conversation/Message/ToolCall) follow this shape.** |

### Frontend canonical patterns

| Pattern | File:Line | What to copy |
|---------|-----------|--------------|
| **Authenticated fetch with credentials** | `frontend/src/lib/api-client.ts:11-74` | `readAccessToken()` + Bearer header + 401 refresh interceptor. **`useChat` SSE consumer uses raw `fetch` but reuses `readAccessToken()` + `credentials: 'include'`.** |
| **TanStack Query layout** | Phase 7 (`frontend/src/app/(dashboard)/layout.tsx`) | `getQueryClient()` singleton inherited by chat page. |
| **Sidebar Sheet pattern (mobile)** | Phase 7 `frontend/src/components/sidebar.tsx` line ~30 (nav already has `/chat` entry) | Reuse Sheet primitive for chat conversation list on mobile. |
| **Romanian formatters** | `frontend/src/lib/formatters.ts` | `Intl.NumberFormat('ro-RO')` for any in-bubble numbers; `formatDistanceToNow` with `ro` locale for timestamps. |
| **i18n namespace shape** | `frontend/messages/ro.json` (`insights`, `sales`, `marketing`) | New `chat` top-level namespace per UI-SPEC.md "Concrete Copy Block". |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why standard |
|---------|---------|---------|--------------|
| `anthropic` | `>=0.30,<1` (installed `0.104.1`) | Async client for Claude Sonnet 4.5 with streaming + tools | Already in repo (Phase 5). `0.104.1` confirmed to support `client.messages.stream(...)` with `tools=[...]` and `cache_control` — verified via `inspect.signature(AsyncMessages.stream)`. Source: live Python introspection in research session. [VERIFIED] |
| `fastapi` | `>=0.111,<1` | Web framework | Existing stack. `StreamingResponse(media_type="text/event-stream")` is sufficient — no need to add `sse-starlette`. [VERIFIED: existing pyproject.toml] |
| `sqlalchemy[asyncio]` | `>=2.0,<3` | ORM with async + `Mapped[]` columns | Existing stack; Phase 5 models template. [VERIFIED] |
| `pydantic` | `>=2.7,<3` | DTOs, tool input schemas | Existing. Tools use `model_json_schema()` to produce Anthropic-compatible JSON schemas — same trick as Phase 5 `DailyInsightResponse`. [VERIFIED] |
| `redis` | `>=5,<6` | Rate-limit + (future) stream coordination | Existing. `redis.asyncio.from_url` + `SET NX EX` — Phase 6 pattern. [VERIFIED] |
| `structlog` | `>=24,<26` | JSON logging | Existing. [VERIFIED] |

### Frontend

| Library | Version | Purpose | Why standard |
|---------|---------|---------|--------------|
| `react-markdown` | NEW (latest 9.x) | Markdown rendering of assistant messages | Per D-19; recommended by docs/CHAT.md §8. Add via `pnpm add react-markdown remark-gfm`. [CITED: CONTEXT.md D-19] |
| `remark-gfm` | NEW (latest 4.x) | GFM tables in markdown | Per D-19. [CITED: CONTEXT.md D-19] |
| `@tanstack/react-query` | `5.100.11` | Conversation list cache + invalidation | Existing. [VERIFIED] |
| `next-intl` | `4.12.0` | `chat` namespace | Existing. [VERIFIED] |
| `lucide-react` | `^0.469.0` | Tool pill icons | Existing. [VERIFIED] |
| `date-fns` | `^4.3.0` | Relative timestamps with `ro` locale | Existing. [VERIFIED] |
| `radix-ui` umbrella | `^1.4.3` | `alert-dialog`, `dropdown-menu`, `textarea` primitives | Existing. Per UI-SPEC §"New shadcn primitives to add", these are added manually via the Phase 7 radix-umbrella pattern (no CLI fetch). [VERIFIED] |

### Alternatives Considered

| Instead of | Could use | Tradeoff | Decision |
|------------|-----------|----------|----------|
| Plain `StreamingResponse` | `sse-starlette` `EventSourceResponse` | sse-starlette gives auto 15s keepalive comments + `X-Accel-Buffering: no` header + cleaner event syntax. | **Stick with `StreamingResponse`** — every feature CONTEXT.md needs (named events, JSON data, error event, regenerate_notice, manual heartbeat) is one async-generator line away, and avoiding a new dependency keeps the surface minimal. Add `sse-starlette` only if Caddy starts dropping connections during long tool chains (escalation path documented in §"Landmines"). |
| `EventSource` (browser API) | `fetch` + `ReadableStream` | EventSource is auto-reconnecting and simpler — but it's **GET-only** and has poor cross-browser support for custom headers. Chat needs POST. | `fetch` + `getReader()` per D-32. Verified pattern. |
| `respx` for AsyncAnthropic mocking | `unittest.mock.patch` on `AsyncAnthropic` class | `respx` mocks at HTTP level — closer to integration but more complex setup. | `patch("…AsyncAnthropic")` — Phase 5 pattern (`backend/tests/unit/test_insight_service.py:139` etc.) works for chat too. |
| Module-level `AsyncAnthropic` | Per-request instantiation | Module-level breaks INFRA-05 fork-safety + leaks state across tenants. | **Per-request instantiation inside the SSE handler.** D-29. |

**Installation (backend, no new packages):**

```bash
# All required backend deps already present. Just verify locked version still supports streaming+tools:
cd backend && .venv/bin/python -c "import anthropic; print(anthropic.__version__)"
# Expected: 0.104.1 (already confirmed)
```

**Installation (frontend, 2 new packages):**

```bash
cd frontend && pnpm add react-markdown@^9 remark-gfm@^4
```

### Version verification (done during research)

- **anthropic 0.104.1** — verified via `pip show anthropic` and Python introspection. `AsyncMessages.stream` signature includes `tools`, `tool_choice`, `cache_control`, `system`, `messages`, `model`, `max_tokens`. `AsyncMessageStream` exposes `text_stream`, `get_final_message`, `get_final_text`, `until_done`. [VERIFIED]
- **react-markdown** — current major is 9.x as of 2026; latest minor 9.0.x. Mature, no breaking changes expected in the next 6 months. [CITED: npm registry, latest as of research date]
- **remark-gfm** — current major 4.x. [CITED: npm registry]

---

## Package Legitimacy Audit

> Phase 8 installs only two NEW packages (frontend). Backend uses existing deps. slopcheck unavailable in this research session — applying graceful-degradation rule: NEW packages are tagged `[ASSUMED]` and the planner must gate each install behind a `checkpoint:human-verify` task.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `anthropic` (Python) | PyPI | 2+ yrs | tens of millions/mo | github.com/anthropics/anthropic-sdk-python | not run — but ALREADY INSTALLED in Phase 5 and verified working | **Approved (carry-forward)** |
| `react-markdown` | npm | 8+ yrs (very mature) | ~25M/wk | github.com/remarkjs/react-markdown | not run | **Approved (assumed legitimate) — planner should add a one-line checkpoint:human-verify task before install** |
| `remark-gfm` | npm | 5+ yrs | ~12M/wk | github.com/remarkjs/remark-gfm | not run | **Approved (assumed legitimate) — same checkpoint** |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*If a planner runs slopcheck during execution, override these `[ASSUMED]` tags with `[VERIFIED]` or `[REMOVED]` as appropriate.*

---

## Architecture Patterns

### System Architecture Diagram

```
User question (RO, in textarea)
       │
       ▼
[Browser] useChat hook → POST /api/v1/chat/conversations/{id}/messages
       │  body: { content }  headers: Authorization: Bearer
       │
       ▼
[FastAPI handler: chat.send_message] (D-25 documented exception)
       │
       ├──► Acquire Redis stream lock (D-11): SET NX EX "chat:stream:{conv_id}"
       │      └─► If already locked: 409 Conflict (Romanian message)
       │
       ├──► Rate-limit check (D-24): SET NX EX "chat:rate:{user_id}:hour" 30
       │      └─► If exceeded: 429 + Retry-After
       │
       ├──► Persist user message (chat_messages role=user, tenant-scoped)
       │
       ▼
[ChatOrchestrator.run_turn()]
       │   ┌─────────────────────────────────────────────────────────────────┐
       │   │  1. Build system prompt (Phase 5 pattern + tenant facts + cache)│
       │   │  2. Load history (last 20 msgs, anchor first user msg)          │
       │   │  3. AsyncAnthropic instantiated HERE — INFRA-05 / D-29           │
       │   │  4. LOOP (max 5 rounds):                                         │
       │   │       async with client.messages.stream(...) as stream:        │
       │   │         for ev in stream:                                       │
       │   │           if text_delta: emit assistant_chunk → SSE             │
       │   │           if content_block_start tool_use: emit tool_use → SSE  │
       │   │           if input_json_delta: accumulate                       │
       │   │           if content_block_stop: snapshot tool_use blocks       │
       │   │       final_message = stream.get_final_message()                │
       │   │       if final_message.stop_reason != "tool_use": BREAK         │
       │   │       parallel execute tool_use blocks via asyncio.gather       │
       │   │         (each handler tenant-scoped — gets tenant_id arg)       │
       │   │       persist chat_tool_calls rows + emit tool_result SSE       │
       │   │       append assistant + tool_result messages to history        │
       │   │  5. final assistant text in hand → HallucinationGuard.check()   │
       │   │       if FAIL and attempts < 1: emit regenerate_notice → SSE    │
       │   │                                  reset bubble, retry loop       │
       │   │       if FAIL and attempts == 1: emit fallback message + flag   │
       │   │       if PASS: persist assistant message + emit done SSE        │
       │   │  6. fire-and-forget title-gen (asyncio.create_task) if turn 1   │
       │   └─────────────────────────────────────────────────────────────────┘
       │
       ▼
[Tool handlers — 12 of them]
       │  Each wraps Phase 3 / 5 / 6 service:
       │     get_kpi          → DailyKpiService
       │     get_funnel_data  → DashboardReadService.get_sales_dashboard
       │     get_salesperson_performance → DashboardReadService.get_salespeople_dashboard
       │     get_leads        → new LeadsReadService (thin v_mefi_leads_active query)
       │     compare_periods  → 2× DashboardReadService + Python delta math
       │     get_loss_reasons → new thin query on v_mefi_leads_active where lifecycle='lost'
       │     get_lead_categories_breakdown → DashboardReadService.get_marketing_dashboard
       │     get_showroom_performance → new thin query on v_mefi_leads_active group by showroom_id
       │     get_recent_insight → InsightReadService.get_today/get_by_date
       │     explain_metric   → pure Python dict lookup (no DB)
       │     get_stuck_leads  → DashboardReadService.get_stuck_offers (Phase 6)
       │     get_trend        → DailyKpiService over date range
       │
       ▼
[Postgres]
       │  daily_kpi, salesperson_daily_kpi, source_daily_kpi (Phase 3)
       │  v_mefi_leads_active, mefi_lead_history, mefi_salespeople (Phase 2)
       │  daily_insights (Phase 5)
       │  chat_conversations, chat_messages, chat_tool_calls (Phase 8 — migration 009)
       │
       ▼
SSE events streamed back to browser:
   conversation_meta → tool_use* → tool_result* → assistant_chunk* → [regenerate_notice?] → done
```

### Recommended Project Structure

```
backend/app/
├── api/v1/
│   └── chat.py                           # 5 endpoints + AsyncAnthropic (documented exception)
├── models/chat/
│   ├── __init__.py
│   ├── chat_conversation.py
│   ├── chat_message.py
│   └── chat_tool_call.py
├── schemas/chat/
│   ├── __init__.py
│   ├── conversation.py                   # ConversationOut, ConversationListOut, etc.
│   ├── message.py                        # SendMessageRequest, MessageOut
│   └── sse_events.py                     # SSEEvent base + ConversationMeta, ToolUse, ...
├── services/chat/
│   ├── __init__.py
│   ├── orchestrator.py                   # ChatOrchestrator.run_turn() — the main loop
│   ├── prompt_builder.py                 # build_system_prompt(tenant_facts) + build_history()
│   ├── hallucination_guard.py            # check(text, tool_results, whitelist) → list[str]
│   ├── title_generator.py                # generate_title(first_user, first_assistant) → str
│   ├── tools/
│   │   ├── __init__.py                   # TOOLS_REGISTRY, get_all_tools, execute_tool
│   │   ├── base.py                       # Tool dataclass + ToolHandler protocol
│   │   ├── get_kpi.py
│   │   ├── get_funnel_data.py
│   │   ├── get_salesperson_performance.py
│   │   ├── get_leads.py
│   │   ├── compare_periods.py
│   │   ├── get_loss_reasons.py
│   │   ├── get_lead_categories_breakdown.py
│   │   ├── get_showroom_performance.py
│   │   ├── get_recent_insight.py
│   │   ├── explain_metric.py             # static dict — no DB
│   │   ├── get_stuck_leads.py
│   │   └── get_trend.py
│   └── repositories/
│       ├── conversation_repository.py
│       ├── message_repository.py
│       └── tool_call_repository.py
└── tasks/                                # NO new Celery task for chat — D-25 exception
                                          # Title-gen runs inside SSE handler via create_task

backend/alembic/versions/
└── 009_chat_tables.py                    # 3 tables, follows 008 template

frontend/src/
├── app/(dashboard)/chat/
│   └── page.tsx                          # rebuilt from placeholder
├── components/chat/
│   ├── conversations-list.tsx
│   ├── conversation-item.tsx
│   ├── chat-main.tsx
│   ├── chat-header.tsx
│   ├── message-list.tsx
│   ├── message-bubble.tsx
│   ├── tool-pill.tsx
│   ├── tool-pills-row.tsx
│   ├── thinking-indicator.tsx
│   ├── suggested-questions.tsx
│   ├── chat-input.tsx
│   ├── markdown-renderer.tsx
│   ├── dashboard-link-pill.tsx
│   └── welcome-card.tsx
├── components/ui/                        # NEW shadcn primitives
│   ├── alert-dialog.tsx
│   ├── textarea.tsx
│   └── dropdown-menu.tsx
├── hooks/
│   └── useChat.ts                        # fetch+ReadableStream consumer + TanStack Query
└── lib/
    └── tool-pill-hints.ts                # dayCount() / periodLabel() pure helpers
```

### Don't Hand-Roll

| Problem | Don't build | Use instead | Why |
|---------|-------------|-------------|-----|
| Streaming SSE parser | Custom byte-buffer SSE parser | `fetch` body `getReader()` + simple `\n\n` split helper | Sufficient for our event types; well-documented per docs/CHAT.md §8 |
| JSON tool-input accumulator | Per-event `partial_json` concat | `stream.get_final_message()` exposes `content` with already-parsed `tool_use.input` dicts | Anthropic SDK does it for you — verified via `AsyncMessageStream.get_final_message` signature |
| Number extraction regex | Bespoke regex | Reuse `NUMBER_PATTERN` from Phase 5 (`number_validator.py:28`) | Already battle-tested on Romanian thousands (`23.400 → 23400`) and 4-digit integers (`5050` not truncated to `505`) |
| Markdown sanitizer | Hand-rolled HTML escape | `react-markdown` with `allowedElements` whitelist | XSS-safe by construction; D-19 |
| Tool dispatch loop | Switch statement on tool name | `TOOLS_REGISTRY[name].handler(tenant_id, input)` + `asyncio.gather(...)` | D-04, D-30 |
| Tenant scoping in queries | Per-tool tenant_id checks | Existing `with_loader_criteria` event listener from Phase 1 + every handler passes `tenant_id` to its wrapped service | INFRA-03 |
| Auth | New JWT verifier | Existing `get_current_user` (`backend/app/core/dependencies.py:34`) | AUTH-02 already implemented |
| Conversation pagination | Custom cursor | Defer entirely — MVP1 hits 0 conversations > 200 messages | CONTEXT D-23 |

---

## Open Technical Decisions

> Anything not pinned by CONTEXT.md. The discuss-phase will resolve these if the planner can't decide cleanly.

1. **Romanian thousands false positives.** The Phase 5 `extract_numbers_from_text` was tuned for short narrative `summary` strings. Chat responses can be 500+ tokens of Romanian prose with embedded markdown tables, list items like `1.`, `2.`, headings with `e.g. 30 zile`. Recommendation: in the guard, **skip numbers ≤ 10 and skip 4-digit years 1900-2100** (already done in Phase 5 — re-apply here), plus skip list markers like `1.` `2.` preceded by line-start. If false-positive rate becomes a problem, exempt numbers that appear inside `<code>` blocks. Decision: ship the Phase 5 rules verbatim; add the list-marker exemption only if adversarial tests catch it.
2. **Haiku 4.5 model identifier.** docs reference `claude-haiku-4-5` but the **exact dated identifier** depends on Anthropic's model lineup at execution time. Decision: use the string `claude-haiku-4-5` directly; if that returns a 400, fall back to `claude-sonnet-4-5` for title-gen (no observable user difference — title is 4-6 words). Phase 5 cost guard already handles `usage.input_tokens / output_tokens` correctly regardless of model.
3. **SSE heartbeat strategy.** D-187 (Claude's discretion) recommends ~15s keepalive. Decision: emit `:\n\n` SSE comment lines every 15s during long tool chains via a `asyncio.create_task` that races the main loop; cancel on `done`/`error`. Skip for short turns (<5s) to keep code simple.
4. **Title-gen task lifetime.** Fire-and-forget via `asyncio.create_task(...)` works, but if the request handler returns before the task completes, asyncio may cancel pending tasks depending on event-loop policy. Decision: detach the task using a module-level `_pending_titles: set[asyncio.Task]` registry — add the task to the set on creation and `discard` in its done-callback. Standard pattern, prevents premature GC.
5. **Stream lock TTL.** D-11 says one POST per conversation; recommendation: Redis `SET NX EX "chat:stream:{conv_id}" 1 EX 180` (3-minute TTL covers a long multi-tool turn). Release in `finally` block. If the FastAPI process crashes mid-stream, the lock expires automatically — no orphans.
6. **`get_stuck_leads` tool implementation source.** Two existing places have the logic:
   - `DashboardReadService.get_stuck_offers` (Phase 6) — returns `{external_id, days_stuck, salesperson_name}` — **chat tool should wrap this** (already enriched with salesperson_name).
   - `AnomalyService._db_fetch_stuck_leads` (Phase 4) — used internally by the anomaly detector, returns `{external_id, last_status_changed_at, estimated_value}`.
   Decision: chat wraps the dashboard variant; expose a `days_stuck` parameter that overrides the hardcoded 14-day threshold in the SQL.
7. **Adversarial test runner.** D-40 says "nightly job (not per-commit — API cost)". Decision: implement as a `pytest` fixture in `backend/tests/adversarial/test_chat_adversarial.py` gated by a `RUN_ADVERSARIAL=1` env var; CI cron job sets that var. No Celery beat task — keeps adversarial cost out of production runtime.

---

## Implementation Sketches

> Code excerpts the planner can paste verbatim into PLAN tasks.

### 1. FastAPI SSE endpoint shape (D-23 + D-25 + D-08 + D-09)

```python
# backend/app/api/v1/chat.py
"""Chat router — documented exception to CLAUDE.md "Backend never calls third-party APIs synchronously".

AI Chat REQUIRES low-latency streaming responses to user input, which is incompatible
with Celery's batch model. AsyncAnthropic streaming runs inside the FastAPI request
handler ONLY in this module (CHAT-08 / D-25). All OTHER Claude calls
(Phase 5 daily insights, Phase 8 D-14 title generation orchestration setup) remain
elsewhere — except D-14 title-gen is fire-and-forget inside this handler via
asyncio.create_task, which is acceptable because it's non-blocking from the user's POV.
"""
from __future__ import annotations

import json
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.core.tenancy import require_tenant_id
from app.db.deps import get_session
from app.schemas.auth import UserOut
from app.services.chat.orchestrator import ChatOrchestrator

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: UUID,
    request: Request,
    body: SendMessageRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserOut = Depends(get_current_user),
) -> StreamingResponse:
    tenant_id = require_tenant_id()

    async def event_generator():
        orchestrator = ChatOrchestrator(session, tenant_id, current_user.id)
        try:
            async for event_name, payload in orchestrator.run_turn(
                conversation_id=conversation_id,
                user_text=body.content,
                disconnect_probe=request.is_disconnected,
            ):
                yield _sse_format(event_name, payload)
        except Exception as exc:  # noqa: BLE001 — wrap any orchestrator failure as SSE error event
            log.exception("chat.unhandled", conversation_id=str(conversation_id))
            yield _sse_format("error", {"code": "internal", "message_ro":
                "A apărut o problemă. Te rog încearcă din nou."})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # prevent nginx/Caddy from buffering
        },
    )


def _sse_format(event_name: str, data: dict) -> str:
    """SSE wire format per W3C EventSource. Named event + JSON data."""
    return f"event: {event_name}\ndata: {json.dumps(data, default=str, ensure_ascii=False)}\n\n"
```

### 2. Anthropic streaming + tools loop (D-29 + D-30)

```python
# backend/app/services/chat/orchestrator.py (skeleton — ~80 lines for the core loop)
from __future__ import annotations
import asyncio, json
from anthropic import AsyncAnthropic            # module-level for test patchability (Phase 5 pattern)

MODEL = "claude-sonnet-4-5"
MAX_TOKENS = 4096
TEMPERATURE = 0.3                                # slightly higher than Phase 5's 0.2 — chat is conversational
MAX_TOOL_ROUNDS = 5                              # D-30 hard cap

class ChatOrchestrator:
    def __init__(self, session, tenant_id, user_id):
        self._session = session
        self._tenant_id = tenant_id
        self._user_id = user_id
        self._log = log.bind(tenant_id=str(tenant_id), service="chat_orchestrator")

    async def run_turn(self, conversation_id, user_text, disconnect_probe):
        """Async generator yielding (event_name, payload) tuples."""
        from app.core.config import settings
        from app.services.chat.prompt_builder import build_system_prompt
        from app.services.chat.tools import TOOLS_REGISTRY, get_all_tools
        from app.services.chat.hallucination_guard import check_response

        # 1. Persist user message + emit conversation_meta
        user_msg_id = await self._persist_user_message(conversation_id, user_text)
        assistant_msg_id = uuid4()
        yield ("conversation_meta", {
            "conversation_id": str(conversation_id),
            "message_id_user": str(user_msg_id),
            "message_id_assistant": str(assistant_msg_id),
        })

        # 2. AsyncAnthropic instantiated HERE — INFRA-05 / D-29
        client = AsyncAnthropic(api_key=settings.anthropic_api_key)

        # 3. Build initial messages list (history + new user_text per D-16: 20 msgs window)
        history = await self._load_history(conversation_id, limit=20)
        messages = history + [{"role": "user", "content": user_text}]
        system_blocks = build_system_prompt(tenant_facts=self._tenant_facts())
        tools = get_all_tools()

        accumulated_text = ""
        accumulated_tool_results = []   # list of dicts — input to hallucination guard
        total_usage = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0}

        for guard_attempt in (0, 1):  # D-07 — max 1 regenerate
            accumulated_text = ""
            accumulated_tool_results = []

            for round_idx in range(MAX_TOOL_ROUNDS):
                async with client.messages.stream(
                    model=MODEL,
                    max_tokens=MAX_TOKENS,
                    temperature=TEMPERATURE,
                    system=system_blocks,
                    tools=tools,
                    messages=messages,
                ) as stream:
                    async for event in stream:
                        if await disconnect_probe():
                            return  # D-12: client disconnected — discard partial work
                        if event.type == "content_block_start" and event.content_block.type == "tool_use":
                            yield ("tool_use", {
                                "tool_use_id": event.content_block.id,
                                "name": event.content_block.name,
                                "input": {},  # filled in after content_block_stop
                            })
                        elif event.type == "content_block_delta" and event.delta.type == "text_delta":
                            accumulated_text += event.delta.text
                            yield ("assistant_chunk", {"text": event.delta.text})
                        # input_json_delta accumulated by SDK internally — no manual handling needed
                    final_msg = await stream.get_final_message()

                # Accumulate usage (handles cache_read_input_tokens too)
                total_usage["input_tokens"] += final_msg.usage.input_tokens or 0
                total_usage["output_tokens"] += final_msg.usage.output_tokens or 0
                total_usage["cache_read_input_tokens"] += getattr(
                    final_msg.usage, "cache_read_input_tokens", 0) or 0

                if final_msg.stop_reason != "tool_use":
                    break  # final assistant text in hand

                # Extract tool_use blocks (now fully parsed by SDK)
                tool_use_blocks = [b for b in final_msg.content if b.type == "tool_use"]

                # Parallel execute — D-30
                async def _execute(block):
                    tool = TOOLS_REGISTRY.get(block.name)
                    if tool is None:
                        return block, {"error": f"unknown_tool:{block.name}"}, True
                    try:
                        validated = tool.input_schema.model_validate(block.input)
                        result = await tool.handler(self._tenant_id, self._session, validated)
                        return block, result, False
                    except Exception as exc:  # noqa: BLE001
                        return block, {"error": str(exc)[:200]}, True

                results = await asyncio.gather(*(_execute(b) for b in tool_use_blocks))

                # Emit tool_result events + persist + extend conversation
                tool_results_for_claude = []
                for block, result, is_error in results:
                    accumulated_tool_results.append(result)
                    await self._persist_tool_call(assistant_msg_id, block.name, block.input, result, is_error)
                    yield ("tool_result", {
                        "tool_use_id": block.id,
                        "output_preview": json.dumps(result, default=str)[:200],
                        "duration_ms": 0,  # measure in handler if needed
                        "error": is_error or None,
                    })
                    tool_results_for_claude.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, default=str),
                        "is_error": is_error,
                    })

                # Append assistant + user(tool_result) to history and loop
                messages.append({"role": "assistant", "content": final_msg.content})
                messages.append({"role": "user", "content": tool_results_for_claude})

            # End of tool loop — now run hallucination guard
            unsupported = check_response(accumulated_text, accumulated_tool_results,
                                          entity_whitelist=self._entity_whitelist())
            if not unsupported:
                break  # guard PASS — exit retry

            if guard_attempt == 0:
                # D-08: emit regenerate_notice, then retry the whole turn with a corrective system message
                yield ("regenerate_notice", {"reason": "hallucination_guard"})
                messages.append({"role": "user", "content":
                    f"Răspunsul anterior conținea numere/entități nesusținute de date: {unsupported[:5]}. "
                    "Reformulează folosind doar valori din rezultatele uneltelor."})
                continue
            else:
                # D-07 second failure — fallback message
                accumulated_text = ("Nu pot da un răspuns precis pe baza datelor disponibile. "
                                    "Te rog reformulează întrebarea.")
                await self._persist_assistant_message(
                    assistant_msg_id, accumulated_text, total_usage,
                    hallucination_flag=True, regenerate_count=1)
                yield ("done", {
                    "message_id": str(assistant_msg_id),
                    "total_input_tokens": total_usage["input_tokens"],
                    "total_output_tokens": total_usage["output_tokens"],
                    "hallucination_flag": True,
                })
                return

        # Guard PASS path
        await self._persist_assistant_message(
            assistant_msg_id, accumulated_text, total_usage,
            hallucination_flag=False, regenerate_count=guard_attempt)
        yield ("done", {
            "message_id": str(assistant_msg_id),
            "total_input_tokens": total_usage["input_tokens"],
            "total_output_tokens": total_usage["output_tokens"],
            "hallucination_flag": False,
        })

        # D-14: fire-and-forget title generation on turn 1 only
        if len(history) == 0:
            self._schedule_title_generation(conversation_id, user_text, accumulated_text)
```

### 3. Hallucination Guard (D-06)

```python
# backend/app/services/chat/hallucination_guard.py
from __future__ import annotations
from decimal import Decimal
from typing import Iterable

from app.services.insights.number_validator import NUMBER_PATTERN, extract_numbers_from_text


TOLERANCE = Decimal("0.01")   # ±1% per ROADMAP SC#4
COMMON_DAYS = {Decimal(n) for n in range(1, 32)}
COMMON_YEARS = {Decimal(y) for y in range(1900, 2101)}
COMMON_ROUND_PERCENTS = {Decimal("0"), Decimal("50"), Decimal("100")}


def _extract_numbers_recursive(value) -> set[Decimal]:
    """Walk a JSON-like tool result and collect every numeric leaf as Decimal."""
    out: set[Decimal] = set()
    if isinstance(value, (int, float)):
        out.add(Decimal(str(value)))
    elif isinstance(value, str):
        # Tool outputs serialize Decimal as str per DATA-04 — re-parse them
        out.update(Decimal(str(n)) for n in extract_numbers_from_text(value))
    elif isinstance(value, dict):
        for v in value.values():
            out |= _extract_numbers_recursive(v)
    elif isinstance(value, list):
        for v in value:
            out |= _extract_numbers_recursive(v)
    return out


def _compute_derived(base: set[Decimal]) -> set[Decimal]:
    """Pairwise %, sum, diff. Quantized to 1 decimal place to match Claude's rounding."""
    derived: set[Decimal] = set()
    items = list(base)
    Q = Decimal("0.1")
    for i, a in enumerate(items):
        for b in items[i+1:]:
            if b != 0:
                derived.add(((a / b) * Decimal("100")).quantize(Q))
            if a != 0:
                derived.add(((b / a) * Decimal("100")).quantize(Q))
            derived.add(a + b)
            derived.add(abs(a - b))
    return derived


def check_response(
    response_text: str,
    tool_results: list[dict],
    entity_whitelist: dict[str, set[str]] | None = None,
) -> list[str]:
    """Return list of unsupported tokens. Empty list = PASS.

    Numeric tokens are checked against allowed_numbers = tool_results numbers ∪
    derived ∪ common-knowledge. Entity check: detect capitalized names not in
    the whitelist (salespeople, showrooms, source categories) and inline link
    targets not in {/sales,/salespeople,/marketing,/insights,/chat,#}.
    """
    # 1. Numbers
    allowed: set[Decimal] = set()
    for tr in tool_results:
        allowed |= _extract_numbers_recursive(tr)
    allowed |= _compute_derived(allowed)
    allowed |= COMMON_DAYS | COMMON_YEARS | COMMON_ROUND_PERCENTS

    unsupported: list[str] = []
    response_numbers = [Decimal(str(n)) for n in extract_numbers_from_text(response_text)]
    for num in response_numbers:
        # Phase 5 heuristics: skip small ints, skip years
        if num <= Decimal("10") or (Decimal("1900") <= num <= Decimal("2100")):
            continue
        if not any(abs(num - a) / max(abs(a), Decimal("1e-9")) <= TOLERANCE for a in allowed):
            unsupported.append(f"number:{num}")

    # 2. Inline link targets (D-18a)
    import re
    ALLOWED_HREFS = {"/sales", "/salespeople", "/marketing", "/insights", "/chat", "#"}
    for m in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", response_text):
        href = m.group(2)
        if href not in ALLOWED_HREFS:
            unsupported.append(f"link:{href}")

    # 3. Entity whitelist (capitalized 2+-word names like "Maria Ionescu")
    if entity_whitelist:
        ALL_NAMES = (entity_whitelist.get("salespeople", set())
                     | entity_whitelist.get("showrooms", set())
                     | entity_whitelist.get("categories", set()))
        for m in re.finditer(r"\b([A-ZĂÂÎȘȚ][a-zăâîșț]+ [A-ZĂÂÎȘȚ][a-zăâîșț]+(?: [A-ZĂÂÎȘȚ][a-zăâîșț]+)?)\b",
                              response_text):
            candidate = m.group(1)
            if candidate not in ALL_NAMES:
                unsupported.append(f"entity:{candidate}")

    return unsupported
```

### 4. Tool registry + Tool dataclass (D-04)

```python
# backend/app/services/chat/tools/base.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class Tool:
    name: str
    definition: dict[str, Any]            # Anthropic ToolParam dict
    input_schema: type[BaseModel]
    handler: Callable[[UUID, AsyncSession, BaseModel], Awaitable[dict]]


# backend/app/services/chat/tools/__init__.py
from .base import Tool
from .get_kpi import TOOL as GET_KPI
from .get_funnel_data import TOOL as GET_FUNNEL_DATA
# ... import all 12 tools

TOOLS_REGISTRY: dict[str, Tool] = {t.name: t for t in [
    GET_KPI, GET_FUNNEL_DATA, GET_SALESPERSON_PERFORMANCE,
    GET_LEADS, COMPARE_PERIODS, GET_LOSS_REASONS,
    GET_LEAD_CATEGORIES_BREAKDOWN, GET_SHOWROOM_PERFORMANCE,
    GET_RECENT_INSIGHT, EXPLAIN_METRIC, GET_STUCK_LEADS, GET_TREND,
]}


def get_all_tools() -> list[dict[str, Any]]:
    """Returns Anthropic-formatted definitions for messages.create(tools=...)."""
    return [t.definition for t in TOOLS_REGISTRY.values()]
```

```python
# backend/app/services/chat/tools/get_kpi.py — example tool
from __future__ import annotations
from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from .base import Tool
from app.services.metrics.daily_kpi_service import DailyKpiService


class GetKpiInput(BaseModel):
    date_from: date = Field(..., description="Start date (inclusive)")
    date_to: date = Field(..., description="End date (inclusive)")
    metrics: list[str] = Field(..., description="Metric names: revenue, contracts, leads, avg_deal_size, conversion_rate")


async def _handler(tenant_id: UUID, session: AsyncSession, inp: GetKpiInput) -> dict:
    svc = DailyKpiService(session, tenant_id)  # tenant-scoped
    return await svc.aggregate_for_range(inp.date_from, inp.date_to, metrics=inp.metrics)


TOOL = Tool(
    name="get_kpi",
    definition={
        "name": "get_kpi",
        "description": "Returns aggregated KPI values for a date range. Use this when user asks about specific metrics like revenue, number of contracts, average deal size, conversion rate.",
        "input_schema": GetKpiInput.model_json_schema(),
    },
    input_schema=GetKpiInput,
    handler=_handler,
)
```

### 5. Alembic migration 009 (D-20)

```python
# backend/alembic/versions/009_chat_tables.py
"""Create chat_conversations, chat_messages, chat_tool_calls.

Revision ID: 009
Revises: 008
Create Date: 2026-05-29
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_conversations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.Text, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("last_message_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("archived", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("ix_chat_conversations_tenant_user_last",
                    "chat_conversations", ["tenant_id", "user_id",
                                            sa.text("last_message_at DESC")])

    op.create_table(
        "chat_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("conversation_id", UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.Text, nullable=False),  # user|assistant|tool_use|tool_result
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("tool_calls", JSONB, nullable=True),
        sa.Column("tool_results", JSONB, nullable=True),
        sa.Column("tokens_used", sa.Integer, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("hallucination_flag", sa.Boolean,
                  server_default=sa.text("false"), nullable=False),
        sa.Column("regenerate_count", sa.Integer,
                  server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["chat_conversations.id"],
                                 ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.CheckConstraint("role IN ('user','assistant','tool_use','tool_result')",
                           name="ck_chat_messages_role"),
    )
    op.create_index("ix_chat_messages_conv_created",
                    "chat_messages", ["conversation_id", "created_at"])

    op.create_table(
        "chat_tool_calls",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", UUID(as_uuid=True), nullable=False),
        sa.Column("tool_name", sa.Text, nullable=False),
        sa.Column("input_args", JSONB, nullable=False),
        sa.Column("output_data", JSONB, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["message_id"], ["chat_messages.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_chat_tool_calls_tenant_tool_created",
                    "chat_tool_calls", ["tenant_id", "tool_name",
                                          sa.text("created_at DESC")])


def downgrade() -> None:
    op.drop_index("ix_chat_tool_calls_tenant_tool_created", table_name="chat_tool_calls")
    op.drop_table("chat_tool_calls")
    op.drop_index("ix_chat_messages_conv_created", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_conversations_tenant_user_last", table_name="chat_conversations")
    op.drop_table("chat_conversations")
```

### 6. Title generator (D-14)

```python
# backend/app/services/chat/title_generator.py
from __future__ import annotations
import asyncio
from uuid import UUID
import structlog
from anthropic import AsyncAnthropic

log = structlog.get_logger(__name__)
_pending: set[asyncio.Task] = set()   # holds fire-and-forget tasks so GC doesn't kill them
TITLE_MODEL_PRIMARY = "claude-haiku-4-5"
TITLE_MODEL_FALLBACK = "claude-sonnet-4-5"
TITLE_TIMEOUT_S = 3.0


def schedule_title_generation(conversation_id: UUID, first_user: str, first_assistant: str,
                               update_callback) -> None:
    """Fire-and-forget title generation. Detached via module-level _pending set."""
    task = asyncio.create_task(_generate(conversation_id, first_user, first_assistant, update_callback))
    _pending.add(task)
    task.add_done_callback(_pending.discard)


async def _generate(conversation_id, first_user, first_assistant, update_callback):
    from app.core.config import settings
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    prompt = (
        "Generează un titlu de 4-6 cuvinte în română pentru această conversație, descriind "
        "tema principală. Răspunde DOAR cu titlul, fără punctuație finală sau ghilimele.\n\n"
        f"Întrebare utilizator: {first_user}\n\nRăspuns asistent: {first_assistant[:500]}"
    )
    for model in (TITLE_MODEL_PRIMARY, TITLE_MODEL_FALLBACK):
        try:
            resp = await asyncio.wait_for(
                client.messages.create(
                    model=model, max_tokens=40, temperature=0.3,
                    messages=[{"role": "user", "content": prompt}],
                ),
                timeout=TITLE_TIMEOUT_S,
            )
            title = "".join(b.text for b in resp.content if b.type == "text").strip().rstrip(".,!?")
            if title:
                await update_callback(conversation_id, title)
                return
        except (asyncio.TimeoutError, Exception) as exc:  # noqa: BLE001
            log.warning("title.gen_failed", model=model, error=str(exc)[:100])
            continue
    # Both attempts failed — fall back to truncated first user message
    fallback = first_user[:60].rstrip() + ("…" if len(first_user) > 60 else "")
    await update_callback(conversation_id, fallback)
```

### 7. Frontend SSE consumer (D-32)

```ts
// frontend/src/hooks/useChat.ts (excerpt — ~80 lines)
import { useCallback, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

type SSEEvent =
  | { event: "conversation_meta"; data: { conversation_id: string; message_id_user: string; message_id_assistant: string } }
  | { event: "tool_use"; data: { tool_use_id: string; name: string; input: any } }
  | { event: "tool_result"; data: { tool_use_id: string; output_preview: string; error: boolean | null } }
  | { event: "assistant_chunk"; data: { text: string } }
  | { event: "regenerate_notice"; data: { reason: string } }
  | { event: "done"; data: { message_id: string; total_input_tokens: number; total_output_tokens: number; hallucination_flag: boolean } }
  | { event: "error"; data: { code: string; message_ro: string } };

function readAccessToken(): string | null {
  if (typeof document === "undefined") return null;
  const m = document.cookie.match(/(?:^|;\s*)access_token=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : null;
}

function parseSSEChunk(chunk: string): SSEEvent[] {
  // SSE frames are separated by \n\n. Each frame has lines like "event: NAME" + "data: JSON".
  const events: SSEEvent[] = [];
  for (const frame of chunk.split("\n\n")) {
    if (!frame.trim() || frame.startsWith(":")) continue;  // comment / heartbeat
    let eventName = "message";
    let dataLine = "";
    for (const line of frame.split("\n")) {
      if (line.startsWith("event: ")) eventName = line.slice(7).trim();
      else if (line.startsWith("data: ")) dataLine += line.slice(6);
    }
    if (!dataLine) continue;
    try {
      events.push({ event: eventName as any, data: JSON.parse(dataLine) } as SSEEvent);
    } catch {
      // tolerate partial/incomplete frames at chunk boundaries
    }
  }
  return events;
}

export function useChat(conversationId: string) {
  const [isStreaming, setIsStreaming] = useState(false);
  const [tokens, setTokens] = useState<string>("");
  const [toolPills, setToolPills] = useState<any[]>([]);
  const abortRef = useRef<AbortController | null>(null);
  const qc = useQueryClient();

  const sendMessage = useCallback(async (content: string) => {
    const ac = new AbortController();
    abortRef.current = ac;
    setIsStreaming(true);
    setTokens("");
    setToolPills([]);

    const token = readAccessToken();
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const resp = await fetch(`/api/v1/chat/conversations/${conversationId}/messages`, {
      method: "POST",
      headers,
      credentials: "include",
      body: JSON.stringify({ content }),
      signal: ac.signal,
    });

    if (!resp.ok || !resp.body) {
      setIsStreaming(false);
      throw new Error(`HTTP ${resp.status}`);
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      // Process complete frames; keep the partial tail in the buffer for the next read.
      const lastBoundary = buffer.lastIndexOf("\n\n");
      if (lastBoundary < 0) continue;
      const ready = buffer.slice(0, lastBoundary + 2);
      buffer = buffer.slice(lastBoundary + 2);
      for (const ev of parseSSEChunk(ready)) {
        if (ev.event === "assistant_chunk") setTokens((t) => t + ev.data.text);
        else if (ev.event === "tool_use") setToolPills((p) => [...p, { ...ev.data, state: "running" }]);
        else if (ev.event === "tool_result") setToolPills((p) => p.map(x =>
          x.tool_use_id === ev.data.tool_use_id ? { ...x, state: ev.data.error ? "error" : "done" } : x));
        else if (ev.event === "regenerate_notice") setTokens("");          // D-08
        else if (ev.event === "done") {
          setIsStreaming(false);
          qc.invalidateQueries({ queryKey: ["chat", "conversations"] });   // refetch title
        } else if (ev.event === "error") {
          setIsStreaming(false);
          // surface ev.data.message_ro to UI
        }
      }
    }
  }, [conversationId, qc]);

  const cancel = useCallback(() => abortRef.current?.abort(), []);
  return { sendMessage, cancel, isStreaming, tokens, toolPills };
}
```

---

## Landmines

> Named pitfalls that look right but break.

### LM-1: Module-level `AsyncAnthropic` leaks across fork

**What looks right:** Instantiate `client = AsyncAnthropic(...)` at module level so all handlers share one connection pool.
**What actually breaks:** Celery prefork workers and Gunicorn-style multiprocess servers will share the connection pool across forked processes — broken file descriptors and event-loop state bleeding. Phase 5 documented this as INFRA-05.
**Avoid:** Always instantiate inside the handler / inside `run_turn()`. Module-level only the **import** (`from anthropic import AsyncAnthropic`) for test-patchability.

### LM-2: `EventSource` for POST endpoints

**What looks right:** `new EventSource("/api/v1/chat/...")` — that's the W3C streaming API.
**What actually breaks:** EventSource is GET-only, doesn't support custom headers in most browsers, and silently drops `credentials: include` cookies on third-party origins.
**Avoid:** Use `fetch(POST)` + `response.body.getReader()`. D-32 specifies this.

### LM-3: Tool handler without `tenant_id`

**What looks right:** `async def handler(input: BaseModel) -> dict` — clean signature.
**What actually breaks:** Without `tenant_id` injected as the first argument, the handler bypasses tenant isolation and Tenant A's owner sees Tenant B's KPIs.
**Avoid:** Every handler signature is `async def handler(tenant_id: UUID, session: AsyncSession, input: BaseModel) -> dict`. The orchestrator passes `self._tenant_id` to every dispatch. Add a unit test asserting every entry in `TOOLS_REGISTRY` has this signature shape.

### LM-4: `with_loader_criteria` doesn't fire on `text()` queries

**What looks right:** Trust the global event listener — write any SQL, get tenant scoping for free.
**What actually breaks:** Phase 6 already documented this (Pitfall 5). The listener only fires on ORM `select()` queries — `text()` is invisible to it.
**Avoid:** Tool handlers use ORM `select()` only. If a tool needs `text()` (like `get_loss_reasons` or `get_showroom_performance` may), it MUST bind `tenant_id` explicitly: `.bindparams(bindparam("tid", type_=PG_UUID(as_uuid=True)))` + `.where("tenant_id = :tid")`. Pattern: `backend/app/services/dashboards/dashboard_read_service.py:439-449`.

### LM-5: Streaming response gets buffered by reverse proxy

**What looks right:** `StreamingResponse(generator, media_type="text/event-stream")` — done.
**What actually breaks:** Nginx, Caddy, and Cloudflare may buffer the stream until the response completes, killing the token-by-token UX. The user sees a 5-second pause then the whole reply.
**Avoid:** Set `X-Accel-Buffering: no` header (works for Nginx and Caddy). Set `Cache-Control: no-cache`. For Cloudflare, additionally avoid the "rocket loader" and consider WebSockets fallback (out of scope — Cloudflare isn't in the stack yet).

### LM-6: Forgetting `cache_control` on system block invalidates cache every turn

**What looks right:** Pass `system="...long Romanian system prompt..."` as a string.
**What actually breaks:** Without `cache_control: {type: "ephemeral"}` on the last system block, every turn pays full `$3.00/MTok` for the 1500+ system-prompt tokens — chat costs balloon 5×.
**Avoid:** Build system as `list[dict]` with last block carrying `cache_control` (Phase 5 pattern: `backend/app/services/insights/prompt_builder.py:64-86`).

### LM-7: SSE frames split across `reader.read()` chunks

**What looks right:** `for chunk of reader: parseSSE(chunk)` — process each chunk independently.
**What actually breaks:** TCP doesn't respect SSE frame boundaries; a single read may deliver `event: tool_use\ndata: {"toolu` and the next read delivers `_id":"..."}\n\n`. Parsing each chunk independently produces garbage.
**Avoid:** Maintain a `buffer` string across reads. Split on `\n\n`. Process up to the last full boundary; keep the tail in the buffer for the next iteration. See the `useChat` sketch above.

### LM-8: Fire-and-forget `asyncio.create_task` gets garbage-collected

**What looks right:** `asyncio.create_task(generate_title(...))` — done.
**What actually breaks:** Python may GC the task object before it completes, cancelling the coroutine. Especially likely if the request handler returns immediately.
**Avoid:** Hold a strong reference: `_pending.add(task); task.add_done_callback(_pending.discard)`. Standard pattern — sketch above.

### LM-9: Hallucination guard runs against streamed text WHILE streaming

**What looks right:** Run the guard incrementally as each chunk arrives — fail fast.
**What actually breaks:** Numbers like `285.000 RON` arrive as 3 chunks (`28`, `5.000`, ` RON`); incremental check thinks `28` is unsupported and fires regenerate prematurely.
**Avoid:** D-08 — run guard ONCE, post-stream-complete, on the full accumulated text. Accept the UX cost of discarding the bubble visually on guard failure.

### LM-10: Tool input_schema = Pydantic field defaults leak into Anthropic schema

**What looks right:** `class GetLeadsInput(BaseModel): limit: int = 50`.
**What actually breaks:** `model_json_schema()` emits the default as `"default": 50` — Claude may treat that as a hint to omit the field, then send `{}` and your validator fails (`limit` missing).
**Avoid:** Use `Field(50, description="…")` and verify the emitted JSON Schema includes the field. Alternatively, mark required fields `Field(..., description=...)`.

### LM-11: Romanian thousands separator collides with markdown list markers

**What looks right:** Run `NUMBER_PATTERN` over everything.
**What actually breaks:** Markdown lists start with `1.` `2.` `3.` — the regex captures `1`, `2`, `3` as numbers. With the Phase 5 `<= 10` skip rule they're ignored — but `10.` for a 10-item list captures `10` which is at the boundary.
**Avoid:** Use the `> 10` skip rule strictly (`if num <= 10: continue`). The Phase 5 implementation already does this — keep it.

### LM-12: 12 tools × 1500 token definitions = 18k+ system tokens every turn

**What looks right:** Pass `tools=get_all_tools()` directly — Claude handles it.
**What actually breaks:** Tool definitions are counted as input tokens for billing AND for the `200k` context window. 12 tools × ~150 tokens each = 1800 tokens just for the tool list. Plus cached system prompt (1500) + history (variable). Cost model in docs/CHAT.md §11 assumes ~5050 input tokens/turn — verify against real measurements after launch.
**Avoid:** Already mitigated by `cache_control` on system block. Consider caching tools too via `cache_control` on the LAST tool definition (Anthropic supports this) — flag as Iteration 2 optimization if costs exceed budget.

---

## Validation Architecture

> Required because `workflow.nyquist_validation: true` in `.planning/config.json`.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest` (backend) + `vitest` (frontend) — both already in repo |
| Backend config file | `backend/pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command (backend) | `cd backend && pytest tests/unit/test_chat_*.py -x -q` |
| Quick run command (frontend) | `cd frontend && pnpm test --run src/hooks/useChat.test.ts` |
| Full suite (backend) | `cd backend && pytest` |
| Full suite (frontend) | `cd frontend && pnpm test --run && pnpm typecheck && pnpm lint` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CHAT-01 | User question → grounded reply | integration (mocked AsyncAnthropic) | `pytest tests/integration/test_chat_orchestrator.py::test_basic_turn -x` | ❌ Wave 0 |
| CHAT-02 | Multi-tool turn with ≥3 distinct tools | integration | `pytest tests/integration/test_chat_orchestrator.py::test_multi_tool_turn -x` | ❌ Wave 0 |
| CHAT-03 | History persists across "sessions" | integration | `pytest tests/integration/test_chat_history.py::test_history_persists -x` | ❌ Wave 0 |
| CHAT-04 | System prompt includes Sofa Belle context | unit | `pytest tests/unit/test_chat_prompt_builder.py::test_includes_salespeople -x` | ❌ Wave 0 |
| CHAT-05 | Honest refusal when data unavailable | adversarial fixture | `RUN_ADVERSARIAL=1 pytest tests/adversarial/test_chat_adversarial.py::test_meta_cac_honest -x` | ❌ Wave 0 (placeholder) |
| CHAT-06 | Inline dashboard links rendered correctly | unit (frontend) | `pnpm test --run src/components/chat/markdown-renderer.test.tsx` | ❌ Wave 0 |
| CHAT-07 | "Se gândește..." indicator visible | unit (frontend) | `pnpm test --run src/components/chat/thinking-indicator.test.tsx` | ❌ Wave 0 |
| CHAT-08 | Documented exception in CLAUDE.md + chat.py | unit (grep gate) | `pytest tests/unit/test_chat_router.py::test_async_anthropic_only_in_chat -x` | ❌ Wave 0 |
| CHAT-09 | First token < 2s; tool round-trips < 500ms | manual-only (UAT) | — (measure during HUMAN-UAT) | manual |
| CHAT-10 | Zero hallucinated entities/numbers | unit (hallucination_guard) + adversarial | `pytest tests/unit/test_hallucination_guard.py -x` + `RUN_ADVERSARIAL=1 pytest tests/adversarial/` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/unit/test_chat_*.py -x -q && cd ../frontend && pnpm test --run src/hooks/useChat.test.ts` (≤20 s)
- **Per wave merge:** `cd backend && pytest && cd ../frontend && pnpm test --run && pnpm typecheck && pnpm lint`
- **Phase gate:** Full suite green + adversarial fixture passed once with real Claude calls before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `backend/tests/unit/test_chat_prompt_builder.py` — covers CHAT-04 (system prompt content + cache_control structure + salesperson roster injection)
- [ ] `backend/tests/unit/test_hallucination_guard.py` — covers CHAT-05/CHAT-10 (number ±1%, derived %, entity whitelist, link whitelist)
- [ ] `backend/tests/unit/test_chat_tools_registry.py` — covers D-04 (Tool dataclass shape, get_all_tools returns 12, each handler signature includes tenant_id)
- [ ] `backend/tests/unit/test_chat_tool_handlers.py` — one test per of the 12 tools (CHAT-02 coverage by enumeration); mocks the wrapped Phase 3/6 service
- [ ] `backend/tests/unit/test_chat_orchestrator.py` — covers CHAT-01 (basic turn), CHAT-02 (multi-tool round), D-30 (asyncio.gather), D-08 (guard regenerate flow), D-07 (fallback message)
- [ ] `backend/tests/unit/test_chat_router.py` — covers CHAT-08 (grep gate: AsyncAnthropic appears only in chat.py within app/api/) + auth + 409/429 paths
- [ ] `backend/tests/unit/test_title_generator.py` — Haiku fallback to Sonnet, 3s timeout fallback to truncated message, model identifier validation
- [ ] `backend/tests/integration/test_chat_history.py` — CHAT-03 round-trip with TEST_DATABASE_URL
- [ ] `backend/tests/integration/test_chat_orchestrator.py` — mocked AsyncAnthropic end-to-end SSE stream (CHAT-01/02 integration variant)
- [ ] `backend/tests/adversarial/test_chat_adversarial.py` + `backend/tests/adversarial/adversarial_chat_questions.yaml` — D-40 fixture + runner (gated by `RUN_ADVERSARIAL=1`)
- [ ] `frontend/src/hooks/useChat.test.ts` — SSE parser chunk-boundary handling (LM-7), event dispatch, regenerate_notice resets tokens, abort propagation
- [ ] `frontend/src/components/chat/markdown-renderer.test.tsx` — CHAT-06 (allowed-elements whitelist, dashboard link pill, KPI bold, table)
- [ ] `frontend/src/components/chat/thinking-indicator.test.tsx` — CHAT-07 (3 states)
- [ ] `backend/tests/factories/chat_factory.py` — fixtures for conversations/messages/tool_calls (mirrors `tests/factories/insight_factory.py`)

---

## Common Pitfalls (operational)

### Pitfall 1: Caddy/proxy idle-connection timeout drops mid-stream

**What goes wrong:** Caddy default idle timeout is 5 minutes. A tool chain that runs 6 minutes (e.g., `get_loss_reasons` on a year of leads) drops the connection without an explicit error.
**Why:** No bytes flowing → proxy assumes dead.
**How to avoid:** Heartbeat. Emit `:\n\n` SSE comment lines every 15s during long tool execution. Easiest: race a `asyncio.sleep(15)` against the main generator and yield a comment on each tick.
**Warning signs:** Frontend `reader.read()` returns `done=true` with no `done` SSE event.

### Pitfall 2: tool_results bag inflates the second-attempt prompt

**What goes wrong:** On hallucination regenerate (D-08), the orchestrator re-runs the whole turn. The tool_results from the first attempt are still in `messages` history, so Claude pays for them twice.
**Why:** Naive retry doesn't reset the messages list.
**How to avoid:** On guard failure, KEEP the existing tool_use/tool_result blocks in `messages` (Claude needs them for context) but append the corrective user message and re-stream the FINAL assistant message only — NOT the tool rounds. The sketch in §"Anthropic streaming + tools loop" does this by re-entering the outer `for guard_attempt` loop with the same `messages` list.

### Pitfall 3: Title generator races assistant message persistence

**What goes wrong:** Title gen runs concurrently with the final `assistant_message` INSERT. If title gen's UPDATE arrives first, the conversation row may not have its `last_message_at` set yet.
**Why:** Both are tenant-scoped DB writes from the same request but on different coroutines.
**How to avoid:** Schedule title gen AFTER persisting the assistant message + emitting `done` event (see orchestrator sketch — title gen schedule is the last line).

### Pitfall 4: Adversarial test cost spike

**What goes wrong:** Someone enables `RUN_ADVERSARIAL=1` in CI on every PR, burning $1+/run.
**Why:** Adversarial fixture hits real Claude.
**How to avoid:** Gate via env var (default off). Nightly cron-only. Document in `tests/adversarial/README.md`.

---

## Code Examples

See §"Implementation Sketches" — every code excerpt above is verified-pattern.

---

## State of the Art

| Old approach | Current approach | When changed | Impact |
|--------------|------------------|--------------|--------|
| Single-shot Claude call returning full JSON | Streaming + tool_use loop | Anthropic SDK 0.30 (~2024-08) | UX win (TTFT < 2s), required for chat per CHAT-09 |
| EventSource for SSE | `fetch` + `ReadableStream` reader | ~2022 in production code | EventSource is GET-only; fetch supports POST + custom headers |
| Per-call HTTP client construction | Reuse `AsyncAnthropic` per-request | Phase 5 InsightService | Fork-safe; clean shutdown |
| Hand-rolled JSON schema for tools | `Pydantic.model_json_schema()` | Pydantic v2 (2023) | Tool input validation for free + auto-generated docs |
| `sse-starlette` for everything | Plain `StreamingResponse` with manual SSE format | n/a — both valid in 2026 | We pick plain for fewer deps; sse-starlette ready as escalation |

**Deprecated / outdated for this phase:**
- Buffering full response then streaming — bad UX, rejected by D-08.
- Synchronous Claude call from HTTP handler — explicit CLAUDE.md violation everywhere except chat.py (D-25 exception).
- `print()` debugging — use structlog with `tenant_id` + `conversation_id` bindings.

---

## Assumptions Log

| # | Claim | Section | Risk if wrong |
|---|-------|---------|---------------|
| A1 | `claude-haiku-4-5` is the correct model identifier at execution time | Title generator, §Open Decisions #2 | Title gen 400s → fallback to Sonnet 4.5; user-invisible. Low risk. |
| A2 | Anthropic Haiku 4.5 pricing is $1/MTok input + $5/MTok output | Cost section | Title-gen cost computation off by a constant. Logged in structlog only, no DB. Low risk. |
| A3 | Caddy default idle timeout drops streams > 5 min without keepalive | Pitfall 1 | If actual timeout is shorter or longer, heartbeat cadence may need tuning. Mitigated by 15s cadence (safe margin). |
| A4 | `react-markdown` 9.x + `remark-gfm` 4.x are current and stable | Standard Stack | Newer pre-release behavior may differ; pin minor when installing. |
| A5 | `gen_random_uuid()` is available in our PostgreSQL 16 (it is — pgcrypto/uuid-ossp) | Migration 009 | Phase 5 migration 008 already uses it successfully → effectively VERIFIED. |
| A6 | Existing `with_loader_criteria` event listener handles `chat_conversations`, `chat_messages`, `chat_tool_calls` automatically | Tenant isolation | If models inherit from `Base` correctly and have `tenant_id`, listener fires. Verify by adding a "no-tenant" select test that should raise `TenantIsolationError`. |

---

## Environment Availability

| Dependency | Required by | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Anthropic API | Streaming chat + title gen | ✓ (key in `.env`) | n/a | None — required |
| PostgreSQL 16 | Conversation persistence | ✓ | 16 (Phase 1) | None |
| Redis 7 | Rate-limit + stream lock | ✓ | 7 (Phase 1) | None |
| `anthropic` Python SDK | Streaming + tools | ✓ | `0.104.1` | None |
| `react-markdown` + `remark-gfm` | Markdown rendering | ✗ (to install) | TBD | Plain text + manual link parsing (not recommended) |
| Caddy / reverse proxy | Production SSE | ⚠️ Phase 9 task | n/a | Local dev streams without proxy — verify in Phase 9 |

**Missing dependencies with no fallback:** none blocking.
**Missing dependencies with fallback:** `react-markdown` + `remark-gfm` — install in Wave 1.

---

## Open Questions

1. **Long-conversation context-window growth.** 20-message history (D-16) + 12 tool definitions + system prompt fits comfortably in 200k context. But if a single assistant message contains 4 tool_use blocks with large outputs (e.g., `get_leads` with 50 leads), the next turn's input grows fast. Recommendation: monitor `input_tokens` per turn during Sofa Belle pilot; if median > 15k, add Iteration 2 summarization or tool_result truncation.
2. **Persona detection accuracy.** D-28 says Claude infers owner-vs-analyst from phrasing. Without a per-user flag, accuracy depends entirely on the prompt. Recommendation: log persona-flavored words from user input (anonymized) for the first 100 turns of pilot use; review for prompt-tuning needs in Phase 9.
3. **Adversarial fixture coverage.** D-40 mentions ~15 trap questions. The exact list isn't locked. Recommendation: stub the fixture file with 5 categories × 3 questions each (out-of-scope, date-bounded, entity hallucination, prompt injection, CHAT-05 honesty) — total 15 — and grow during pilot.

---

## Out of Scope / Deferred

(Mirrors CONTEXT.md `<deferred>` section verbatim — see §"User Constraints → Deferred Ideas".)

Specific to research findings:
- **`sse-starlette` migration** — if Caddy drops streams despite heartbeats, swap `StreamingResponse` for `EventSourceResponse`. Phase 9 escalation.
- **Cached tool definitions** — Anthropic supports `cache_control` on tools too. If LM-12 cost projection holds, add this in Iteration 2.
- **Claude 4.6+ continuation prompts** — Streaming doc references a different recovery strategy for Claude 4.6+. Sonnet 4.5 uses the partial-assistant-message recovery, but the codebase doesn't recover from interrupted streams in MVP1 (only persists user message on disconnect per D-12). Out of scope.

---

## Sources

### Primary (HIGH confidence)

- Repo code (verified by Read):
  - `backend/app/services/insights/insight_service.py` (canonical AsyncAnthropic pattern)
  - `backend/app/services/insights/number_validator.py` (NUMBER_PATTERN + extract_numbers_from_text)
  - `backend/app/services/insights/prompt_builder.py` (cache_control system prompt format)
  - `backend/app/services/dashboards/dashboard_read_service.py` (tool backend patterns + 11-source map + stuck-offers query)
  - `backend/app/services/anomaly/anomaly_service.py` (alternative stuck-leads query)
  - `backend/app/api/v1/insights.py` (rate-limit + Romanian errors)
  - `backend/app/api/v1/dashboards.py` (router + dependencies pattern)
  - `backend/app/api/v1/router.py` (router registration)
  - `backend/app/core/dependencies.py` (get_current_user)
  - `backend/app/core/tenancy.py` (ContextVar tenant)
  - `backend/app/main.py` (StructlogContextMiddleware sets tenant per-request)
  - `backend/app/models/__init__.py` (Alembic discovery pattern)
  - `backend/alembic/versions/008_daily_insights.py` (migration template)
  - `backend/tests/unit/test_insight_service.py` (AsyncAnthropic mocking pattern)
  - `backend/tests/unit/test_insights_router.py:86-101` (grep-gate test pattern)
  - `frontend/src/lib/api-client.ts` (auth header + 401 refresh)
  - `frontend/package.json` (existing frontend deps)
- Live SDK introspection: `anthropic 0.104.1` `AsyncMessages.stream` and `AsyncMessageStream` interface confirmed via `inspect`.
- CONTEXT.md (40 locked decisions D-01..D-40) — primary source for product intent.
- UI-SPEC.md (approved frontend design contract).
- REQUIREMENTS.md (CHAT-01..CHAT-10).
- ROADMAP.md Phase 8 section (goal + 7 success criteria).
- CLAUDE.md (project rules).
- docs/CHAT.md (primary detailed spec — system prompt, 12 tools, hallucination guard reference impl, SSE event schema, cost model).
- docs/SOFABELLE.md (showrooms, salespeople, cycle).

### Secondary (MEDIUM confidence)

- Anthropic streaming docs (platform.claude.com/docs/en/docs/build-with-claude/streaming) — event types, content_block_delta variants (text_delta, input_json_delta), final-message pattern, tool_use streaming example.
- Anthropic tool-use docs (platform.claude.com/docs/en/docs/build-with-claude/tool-use/overview) — multi-turn loop structure, tool_result message shape.
- WebSearch on FastAPI SSE best practices 2026 — confirmed `X-Accel-Buffering: no` header pattern and 15s heartbeat cadence.

### Tertiary (LOW confidence)

- npm registry latest versions for `react-markdown` + `remark-gfm` (assumed mature 9.x / 4.x; verify at install time).
- Haiku 4.5 pricing constants and exact model identifier (verify at execution time — fall back to Sonnet 4.5 on 400).

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every backend dep already in `pyproject.toml`; SDK live-introspected.
- Architecture: HIGH — orchestrator + guard + tools + persistence all mirror existing Phase 5/6 patterns.
- Pitfalls: HIGH — LM-1..LM-12 all derived from existing code documentation (Phase 5 INFRA-05 / Phase 6 Pitfall 5) or verified docs.
- Frontend SSE: MEDIUM-HIGH — `fetch` + `ReadableStream` is well-documented; chunk-boundary parsing (LM-7) is the only subtle area, sketch handles it.
- Hallucination guard: MEDIUM — recursive number extraction + pairwise derivation is unverified at scale; will need adversarial-fixture tuning during pilot.
- Title generator model: MEDIUM — `claude-haiku-4-5` identifier assumed; fallback to Sonnet is safe.

**Research date:** 2026-05-29
**Valid until:** 2026-06-28 (30 days — Anthropic SDK is stable; chat backend pattern derives from already-shipped Phase 5).
