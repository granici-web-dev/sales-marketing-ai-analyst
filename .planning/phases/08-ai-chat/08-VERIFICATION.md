---
phase: 08-ai-chat
verified: 2026-05-29T00:00:00Z
status: gaps_found
score: 3/7 must-haves verified (4 BLOCKED by CR-01..CR-05, all blockers were already surfaced by 08-REVIEW.md)
overrides_applied: 0
re_verification:
  previous_status: initial
gaps:
  - truth: "SC#1 — User can ask 'Cum stăm comparativ cu săptămâna trecută?' and receive a Romanian-language answer with actual WoW delta values via compare_periods + 'Se gândește...' indicator (CHAT-01, CHAT-07)"
    status: partial
    reason: "Code paths exist (compare_periods tool + ThinkingIndicator + streaming SSE) but the hallucination guard's entity regex (CR-04) flags legitimate Romanian sentence starts as fake entities, burning the regenerate budget and likely surfacing the fallback 'Nu pot da un răspuns precis' on real responses. The bug is reproducible in <5 lines of Python on the production regex."
    artifacts:
      - path: "backend/app/services/chat/hallucination_guard.py"
        issue: "Lines 77-79: _ENTITY_PATTERN matches any two capitalized words including Romanian sentence-starters (Conform, În, Pentru, Astăzi, Comparativ, Săptămâna). Verified by repro: 'Conform Sofa Belle' matches as entity 'Conform Sofa Belle'. Check at lines 201-204 has no stopword filter."
    missing:
      - "Romanian sentence-starter stopword list applied before entity match (per 08-REVIEW.md CR-04 fix #1) OR sentence-start detection (preceded by . ? ! or ^) to skip first token"
      - "Corpus regression test asserting common Romanian openers don't trip the entity check"
  - truth: "SC#2 — Claude calls ≥3 distinct tools in a single conversation turn; tool I/O logged in chat_tool_calls (CHAT-02, D-21)"
    status: partial
    reason: "Multi-tool loop with asyncio.gather is correctly implemented and 12 tools are registered. However, D-21 atomicity guarantee is structurally broken: orchestrator never commits between insert_tool_call and insert_assistant_message — if assistant persist fails, the entire turn rolls back including all chat_tool_calls audit rows. The audit guarantee is violated on the failure path that needs it most."
    artifacts:
      - path: "backend/app/services/chat/orchestrator.py"
        issue: "Lines 285-322 write tool audit rows via tool_repo.insert_tool_call (flush only, no commit). Lines 367-386 try to insert_assistant_message — on failure, yields error and returns, leaving no commit. Session is left in an error state, rolling back ALL chat_tool_calls written for the turn. Confirmed by 08-REVIEW.md CR-05."
    missing:
      - "Explicit await self._session.commit() after each successful tool round so audit rows survive a later assistant-persist failure (per 08-REVIEW.md CR-05 fix)"
      - "Explicit await self._session.commit() after insert_user_message before yielding conversation_meta so the frontend's optimistic-ID-swap target row is durable"
  - truth: "SC#4 + SC#5 — All numeric values within ±1% AND conversation history persists across browser sessions per-USER (CHAT-03, CHAT-05, CHAT-10)"
    status: failed
    reason: "Per-user authorization is missing on every conversation endpoint. ConversationRepository filters only by tenant_id, not user_id (CR-01). In a multi-user tenant (Sofa Belle owner + analyst + 6 salespeople), ANY authenticated user can GET/DELETE/POST messages to ANY other user's conversation by guessing/replaying a UUID. Cross-user data leak inside a tenant. CHAT-03's promise ('history stored per user') is broken at the storage layer."
    artifacts:
      - path: "backend/app/services/chat/repositories/conversation_repository.py"
        issue: "Lines 32-34: __init__ takes only tenant_id (no user_id). Lines 75-93 (list/get) and lines 95-123 (update_title/last_message_at/soft_archive) filter only by tenant_id. ChatConversation HAS a user_id column but it is never used as a query predicate."
      - path: "backend/app/api/v1/chat.py"
        issue: "All 5 endpoints (lines 141-275) instantiate ConversationRepository(session, tenant_id) without passing current_user.id. The send_message handler also does not verify conversation ownership before invoking the orchestrator, so any user can stream a reply into any other user's conversation."
    missing:
      - "ConversationRepository accepts user_id and includes it in every WHERE clause (per 08-REVIEW.md CR-01 fix)"
      - "send_message verifies conversation ownership BEFORE orchestrator.run_turn() — return 404 on mismatch"
      - "Cross-user authorization integration test (User A POSTs to User B's conversation_id → 404)"
  - truth: "SC#6 — Streaming first token <2s, no loading pauses; tool round-trips <500ms (CHAT-06, CHAT-09)"
    status: partial
    reason: "Streaming infrastructure is correctly assembled (StreamingResponse, fetch+ReadableStream, X-Accel-Buffering: no, 15s heartbeat, asyncio.Queue producer/consumer). Two latency-degrading bugs surface: (a) Stream-lock 409 burns rate-limit tokens (CR-02), causing legitimate users to hit 429 after ~30 accidental double-taps within an hour; (b) the 1-shot regenerate triggered by CR-04 false positives doubles the perceived latency on responses that contain ordinary Romanian sentences. The plan's BLOCKING mobile + latency UAT (08-06 Task 4) was deferred and never executed."
    artifacts:
      - path: "backend/app/api/v1/chat.py"
        issue: "Lines 305-333: rate-limit INCR happens BEFORE stream-lock SET NX. On 409 conflict, the counter is incremented and never decremented. CR-02 confirmed."
      - path: "backend/app/services/chat/orchestrator.py"
        issue: "Lines 207-357: each guard retry re-streams a full Claude response. With CR-04 firing on common Romanian openers, the second attempt is the norm for sentences like 'Conform Sofa Belle...', doubling time-to-final-token."
    missing:
      - "Reorder rate-limit and stream-lock (acquire lock first, then INCR rate-limit) OR DECR on 409 branch (per 08-REVIEW.md CR-02 fix)"
      - "Live latency measurement at 360/768/1280px with first-token timestamps recorded (08-06 Task 4 BLOCKING UAT)"
      - "3 live Anthropic conversations exercising CHAT-01/CHAT-05/CHAT-10 (08-06 Task 4 BLOCKING UAT)"
  - truth: "Auto-title via Haiku→Sonnet fallback persists to chat_conversations after first turn (D-14)"
    status: failed
    reason: "Title generator is implemented (haiku + sonnet fallback + truncation), but the orchestrator's _update_title closure captures self._session and calls self._session.commit() AFTER the SSE response has already returned. FastAPI's get_session dependency closes the AsyncSession when the request handler exits — so the title UPDATE either raises InvalidRequestError on a closed session or runs against a connection that's already been returned to the pool. Both error paths are swallowed by 'except Exception: pass'. CR-03: titles never persist in production."
    artifacts:
      - path: "backend/app/services/chat/orchestrator.py"
        issue: "Lines 412-428: schedule_title_generation runs as asyncio.create_task that outlives the request. Lines 414-421: closure captures self._session and calls self._session.commit() — but self._session is closed by the time this task fires (~3s later via Haiku timeout). The except Exception: pass at line 420 silently hides every production failure."
      - path: "backend/app/services/chat/title_generator.py"
        issue: "schedule_title_generation accepts update_callback but provides no DB session lifecycle — the callback signature (UUID, str) -> None puts the lifecycle burden on the caller, who got it wrong."
    missing:
      - "Detached title task opens its OWN AsyncSession via AsyncSessionLocal (per 08-REVIEW.md CR-03 fix). Do NOT capture orchestrator._session."
      - "Pass tenant_id (and user_id, once CR-01 is fixed) into schedule_title_generation so the new session can build its own ConversationRepository"
      - "Replace except Exception: pass at line 420-421 with a structured warning log (per 08-REVIEW.md WR-10)"
  - truth: "get_loss_reasons safely interpolates group_by column (no SQL injection vector)"
    status: partial
    reason: "Today the code is safe because group_by is constrained to Literal['source','salesperson']. But the codebase elsewhere uses bindparam discipline religiously, and f-string interpolation of a column name into a text() query is a fragile pattern. Future contributor relaxing the Literal opens real SQLi (08-REVIEW.md CR-06). CHAT-02 requires get_loss_reasons exist; the pattern violates project SQL hygiene."
    artifacts:
      - path: "backend/app/services/chat/tools/get_loss_reasons.py"
        issue: "Lines 63-75: group_col = 'source_id' if ... else 'assigned_to_id'; then f'GROUP BY {group_col}' interpolated into text() at lines 67 + 73. Pattern repeated twice (SELECT + GROUP BY)."
    missing:
      - "Static enum→identifier dict + dict-lookup membership assertion (per 08-REVIEW.md CR-06 fix)"
      - "Unit test asserting model_validate rejects malicious group_by values (defense in depth)"
