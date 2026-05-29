---
phase: 08-ai-chat
reviewed: 2026-05-29T00:00:00Z
depth: standard
files_reviewed: 49
files_reviewed_list:
  - backend/alembic/versions/009_chat_tables.py
  - backend/app/api/v1/chat.py
  - backend/app/api/v1/router.py
  - backend/app/models/chat/chat_conversation.py
  - backend/app/models/chat/chat_message.py
  - backend/app/models/chat/chat_tool_call.py
  - backend/app/schemas/chat/conversation.py
  - backend/app/schemas/chat/message.py
  - backend/app/schemas/chat/sse_events.py
  - backend/app/services/chat/__init__.py
  - backend/app/services/chat/hallucination_guard.py
  - backend/app/services/chat/orchestrator.py
  - backend/app/services/chat/prompt_builder.py
  - backend/app/services/chat/repositories/__init__.py
  - backend/app/services/chat/repositories/conversation_repository.py
  - backend/app/services/chat/repositories/message_repository.py
  - backend/app/services/chat/repositories/tool_call_repository.py
  - backend/app/services/chat/title_generator.py
  - backend/app/services/chat/tools/__init__.py
  - backend/app/services/chat/tools/base.py
  - backend/app/services/chat/tools/compare_periods.py
  - backend/app/services/chat/tools/explain_metric.py
  - backend/app/services/chat/tools/get_funnel_data.py
  - backend/app/services/chat/tools/get_kpi.py
  - backend/app/services/chat/tools/get_lead_categories_breakdown.py
  - backend/app/services/chat/tools/get_leads.py
  - backend/app/services/chat/tools/get_loss_reasons.py
  - backend/app/services/chat/tools/get_recent_insight.py
  - backend/app/services/chat/tools/get_salesperson_performance.py
  - backend/app/services/chat/tools/get_showroom_performance.py
  - backend/app/services/chat/tools/get_stuck_leads.py
  - backend/app/services/chat/tools/get_trend.py
  - frontend/src/app/(dashboard)/chat/page.tsx
  - frontend/src/components/chat/chat-header.tsx
  - frontend/src/components/chat/chat-input.tsx
  - frontend/src/components/chat/chat-main.tsx
  - frontend/src/components/chat/conversation-item.tsx
  - frontend/src/components/chat/conversations-list.tsx
  - frontend/src/components/chat/dashboard-link-pill.tsx
  - frontend/src/components/chat/markdown-renderer.tsx
  - frontend/src/components/chat/message-bubble.tsx
  - frontend/src/components/chat/message-list.tsx
  - frontend/src/components/chat/suggested-questions.tsx
  - frontend/src/components/chat/thinking-indicator.tsx
  - frontend/src/components/chat/tool-pill.tsx
  - frontend/src/components/chat/tool-pills-row.tsx
  - frontend/src/components/chat/welcome-card.tsx
  - frontend/src/hooks/useChat.ts
  - frontend/src/hooks/useConversations.ts
  - frontend/src/hooks/useSuggestedQuestions.ts
  - frontend/src/lib/chat/parseSSE.ts
  - frontend/src/lib/tool-pill-hints.ts
findings:
  critical: 6
  warning: 14
  info: 7
  total: 27
status: issues_found
---

# Phase 8: Code Review Report

**Reviewed:** 2026-05-29T00:00:00Z
**Depth:** standard
**Files Reviewed:** 49
**Status:** issues_found

## Summary

Phase 8 ships a substantial and well-documented AI Chat surface — 12 tools, 6 endpoints, hallucination guard, SSE streaming, full conversation persistence, and a React chat client. The threat-model discipline is visible everywhere (T-08-01 through T-08-06 references; LM-1 through LM-11 mitigations; explicit defense-in-depth on tenant scoping). Most of the code is correct.

That said, the adversarial review found multiple **BLOCKER** defects that will affect production correctness and security:

1. **Authorization gap on every conversation endpoint** — only `tenant_id` is filtered, not `user_id`. Any user in a tenant can read/archive/post messages to ANY other user's conversation by guessing/replaying a UUID. This is a real cross-user data leak inside a tenant.
2. **Stream-lock is leaked on rate-limit overrun** — the lock acquire happens *after* the rate-limit check inside the same `async with`, but on the rate-limit branch we `raise HTTPException` *before* acquiring the lock (correct); however, on the lock-contended branch (HTTP 409) the rate-limit counter has already been INCR'd and IS NOT decremented, so every contended request burns one of the 30 hourly quota tokens. Combined with finding 3 below this lets a user lock themselves out by accident.
3. **`title_generator._generate` re-uses the request-scoped DB session after the SSE response closes** — the orchestrator schedules title generation as a detached `asyncio.create_task`, and the `_update_title` closure captures `self._session` plus calls `self._session.commit()`. By the time the title call returns (Haiku + 3s timeout), the FastAPI request handler that owns the AsyncSession has already returned and the session is closed/expired. This will silently fail in production (the title never lands). The `try/except` swallows the error.
4. **Hallucination guard entity regex matches sentence-start Romanian words** — `_ENTITY_PATTERN` matches any two-word capitalized phrase, so a normal Romanian sentence "**Conform** datelor **Maria Popescu**..." matches `Conform Datele` (sentence start + capitalized noun) as an entity and flags it. Verified by Python repro: regex matches "Conform Sofa" in "Conform Sofa Belle". This will cause spurious guard failures and burn the regenerate budget on legitimate responses.
5. **Tool audit log persistence likely lost when assistant persist fails** — the orchestrator never commits between `_execute_tool` and `insert_assistant_message`. If the assistant insert raises, the whole turn rolls back including all `chat_tool_calls` rows just written by `tool_repo.insert_tool_call(...)`. The D-21 audit guarantee says "every tool call writes exactly one row" — this is structurally violated on failure paths.
6. **SQL injection vector via `get_loss_reasons.group_col`** — the column name is selected by an enum but interpolated via f-string directly into `text(...)`. Today it's safe because `Literal["source","salesperson"]` constrains the values; but the Pydantic input is `model_validate`d from Claude's free-form `input` dict and the f-string interpolation is the wrong pattern for this codebase. Any future contributor adding a new `group_by` value or relaxing the Literal opens an SQLi. Stronger: bind the column via a static dict mapping enum → identifier and assert membership at runtime.

