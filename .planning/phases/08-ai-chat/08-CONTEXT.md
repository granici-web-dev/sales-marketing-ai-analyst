# Phase 8: AI Chat - Context

**Gathered:** 2026-05-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the `/chat` placeholder stub with a fully working interactive Romanian AI chat. User asks business questions in plain Romanian; Claude Sonnet 4.5 calls tools backed by Phase 3 metric services / Phase 6 read services to fetch grounded numbers; responses stream token-by-token via SSE; conversation history persists across browser sessions; all numeric values cross-checked against tool results before reaching the user.

**This phase delivers:**

Backend
- `backend/alembic/versions/009_chat_tables.py` — Alembic migration for `chat_conversations`, `chat_messages`, `chat_tool_calls` (SPEC.md §7 Layer 5 schema)
- `backend/app/models/chat/` — 3 SQLAlchemy ORM models matching the migration
- `backend/app/schemas/chat/` — Pydantic v2 request/response/SSE-event schemas
- `backend/app/services/chat/tools/` — 12 tool definitions + handlers + `TOOLS_REGISTRY`
- `backend/app/services/chat/orchestrator.py` — Claude conversation loop (system prompt + history + tool execution + retry + streaming)
- `backend/app/services/chat/prompt_builder.py` — Romanian system prompt assembly + tenant context block (Sofa Belle facts, salesperson roster, showrooms, MVP1 data limits)
- `backend/app/services/chat/hallucination_guard.py` — strict number cross-check + entity whitelist + regenerate loop
- `backend/app/services/chat/title_generator.py` — auto-title after turn 1 (4-6 Romanian words via cheap Claude call)
- `backend/app/services/chat/repositories/` — ConversationRepository + MessageRepository + ToolCallRepository
- `backend/app/api/v1/chat.py` — 5 endpoints (create conversation, list, get history, send message SSE, suggested questions)
- `backend/app/api/v1/router.py` — register chat router

Frontend
- `frontend/src/app/(dashboard)/chat/page.tsx` — split-panel layout (sidebar + main pane)
- `frontend/src/components/chat/` — ConversationsList, ChatMain, MessageBubble, ToolPill, ThinkingIndicator, SuggestedQuestions, ChatInput, MarkdownRenderer with inline dashboard link mapper
- `frontend/src/hooks/useChat.ts` — TanStack Query hooks + fetch+ReadableStream SSE consumer + optimistic message state
- `frontend/messages/ro.json` + `en.json` — `chat` namespace strings