deferred:
  - truth: "Multi-user / per-user authorization beyond Phase 1's single owner user"
    addressed_in: "Iteration 4 (Phase 9+)"
    evidence: "08-CONTEXT.md § Does NOT include: 'Multi-user / per-user authorization beyond Phase 1's single owner user (Iteration 4 multi-tenancy)'. HOWEVER: the model schema already has a user_id column and the planner committed CR-01 by SKIPPING user_id filtering even within the same single-user tenant. CR-01 is NOT deferred — it is a structural authorization bypass with the user_id column literally sitting unused. Listed here only to acknowledge the planner's deferred-multi-user claim does not cover the bug."
human_verification:
  - test: "Mobile 360px DevTools (Pixel 8 emulation): navigate to /chat, tap hamburger, create conversation, type 'Cum stăm cu vânzările luna asta?', press Enter. Send button visually ≥44px, first token appears within 2s."
    expected: "Hamburger opens a Sheet (w-[85vw] max-w-[320px]); 'Conversație nouă' button is min-h-[44px]; ThinkingIndicator shows; assistant streams Romanian text within 2s; tool pills render inline above text."
    why_human: "Requires real DevTools mobile emulation + live Anthropic API connection. Plan 08-06 Task 4 (BLOCKING) was deferred and remains uncompleted."
  - test: "Tablet 768px: ConversationsList renders as fixed 260px panel; ChatMain flex-1; bubbles max-w-[75%]."
    expected: "Split-panel layout visible without horizontal scroll; conversation sidebar persists during message send/receive."
    why_human: "Visual layout verification at exact breakpoint requires DevTools emulation. Plan 08-06 Task 4 deferred."
  - test: "Desktop 1280px: MessageList uses max-w-3xl mx-auto for readability."
    expected: "Centered message column; no edge-to-edge text on wide displays."
    why_human: "Visual readability check requires real rendering. Plan 08-06 Task 4 deferred."
  - test: "Live Anthropic — Ask 'Cum stăm comparativ cu săptămâna trecută?' and verify response references compare_periods tool data with actual WoW delta values."
    expected: "Romanian response with non-zero numeric WoW deltas; chat_tool_calls table has a row for compare_periods; response is NOT the fallback 'Nu pot da un răspuns precis'."
    why_human: "Requires live Anthropic API connection + verification that CR-04 entity regex does not flag the response. The CR-04 bug means this test will frequently produce the fallback string, BUT it requires a live run to confirm in real-world distribution. Plan 08-06 Task 4 deferred."
  - test: "Live Anthropic — Ask 'Care e CAC-ul Meta?' and verify honest refusal."
    expected: "Response contains 'nu am acces' or equivalent Romanian refusal; NO fabricated CAC number; hallucination_flag may be true; chat_tool_calls log shows Claude did NOT invent a tool to generate ad-spend data."
    why_human: "Requires live Anthropic API. CHAT-05 honesty contract can only be confirmed end-to-end. Plan 08-06 Task 4 deferred."
  - test: "Live Anthropic — Ask 'Care e cel mai bun vânzător?' and verify a real Sofa Belle salesperson name is returned (not 'Maria Popescu' or similar fictitious name)."
    expected: "Response mentions one of: Roibu Valeria, Raileanu Leon, Godja Adina Maria, Dragoi Mihaela, Zagrian Emilia, Moaca Andreea — verified by chat_tool_calls log showing get_salesperson_performance was invoked."
    why_human: "Requires live Anthropic API + real CRM data. CHAT-10 entity-grounding requires end-to-end verification. Plan 08-06 Task 4 deferred."
  - test: "After first assistant turn completes, conversation title in sidebar updates from null/truncated-first-user to a 4-6 Romanian word title within ~5s."
    expected: "Sidebar title visibly changes; chat_conversations.title in DB is updated."
    why_human: "Verifies D-14 title generator AND CR-03 fix. Until CR-03 is fixed, this test will FAIL silently in production (title remains null/truncated forever). Requires live database inspection + live Anthropic call. Plan 08-06 Task 4 deferred."
  - test: "Inline dashboard link: ask 'Unde văd lead-urile blocate?' → response includes [Sales Dashboard](/sales) or similar; renders as DashboardLinkPill with bg-accent/10 + ChevronRight."
    expected: "Link pill rendered with accent style; click navigates to /sales."
    why_human: "CHAT-06 (inline deep-links) requires Claude to actually emit the link AND the MarkdownRenderer to recognize it. Visual + functional check. Plan 08-06 Task 4 deferred."
  - test: "Touch targets (DevTools mobile): Send button computed height ≥44px; ConversationItem ≥44px; suggested-question chip ≥44px."
    expected: "Computed-style inspector shows all three at ≥44px."
    why_human: "Phase 7 D-17 NON-NEGOTIABLE carry-forward (D-36). Requires DevTools inspection. Plan 08-06 Task 4 deferred."
  - test: "Keyboard-only flow + screen reader announcements per UI-SPEC § Accessibility."
    expected: "Tab order reaches all interactive elements; focus ring visible; SR announces 'Răspuns asistent AI' + completed text; tool pill states NOT individually announced."
    why_human: "A11y verification requires assistive tech. Plan 08-06 Task 4 deferred."
  - test: "Conversation persistence across browser sessions: send a message, close browser, reopen, navigate to /chat, click conversation → prior messages and follow-up context visible."
    expected: "All persisted messages reappear in chronological order; reply to last message includes prior context (D-16 history window passes to Claude)."
    why_human: "CHAT-03 / SC#5 end-to-end behavior. Requires real session lifecycle, real refresh, real Anthropic call. Plan 08-06 Task 4 deferred."