There are also significant correctness concerns in the tools that wrap Phase 6 services (the `get_stuck_leads` `days` parameter is ignored by the SQL, the `compare_periods` baseline-percentage uses metric names that don't match the dashboard shape, etc.). The frontend has good defensive code but leaks two real bugs: the `useEffect` in `chat-main.tsx` overrides optimistic UI on conversation refetch, and the rate-limit retry logic in `useChat` has no exponential backoff.

The good news: tenant scoping at the DB layer is genuinely solid (TenantScopedMixin + explicit tenant_id binds on text() queries + repository validation), the Pydantic v2 input validation is rigorous, and the SSE protocol is correctly implemented with heartbeats and proxy buffer disabling.

## Critical Issues

### CR-01: Authorization bypass — conversation endpoints don't filter by `user_id`

**File:** `backend/app/api/v1/chat.py:200-275` (all conversation endpoints)
**Issue:** Every chat endpoint authenticates the user but never restricts queries to the *owner's* conversations. `ConversationRepository.get_by_id`, `list_conversations`, `update_title`, and `soft_archive` filter only by `tenant_id`. In a multi-user tenant (e.g. Sofa Belle owner + analyst + 6 salespeople), any authenticated user can:

  - `GET /chat/conversations/{any_uuid}` → read any other user's conversation envelope (404 leaks existence; 200 leaks title)
  - `DELETE /chat/conversations/{any_uuid}` → soft-archive another user's conversation
  - `POST /chat/conversations/{any_uuid}/messages` → inject messages into another user's conversation and stream replies through their context (history is loaded by `conversation_id` only — D-16)

The `ChatConversation` model HAS a `user_id` column and the table is documented as "owned by a single user inside a tenant" (model docstring). The filter is just missing.

The conversation list endpoint `list_conversations` ALSO returns all tenant conversations — not just `current_user`'s. The Phase 1 `with_loader_criteria` event listener only scopes by tenant_id; it does NOT cover user_id.

**Fix:**
```python
# In ConversationRepository.get_by_id / soft_archive / update_title / list_conversations
# Accept user_id and filter on it (defense-in-depth)
class ConversationRepository:
    def __init__(self, session: AsyncSession, tenant_id: UUID, user_id: UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id
        self._user_id = user_id

    async def get_by_id(self, conversation_id: UUID) -> ChatConversation | None:
        stmt = (
            select(ChatConversation)
            .where(ChatConversation.tenant_id == self._tenant_id)
            .where(ChatConversation.user_id == self._user_id)  # ADD
            .where(ChatConversation.id == conversation_id)
        )
        ...

# In every endpoint:
repo = ConversationRepository(session, tenant_id, current_user.id)
```

For `send_message`: load the conversation FIRST, verify ownership, then run the orchestrator. If the row is missing or owned by another user → 404 (avoid leaking the difference between "no such conversation" and "forbidden").

---

### CR-02: Rate-limit counter increments on stream-lock conflict — locks user out after a few mis-fires

**File:** `backend/app/api/v1/chat.py:307-333`
**Issue:** The flow inside the `async with aioredis...` block is:

```
1. INCR rate_key  ← always runs
2. if count > 30 → 429
3. SET NX lock_key → if not acquired → 409
```

If two browser tabs fire `send_message` near-simultaneously (a common race in chat UIs — user double-taps Send, or the input retries on network flakiness), the first wins the lock and starts streaming, the second gets 409. But the second request has already **consumed** one of the 30 tokens before the 409 was raised. There is no decrement.

Repeat this 30 times in an hour (entirely plausible during a flaky Wi-Fi session) and the user is locked out for the rest of the hour with HTTP 429 — even though they never received an answer.

The same applies to legitimate "send while already streaming" UI errors: the user expects nothing to happen, but their hourly budget shrinks.

**Fix:** Either acquire the stream-lock FIRST and increment the rate-limit AFTER (so a 409 doesn't burn budget), or DECR the counter on the 409 branch:

```python
async with aioredis.from_url(...) as r:
    # 1. Stream-lock FIRST
    was_set = await r.set(lock_key, "1", nx=True, ex=STREAM_LOCK_TTL)
    if not was_set:
        raise HTTPException(409, ...)

    # 2. Rate-limit (only after we know we'll actually stream)
    count = await r.incr(rate_key)
    if count == 1:
        await r.expire(rate_key, RATE_LIMIT_TTL)
    if count > RATE_LIMIT_MAX:
        # Release the lock we just took (we won't stream)
        await r.delete(lock_key)
        raise HTTPException(429, ..., headers={"Retry-After": str(...)})
```

Note: this also fixes the symmetric leak — currently a 429 leaves the **lock** un-acquired (OK), but the swap above would require careful symmetric cleanup. Pick a defensive order and document it.

---

### CR-03: Title generator runs after session is closed — title persistence silently fails

**File:** `backend/app/services/chat/orchestrator.py:412-428`, `backend/app/services/chat/title_generator.py:78-141`
**Issue:** After the `done` SSE event yields, the orchestrator schedules title generation:

```python
async def _update_title(cid: UUID, title: str) -> None:
    await conv_repo.update_title(cid, title)
    try:
        await self._session.commit()
    except Exception:
        pass

schedule_title_generation(conversation_id, user_text, accumulated_text, _update_title)
```

`schedule_title_generation` calls `asyncio.create_task(...)`. The task captures `self._session` and `conv_repo` (which itself holds a reference to `self._session`). The HTTP request returns immediately after the SSE generator finishes — at that point, FastAPI's `get_session` dependency exits its `async with` block and **closes the AsyncSession** (or returns it to the pool).

When `_update_title` runs ~3 seconds later (Haiku timeout), `self._session` is either:
  - Closed (cannot execute UPDATE) → `IllegalStateError` or `InvalidRequestError`, silently swallowed by the bare `except Exception: pass`
  - Returned to the pool and given to another request → potential data corruption

The result: **conversation titles never get persisted in production**. The bug is hidden because every error path in `_generate` and `_update_title` is `except Exception: pass` or `logger.warning`.

This is a real production bug, not a theoretical one. The fact that `commit()` is wrapped in `try/except` with no logging is a smell that the author suspected the session might be unusable.

**Fix:** The detached title task must own its own DB session lifecycle. Use the SessionLocal factory:

```python
# title_generator._generate (or a new helper)
from app.db.session import AsyncSessionLocal  # adjust to your factory name

async def _persist_title(conversation_id: UUID, title: str, tenant_id: UUID) -> None:
    async with AsyncSessionLocal() as session:
        repo = ConversationRepository(session, tenant_id, user_id)
        await repo.update_title(conversation_id, title)
        await session.commit()
```

Pass `tenant_id` + `user_id` into `schedule_title_generation` and have it open its own session. Do NOT capture `orchestrator._session`.

---

### CR-04: Hallucination guard entity regex flags sentence-start Romanian words

**File:** `backend/app/services/chat/hallucination_guard.py:77-79, 200-204`
**Issue:** The entity pattern matches any capitalized 2-3-word phrase:

```python
_ENTITY_PATTERN = re.compile(
    r"\b([A-ZĂÂÎȘȚ][a-zăâîșț]+ [A-ZĂÂÎȘȚ][a-zăâîșț]+(?: [A-ZĂÂÎȘȚ][a-zăâîșț]+)?)\b"
)
```

This matches `Conform Sofa` in a sentence like "Conform Sofa Belle, vânzările au crescut...", because Romanian sentences often START with a capitalized adverb (`Conform`, `În`, `Pentru`, `Astăzi`, `Săptămâna`, `Luna`, `Showroom-ul`) followed by a capitalized proper noun. I verified this with a Python repro on the very example string.

Worse: the Romanian prompt instructs the model to write sentences like "**Comparativ cu** săptămâna trecută, lead-urile au crescut" — `Comparativ Săptămâna` would match. Or "**În** showroom-ul **Brașov**" → `În Showroom` matches.

Every such false positive triggers `regenerate_notice` and burns the 1-shot retry budget. Worse, on the second regeneration the model is told its previous reply contained "numere/entități nesusținute de date: ['entity:Conform Sofa']" — which is gaslighting the model with a guard bug.

Net effect: legitimate Romanian responses will frequently be flagged as hallucinations and replaced with the fallback "Nu pot da un răspuns precis". UX degrades severely.

**Fix:** Either:
  1. Use a stopword list of common Romanian sentence-starters (`{Conform, În, Pentru, Astăzi, Săptămâna, Luna, Anul, Vânzările, Comparativ, ...}`) and skip matches where the first token is in it.
  2. Require BOTH tokens to look like proper nouns (e.g., NOT in a stopword set), OR run a Romanian POS tagger.
  3. Restrict the entity check to NAMES specifically — match only patterns that look like First Last with both tokens NOT in a Romanian function-word set.
  4. Most pragmatic: skip the entity check entirely when the first character of the match is at the start of a sentence (preceded by `.`, `?`, `!`, or `^`).

```python
_ROMANIAN_SENTENCE_STARTERS = {
    "Conform", "În", "Pentru", "Astăzi", "Săptămâna", "Luna", "Anul",
    "Vânzările", "Comparativ", "Datele", "Showroom", "Showroom-ul",
    "Lead", "Lead-uri", "Oferta", "Contractul", "Cel", "Cea", ...
}

for match in _ENTITY_PATTERN.finditer(response_text):
    candidate = match.group(1)
    first_word = candidate.split()[0]
    if first_word in _ROMANIAN_SENTENCE_STARTERS:
        continue
    if candidate not in all_names:
        unsupported.append(f"entity:{candidate}")
```

Also add a corpus regression test using real model output samples.

---

### CR-05: Tool audit rows are rolled back when assistant persistence fails

**File:** `backend/app/services/chat/orchestrator.py:285-322, 367-386`
**Issue:** During the tool loop, each `_execute_tool` call writes a `chat_tool_calls` audit row via `tool_repo.insert_tool_call(...)`. The repository calls `session.add()` + `flush()` but **does not commit** (per WR-04 — caller commits atomically).

Later, the orchestrator tries to write the assistant message:

```python
try:
    await msg_repo.insert_assistant_message(...)
except Exception:
    self._log.exception("chat.assistant_persist_failed")
    yield ("error", ...)
    return
```

If `insert_assistant_message` fails (CHECK constraint, FK violation, conn drop), the orchestrator returns. At no point in the entire `run_turn` flow does the orchestrator explicitly commit. Commits are owned by the FastAPI dependency wrapper or by the SSE generator's `finally` — both of which will see the session in an error state and roll back.

Result: every tool call that ran (and its audit row) is **lost from the DB**, contradicting D-21 ("every tool call writes exactly one chat_tool_calls row"). The audit guarantee is broken on the failure path that needs it most (the failure path where you most want to know what tools were attempted).

Note: the user message ALSO gets rolled back, but the orchestrator already streamed `conversation_meta` advertising its UUID to the frontend. Now the frontend holds a `message_id_user` that does not exist in the DB. If the user retries or refreshes, the row is missing — silent data loss.

**Fix:** Commit incrementally so audit rows survive downstream failures:
  - Commit after `insert_user_message` (before yielding `conversation_meta`).
  - Commit after each successful tool loop round (after the audit rows are flushed).
  - Commit after `insert_assistant_message` succeeds.

```python
# After persisting the user message
await self._session.commit()  # so conversation_meta UUID is durable

# After each tool round (between rounds)
await self._session.commit()  # so chat_tool_calls audit survives

# After assistant insert
await self._session.commit()
```

Tradeoff: this trades atomicity for durability. Given D-21's audit contract, durability is the correct choice. Document the change in PATTERNS.md.

---

### CR-06: `get_loss_reasons` f-string interpolation of column name is the wrong codebase pattern

**File:** `backend/app/services/chat/tools/get_loss_reasons.py:63-75`
**Issue:**

```python
group_col = "source_id" if inp.group_by == "source" else "assigned_to_id"

sql = text(
    "SELECT "
    f"  {group_col} AS group_key, "
    "  COUNT(*) AS lost_count "
    "FROM v_mefi_leads_active "
    "WHERE tenant_id = :tid "
    "  AND lifecycle = 'lost' "
    "  AND (created_at_source AT TIME ZONE 'Europe/Bucharest')::date BETWEEN :df AND :dt "
    f"GROUP BY {group_col} "
    "ORDER BY lost_count DESC"
).bindparams(bindparam("tid", type_=PG_UUID(as_uuid=True)))
```

Today this is safe: `group_by: Literal["source","salesperson"]` is enforced by Pydantic before the f-string runs. But this pattern is fragile in a codebase that elsewhere uses `bindparam` discipline religiously:

  1. Any future contributor relaxing the Literal (e.g. adding a third grouping like `"showroom"`) and forgetting the safety net opens a real SQLi.
  2. A future schema change that introduces a column with the same name as a malicious payload becomes ambient code-execution surface.
  3. The same f-string pattern is repeated 3 times in the file (SELECT and GROUP BY), increasing audit cost.

CLAUDE.md says "Не использовать raw SQL без причины" — when raw SQL IS used, the convention should be **never interpolate identifiers with f-strings**. Use a dict mapping enum → tuple of (select-expr, group-by-expr) and assert membership before the SQL is built.

**Fix:**
```python
_GROUP_COLUMNS: dict[str, str] = {
    "source": "source_id",
    "salesperson": "assigned_to_id",
}
group_col = _GROUP_COLUMNS[inp.group_by]  # KeyError if Pydantic ever relaxes the Literal
# Use the .format() or string concat on a value we've JUST asserted via dict membership.
sql = text(
    f"SELECT {group_col} AS group_key, COUNT(*) AS lost_count "
    "FROM v_mefi_leads_active "
    f"WHERE tenant_id = :tid AND lifecycle = 'lost' "
    "AND (created_at_source AT TIME ZONE 'Europe/Bucharest')::date BETWEEN :df AND :dt "
    f"GROUP BY {group_col} ORDER BY lost_count DESC"
)
```

The minimal change is the dict lookup — but please also add a unit test that calls `_handler` with a synthetic `inp.group_by = "'; DROP TABLE chat_messages; --"` to prove the type system fails closed.

## Warnings

### WR-01: `get_stuck_leads` `days` input is ignored by the SQL — output is misleading

**File:** `backend/app/services/chat/tools/get_stuck_leads.py:38-97`
**Issue:** The tool accepts `days: int` (defaults to 14, range 1-365) but the wrapped `DashboardReadService.get_stuck_offers` hardcodes a 14-day threshold inside its SQL (`HAVING MAX(h.changed_at) < now() - interval '14 days'`). The handler just echoes the user-requested threshold in the response (`"days_threshold": inp.days`) without applying it.

When Claude calls `get_stuck_leads(days=30)`, the response says `"days_threshold": 30` but the actual data filter was 14. Claude then quotes back "Avem 12 lead-uri blocate de peste 30 zile" when the underlying SQL only filtered ≥14 days. This is a **correctness defect** that the hallucination guard cannot catch (the number 12 IS in the tool result, just for the wrong threshold).

**Fix:** Either:
  - Filter the result in Python: drop leads whose `days_stuck < inp.days`.
  - Or refuse the call when `inp.days != 14` with an error so Claude knows the constraint.
  - Best: extend `get_stuck_offers` to accept a `days_threshold` parameter (RESEARCH Open Decisions #6 notes this is deferred — but the deferral plus the unused-input field combine to make a real bug).

```python
leads_filtered = [lead for lead in leads if lead.get("days_stuck", 0) >= inp.days]
```

---

### WR-02: `compare_periods` `_extract_metric` reads `funnel.leads` etc., but the dashboard returns a different shape

**File:** `backend/app/services/chat/tools/compare_periods.py:50-76`
**Issue:** The extractor probes several locations:
```python
funnel.get("leads", kpi.get("leads_total"))
```

But looking at the dashboard service (`DashboardReadService.get_sales_dashboard`), the actual returned `funnel` dict is keyed by **funnel STAGES** (`{"lead": N, "visit": N, "offer": N, "contract": N}` — singular nouns) not `leads`/`visits`/`offers`/`contracts` plural. Verifying this is outside the file scope, but the fallback chain only works because of the secondary `kpi.get("leads_total")` lookup. If `funnel.get("leads")` actually returns None and `kpi.get("leads_total")` returns the integer, the delta math works. If both return None silently, the per-metric delta is silently None.

There is no test asserting the dashboard's actual keys match the chain. Add one. (And consider falling through with a structlog warning so silent-None doesn't hide the schema drift.)

**Fix:** Add an integration test that builds a real dashboard, runs `compare_periods`, and asserts each requested metric resolves to a non-None Decimal.

---

### WR-03: `MessageRepository.load_history` will deduplicate by Python identity, not content

**File:** `backend/app/services/chat/repositories/message_repository.py:139-144`
**Issue:**

```python
first_user = next((r for r in rows if r.role == "user"), None)
recent = rows[-(limit - 1):]
if first_user is not None and first_user not in recent:
    keep = [first_user, *recent]
```

`first_user not in recent` calls SQLAlchemy ORM `__eq__`, which for ORM instances **compares by identity / PK**. If `first_user.id == recent[0].id`, the check works correctly. But if the same row is loaded twice in a session (rare here — single SELECT), the comparison can do object-identity comparison. The codepath is correct *today* because all `rows` come from the same SELECT; calling it out so a future refactor that loads `first_user` separately doesn't silently break dedup.

Also: when `limit == 1`, `recent = rows[-0:]` which is **the full list**, not an empty list. So `load_history(conv_id, limit=1)` returns the entire history. This is an off-by-one — Python slicing edge case.

**Fix:**
```python
if limit <= 1:
    keep = [rows[-1]] if rows else []
else:
    recent = rows[-(limit - 1):]
    first_user = next((r for r in rows if r.role == "user"), None)
    if first_user is not None and first_user.id not in {r.id for r in recent}:
        keep = [first_user, *recent]
    else:
        keep = recent
```

---

### WR-04: `chat-main.tsx` `useEffect` overwrites optimistic state on every conversation refetch

**File:** `frontend/src/components/chat/chat-main.tsx:60-74`
**Issue:**

```javascript
useEffect(() => {
  if (conversation?.messages && conversation.messages.length > 0) {
    setMessages(
      conversation.messages.map((m) => ({...}))
    );
  } else if (!conversationId) {
    setMessages([]);
  }
}, [conversation, conversationId]);
```

`conversation` is the result of `useConversation(conversationId)` — a TanStack Query that revalidates on focus, on the `done` SSE event (via `qc.invalidateQueries(["chat","conversations"])`), and every `STALE_TIME` (60s).

When the user is mid-stream (optimistic bubble + accumulated tokens in local state), TanStack invalidation can trigger a refetch of `useConversation`. The hook returns the **server's** message list (which now includes the just-persisted assistant message), and the `useEffect` replaces local state — **wiping the streaming bubble** mid-token and showing the server snapshot.

If the streaming bubble had any local content the user was watching, they'll see it flash to a different layout (server message comes back, optimistic UI vanishes, then new tokens append to nothing).

Also note: the `useConversation` query is fired on every `conversationId` change but `ConversationDetail.messages` is **always undefined** in the current backend (the `GET /chat/conversations/{id}` endpoint comment explicitly says "Message history is intentionally NOT returned"). So the `if` branch is dead code today — but the moment someone adds it, the bug fires.

**Fix:** Make the effect a one-shot per conversation switch:
```javascript
const prevConvIdRef = useRef<string | null>(null);
useEffect(() => {
  if (prevConvIdRef.current !== conversationId) {
    // Conversation switched — reset to server messages.
    if (conversation?.messages?.length) setMessages(conversation.messages.map(...));
    else setMessages([]);
    prevConvIdRef.current = conversationId;
  }
  // Do NOT re-hydrate on refetch of the same conversation.
}, [conversationId, conversation]);
```

---

### WR-05: `useChat.sendMessage` does not propagate the error to the assistant bubble UI

**File:** `frontend/src/hooks/useChat.ts:147-164`, `frontend/src/components/chat/chat-main.tsx:77-93`
**Issue:** When the SSE call returns a non-OK status (429/409/other), `useChat` sets the `error` state and bails. But the optimistic assistant bubble that `chat-main.tsx` pushed in `sendMessage` BEFORE awaiting `chat.sendMessage` is still in `messages` with `status: "pending"`. The user sees an empty bubble with the thinking dots forever, plus a red error banner. The bubble is never cleared.

**Fix:** When the error fires, remove the pending optimistic bubble (or transition it to an inline error state):
```javascript
const chat = useChat({
  onDone: (...) => { ... },
});
// Watch for chat.error and clean up the orphan bubble.
useEffect(() => {
  if (chat.error) {
    setMessages((prev) => prev.filter(m => m.status !== "pending" || m.role !== "assistant"));
  }
}, [chat.error]);
```

---

### WR-06: `useChat.cancel` does not release the server-side stream-lock

**File:** `frontend/src/hooks/useChat.ts:264-266`, `backend/app/api/v1/chat.py:404-424`
**Issue:** The client `cancel()` aborts the fetch via `AbortController`. The server-side generator catches the aborted client via `disconnect_probe = request.is_disconnected`, exits, and the `finally` block deletes the Redis lock. Good.

But the lock release lives behind a network round-trip and is best-effort (`except Exception: pass`). If the server crashes or the worker is killed between the abort and the cleanup, the lock survives 180s. Meanwhile the user's UI cleared `isStreaming=false`, so they hit Send again → 409.

UX-level fix: surface a Romanian-localized retry hint ("conexiunea anterioară încă se eliberează — așteaptă 30 sec") instead of bare "Așteaptă răspunsul curent" when the lock conflict happens shortly after a client cancel.

Server-side: consider keying the lock on `(conversation_id, request_id)` instead of just `conversation_id`, so the cleanup callback (or the next request from the same client) can disambiguate "my old aborted stream" from "someone else streaming".

---

### WR-07: `useChat` reads `access_token` from `document.cookie` — XSS escalation surface

**File:** `frontend/src/hooks/useChat.ts:21-25`
**Issue:**
```javascript
function readAccessToken(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/(?:^|;\s*)access_token=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}
```

Reading the access token from `document.cookie` means the cookie is **not HttpOnly** — any JavaScript injection (compromised npm dep, XSS in `MarkdownRenderer` if its allowlist is bypassed, browser extension) can exfiltrate the session token. The rest of the codebase appears to also use cookies (`credentials: "include"` is set on the fetch), so the cookie is sent automatically and the `Authorization: Bearer` header is **redundant**.

If the backend accepts EITHER, the `Bearer` header is redundant AND increases attack surface. If the backend requires `Bearer`, then the access-token cookie can't be HttpOnly.

**Fix:** Pick one auth mechanism:
  - Cookie-only: drop `readAccessToken()` and the `Authorization` header from `useChat`. Mark the access-token cookie HttpOnly + Secure + SameSite=Lax server-side. This prevents JS exfiltration.
  - Header-only: keep the current code but store the token in `sessionStorage` instead of a JS-readable cookie (sessionStorage is also XSS-readable but at least the access path is explicit).

Discuss with whoever owns the Phase 1 auth contract before changing.

---

### WR-08: SSE multi-line `data:` concatenation in `parseSSE.ts` is incorrect per spec

**File:** `frontend/src/lib/chat/parseSSE.ts:73-80`
**Issue:**
```javascript
for (const line of frame.split("\n")) {
  ...
  } else if (line.startsWith("data: ")) {
    dataLine += line.slice(6);
  }
}
```

Per the W3C EventSource spec, multi-line `data:` fields should be joined with `\n`, NOT bare concatenation. So:
```
data: {"foo":
data: 1}
```
Should produce `{"foo":\n1}`, but this code produces `{"foo":1}`. Today the backend always emits a single `data:` line per frame, so the bug is latent. If anyone ever streams a multi-line payload (or a payload that exceeds the SSE line-length limit), JSON parsing silently corrupts.

**Fix:**
```javascript
} else if (line.startsWith("data:")) {
  // Strip exactly the "data:" prefix and optional leading space; join with "\n".
  const value = line.startsWith("data: ") ? line.slice(6) : line.slice(5);
  dataLine = dataLine ? dataLine + "\n" + value : value;
}
```

---

### WR-09: `_compute_derived` in hallucination_guard is O(n²) — explodes when tool results have many numbers

**File:** `backend/app/services/chat/hallucination_guard.py:112-130`
**Issue:** This is the only "performance smell" that is also a correctness risk: when tool results include large tables (e.g. `get_leads` returns up to 50 lead rows × 6 fields = 300 numbers; `get_trend` returns 90 daily points × 1 value = 90 numbers + dates → up to 200 numbers total per tool call), the pairwise derived set grows as O(N²). For N=200 numbers across multiple tools, that's 40k derived values × 3 operations = 120k Decimal computations per guard call.

Worse, every assertion is also O(allowed) inside `_is_within_tolerance` — so the full guard pass is O(R × |allowed|) where R is the number of response numbers. For a typical 30-number response and N=200, that's 30 × 120k = 3.6M Decimal divisions. The guard runs **twice** (once per attempt) on the worst path.

Out-of-scope per phase config (performance not in v1). Listed as Warning because the guard latency directly affects user-perceived response time AFTER the stream completes (D-08 — "frontend has already painted the first stream"). Cap N defensively:

**Fix:** Bound the derived set size — sample if needed:
```python
def _compute_derived(base: set[Decimal]) -> set[Decimal]:
    items = list(base)
    if len(items) > 40:
        # Cap pairwise expansion at 40 items (1600 pairs is plenty for grounding).
        items = items[:40]
    ...
```

---

### WR-10: Title generator catches `Exception` and never logs the failure for the assistant_persist case

**File:** `backend/app/services/chat/orchestrator.py:419-421`
**Issue:**
```python
try:
    await self._session.commit()
except Exception:  # noqa: BLE001
    pass
```

The bare-except-pass swallows the entire failure mode of CR-03. If CR-03 is fixed, this clause is dead. If CR-03 is NOT fixed, this clause silently hides every production failure of the title generator commit path. At a minimum, log a structured warning so the team sees the broken pattern in dashboards.

**Fix:**
```python
try:
    await self._session.commit()
except Exception as exc:
    self._log.warning("chat.title.commit_failed", error=str(exc)[:200])
```

---

### WR-11: `get_kpi.compute_for_date` is called once per day in a 365-day range — quadratic cost potential

**File:** `backend/app/services/chat/tools/get_kpi.py:88-124`, `backend/app/services/chat/tools/get_trend.py:138-148`
**Issue:** Both tools accept user-controlled date ranges (`get_kpi` has no upper bound on `date_to - date_from`; `get_trend` is bounded by Literal[7,30,90]). A Claude call to `get_kpi(date_from="2024-01-01", date_to="2026-05-29")` will fire ~880 sequential `compute_for_date(day)` calls, each doing a fresh aggregate query. Per turn, this can blow past the 30s budget and the 180s stream-lock — turn never completes, user thinks chat is broken.

Out-of-scope per phase config (performance v1 deferred), but flagging because: an LLM under guard pressure may broaden date ranges to escape regenerate, intentionally triggering this. T-08-04 (cost guard) is explicitly listed as a phase concern. Add an explicit date-range cap:

**Fix:** Add `ge` constraint + a max-range check:
```python
class GetKpiInput(BaseModel):
    date_from: date = Field(...)
    date_to: date = Field(...)
    ...

    @model_validator(mode="after")
    def _bound_range(self):
        if (self.date_to - self.date_from).days > 365:
            raise ValueError("date range > 365 days not supported")
        return self
```

---

### WR-12: Suggested-questions endpoint trusts `payload.problems[*].title` without escaping

**File:** `backend/app/api/v1/chat.py:484-487`
**Issue:**
```python
title = (problem.get("title") or "").strip()
if title:
    questions.append(f"Spune-mi mai mult despre: {title}")
```

The `daily_insight.problems[*].title` comes from Phase 5 Claude output, which is owner-attestation-safe in MVP1. But the title is rendered directly into the suggested-questions list, which the frontend inserts into the chat input (`ChatInput.insertText`). If a problem.title is something like `"); fetch('https://attacker..."` injection target (or even a less malicious very-long string), the user's input box gets a strange value.

Not exploitable in MVP1 because Claude controls the title. But: validate length and strip newlines:

**Fix:**
```python
title = (problem.get("title") or "").strip().replace("\n", " ")[:200]
if title:
    questions.append(f"Spune-mi mai mult despre: {title}")
```

---

### WR-13: `chat-input.tsx` `insertText` doesn't refocus or scroll into view on mobile

**File:** `frontend/src/components/chat/chat-input.tsx:52-58`
**Issue:** `insertText` is called from suggested-question chips. On mobile, when the user taps a chip, the keyboard does not pop up because `focus()` happens AFTER setValue triggers a re-render, by which point the textarea may have re-mounted (rare). More importantly, the inserted text isn't visible: the textarea may not have grown yet to show the new content. The user taps a chip and "nothing happens" visually.

UX bug, not a correctness bug.

**Fix:**
```javascript
insertText: (text: string) => {
  setValue((v) => (v ? `${v} ${text}` : text));
  requestAnimationFrame(() => {
    textareaRef.current?.focus();
    textareaRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  });
},
```

---

### WR-14: `message-bubble.tsx` `fallback` mode renders `t("fallback")` from i18n, but the backend emits Romanian fallback text directly

**File:** `frontend/src/components/chat/message-bubble.tsx:122-126`, `backend/app/services/chat/orchestrator.py:355-356`
**Issue:** The backend streams `GUARD_FALLBACK_TEXT` ("Nu pot da un răspuns precis...") via `assistant_chunk` and persists it as the message content. The frontend's `MessageBubble` in `fallback` state then renders `t("fallback")` from `chat.messages.fallback` (also Romanian, same string) — but **only when `!content`**. Since `content` is non-empty (it carries the streamed text), the frontend actually renders the `MarkdownRenderer` with `content`, not the i18n fallback.

Wait — re-reading the bubble: `{content && !isFallback && <MarkdownRenderer .../>}`. So when isFallback is true, MarkdownRenderer is SKIPPED and the i18n `t("fallback")` IS rendered. That means the persisted message content is rendered TO THE DB but NOT shown to the user — the i18n string is shown instead. If the i18n string and the backend constant ever drift (a copy edit on one side), users see different text in the UI vs. what's persisted.

Mild but real: keep a single source of truth.

**Fix:** Either render `<MarkdownRenderer content={content} />` in fallback mode (so the persisted text wins) and drop the i18n key, or extract the Romanian fallback string into a shared constants module that both backend and frontend reference.

## Info

### IN-01: Module-level `from anthropic import AsyncAnthropic` in `chat.py` is annotated `noqa: F401` but is also used at runtime

**File:** `backend/app/api/v1/chat.py:59, 358-359`
**Issue:** The import is real — it's instantiated inside `event_generator` to "activate the CHAT-08 grep gate" and then immediately `del`'d. The `noqa: F401` comment is misleading (the import IS used). Either drop the `del`-and-discard pattern (just instantiate when needed via the orchestrator) OR drop the noqa and let mypy flag any future unused-import drift.

**Fix:** Drop the `_anthropic_client = ...; del _anthropic_client` block — the grep gate fires on the `from anthropic import AsyncAnthropic` line at the top of the module. The runtime instantiation is dead code.

---

### IN-02: `_to_jsonable` is duplicated across 9+ tool files

**File:** `backend/app/services/chat/tools/{compare_periods,get_funnel_data,get_lead_categories_breakdown,get_recent_insight,get_salesperson_performance,get_stuck_leads,get_kpi}.py`
**Issue:** Nearly identical `_jsonable` / `_to_jsonable` helpers in 7+ tool files. Same pattern as the orchestrator's `_to_jsonable`. Magnet for drift bugs (one file gets a fix for `datetime`, others don't).

**Fix:** Extract to `backend/app/services/chat/tools/_serialization.py` and import.

---

### IN-03: Hallucination guard rejects "120%" but accepts "120,5%" inconsistently

**File:** `backend/app/services/chat/hallucination_guard.py:177-187`
**Issue:** The number extractor reuses Phase 5's `extract_numbers_from_text` (Romanian decimal comma → `.`). The skip rule for years (`1900..2100`) will skip `2100,5` since the integral 2100 part is in range — but `2100.5` parsed as Decimal is NOT in `[1900, 2100]`. Verify against Phase 5 extractor behavior — the skip rule depends on whether parsed Decimal == 2100.5 or 2100. Likely OK but worth a unit test.

**Fix:** Add unit test asserting "120%" → flagged, "120,5%" → flagged, "2000" → skipped (year), "20.500" → flagged (Romanian thousands).

---

### IN-04: `useChat` `dispatch` is a function declared after the `try` block that uses it — TDZ smell

**File:** `frontend/src/hooks/useChat.ts:184, 202-258`
**Issue:** `dispatch` is referenced inside the `try` block at line 185 (`dispatch(ev)`) but the function declaration is hoisted from line 202. This works in JS because function declarations hoist, but it's unidiomatic and confusing. Move the declaration above the `try` to match reading order.

**Fix:** Move `function dispatch(ev: SSEEvent) { ... }` above the `try` block, or convert to a `const dispatch = useCallback(...)` to share the React idiom.

---

### IN-05: `MarkdownRenderer` allows `<code>` but not `<pre>` — blocks > 1-line snippets

**File:** `frontend/src/components/chat/markdown-renderer.tsx:32-48`
**Issue:** `ALLOWED_ELEMENTS` includes `code` but not `pre`. Code fences in Markdown render as `<pre><code>...</code></pre>`; without `pre` the renderer strips both — multi-line code snippets disappear. The system prompt does not encourage code blocks but if Claude ever produces one, it vanishes.

**Fix:** Add `"pre"` to `ALLOWED_ELEMENTS` and supply a sensible `pre` component renderer.

---

### IN-06: `message-list.tsx` `useEffect` recomputes `el.scrollHeight - el.scrollTop - el.clientHeight` but never debounces

**File:** `frontend/src/components/chat/message-list.tsx:34-44`
**Issue:** Every token chunk bumps `scrollKey`, which fires the effect — which calls `scrollHeight` (a layout-triggering property) on every chunk. This forces layout sync per token. Out of v1 perf scope but worth a follow-up: use `IntersectionObserver` or rAF-throttle.

---

### IN-07: No test asserting `system_prompt` salesperson roster matches `MefiSalesperson` table in dev DB

**File:** `backend/app/services/chat/prompt_builder.py:38-44`, `backend/app/services/chat/hallucination_guard.py:217-248`
**Issue:** The system prompt lists 6 hardcoded salesperson names verbatim. The hallucination guard's entity whitelist is built from the DB. If the DB roster drifts from the prompt (sales rep added, fired, renamed), Claude will produce names that the guard rejects, or the prompt will mention names Claude can't verify. There's no test catching this drift.

**Fix:** Add an integration test that boots the DB, builds the prompt + the whitelist, and asserts:
  - Every name in the prompt is in the whitelist.
  - The whitelist is a strict superset of the prompt list.

---

_Reviewed: 2026-05-29T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
