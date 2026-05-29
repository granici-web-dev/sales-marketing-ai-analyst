---
phase: 08-ai-chat
plan: 07
subsystem: security
tags: [chat, authorization, multi-user, repositories, sqlalchemy, fastapi, CR-01, gap-closure]

# Dependency graph
requires:
  - phase: 08-ai-chat
    provides: ConversationRepository + 5 chat endpoints (plans 08-04, 08-05); chat_conversations.user_id column (plan 08-02)
  - phase: 01-foundation
    provides: TenantScopedMixin + with_loader_criteria seam (tenant_id scoping); UserOut.id exposed via get_current_user
provides:
  - "ConversationRepository.__init__(session, tenant_id, user_id) — per-user authorization predicate on every SELECT/UPDATE"
  - "send_message ownership pre-check (404 BEFORE Redis rate-limit + stream-lock — prevents budget burn by probing attackers)"
  - "Cross-user authorization integration test suite (4 tests) verifying GET/DELETE/POST/list endpoint behavior under cross-user probes"
  - "Romanian-only 404 copy ('Conversația nu există.') uniformly used — no 403-vs-404 existence-leak distinction (T-08-01b)"
affects: [08-08-PLAN.md (CR-03 detached title task can now take user_id), 08-10-PLAN.md (HUMAN-UAT can verify SC#5 per-user persistence)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-user authorization predicate co-located with tenant predicate (defense-in-depth on top of with_loader_criteria seam)"
    - "Storage-layer cross-user write guard mirrors existing tenant cross-write guard (parallel ValueError shape)"
    - "Endpoint ownership pre-check BEFORE Redis side-effects so failed authorization doesn't consume rate-limit budget"

key-files:
  created:
    - "backend/tests/integration/chat/test_cross_user_isolation.py (CR-01 regression suite, 4 tests)"
    - ".planning/phases/08-ai-chat/08-07-SUMMARY.md"
  modified:
    - "backend/app/services/chat/repositories/conversation_repository.py (constructor + 5 WHERE clauses + insert_conversation guard + module docstring)"
    - "backend/app/api/v1/chat.py (5 endpoint call-sites + send_message ownership pre-check before Redis block)"
    - "backend/tests/unit/chat/test_chat_repositories.py (6 new TestConversationRepositoryCrossUserCR01 tests + 4 existing tests updated to 3-arg signature)"
    - "backend/tests/unit/chat/test_chat_router.py (R5/R6/R12 patched ConversationRepository so new pre-check sees a valid owned row)"
    - "backend/tests/integration/chat/test_chat_endpoints.py (4 send_message tests patched ConversationRepository for same reason)"

key-decisions:
  - "CR-01 ownership pre-check fires BEFORE Redis rate-limit INCR and stream-lock SET NX so a probing attacker cannot burn the legitimate owner's 30/hour budget or acquire a lock on a conversation they don't own"
  - "Cross-user reads return None from repository → 404 in router with same Romanian copy as a non-existent row — no 403 path, no existence-leak (T-08-01b mitigation)"
  - "insert_conversation gains a parallel ValueError('cross-user write blocked') guard mirroring the existing tenant guard — prevents a future contributor from constructing the repo with current_user.id but writing a row with someone else's user_id"
  - "User_id predicate added explicitly on every SELECT and UPDATE; the Phase 1 with_loader_criteria seam only scopes by tenant_id, so this is the sole enforcement point for per-user authorization"

patterns-established:
  - "3-arg repository constructor (session, tenant_id, user_id) is the canonical shape for any chat-scope repo that owns user-specific rows. Plan 08-08 CR-03 will use this same signature for the detached title task."
  - "Endpoint pattern: instantiate the repo with current_user.id, then either rely on the predicate-filtered None return (get/delete) or run an explicit pre-check (send_message — where downstream side-effects are expensive)."
  - "Test pattern for routes that gained an ownership pre-check: pre-existing happy-path tests must patch ConversationRepository with an AsyncMock whose get_by_id returns a non-None row, so the pre-check passes and the test exercises the intended branch (rate-limit, stream-lock, SSE headers)."

requirements-completed: [CHAT-03, CHAT-05]

# Metrics
duration: ~38min
completed: 2026-05-29
---

# Phase 8 Plan 07: CR-01 Cross-User Authorization Closure Summary

**ConversationRepository now requires user_id; all 5 chat endpoints pass current_user.id into the repo; send_message rejects cross-user conversation_ids with 404 BEFORE Redis touches; 4-test integration regression suite proves the structural bypass is closed.**

## Performance

- **Duration:** ~38 min
- **Started:** 2026-05-29T18:03Z (approximate — after initial context load)
- **Completed:** 2026-05-29T18:41:03Z
- **Tasks:** 2 (Task 1: storage-layer predicate; Task 2: endpoint + integration tests)
- **Files modified:** 5 (2 source + 3 tests, 1 new integration test file)

## Accomplishments

- **CR-01 closed** — the structural authorization bypass identified in 08-REVIEW.md is fixed at both storage and endpoint layers. Cross-user reads / archives / message-posts now return 404 with the Romanian copy `Conversația nu există.`
- **SC#4 + SC#5 gap from 08-VERIFICATION.md closed** — all three "missing items" from that gap entry are present:
  1. ConversationRepository accepts user_id and includes it in every WHERE clause ✓
  2. send_message verifies conversation ownership BEFORE orchestrator.run_turn ✓
  3. Cross-user authorization integration test (User A POSTs to User B's conversation_id → 404) ✓
- **Rate-limit budget protected** — the ownership pre-check runs BEFORE the Redis INCR, so a probing attacker cannot burn through the legitimate owner's 30/hour quota by repeatedly POSTing into UUIDs they don't own. Verified explicitly in `test_cross_user_post_returns_404` via `redis_from_url.assert_not_called()`.
- **138 chat tests GREEN** including:
  - 25 unit tests in `test_chat_repositories.py` (6 new for CR-01)
  - 4 new integration tests in `test_cross_user_isolation.py` (the SC#4+SC#5 regression suite)
  - 7 pre-existing tests updated to handle the new pre-check code path
- **Plan 08-08 unblocked** — CR-03 (detached title task with its own AsyncSessionLocal session) can now adopt the 3-arg `ConversationRepository(session, tenant_id, user_id)` signature in its detached-session call site.

## Task Commits

Each task was committed atomically:

1. **Task 1: Thread user_id through ConversationRepository (CR-01 storage fix)** — `a60598f7` (fix)
2. **Task 2: Update chat router endpoints + cross-user integration tests** — `9b742b74` (fix)

**Plan metadata:** _(this SUMMARY commit, hash pending)_

## Files Created/Modified

**Created**

- `backend/tests/integration/chat/test_cross_user_isolation.py` — CR-01 regression suite (4 tests): `test_cross_user_get_returns_404`, `test_cross_user_delete_returns_404`, `test_cross_user_post_returns_404`, `test_cross_user_list_excludes_b_conversations`. Per-test `_integration_skip` decorator (Phase 5 carry-forward pattern) — pass under `TEST_DATABASE_URL`, skip cleanly otherwise.
- `.planning/phases/08-ai-chat/08-07-SUMMARY.md` — this file.

**Modified**

- `backend/app/services/chat/repositories/conversation_repository.py` — Constructor now requires `user_id: UUID`; stored as `self._user_id`. Every SELECT (`get_by_id`, `list_conversations`) and UPDATE (`update_title`, `update_last_message_at`, `soft_archive`) emits `ChatConversation.user_id == self._user_id`. `insert_conversation` gains a parallel `ValueError("cross-user write blocked")` guard. Module docstring updated with the CR-01 (Plan 08-07) reference.
- `backend/app/api/v1/chat.py` — All 5 conversation endpoints now use the 3-arg constructor. `send_message` gains an ownership pre-check (`conv_repo.get_by_id` → `HTTPException(404, "Conversația nu există.")` on None) that fires BEFORE the Redis rate-limit + stream-lock block.
- `backend/tests/unit/chat/test_chat_repositories.py` — 6 new tests in `TestConversationRepositoryCrossUserCR01` (insert cross-user guard + 5 method predicate assertions); 4 existing `TestConversationRepository` tests updated to the new 3-arg signature.
- `backend/tests/unit/chat/test_chat_router.py` — R5 (429 rate-limit), R6 (409 stream-lock), R12 (SSE headers) tests patched to inject a `ConversationRepository` mock whose `get_by_id` returns a non-None row, so the new ownership pre-check passes and the tests still exercise their intended branches.
- `backend/tests/integration/chat/test_chat_endpoints.py` — 4 `send_message` tests (basic_turn, multi_tool, rate_limit_429, concurrent_stream_409) patched for the same reason.

## Decisions Made

- **Ownership pre-check placement: BEFORE Redis side-effects.** This is the security-meaningful choice. If the pre-check ran AFTER the rate-limit INCR, a probing attacker would burn through the legitimate owner's hourly budget just by trying random UUIDs. CR-02 (plan 08-08) will further reorder the rate-limit / stream-lock pair, but this 404 stays in front of BOTH. Verified by `test_cross_user_post_returns_404` which asserts `redis_from_url` is never called and `ChatOrchestrator` is never instantiated on the cross-user path.
- **404 not 403, with identical Romanian copy.** Returning 403 (or even a different message) would let an attacker distinguish "exists, owned by someone else" from "does not exist" — T-08-01b existence-leak. All cross-user paths fold into the same `404 + "Conversația nu există."` response used for genuinely-non-existent rows.
- **insert_conversation gains a cross-user ValueError, parallel to the cross-tenant one.** Today both the create_conversation endpoint and the only other caller pass `row["user_id"] = current_user.id`, so this guard cannot fire from existing code paths. It exists as a future-proofing tripwire so a contributor cannot construct a repo with one user's id but write a row with another user's id (the exact mistake we just fixed at the read side).
- **`update_title`, `update_last_message_at`, `soft_archive` are silent no-ops on cross-user UPDATEs** (zero rows matched). The router's `get_by_id` pre-check is the public-facing 404 path; the predicate on UPDATE is defense-in-depth in case a future caller forgets the pre-check.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Existing send_message tests broke when the new ownership pre-check was added**

- **Found during:** Task 2 verification (running the full chat regression suite)
- **Issue:** Adding `conv_repo.get_by_id(...)` at the top of `send_message` broke 7 pre-existing tests that called `send_message` without patching `ConversationRepository`. The pre-check tried to use the real repo against an `AsyncMock` session, which fails on `result.scalars()` of an awaited coroutine. Failures:
  - `tests/unit/chat/test_chat_router.py`: `test_r5_post_messages_returns_429_when_rate_limit_exceeded`, `test_r6_post_messages_returns_409_when_stream_lock_held`, `test_r12_sse_endpoint_sets_text_event_stream_and_x_accel_buffering`
  - `tests/integration/chat/test_chat_endpoints.py`: `test_send_message_sse_basic_turn`, `test_send_message_sse_multi_tool`, `test_rate_limit_429`, `test_concurrent_stream_409`
- **Fix:** Each of the 7 tests wrapped its existing `patch(...)` block with an additional `patch("app.api.v1.chat.ConversationRepository", return_value=conv_repo)` where `conv_repo.get_by_id` returns a non-None row, so the new pre-check passes and the test still exercises its intended branch (rate-limit, stream-lock, SSE headers, etc.). Each updated test also got a comment block explaining why the new patch is required (CR-01 Plan 08-07 reference).
- **Files modified:** `backend/tests/unit/chat/test_chat_router.py`, `backend/tests/integration/chat/test_chat_endpoints.py`
- **Verification:** Full chat regression suite `pytest tests/unit/chat/ tests/integration/chat/` returns 138/138 GREEN (134 always-on + 4 cross-user with `TEST_DATABASE_URL` set; same suite returns 130 passed + 8 skipped without the env var).
- **Committed in:** `9b742b74` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug introduced by intentional code change broke pre-existing test contracts)
**Impact on plan:** The deviation was inherent to the plan (any new mandatory pre-check at the top of an endpoint will break tests that don't patch the new dependency). The fix is mechanical — bundle the new patch into each affected test. No scope creep, no architectural change.

## Issues Encountered

- **ruff / mypy not available in this environment.** The plan's `<verification>` block calls for `cd backend && uv run ruff check ...` and `... mypy ...` on the two modified source files. `uv` is not installed on this machine, and `.venv/bin/ruff` / `.venv/bin/mypy` are absent from the backend venv (only `pytest` is present). No pre-commit hook is configured at the repo level (`.pre-commit-config.yaml` absent), so `git commit` did not run ruff/mypy automatically. **The pytest verification is the actual functional gate** and it returns 138/138 GREEN — the static-analysis gates would be best-effort in this environment regardless. CI is expected to run these gates per `CLAUDE.md`. This is documented here so the verifier knows ruff/mypy were skipped due to environment, not avoided.

## User Setup Required

None — no external service configuration required. This plan is purely a code-layer security fix.

## Next Phase Readiness

- **Plan 08-08 (CR-02 + CR-03 + CR-05 + WR-10)** is unblocked:
  - CR-03 (detached title task) can now construct its `ConversationRepository(detached_session, tenant_id, user_id)` using the 3-arg signature established here. The `user_id` is in scope at the `schedule_title_generation` call site (the orchestrator already takes `user_id` in `__init__`, so plumbing it into the detached task is trivial).
  - CR-02 (acquire stream-lock before rate-limit INCR) can freely reorder the rate-limit / stream-lock pair without touching the CR-01 pre-check — both CR-01 and CR-02 stay in front of the entire Redis block.
- **Plan 08-09 (CR-04 + CR-06)** is independent of this plan.
- **Plan 08-10 (HUMAN-UAT)** can now verify SC#5 (conversation persistence per USER) — the structural bypass that would have made any per-user UAT meaningless is now closed.

## Self-Check: PASSED

**Files verified to exist:**
- `backend/app/services/chat/repositories/conversation_repository.py` — FOUND (modified, 174 lines)
- `backend/app/api/v1/chat.py` — FOUND (modified)
- `backend/tests/unit/chat/test_chat_repositories.py` — FOUND (modified, 25 tests)
- `backend/tests/unit/chat/test_chat_router.py` — FOUND (modified)
- `backend/tests/integration/chat/test_chat_endpoints.py` — FOUND (modified)
- `backend/tests/integration/chat/test_cross_user_isolation.py` — FOUND (created, 4 tests)

**Commits verified to exist:**
- `a60598f7` (Task 1 storage fix) — FOUND
- `9b742b74` (Task 2 endpoint + integration tests) — FOUND

**Grep gates verified:**
- 3-arg `ConversationRepository(session, tenant_id, current_user.id)` count: 5 (expect ≥5) ✓
- 2-arg `ConversationRepository(session, tenant_id)` count in chat.py: 0 (expect 0) ✓
- `"Conversația nu există"` count in chat.py: 4 (expect ≥4) ✓
- `self._user_id` count in repository: 10 (expect ≥6) ✓
- `ChatConversation.user_id == self._user_id` count: 5 (expect ≥5) ✓
- `test_cross_user_*` function count: 4 (expect 4) ✓

**Test gates verified:**
- `pytest tests/unit/chat/test_chat_repositories.py`: 25/25 GREEN
- `pytest tests/integration/chat/test_cross_user_isolation.py` (no DB env): 4/4 SKIPPED cleanly
- `TEST_DATABASE_URL=... pytest tests/integration/chat/test_cross_user_isolation.py`: 4/4 PASSED
- Full chat regression `pytest tests/unit/chat/ tests/integration/chat/`: 138/138 GREEN (with DB env) / 130 passed + 8 skipped (without)

---
*Phase: 08-ai-chat*
*Completed: 2026-05-29*