---

# Phase 8: AI Chat Verification Report

**Phase Goal:** Business owners and managers can ask questions about their data in plain Romanian and receive accurate, tool-grounded answers with inline dashboard links — turning the product from "dashboard + daily report" into an interactive AI consultant.

**Verified:** 2026-05-29T00:00:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (mapped to ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC#1 | User asks "Cum stăm comparativ cu săptămâna trecută?" → Romanian answer with actual WoW delta via compare_periods + "Se gândește..." indicator | ⚠️ PARTIAL | compare_periods tool implemented (`backend/app/services/chat/tools/compare_periods.py`), ThinkingIndicator + 3 states in UI (`frontend/src/components/chat/thinking-indicator.tsx`), SSE wiring complete. BUT hallucination guard's entity regex (CR-04) reproducibly matches `Conform Sofa Belle` in Romanian responses → triggers regenerate → ultimately surfaces fallback "Nu pot da un răspuns precis". Verified by Python repro on live regex. |
| SC#2 | Claude calls ≥3 distinct tools in a single turn; tool I/O logged in chat_tool_calls (D-21) | ⚠️ PARTIAL | Tool loop with asyncio.gather + 12 tools registered (`TOOLS_REGISTRY` has all 12), audit row written per tool call via `tool_repo.insert_tool_call`. BUT D-21 atomicity broken (CR-05): no commits between tool writes and assistant write — assistant-persist failure rolls back the audit. The audit fails exactly when you most need it. |
| SC#3 | "Nu am acces…" for unavailable data (Meta CAC etc.) | ❓ HUMAN-NEEDED | System prompt instructs Claude to honestly defer (`prompt_builder.py` includes Sofa Belle data-limit block); no automated way to verify Claude's response distribution. Plan 08-06 Task 4 (live UAT) deferred. |
| SC#4 | All numeric values match daily_kpi/salesperson_daily_kpi within ±1% (cross-check test) | ⚠️ PARTIAL | Guard implemented with TOLERANCE=0.01 (1%), reuses Phase 5 `NUMBER_PATTERN`, 22 unit tests passing. BUT CR-04 entity regex false-positives waste the 1-shot regenerate budget and CR-01 means cross-user reads could surface wrong-user data anyway. Live cross-check test missing (deferred to UAT). |
| SC#5 | Conversation history persists per USER; reopen shows prior messages with follow-up context | ❌ FAILED | History persists at TENANT level (migration 009 creates the tables, MessageRepository loads history). BUT CR-01: ConversationRepository never filters by user_id. Any authenticated tenant user can read/archive/post messages to any other user's conversations. "Per user" promise of CHAT-03 is structurally broken. |
| SC#6 | Streaming: first token <2s; tool round-trips <500ms; no loading pauses | ❓ HUMAN-NEEDED | StreamingResponse wired (`backend/app/api/v1/chat.py:426-438`), X-Accel-Buffering: no header, 15s heartbeat via asyncio.Queue race. `useChat` hook implements fetch+ReadableStream+chunk-boundary buffer. Latency NOT measured in real env — Plan 08-06 Task 4 deferred. CR-02 (rate-limit burns on 409) degrades reliability under chat-UI double-tap conditions. |
| SC#7 | Chat endpoint exists as StreamingResponse using Anthropic async client; CLAUDE.md documents D-25 exception | ✅ VERIFIED | `POST /api/v1/chat/conversations/{id}/messages` returns `StreamingResponse(event_generator(), media_type="text/event-stream")` (chat.py:426). `from anthropic import AsyncAnthropic` at chat.py:59. CLAUDE.md contains D-25 documented exception sub-bullet (lines 75-77). CHAT-08 grep gate test PASSES (1/1). |

**Score:** 1 VERIFIED, 4 PARTIAL/FAILED, 2 HUMAN-NEEDED out of 7 success criteria.

### Required Artifacts (from PLAN.md frontmatter and ROADMAP SC#7)

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `backend/alembic/versions/009_chat_tables.py` | 3 tables (chat_conversations/chat_messages/chat_tool_calls) + D-20 columns (hallucination_flag, regenerate_count) + CASCADE FKs | ✅ VERIFIED | revision="009", down_revision="008", all 3 tables defined, CASCADE on conversation_id and message_id, hallucination_flag BOOLEAN, regenerate_count INTEGER, CHECK on role column. test_migration_009_exists_with_correct_revision_chain PASSES. |
| `backend/app/models/chat/` | 3 ORM models matching migration | ✅ VERIFIED | ChatConversation, ChatMessage, ChatToolCall present. All 7 model tests pass. |
| `backend/app/schemas/chat/` | Pydantic v2 request/response/SSE schemas | ✅ VERIFIED | conversation.py, message.py, sse_events.py — 7 SSE event types. |
| `backend/app/services/chat/tools/` | 12 tools + TOOLS_REGISTRY per D-02 | ✅ VERIFIED | All 12 tools registered: compare_periods, explain_metric, get_funnel_data, get_kpi, get_lead_categories_breakdown, get_leads, get_loss_reasons, get_recent_insight, get_salesperson_performance, get_showroom_performance, get_stuck_leads, get_trend. TOOLS_REGISTRY length verified at runtime. |
| `backend/app/services/chat/orchestrator.py` | Streaming + tool loop + guard retry + persistence | ⚠️ ORPHANED-WIRED-BUT-FLAWED | 492 lines, runs Claude tool loop, asyncio.gather, MAX_TOOL_ROUNDS=5, GUARD_RETRY_BUDGET=1. BUT CR-03 (session closed before title commit), CR-05 (no commits between audit and assistant insert). |
| `backend/app/services/chat/hallucination_guard.py` | Strict ±1% number cross-check + entity whitelist + regenerate loop | ⚠️ ORPHANED-WIRED-BUT-FLAWED | TOLERANCE=Decimal("0.01"), reuses Phase 5 NUMBER_PATTERN, 12 unit tests pass. BUT CR-04 entity regex matches Romanian sentence starts. |
| `backend/app/services/chat/title_generator.py` | Auto-title via Haiku→Sonnet fallback | ⚠️ ORPHANED-WIRED-BUT-FLAWED | Title generator works in isolation (6 unit tests pass), but the orchestrator's `_update_title` closure breaks the commit boundary (CR-03). |
| `backend/app/services/chat/prompt_builder.py` | Romanian system prompt + tenant facts + cache_control | ✅ VERIFIED | 161 lines, includes Sofa Belle facts, salesperson roster, MVP1 data-limit block. |
| `backend/app/services/chat/repositories/` | 3 repositories (Conversation/Message/ToolCall) with tenant filter | ❌ FAILED (CR-01) | All 3 repos present and tenant-filtered, BUT ConversationRepository never filters by user_id → cross-user data leak. |
| `backend/app/api/v1/chat.py` | 6 endpoints (5 CRUD + suggested-questions) per D-23 | ⚠️ ORPHANED-WIRED-BUT-FLAWED | All 6 endpoints present (POST conversations, GET list, GET single, DELETE archive, POST messages SSE, GET suggested-questions). BUT all 5 conversation endpoints inherit CR-01. POST messages also has CR-02 (rate-limit burns on 409). |
| `backend/app/api/v1/router.py` | Chat router registered | ✅ VERIFIED | `api_router.include_router(chat.router)` present. |
| `frontend/src/app/(dashboard)/chat/page.tsx` | Split-panel layout (sidebar + main pane) | ✅ VERIFIED | 49 lines, Suspense boundary, useSearchParams, ConversationsList + ChatMain. NOT a stub. |
| `frontend/src/components/chat/` | 14 chat components | ✅ VERIFIED | 14 components present: chat-header, chat-input, chat-main, conversation-item, conversations-list, dashboard-link-pill, markdown-renderer, message-bubble, message-list, suggested-questions, thinking-indicator, tool-pill, tool-pills-row, welcome-card. |
| `frontend/src/hooks/useChat.ts` | SSE consumer hook | ✅ VERIFIED | fetch + ReadableStream + chunk-boundary buffer + 7-event dispatch + AbortController. 9/9 unit tests pass. |
| `frontend/messages/ro.json` + `en.json` | `chat` i18n namespace | ✅ VERIFIED | Both files extended; chat namespace covers welcome/sidebar/input/indicators/tools/suggested/messages/archive/timestamps. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `chat.py:send_message` | `ChatOrchestrator.run_turn` | direct call | ✅ WIRED | Line 366-372 instantiates orchestrator and async iterates run_turn. |
| `chat.py:event_generator` | SSE wire format | `_sse_format(event_name, payload)` + `event:` / `data:` lines | ✅ WIRED | Line 122-130 produces correct W3C EventSource format with `ensure_ascii=False` for Romanian. |
| `orchestrator.py` | `TOOLS_REGISTRY` + asyncio.gather | `_execute_tool` dispatch | ✅ WIRED | Lines 285-322 parallel-execute multiple tool_use blocks per round. |
| `orchestrator.py` | `hallucination_guard.check_response` | post-stream invocation | ✅ WIRED | Lines 329-357. Up to 1 regenerate on FAIL. |
| `orchestrator.py` | `title_generator.schedule_title_generation` | first-turn detection (`is_first_turn = len(history) == 0`) | ❌ NOT_WIRED CORRECTLY (CR-03) | Title task captures `self._session` which is closed by FastAPI's get_session dependency before the task runs. Commit silently fails. |
| `chat.py:send_message` | Redis rate-limit + stream-lock | `aioredis.from_url` + INCR + SET NX | ⚠️ PARTIAL (CR-02) | Both present, but rate-limit INCR happens BEFORE stream-lock check, so 409 burns budget. |
| `useChat.ts` | `/api/v1/chat/conversations/{id}/messages` | `fetch POST + response.body.getReader()` | ✅ WIRED | useChat.test.ts UC1-UC9 all PASS. |
| `markdown-renderer.tsx` | `dashboard-link-pill.tsx` | `renderLink` mapper for /sales, /salespeople, /marketing, /insights, /chat | ✅ WIRED | MR1-MR6 tests pass. |
| `chat-main.tsx` | `useChat` hook | optimistic UI + onMeta + onDone | ✅ WIRED | Owns user/assistant bubble identity; useChat is stateless w.r.t. message IDs. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `chat.py:list_conversations` | `rows` | `ConversationRepository.list_conversations` | DB SELECT from chat_conversations | ✅ FLOWING (but with CR-01: returns ALL tenant conversations, not just current_user's) |
| `chat.py:event_generator` (assistant_chunk) | `accumulated_text` | Anthropic streaming API via `client.messages.stream(...)` | Yes — `text_delta` events accumulated | ✅ FLOWING (when CR-04 doesn't trigger fallback) |
| `chat.py:event_generator` (tool_result) | `result` | TOOLS_REGISTRY handler dispatch → Phase 3/5/6 services → DB | DB queries with tenant_id binding | ✅ FLOWING |
| `chat.py:get_suggested_questions` | `questions` | 5 static Romanian strings + `InsightReadService.get_today()` problems | DB read of daily_insights | ✅ FLOWING (with silent fallback on error) |
| Frontend `useConversation(id)` | `conversation` | `/api/v1/chat/conversations/{id}` | Backend SQL | ✅ FLOWING (subject to CR-01 cross-user leak) |
| Frontend `useChat` (tokens, toolPills) | streaming SSE events | Backend orchestrator | Live SSE | ✅ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| All chat unit tests collect | `pytest tests/unit/chat/ --collect-only` | 115 tests collected | ✅ PASS |
| Chat unit tests pass | `pytest tests/unit/chat/` | 115 passed | ✅ PASS |
| CHAT-08 grep gate passes | `pytest tests/unit/chat/test_anthropic_scope.py` | 1 passed | ✅ PASS |
| Hallucination guard tests | `pytest tests/unit/chat/test_hallucination_guard.py` | 12 passed | ✅ PASS |
| Title generator tests | `pytest tests/unit/chat/test_title_generator.py` | 6 passed (BUT: only unit-level; the CR-03 lifecycle bug requires integration test to surface) | ✅ PASS-but-misleading |
| Chat models reflect migration 009 | `pytest tests/unit/chat/test_chat_models.py` | 9 passed | ✅ PASS |
| Integration test discovery | `pytest tests/integration/chat/ --collect-only` | 13 integration tests collected | ✅ PASS |
| TOOLS_REGISTRY has 12 tools | `python -c "from app.services.chat.tools import TOOLS_REGISTRY; print(len(TOOLS_REGISTRY))"` | 12 | ✅ PASS |
| CR-04 entity regex repro | `python -c "import re; ... 'Conform Sofa Belle'"` | matched: 'Conform Sofa Belle' | ❌ FAIL — confirms the regex flags legitimate Romanian sentence-starts |
| Alembic current = 009 | `alembic current` | KeyError: DATABASE_URL (env not in this shell) | ? SKIP — env-specific, but migration file present and test_migration_009_exists_with_correct_revision_chain passes |

### Probe Execution

No phase-declared probes found under `scripts/*/tests/probe-*.sh` for Phase 8. The phase is a feature-build phase (chat surface), not a migration/tooling phase. SKIPPED.

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|---|---|---|---|---|
| CHAT-01 | 08-05, 08-06 | Romanian question → grounded answer | ⚠️ PARTIAL | UI wired, backend wired, but CR-04 causes false-positive guard rejections on common Romanian phrasing |
| CHAT-02 | 08-03, 08-04 | Tool Use with ≥6 tools | ✅ SATISFIED | 12 tools registered, multi-round loop with asyncio.gather, MAX_TOOL_ROUNDS=5 |
| CHAT-03 | 08-02, 08-04, 08-05 | Conversation history per user persists across sessions | ❌ BLOCKED (CR-01) | Tables exist, history loads, BUT not filtered by user_id — cross-user data leak |
| CHAT-04 | 08-04 | System prompt includes Sofa Belle context | ✅ SATISFIED | prompt_builder.py 161 lines including Sofa Belle facts, salesperson roster, MVP1 data-limit block |
| CHAT-05 | 08-04 | Number cross-check + uncertainty for unavailable data | ⚠️ PARTIAL | Guard implemented, prompt instructs Claude to defer. CR-04 affects accuracy. CHAT-05 honesty live-test deferred. |
| CHAT-06 | 08-05, 08-06 | Inline deep-links to dashboards | ⚠️ PARTIAL | MarkdownRenderer renders /sales /salespeople /marketing /insights /chat as DashboardLinkPill (MR2 test passes). Live verification deferred. |
| CHAT-07 | 08-05, 08-06 | "Se gândește..." indicator | ✅ SATISFIED | ThinkingIndicator with 3 states (thinking, looking-up, verifying-numbers) — TI1-TI5 tests pass |
| CHAT-08 | 08-01, 08-05 | FastAPI StreamingResponse with Anthropic async client + documented exception | ✅ SATISFIED | StreamingResponse at chat.py:426, AsyncAnthropic at chat.py:59, CLAUDE.md D-25 sub-bullet (lines 75-77), CHAT-08 grep gate PASSES |
| CHAT-09 | 08-01, 08-02, 08-03, 08-04, 08-05, 08-06 | <2s to first token; tool round-trips <500ms | ❓ HUMAN-NEEDED | Streaming infrastructure complete (X-Accel-Buffering, heartbeat, asyncio.Queue). CR-02 + CR-04 affect perceived latency. Real measurement deferred (08-06 Task 4). |
| CHAT-10 | 08-04 | Zero hallucinated salesperson/funnel/KPI values | ⚠️ PARTIAL | Guard + entity whitelist implemented (build_entity_whitelist queries mefi_salespeople); CR-04 means real Romanian responses will fire false-positives. CHAT-10 live-test deferred. |

**Orphaned requirements check:** REQUIREMENTS.md lists CHAT-01..CHAT-10 mapped to Phase 8. All 10 IDs appear across at least one plan's `requirements:` frontmatter. No orphaned requirements.

### Anti-Patterns Found

| File | Line(s) | Pattern | Severity | Impact |
|---|---|---|---|---|
| `backend/app/services/chat/orchestrator.py` | 411-412 | `except (asyncio.CancelledError, Exception): pass` | ⚠️ Warning | Bare exception swallow hides cancellation + task errors during cleanup. Acceptable for finally-block cleanup but loses diagnostics. |
| `backend/app/services/chat/orchestrator.py` | 419-421 | `try: await self._session.commit(); except Exception: pass` | 🛑 BLOCKER (CR-03) | The bare-except hides every production failure of CR-03 title persistence. Smell that author suspected the session might be unusable. |
| `backend/app/services/chat/hallucination_guard.py` | 77-79, 201-204 | `_ENTITY_PATTERN` regex matches any 2-3 capitalized words; no Romanian stopword skip | 🛑 BLOCKER (CR-04) | Sentence-start `Conform Sofa` flagged as fake entity. Burns regenerate budget on legitimate responses. Reproducible. |
| `backend/app/services/chat/repositories/conversation_repository.py` | 32-34, 75-93, 115-123 | All methods filter by `tenant_id` only; ChatConversation.user_id column unused | 🛑 BLOCKER (CR-01) | Cross-user data leak within tenant. Every Phase 8 endpoint inherits. |
| `backend/app/services/chat/tools/get_loss_reasons.py` | 63-75 | f-string interpolation of column name into `text()` | 🛑 BLOCKER (CR-06) | Safe today (Literal type), fragile for future contributors. Violates project convention of bindparam discipline. |
| `backend/app/api/v1/chat.py` | 305-333 | INCR rate-limit BEFORE stream-lock check, no DECR on 409 | 🛑 BLOCKER (CR-02) | User locks self out after ~30 accidental double-taps in an hour. |
| `backend/app/services/chat/orchestrator.py` | 285-322 + 367-386 | No commit between `insert_tool_call` and `insert_assistant_message` | 🛑 BLOCKER (CR-05) | D-21 audit guarantee structurally broken on failure path. |
| `backend/app/services/chat/repositories/message_repository.py` | 139-144 | `rows[-(limit-1):]` returns full list when limit=1 (`rows[-0:]`) | ⚠️ Warning (WR-03) | Off-by-one Python slicing edge case. Latent until anyone passes limit=1. |
| `frontend/src/hooks/useChat.ts` | 21-25 | `readAccessToken` reads cookie via JS → not HttpOnly | ⚠️ Warning (WR-07) | XSS escalation surface. Project-wide auth contract decision needed. |
| `frontend/src/lib/chat/parseSSE.ts` | 73-80 | Multi-line `data:` field concatenation without `\n` join | ⚠️ Warning (WR-08) | Latent — backend always sends single-line `data:` today. |
| `frontend/src/components/chat/chat-main.tsx` | 60-74 | `useEffect` rewrites local state on every `useConversation` refetch | ⚠️ Warning (WR-04) | Will overwrite optimistic streaming bubble if `useConversation` ever returns messages. |
| Multiple tool files | various | `_to_jsonable` / `_jsonable` helpers duplicated across 7+ files | ℹ️ Info (IN-02) | Magnet for drift bugs. Extract to shared module. |

**Debt markers (TBD/FIXME/XXX) in Phase 8 files:**
```
grep -rn "TBD\|FIXME\|XXX" backend/app/api/v1/chat.py backend/app/services/chat/ backend/app/models/chat/ backend/app/schemas/chat/ frontend/src/components/chat/ frontend/src/hooks/useChat.ts frontend/src/lib/chat/
```
No `TBD`, `FIXME`, or `XXX` markers found in Phase 8 source files. (Phase 8 uses formal threat-IDs T-08-XX, decision-IDs D-XX, and review-IDs CR-XX / WR-XX / IN-XX — these are tracked references, not debt markers.) Debt-marker gate: PASS.

### Human Verification Required

11 items, see frontmatter `human_verification:` for full detail. Summary:

1. **Mobile 360px DevTools test** — hamburger, Sheet, touch targets, first token <2s
2. **Tablet 768px layout** — sidebar 260px + ChatMain flex-1
3. **Desktop 1280px readability** — max-w-3xl mx-auto
4. **Live "Cum stăm comparativ cu săptămâna trecută?"** — Romanian + compare_periods + WoW delta (CHAT-01/SC#1)
5. **Live "Care e CAC-ul Meta?"** — honest refusal, no fake number (CHAT-05/SC#3)
6. **Live "Care e cel mai bun vânzător?"** — real Sofa Belle name, not "Maria Popescu" (CHAT-10/SC#4)
7. **Title generator end-to-end** — sidebar title updates to 4-6 Romanian words within ~5s (D-14, blocked by CR-03)
8. **Inline dashboard link** — [Sales Dashboard](/sales) rendered as pill (CHAT-06)
9. **Touch targets ≥44px** — Send, ConversationItem, chip
10. **Keyboard + screen reader** — focus ring, SR announces "Răspuns asistent AI"
11. **Conversation persistence across browser sessions** (CHAT-03/SC#5, will fail user-scoping until CR-01 fixed)

All 11 items inherit from plan 08-06 Task 4 BLOCKING checkpoint that was deferred from execution.

### Gaps Summary

**Phase 8 is feature-complete but the goal — "accurate, tool-grounded answers" delivered to a "business owner" — is undermined by 6 BLOCKER-severity bugs surfaced in the code review and confirmed against the codebase:**

1. **CR-01 (Authorization bypass):** Conversation endpoints filter only by tenant_id, never user_id. The `chat_conversations.user_id` column exists but is never used as a query predicate. In a multi-user tenant (Sofa Belle owner + analyst + 6 salespeople), any user can read/archive/post messages into any other user's conversation. CHAT-03 / SC#5 ("history stored per user") is structurally broken.

2. **CR-02 (Stream-lock 409 burns rate-limit):** Rate-limit INCR happens before stream-lock acquisition. A 409 conflict from a double-tap leaves the counter incremented with no DECR. A user can lock themselves out for an hour after ~30 accidental retries on a flaky connection.

3. **CR-03 (Title generator races a closed session):** The orchestrator's `_update_title` closure captures `self._session` and commits AFTER the SSE response has returned, by which point FastAPI's `get_session` dependency has closed the session. Every production title persistence will silently fail (the failure is swallowed by `except Exception: pass`). D-14 contract violated.

4. **CR-04 (Entity regex flags Romanian sentence-starts):** `_ENTITY_PATTERN` matches `Conform Sofa Belle`, `Comparativ Săptămâna`, `În Showroom` etc. Verified by Python repro. Every false positive burns the 1-shot regenerate budget, and the second attempt often surfaces the fallback "Nu pot da un răspuns precis". UX degrades severely on common Romanian phrasing.

5. **CR-05 (Tool audit rolled back on assistant persist failure):** No commits between `insert_tool_call` (multiple per turn) and `insert_assistant_message`. If the assistant insert fails, the session is left in error state and every `chat_tool_calls` row written for the turn is rolled back. D-21 audit guarantee structurally violated on the failure path that needs it most.

6. **CR-06 (f-string column interpolation in get_loss_reasons):** Today's safety depends on Pydantic `Literal["source","salesperson"]`. The pattern violates the codebase's bindparam discipline and creates SQLi surface for any future contributor relaxing the Literal.

**Additionally:** Plan 08-06 Task 4 was a BLOCKING `checkpoint:human-verify` that was deferred and never completed. It carried the live latency check (CHAT-09 / SC#6), the 3 Romanian-quality live Anthropic conversations (CHAT-01 / CHAT-05 / CHAT-10), and the mobile 360/768/1280px responsive verification (Phase 7 D-17 NON-NEGOTIABLE). 11 human verification items are surfaced for the developer.

**Verdict:** Phase 8 must not progress to Phase 9 until CR-01..CR-06 are addressed AND the deferred 08-06 Task 4 BLOCKING UAT runs. Status: `gaps_found`.

---

*Verified: 2026-05-29T00:00:00Z*
*Verifier: Claude (gsd-verifier)*