**Does NOT include (out of scope, deferred):**
- Multi-user / per-user authorization beyond Phase 1's single owner user (Iteration 4 multi-tenancy)
- Voice input/output (Phase 9+)
- Chat analytics dashboard (Phase 9+)
- ML-driven suggested questions (heuristic only for MVP1)
- Iteration 2+ tools (Meta/Google/TikTok ad spend, GA4 sessions, GSC keywords — Claude must honestly say "Nu am acces la datele de reclamă în această versiune" per CHAT-05 / SC#3)
- Multi-language responses (Romanian-only)
- Editing CRM data from chat (read-only product)

</domain>

<decisions>
## Implementation Decisions

### Tool Scope (D-01..D-04)

- **D-01:** Ship **all 12 tools** from docs/CHAT.md across all 4 tiers. Backends already exist (Phase 3 metric services, Phase 6 read services, Phase 5 insight read service) — incremental cost is the tool wrapper layer + Pydantic input schemas + `TOOLS_REGISTRY` plumbing. Easily clears ROADMAP SC#2 (≥3 distinct tools per turn) and SPEC.md "min 10 tools".

- **D-02:** **Tool list (canonical for Phase 8):**
  1. `get_kpi(date_from, date_to, metrics[])` — daily_kpi aggregation
  2. `get_funnel_data(date_from, date_to)` — Lead→Vizita→Oferta→Contract counts + conversions
  3. `get_salesperson_performance(date_from, date_to, salesperson_id?)` — salesperson_daily_kpi
  4. `get_leads(filters{}, limit≤50)` — v_mefi_leads_active with status/source/salesperson/date filters
  5. `compare_periods(period_a, period_b, metrics[])` — two daily_kpi aggregations + computed deltas
  6. `get_loss_reasons(date_from, date_to)` — distribution of lost leads by source/salesperson (note: estimated_value is NULL for all leads per Phase 3 finding — return counts + pct, omit revenue figures)
  7. `get_lead_categories_breakdown(date_from, date_to)` — source_daily_kpi (11 canonical categories)
  8. `get_showroom_performance(date_from, date_to, showroom?)` — derived from v_mefi_leads_active.showroom_id (3 showrooms per docs/SOFABELLE.md)
  9. `get_recent_insight(date?)` — daily_insights payload (latest if date null)
  10. `explain_metric(metric_name)` — static Romanian glossary (no DB hit; pre-canned dict in code)
  11. `get_stuck_leads(days≥1, status?)` — leads with no activity > N days (default 14, mirrors ANOM-03 + SALE-07)
  12. `get_trend(metric_name, period_days∈{7,30,90}, granularity∈{"day","week"})` — daily_kpi time series for one metric

- **D-03:** **Tool handler reuse policy:** each handler thinly wraps an existing Phase 3/5/6 service. **No new SQL inside chat tools.** If a tool needs data not exposed by an existing service, extend the service. This keeps tool output schemas validated against the same metric definitions used by dashboards (avoiding chat-vs-dashboard number drift).

- **D-04:** **Tool input/output schemas:** every tool has a `BaseModel` input schema (validated before handler call) and returns a `dict` JSON-serializable (Decimal as `str` per DATA-04). `TOOLS_REGISTRY` maps name → `Tool(definition, input_schema, handler)` per docs/CHAT.md §4. `get_all_tools()` returns the list for `messages.create(tools=...)`.

### Hallucination Guard (D-05..D-08)

- **D-05:** **Strict mode for MVP1.** Aligns with CHAT-05 + CHAT-10 + ROADMAP SC#4 ("zero hallucinated salesperson names, funnel stage names, or KPI values"; "all numeric values match DB within ±1%"). Soft-mode docs/CHAT.md §6 MVP1 wording is overridden — pilot CEO cannot see bad numbers.

- **D-06:** **Guard mechanics:** after Claude's assistant message in a turn, extract all numeric tokens via regex (reuse Phase 5 `NUMBER_PATTERN` from `number_validator.py` — handles Romanian thousands like `23.400`). Build the allowed-numbers set as: tool_results numbers (recursive extraction) ∪ derived numbers (pairwise %, sums, diffs, rounded to 1 decimal) ∪ common-knowledge (years 1900-2100, days 1-31, percentage 0/50/100 round numbers). Tolerance: ±1% per ROADMAP SC#4 (tightens docs/CHAT.md §6 default of ±1% — same value, explicit). Entity whitelist: salesperson full names from `mefi_salespeople` table, showroom names from funnel_config, 11 source categories from `MEFI_SOURCE_ID_TO_NAME`.

- **D-07:** **Retry budget:** max 1 regenerate on guard failure. Regenerate call includes a system-level notice appended as a `user`-role message: `"Răspunsul anterior conținea numere/entități nesusținute de date: [list]. Reformulează folosind doar valori din rezultatele uneltelor."` If the 2nd attempt also fails: stream a Romanian fallback text to the user — `"Nu pot da un răspuns precis pe baza datelor disponibile. Te rog reformulează întrebarea."` Mark `chat_messages.hallucination_flag=true` on the failed-and-fallback message for analytics. Both attempts logged to `chat_tool_calls`-style audit (extend or sibling table).

- **D-08:** **Guard runs server-side, post-stream-complete.** Stream Claude's tokens to the frontend as they arrive (UX win), THEN run the guard against the assembled text + tool_results bag. On guard failure (Round 1), emit an SSE `regenerate_notice` event (frontend shows "Verific cifrele..."), discard the streamed bubble, re-stream the regenerated response. The first stream is discarded visually — accept the minor UX hiccup as the cost of accuracy. Alternative considered (buffer entire response, validate, then stream) loses streaming feel; rejected.

### Streaming Protocol (D-09..D-12)

- **D-09:** **SSE custom event schema** per docs/CHAT.md §7. Event types:
  - `conversation_meta` — `{conversation_id, message_id_user, message_id_assistant}` (sent first so frontend can persist IDs)
  - `tool_use` — `{tool_use_id, name, input}` emitted when Claude requests a tool
  - `tool_result` — `{tool_use_id, output_preview, duration_ms, error?}` emitted after handler completes (preview = first 200 chars JSON)
  - `assistant_chunk` — `{text}` per content_block_delta from Anthropic stream
  - `regenerate_notice` — `{reason: "hallucination_guard"}` on guard rejection round 1
  - `done` — `{message_id, total_input_tokens, total_output_tokens, duration_ms, hallucination_flag}`
  - `error` — `{code, message_ro}` on unrecoverable failure (tool exception, Claude API error)

- **D-10:** **Tool-use transparency: pills with tool names.** While a tool runs, frontend renders an inline pill inside the in-progress message bubble: `🔍 get_funnel_data · 30 zile` (tool name + a 1-2 word humanized hint derived from `input.date_from`/`date_to`). Pills collapse into a single line `🔧 3 unelte folosite` after `done` event. Why visible: Sofa Belle CEO is a power user (per docs/SOFABELLE.md context) and analyst persona is the second target; transparency aids trust ("I see it actually queried the data") and pilot debugging. Owner persona can scan past pills since the final answer text is what matters.

- **D-11:** **Concurrency / one stream per conversation:** if a second `POST /messages` arrives while a stream is active for the same conversation, return `409 Conflict` with Romanian error. No queue, no cancel — simplest correct behavior. Frontend Send button disabled while `useChat.isStreaming === true`.

- **D-12:** **Stream cancellation:** if the client disconnects mid-stream, the orchestrator detects via `Request.is_disconnected()` and aborts before persisting the assistant message. The user's message IS persisted at turn start so it's not lost; the partial assistant text is dropped (no half-messages in history).

### Conversation UX (D-13..D-19)

- **D-13:** **Persistent list, ChatGPT-style sidebar.** Single global list scoped to the one owner user (single-user MVP1 — `chat_conversations.user_id` set from `get_current_user`). Sidebar width: 260px desktop (`md:flex w-[260px]`), collapses behind hamburger on mobile (reuse Phase 7 sidebar Sheet pattern). List shows: title, relative timestamp ("acum 2 ore"), unread indicator (skipped for MVP1 — single user reads everything as it happens).

- **D-14:** **Auto-title via separate cheap Claude call after turn 1.** After the first assistant message completes successfully, fire-and-forget a non-streaming `claude-sonnet-4-5` (or `claude-haiku-4-5` to save cost) call: `"Generează un titlu de 4-6 cuvinte în română pentru această conversație, descriind tema principală. Răspunde DOAR cu titlul, fără punctuație finală sau ghilimele."` passing the user's first question + first assistant response. Title set via `UPDATE chat_conversations SET title=...`. If the call fails or times out (>3s): fall back to truncated first user message (first 60 chars + ellipsis). Frontend hot-swaps title via TanStack Query invalidation on first SSE `done`. **Model for titles:** prefer `claude-haiku-4-5` (faster + cheaper) — if not yet wired, fall back to `claude-sonnet-4-5`.

- **D-15:** **Delete = soft archive.** `archived` boolean column already in SPEC.md schema. `DELETE /api/v1/chat/conversations/{id}` sets `archived=true`. Default `GET /api/v1/chat/conversations` returns `archived=false` only; `?archived=true` returns archived list. No "trash" UI in MVP1 — power-user URL-only access. Hard delete deferred to Phase 9 / GDPR retention task.

- **D-16:** **History window passed to Claude:** last 20 messages (10 user + 10 assistant pairs, approximately). Truncation strategy: keep the full first user message (anchors topic), then most recent 19 messages. Older messages logged in DB but excluded from the API call. Crosses ~10k input tokens at the high end with 1500 char/message avg — acceptable cost. Summarization of older history deferred to Iteration 2.

- **D-17:** **Suggested-question chips (above input):** **hybrid source.**
  - **Static base (5 questions):** hardcoded Romanian curated list in code, e.g.: `"Cum stăm cu vânzările luna asta?"`, `"Care e cel mai bun vânzător luna asta?"`, `"Ce lead-uri au nevoie de atenție?"`, `"Comparativ cu săptămâna trecută, cum stăm?"`, `"De ce a scăzut conversia la oferte?"`.
  - **Dynamic injection (up to 2 questions):** read today's `daily_insights.payload_json.problems[].title`, for the top 2 by severity convert to a question form (template: `"Spune-mi mai mult despre: {problem.title}"`). Skip if no insight exists or status != 'success'.
  - Endpoint: `GET /api/v1/chat/suggested-questions?context=homepage` returns merged list (5 static + up to 2 dynamic = 5-7 chips). Click inserts text into input (does NOT auto-send) per docs/CHAT.md.

- **D-18:** **Inline dashboard links — markdown via system prompt, NO date params in MVP1.** System prompt instructs Claude to emit `[Sales Dashboard](/sales)`, `[Salespeople](/salespeople)`, `[Marketing](/marketing)`, `[Insights](/insights)` when referencing a dashboard. Frontend `MarkdownRenderer` recognizes these specific relative paths and renders them as styled "pill" links (`bg-accent`, ChevronRight icon). **Date-aware links rejected for MVP1** (D-18a): adds prompt-engineering surface area (Claude must consistently match dates between answer text and URL — bug-prone), forces a URL-validation rule in the guard, and dashboards already preserve the user's selected range via `useSearchParams`. Deferred to Phase 9 if pilot asks.
  - **D-18a:** Whitelist of allowed link targets enforced in the guard alongside number cross-check: any `[label](href)` where `href` does not start with `/sales`, `/salespeople`, `/marketing`, `/insights`, `/chat`, or is not a bare anchor `#` triggers regeneration. Prevents Claude from emitting external URLs or phishing-shaped paths.

- **D-19:** **Markdown rendering library:** `react-markdown` per docs/CHAT.md §8 with custom renderers for `strong` (bold metrics) + `a` (dashboard link pill mapper) + `table` (shadcn Table primitives). `remark-gfm` enabled for tables. No raw HTML allowed (`allowedElements` whitelist) — XSS hardening.

### Database Schema (D-20..D-22)

- **D-20:** **Migration 009 creates 3 tables per SPEC.md §7 Layer 5** with extensions for the hallucination guard:
  - `chat_conversations(id uuid PK, tenant_id uuid FK, user_id uuid FK, title text, created_at timestamptz, last_message_at timestamptz, archived boolean default false)` + index `(tenant_id, user_id, last_message_at DESC)`
  - `chat_messages(id uuid PK, conversation_id uuid FK ON DELETE CASCADE, tenant_id uuid FK, role text CHECK in ('user','assistant','tool_use','tool_result'), content text, tool_calls jsonb, tool_results jsonb, tokens_used int, duration_ms int, hallucination_flag boolean default false, regenerate_count int default 0, created_at timestamptz)` + index `(conversation_id, created_at)`
  - `chat_tool_calls(id uuid PK, tenant_id uuid FK, message_id uuid FK ON DELETE CASCADE, tool_name text, input_args jsonb, output_data jsonb, duration_ms int, error text, created_at timestamptz)` + index `(tenant_id, tool_name, created_at DESC)`
  - **Added beyond SPEC.md:** `hallucination_flag boolean` and `regenerate_count int` on `chat_messages` for D-07 analytics.

- **D-21:** **Per-tool audit logging:** every tool call writes one `chat_tool_calls` row (D-06 enforces). On handler exception, `error` column populated; the SSE `tool_result` event carries an error field; Claude receives an `is_error: true` tool_result so it can apologize gracefully ("Nu am putut accesa acele date acum") rather than hallucinate.

- **D-22:** **Tenant isolation:** all chat queries filter by `tenant_id` via the existing `with_loader_criteria` seam from Phase 1 (`backend/app/db/session.py`). Tools internally pass `tenant_id` to existing services (Phase 3/6 already isolated). The orchestrator receives `tenant_id` from `get_current_user` dependency.

### Endpoints (D-23..D-25)

- **D-23:** **5 endpoints, all under `/api/v1/chat`:** match docs/CHAT.md §7 + SPEC.md §12:
  - `POST /chat/conversations` — create, optional initial_message body. Returns `{id, title=null, created_at, messages:[]}`. If `initial_message` provided, it's persisted as the first user message; client immediately calls `POST /messages` to stream the assistant reply.
  - `GET /chat/conversations?archived=false&limit=50` — list, ordered by `last_message_at DESC`
  - `GET /chat/conversations/{id}` — full message history (paginated only if message_count > 200 — deferred)
  - `DELETE /chat/conversations/{id}` — soft archive (D-15)
  - `POST /chat/conversations/{id}/messages` — SSE streaming response (D-09 event schema)
  - `GET /chat/suggested-questions?context=homepage|sales|salespeople|marketing|insights` — D-17 hybrid

- **D-24:** **Rate limit:** `POST /messages` rate-limited to 30 messages/hour per user (Redis `SET NX EX`, same pattern as Phase 6 insights refresh). Generous enough for natural conversation, prevents runaway loops. 429 returns Romanian message.

- **D-25:** **CHAT-08 documented exception:** add a docstring at the top of `backend/app/api/v1/chat.py` explaining "This module is the **documented exception** to CLAUDE.md's 'Backend never calls third-party APIs synchronously' rule. AI Chat REQUIRES low-latency streaming responses to user input, which is incompatible with Celery's batch model. AsyncAnthropic streaming runs inside the FastAPI request handler. All OTHER Claude calls (Phase 5 daily insights, D-14 title generation) remain in Celery tasks." Add the same note to CLAUDE.md.

### System Prompt (D-26..D-28)

- **D-26:** **Base prompt = docs/CHAT.md §5 verbatim** as the starting text, parameterized with tenant facts at build time. Tenant facts to inject: tenant_name="Sofa Belle", industry="mobilă premium", showrooms (3 from docs/SOFABELLE.md), salesperson roster (6 names from Phase 5 D-09), avg_cycle_days, business hours, 4h response-time target, MVP1 data limitations block (no Meta/Google/TikTok/GA4/GSC/call transcripts).

- **D-27:** **System prompt cached via `cache_control: {type:"ephemeral"}`** on the system block (same pattern as Phase 5 InsightService). Conversation history + tools list NOT cached (change per turn). Maximizes cache hit rate across turns of the same conversation and across users.

- **D-28:** **Persona detection:** the prompt instructs Claude to infer owner vs analyst persona from the question phrasing (per docs/CHAT.md §5) and adapt tone. No explicit user flag in MVP1 — single user is the owner but may ask analyst-style questions. Deferred: per-user persona setting in Iteration 4.

### Anthropic SDK Usage (D-29..D-31)

- **D-29:** **`AsyncAnthropic` instantiated per request** inside the SSE handler (NOT module-level) to satisfy INFRA-05 fork-safety and the Phase 5 T-05-03-03 testability pattern. Reuse the `anthropic` package already added in Phase 5 (`anthropic>=0.30,<1`). Verify min version supports streaming + tool_use combined; bump if needed.

- **D-30:** **Multi-turn tool loop** (orchestrator core): loop while `stop_reason == "tool_use"`: extract tool_use blocks → execute each via TOOLS_REGISTRY (parallel via `asyncio.gather` when multiple in one block) → append `tool_result` messages → call Claude again with full history. Hard cap: 5 tool-use rounds per user turn (cost guard). Streaming applies to the **final** assistant message (after all tool rounds). Intermediate text deltas during tool-use rounds emitted as `assistant_chunk` events too (so the user sees thinking when Claude narrates between tool calls).

- **D-31:** **Cost tracking:** sum `usage.input_tokens` + `cache_read_input_tokens` + `usage.output_tokens` across all Anthropic calls in a turn (tool rounds + final + guard regenerate + title-gen). Write to `chat_messages.tokens_used` on the assistant message. Compute USD via the same formula as Phase 5 (`input_tokens/1M × 3.0 + output_tokens/1M × 15.0`) — store dollar amount in structlog only for MVP1 (no `cost_usd` column on chat_messages to keep schema lean; add in Phase 9 if budget concerns arise).

### Frontend Implementation (D-32..D-36)

- **D-32:** **Streaming consumer pattern:** `fetch(`/api/v1/chat/conversations/${id}/messages`, { method:'POST', body, headers, credentials:'include' })` + `response.body.getReader()` + custom SSE parser splitting on `\n\n` and `data:` prefix. NOT EventSource (EventSource doesn't support POST + credentials reliably; fetch-stream is the documented pattern for SSE-over-POST in 2026). Wrapped in `useChat` hook exposing `{sendMessage, isStreaming, currentToolPills[], cancel}`.

- **D-33:** **Optimistic UI:** user message appears in MessageList instantly with `role:'user', status:'pending'` before SSE round-trip. On `conversation_meta` event, swap optimistic ID → real DB ID. Assistant bubble starts empty + thinking dot pulse, fills as `assistant_chunk` events arrive. Tool pills render inline above the in-progress text.

- **D-34:** **Auto-scroll:** scroll-to-bottom on each `assistant_chunk` IF user is already within 100px of the bottom; otherwise show a "↓ Mesaje noi" button so we don't yank the user out of scrolled-up history.

- **D-35:** **Empty state for /chat:** when no conversations exist, show centered welcome card: H1 "Bună! Întreabă-mă despre datele tale.", paragraph in Romanian, the 5-7 suggested-question chips as the primary CTA. Empty conversation state (new conversation, no messages yet): same chips above input, no welcome card.

- **D-36:** **Mobile responsiveness (D-17 Phase 7 carries forward — NON-NEGOTIABLE):** at < 768px, the conversation list slides over the chat view as a Sheet (reuse Phase 7 hamburger sheet pattern). On mobile, opening a conversation closes the sheet. Touch targets ≥ 44px (chips, send button, list items). Markdown tables overflow-x-auto. Tool pills wrap on narrow viewports.

### i18n + Localization (D-37)

- **D-37:** **All UI strings in `chat` namespace** added to `frontend/messages/ro.json` and `en.json`. Romanian primary. Strings include: page H1/subtitle, "Conversație nouă" button, "Caut datele...", "Verific cifrele...", input placeholder, send button, archive/delete confirm, suggested-question chip wrapper, error messages, empty states. NO hardcoded Romanian in JSX. **System prompt text + Claude responses are NOT translated** — Claude responds in Romanian per system prompt regardless of `NEXT_LOCALE` cookie.

### Testing Strategy (D-38..D-40)

- **D-38:** **Unit tests:** Tool handlers (each — DB fixtures via existing `metrics_factory`/`anomaly_factory`/`insight_factory`). HallucinationGuard (feed crafted responses with known violations). Prompt builder (snapshot). Title generator (mocked Claude response). SSE parser (frontend).

- **D-39:** **Integration tests:** E2E conversation flow with mocked AsyncAnthropic (`respx`-style for `client.messages.stream`). Tool execution dispatch. Persistence round-trip. Rate-limit. CHAT-08 grep gate: confirm `app/api/v1/chat.py` is the ONLY file outside `app/tasks/` that imports `AsyncAnthropic` (other than tests).

- **D-40:** **Adversarial test fixtures** (per docs/CHAT.md §9): YAML file `tests/adversarial_chat_questions.yaml` with ~15 trap questions covering: out-of-scope data requests ("call sentiments"), date-bounded queries ("2025 vs 2026"), entity hallucination probes, prompt injection ("ignore instructions"), CHAT-05 honesty cases ("CAC for Meta"). Run as nightly job (NOT per-commit — API cost). Pass criteria: honest refusal or correct tool call, zero hallucinated entities/numbers.

### Claude's Discretion

- Exact wording of static suggested-question chips beyond the 5 examples in D-17 (final list to be tuned during execution against Sofa Belle's real KPIs).
- Tool pill icon glyphs (lucide-react icons per tool — `Calculator`, `Funnel`, `Users`, etc. — pick what reads well).
- Specific Tailwind classes for tool pills, message bubbles, sidebar item hover/active states (consistent with Phase 7 dashboard component vocabulary).
- Whether to emit an SSE `keepalive` heartbeat event every ~15s for long-running tool chains (recommended for proxy layers; pick based on Caddy timeout).
- Title generator model: prefer Haiku 4.5 if wired in this phase, else Sonnet 4.5 (D-14).
- Whether to add a `react-markdown` plugin for syntax-highlighting code blocks (not expected — chat is data-Q&A, not code-Q&A; skip unless trivial).
- Exact text of Romanian error messages, fallback messages, and empty-state copy beyond what's specified.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Specs and Requirements
- `docs/CHAT.md` — **Primary spec.** Full chat detailed design (architecture, conversation flow, tools registry, system prompt, hallucination guard reference impl, API spec, frontend layout, testing, cost model). Read end-to-end.
- `SPEC.md` §11 — AI Chat overview (concept, tool list, hallucination protection, UI shape, cost target, success metrics)
- `SPEC.md` §7 Layer 5 — `chat_conversations`/`chat_messages`/`chat_tool_calls` table definitions
- `SPEC.md` §12 — API endpoint list (`/api/v1/chat/*`)
- `SPEC.md` §13.8 — Chat Page UI layout (split panel, sidebar, suggestion chips)
- `.planning/REQUIREMENTS.md` — CHAT-01 through CHAT-10 (lines 80–89)
- `.planning/ROADMAP.md` — Phase 8 goal + 7 success criteria (lines 183–196)
- `docs/SOFABELLE.md` — Tenant context: industry, showrooms (3 locations), salesperson roster, avg cycle, business hours, tone guidelines (for system prompt)
- `docs/api-references/mefi/enums.md` § "Salesperson IDs" — Active salesperson full names (Roibu Valeria, Raileanu Leon, Godja Adina Maria, Dragoi Mihaela, Zagrian Emilia, Moaca Andreea) — entity whitelist source

### Stack and Conventions
- `CLAUDE.md` — Project-wide rules; D-25 adds the documented exception for streaming chat (update during execution)
- `docs/CONVENTIONS.md` — Python + TS code style, commit format
- `docs/ARCHITECTURE.md` — async/sync boundary; Layer responsibilities
- `docs/STACK.md` — Tech choices (check STATE.md for overrides)

### Existing Code Patterns to Mirror
- `backend/app/tasks/insights/generate_daily_insights.py` — InsightService Claude-call pattern (AsyncAnthropic instantiation, cache_control system prompt, model="claude-sonnet-4-5", token usage logging)
- `backend/app/services/insights/insight_service.py` — System prompt builder pattern, retry loop, fallback mechanic (for hallucination guard regenerate analogue)
- `backend/app/services/insights/number_validator.py` — **NUMBER_PATTERN regex** to reuse for hallucination guard number extraction (handles Romanian thousands like `23.400` → `23400`)
- `backend/app/services/dashboards/dashboard_read_service.py` — Read-service pattern for tool handlers; canonical 11-source mapping `MEFI_SOURCE_ID_TO_NAME`
- `backend/app/services/metrics/daily_kpi_service.py` / `salesperson_kpi_service.py` / `source_kpi_service.py` — backends for `get_kpi`/`get_salesperson_performance`/`get_lead_categories_breakdown` tools
- `backend/app/services/insights/insight_read_service.py` — backend for `get_recent_insight` tool
- `backend/app/services/anomaly/anomaly_service.py` — `get_stuck_leads` data shape reference (ANOM-03 14-day threshold)
- `backend/app/api/v1/insights.py` — FastAPI router pattern with rate-limit (`SET NX EX`), `get_current_user` dependency, Romanian error messages
- `backend/app/api/v1/router.py` — register new chat router here

### Frontend Patterns to Mirror
- `frontend/src/app/(dashboard)/insights/page.tsx` — Page-level layout, Suspense, TanStack Query usage, Romanian copy patterns
- `frontend/src/components/dashboards/insights/problem-card.tsx` — shadcn Collapsible + severity badge patterns (reuse for tool pill collapsing)
- `frontend/src/components/sidebar.tsx` — Mobile Sheet collapse pattern (mirror for conversation sidebar)
- `frontend/src/components/dashboards/insights/insight-summary.tsx` — `payload.summary` field reference (D-15 from Phase 7 — chat does NOT use this but pattern is shared)
- `frontend/src/lib/api-client.ts` — apiClient with credentials:'include' + 401 refresh; chat fetch wrappers go through this for non-streaming endpoints; streaming endpoint uses raw fetch+ReadableStream but reuses cookie handling
- `frontend/src/lib/formatters.ts` — Romanian formatters (RON, date) — reused in tool pill hints + markdown rendering
- `frontend/messages/ro.json` / `en.json` — extend with new `chat` namespace

### Anthropic SDK Reference
- [Anthropic Tool Use docs](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)
- [Anthropic Streaming docs](https://docs.anthropic.com/en/docs/build-with-claude/streaming)
- [Anthropic Prompt Caching docs](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching)

### Phase 5 Context (Carry-Forward)
- `.planning/phases/05-ai-insights/05-CONTEXT.md` — D-05 (DailyInsightResponse schema — referenced by `get_recent_insight` tool output), D-07 (cache_control pattern), D-09 (salesperson roster), D-model (claude-sonnet-4-5 LOCKED), D-21 (anthropic SDK version)

### Phase 7 Context (Carry-Forward)
- `.planning/phases/07-frontend-dashboards/07-CONTEXT.md` — D-08 (QueryClientProvider already in dashboard layout — chat page inherits), D-12/D-13/D-14 (loading/error/empty patterns to reuse), D-17 (mobile-first NON-NEGOTIABLE — carries to chat), D-25 (i18n namespace approach)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `frontend/src/app/(dashboard)/chat/page.tsx` — current placeholder (20 lines) — DELETE and rebuild from scratch as the full ChatPage
- `frontend/src/components/sidebar.tsx` line 30 — nav already has `{ href: "/chat", icon: MessageSquare, labelKey: "chat" }` — no nav change needed
- `frontend/messages/ro.json` already has `"chat": "Chat AI"` (nav label) and placeholder `"chat": "Chat-ul AI va fi disponibil în curând."` — replace placeholder, expand `chat` namespace
- `backend/app/core/config.py` — `anthropic_api_key` already in Settings (added in Phase 5) — no new env var
- `backend/app/services/insights/number_validator.py` — `NUMBER_PATTERN` greedy regex `\b(\d[\d.,]*\d|\d)\b` handles Romanian thousands — import and reuse in hallucination guard
- `backend/app/services/insights/insight_service.py` — `MODEL`, `MAX_TOKENS`, `TEMPERATURE` constants + `cost_usd` formula → mirror in chat orchestrator
- `anthropic>=0.30,<1` already in `backend/pyproject.toml` from Phase 5 — verify min version supports `client.messages.stream(...)` with `tools=[...]` (likely yes; bump if not)
- `redis.asyncio` already used in `app/api/v1/insights.py` for rate-limit → same pattern for chat message rate-limit

### Established Patterns
- **`get_current_user` FastAPI dependency** — provides `UserOut` with `id` and tenant context — chat endpoints use the same
- **`AsyncSession` via `get_session` dependency** + `with_loader_criteria` tenant isolation seam (Phase 1) — chat tool handlers and message persistence use this
- **Pydantic v2 + `from __future__ import annotations`** in every backend file
- **structlog tenant_id + task_id in every log line** — chat orchestrator logs include `conversation_id` and `message_id` instead of `task_id`
- **Decimal serialization as string** per DATA-04 — tool output `dict`s convert Decimals to `str` before SSE JSON
- **Romanian-first UI strings** through `useTranslations` — no hardcoded Romanian in JSX
- **shadcn-style components** under `frontend/src/components/ui/` — add new primitives via the radix-ui umbrella pattern from Phase 7 (D-Phase 7) when CLI unavailable
- **TanStack Query `staleTime: 5min`, `refetchOnWindowFocus: false`** for read queries (D-11 Phase 7) — chat conversation list uses similar; message-list is mutation-driven by SSE so no Query stale logic

### Integration Points
- `backend/app/api/v1/router.py` line 5–11 — add `from app.api.v1 import chat` and `api_router.include_router(chat.router)`
- `backend/app/models/__init__.py` — register chat models for Alembic autogenerate (mirror Phase 5 D-… insights pattern)
- `frontend/src/app/(dashboard)/chat/page.tsx` — replace placeholder
- `frontend/src/components/sidebar.tsx` — no change (chat link already present)
- `frontend/messages/ro.json` + `en.json` — replace placeholder `chat` placeholder string, add `chat` namespace (similar shape to `insights`/`sales`/`marketing` namespaces from Phase 7)
- `backend/alembic/versions/` — next migration is 009 (last applied was 008 daily_insights from Phase 5; 005/006 were Phase 3 hotfixes; 007 was Phase 4 detected_problems)
- `docker-compose.yml` — no changes (ANTHROPIC_API_KEY env already wired to backend service in Phase 5)
- `CLAUDE.md` — add the CHAT-08 streaming exception note (D-25) in the existing "Backend never calls third-party APIs synchronously" rule section

### Backend-vs-Chat-Tool Reuse Matrix
| Tool | Backend service (no new SQL) |
|---|---|
| `get_kpi` | `DailyKpiService` (Phase 3) |
| `get_funnel_data` | `DashboardReadService.get_sales_dashboard` (Phase 6) |
| `get_salesperson_performance` | `DashboardReadService.get_salespeople_dashboard` + `SalespersonKpiService` (Phase 3/6) |
| `get_leads` | Extend `DashboardReadService` or new `LeadsReadService` thin query against `v_mefi_leads_active` (no MEFI API) |
| `compare_periods` | `DashboardReadService` twice + delta math |
| `get_loss_reasons` | New thin query on `v_mefi_leads_active` filtered by `lifecycle='lost'` group by source/salesperson |
| `get_lead_categories_breakdown` | `DashboardReadService.get_marketing_dashboard` + `SourceKpiService` |
| `get_showroom_performance` | New thin query on `v_mefi_leads_active` group by `showroom_id` |
| `get_recent_insight` | `InsightReadService` (Phase 6) |
| `explain_metric` | Pure Python dict lookup (no DB) |
| `get_stuck_leads` | Pull logic from `AnomalyService.detect_stuck_offer` (Phase 4) into a thin query |
| `get_trend` | `DailyKpiService` over a date range |

This matrix proves D-03: 11 of 12 tools wrap existing services; only `get_leads`/`get_loss_reasons`/`get_showroom_performance`/`get_stuck_leads` need thin new repository queries.

</code_context>

<specifics>
## Specific Ideas

- **CEO is a mobile-only power user** (carry-forward from Phase 7 D-17): chat must work on a phone with one hand. Conversation sidebar as bottom sheet on mobile. Tool pills must wrap. Send button ≥ 44px. Test on a real phone before declaring complete.
- **Sofa Belle data limits in system prompt** (must be explicit per CHAT-05 + SC#3): `estimated_value` is NULL for all leads → Claude must NOT invent revenue figures; Meta/Google/TikTok/GA4/GSC not connected → Claude must honestly defer with "Nu am acces la datele de reclamă/web în această versiune". List these data limits as a dedicated block in the system prompt.
- **Real Sofa Belle KPI ground truth** (from Phase 5 backfill): 1219 leads → 360 visits → 417 offers → 71 contracts (5.8% L→C); Raileanu Leon top closer (22 contracts, 8.3% conversion); Dragoi Mihaela most leads (351) but only 10 contracts (2.8%); Showroom = 360 leads (29.5% volume, 55% of contracts). The system prompt's tenant context block should include the funnel definitions + that "Showroom este canalul principal de conversie" so Claude generates non-generic insights.
- **Tool description language:** tool descriptions passed to Claude (in `definition.description`) are in **English** (Anthropic convention + tool-use docs use English) — only response text and system prompt content are Romanian. Tool input schemas use English field names too.
- **Markdown bold for KPIs:** Claude is instructed (system prompt) to bold key metrics with `**1.234,56 RON**` Markdown. Frontend `react-markdown` renders `<strong>` with `font-semibold text-accent`.
- **Suggested-question dynamic injection — fault tolerance:** if `daily_insights` query fails or is empty, fall back to the 5 static questions only. The endpoint never returns < 5 chips.
- **Title generator timeout:** if title-gen Claude call exceeds 3s, abort and use the truncated-first-message fallback. Don't block the user from sending more messages while title is pending — title appears asynchronously in the sidebar via TanStack Query refetch on `done`.
- **Anthropic SDK version bump:** Phase 5 installed `anthropic>=0.30,<1` (resolved to `0.104.1` per STATE.md 05-03 entry). Verify `0.104.1` supports `client.messages.stream(..., tools=[...])` + `cache_control` together. If not, bump to latest 0.x or move to 1.0 (newer SDK may have streamlined streaming API — research in `gsd-phase-researcher`).
- **One Anthropic call per turn, multi-tool-round capable** (D-30): the cost model in docs/CHAT.md §11 assumes ~5050 input tokens/turn — that's WITH multi-round tools. Verify our cost stays within $0.11/conversation expectation under real Sofa Belle workloads.
- **Conversation pagination deferred:** `GET /chat/conversations/{id}` returns all messages. If a single conversation ever hits 200+ messages we paginate; for MVP1 this never happens.
- **Static `explain_metric` glossary content:** see SPEC.md §6 + docs/CHAT.md examples — define entries for CAC, ROAS, CPL, Conversie L→V, Conversie L→C, AOV/Cec mediu, TTFT, Data Completeness, Stuck Offer. Even if Sofa Belle doesn't have ad-spend data, the explanation is still valuable.

</specifics>

<deferred>
## Deferred Ideas

- **Date-aware inline dashboard links** (date range derived from question and embedded in URL like `/sales?from=...&to=...`) — Phase 9 polish if pilot asks (D-18a guard already permits dashboard paths)
- **Voice input/output** (Web Speech API mic button) — Phase 9+ per docs/CHAT.md §12
- **Chat analytics dashboard** (popular questions, avg rating, tool-call frequency) — Phase 9+
- **Per-user persona setting** (owner vs analyst toggle) — Iteration 4 with multi-user
- **Conversation sharing / export** — out of MVP1 scope
- **Conversation summarization of older messages** (when history > 20 messages) — Iteration 2 cost optimization
- **ML-driven suggested questions** (learned from user behavior) — Iteration 2+
- **Multi-language responses** (EN/RU on demand) — out of scope, Romanian-only
- **Fine-tuning on Romanian SMB question corpus** — needs 10+ clients first
- **RAG on product catalog / sales scripts** — Iteration 3+
- **Proactive chat messages** (Claude notices anomalies and pings) — Phase 9+
- **Hard delete** of conversations (vs soft archive) — Iteration 4 GDPR retention
- **Pagination** of conversation message history (>200 messages per conversation) — deferred until needed
- **`cost_usd` column on `chat_messages`** — defer to Phase 9 if budget analysis becomes a priority
- **Chat-vs-cron model tier split** (Haiku for tools/title, Sonnet for final answer) — possible cost optimization, evaluate after pilot data
- **Conversation tag/folder organization** — out of MVP1 scope
- **Stop/cancel button mid-stream UX** (backend disconnect already detected per D-12; UI button deferred) — Phase 9 polish

</deferred>

---

*Phase: 08-ai-chat*
*Context gathered: 2026-05-29*
