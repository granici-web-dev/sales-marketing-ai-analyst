---
phase: 08-ai-chat
plan: 02
subsystem: chat/persistence
tags: [chat, schema, alembic, orm, persistence, tdd]
requires:
  - Phase 1 TenantScopedMixin + with_loader_criteria cross-tenant filter (app/db/base.py + session.py)
  - Phase 5 migration 008_daily_insights (down_revision chain)
  - Phase 1 tenants.id + Phase 1 users.id (FK targets)
  - Plan 08-01 backend/tests/unit/chat/ package (test infra)
provides:
  - chat_conversations table (D-20)
  - chat_messages table (D-20 + extensions hallucination_flag + regenerate_count)
  - chat_tool_calls table (D-20 + D-21 audit logging)
  - ChatConversation / ChatMessage / ChatToolCall SQLAlchemy 2.x ORM models
  - 3 PostgreSQL indexes backing CHAT-09 latency queries
  - DB-level CHECK constraint on chat_messages.role (T-08-02 mitigation)
  - 2x ON DELETE CASCADE so child rows die with parents (T-08-DDL)
  - app.models registry entries for Alembic autogenerate discovery
affects:
  - backend/app/models/__init__.py (+9 lines — registers 3 chat classes)
tech-stack:
  added: []
  reused:
    - SQLAlchemy 2.x mapped_column / Mapped[T] syntax (Phase 5 carry-forward)
    - Alembic migration pattern from 008_daily_insights.py
    - TenantScopedMixin from app/db/base.py (Phase 1)
    - PostgreSQL JSONB + UUID types from sqlalchemy.dialects.postgresql
  patterns:
    - "Standalone DDL pattern: TenantScopedMixin columns replicated explicitly in migration so DDL is readable without ORM context"
    - "ORM declares Mapped[UUID] without ForeignKey object; FK lives in migration only (existing project convention)"
    - "try/except import guard in test module so collection survives RED state"
    - "Strict reverse-FK order in downgrade() — drop child tables before parents"
key-files:
  created:
    - backend/alembic/versions/009_chat_tables.py (273 lines)
    - backend/app/models/chat/__init__.py (27 lines)
    - backend/app/models/chat/chat_conversation.py (68 lines)
    - backend/app/models/chat/chat_message.py (102 lines)
    - backend/app/models/chat/chat_tool_call.py (65 lines)
    - backend/tests/unit/chat/test_chat_models.py (310 lines)
    - .planning/phases/08-ai-chat/deferred-items.md (pre-existing test_models.py issue, out-of-scope)
  modified:
    - backend/app/models/__init__.py (+9 lines — registers ChatConversation/ChatMessage/ChatToolCall)
decisions:
  - "TDD discipline: RED commit landed first (db331d32) with all 10 tests failing for the right reason (ModuleNotFoundError on app.models.chat), then GREEN commit (63dadf24) made all 10 pass with zero further iteration."
  - "FK ondelete=CASCADE placed ONLY at migration DDL (not on ORM mapped_column) — matches the existing pattern in 003_mefi_schema/004_metrics_schema. ORM models stay minimal; the DB is the source of truth for referential integrity."
  - "Added updated_at column to all 3 chat tables even though RESEARCH §5 sketch omitted it on chat_conversations / chat_messages — necessary so the TenantScopedMixin contract (which declares updated_at via TimestampMixin) matches the DDL column-for-column. Without it, future autogenerate runs would surface false-positive diffs."
  - "Two explicit ondelete=CASCADE FKs (chat_messages.conversation_id → chat_conversations.id, chat_tool_calls.message_id → chat_messages.id). FK to tenants.id intentionally has NO cascade per project convention — tenants are never hard-deleted; tenant lifecycle is owned by the admin layer."
  - "Migration 009 docstring cites D-20, T-08-01, T-08-02, T-08-DDL, T-08-05 explicitly per planning Rule 2 (threat-model traceability)."
metrics:
  duration: "~25 minutes"
  completed: 2026-05-29
  tasks_completed: 2
  files_created: 7
  files_modified: 1
  lines_added: 854
  commits: 2
---

# Phase 8 Plan 02: Chat Persistence Schema Summary

Establishes the AI Chat persistence foundation: Alembic migration 009 creates `chat_conversations` / `chat_messages` / `chat_tool_calls` per D-20 (with the two D-20 extensions `hallucination_flag` + `regenerate_count` beyond SPEC.md), backed by 3 SQLAlchemy 2.x ORM models that mirror the DDL column-for-column and inherit `TenantScopedMixin` so the Phase 1 `with_loader_criteria` event listener fires on every ORM `select()` (T-08-01 cross-tenant isolation seam). Includes the BLOCKING schema push to PostgreSQL with verified downgrade/upgrade roundtrip.

## What Was Built

### Task 1 — RED phase: 10 failing model tests (commit `db331d32`)

`backend/tests/unit/chat/test_chat_models.py` (310 lines, 10 tests). Wraps every model import in try/except per the Phase-3/Phase-5 convention so collection survives the pre-implementation state. Each test fails with a descriptive `pytest.fail("Run Plan 08-02 Task 1 ...")` when its target class is missing.

Test coverage:

| # | Test | Asserts |
|---|------|---------|
| 1 | `test_chat_package_exports_all_three_models` | `from app.models import chat as chat_pkg` exposes `ChatConversation`, `ChatMessage`, `ChatToolCall` |
| 2 | `test_chat_models_inherit_tenant_scoped_mixin` | All 3 models inherit `Base` AND `TenantScopedMixin` (T-08-01 seam) |
| 3 | `test_chat_conversation_tablename` | `__tablename__ == "chat_conversations"` |
| 4 | `test_chat_message_tablename` | `__tablename__ == "chat_messages"` |
| 5 | `test_chat_tool_call_tablename` | `__tablename__ == "chat_tool_calls"` |
| 6 | `test_chat_message_has_all_d20_columns` | 13 D-20 columns present including `hallucination_flag` + `regenerate_count` extensions |
| 7 | `test_chat_tool_call_has_all_d20_columns` | 10 D-20/D-21 audit columns present |
| 8 | `test_chat_conversation_has_all_d20_columns` | 8 columns present (`user_id`, `title`, `last_message_at`, `archived` + 4 from mixin) |
| 9 | `test_chat_models_registered_with_app_models_package` | `from app.models import ChatConversation, ChatMessage, ChatToolCall` (Alembic autogenerate discovery) |
| 10 | `test_migration_009_exists_with_correct_revision_chain` | Migration file + `revision="009"` + `down_revision="008"` + ≥3 `create_table` + ≥2 `ondelete="CASCADE"` + `ck_chat_messages_role` |

RED verification: `pytest tests/unit/chat/test_chat_models.py -x` → first test fails with `ImportError: cannot import name 'chat' from 'app.models'` (correct RED reason — production code missing).

### Task 1 — GREEN phase: chat ORM models + Alembic migration 009 (commit `63dadf24`)

Six files (5 new + 1 modified), 546 inserted lines:

| File | Purpose | Lines |
|------|---------|-------|
| `backend/alembic/versions/009_chat_tables.py` | Creates the 3 chat tables + 3 indexes + 1 CHECK + 6 FKs (2 with CASCADE). Strict reverse-FK order in `downgrade()`. | 273 |
| `backend/app/models/chat/__init__.py` | Package re-exports `ChatConversation`, `ChatMessage`, `ChatToolCall`. | 27 |
| `backend/app/models/chat/chat_conversation.py` | ORM model: `user_id` (FK→users.id), `title` (NULL), `last_message_at` (NOT NULL), `archived` (DEFAULT false). | 68 |
| `backend/app/models/chat/chat_message.py` | ORM model: `conversation_id` (FK CASCADE), `role`, `content`, `tool_calls`/`tool_results` JSONB, `tokens_used`, `duration_ms`, `hallucination_flag`, `regenerate_count`. | 102 |
| `backend/app/models/chat/chat_tool_call.py` | ORM model: `message_id` (FK CASCADE), `tool_name`, `input_args` JSONB NOT NULL, `output_data` JSONB NULL, `duration_ms`, `error`. | 65 |
| `backend/app/models/__init__.py` (modified) | Appends `from app.models.chat import (...)` + extends `__all__` list. | +9 |

Key migration details (citing D-20 and threat register):

- **Header:** `revision = "009"`, `down_revision = "008"` (chains from Phase 5 daily_insights).
- **3 create_table calls** in dependency order: `chat_conversations` → `chat_messages` → `chat_tool_calls`.
- **2 ondelete=CASCADE FKs:** `chat_messages.conversation_id` → `chat_conversations.id`, `chat_tool_calls.message_id` → `chat_messages.id`. Tenant FK is NOT cascaded (project convention — tenants never hard-deleted).
- **1 CHECK constraint:** `ck_chat_messages_role` enforces `role IN ('user','assistant','tool_use','tool_result')` at the DB layer (T-08-02 tampering mitigation, defense-in-depth on top of the application-layer Literal typing).
- **3 indexes for CHAT-09 latency:**
  - `ix_chat_conversations_tenant_user_last` on `(tenant_id, user_id, last_message_at DESC)` — sidebar "recent conversations" query.
  - `ix_chat_messages_conv_created` on `(conversation_id, created_at)` — per-conversation history fetch.
  - `ix_chat_tool_calls_tenant_tool_created` on `(tenant_id, tool_name, created_at DESC)` — D-21 audit lookup.

GREEN verification: 10/10 tests pass in 0.03s.

### Task 2 — [BLOCKING] Apply migration + verify schema in PostgreSQL (runtime-only)

Task 2 had no source-file output — it's a runtime verification step. All sub-steps executed against `sales-marketing-ai-analyst-postgres-1` (PostgreSQL 16.14):

1. **`alembic upgrade head`** → `Running upgrade 008 -> 009`. SUCCESS.
2. **`alembic current`** → `009 (head)`. SUCCESS.
3. **`\dt chat_*`** lists exactly the 3 expected tables:
   ```
   public | chat_conversations | table | root
   public | chat_messages      | table | root
   public | chat_tool_calls    | table | root
   (3 rows)
   ```
4. **`\d chat_messages`** confirms:
   - `hallucination_flag boolean NOT NULL DEFAULT false` ✓
   - `regenerate_count integer NOT NULL DEFAULT 0` ✓
   - `"ck_chat_messages_role" CHECK (role = ANY (ARRAY['user'::text, 'assistant'::text, 'tool_use'::text, 'tool_result'::text]))` ✓
   - `"fk_chat_messages_conversation_id" FOREIGN KEY (conversation_id) REFERENCES chat_conversations(id) ON DELETE CASCADE` ✓
   - `"ix_chat_messages_conv_created" btree (conversation_id, created_at)` ✓
5. **`\d chat_tool_calls`** confirms:
   - `"fk_chat_tool_calls_message_id" FOREIGN KEY (message_id) REFERENCES chat_messages(id) ON DELETE CASCADE` ✓
   - `"ix_chat_tool_calls_tenant_tool_created" btree (tenant_id, tool_name, created_at DESC)` ✓
6. **Downgrade/upgrade roundtrip:**
   - `alembic downgrade -1` → `Running downgrade 009 -> 008`. SUCCESS.
   - `\dt chat_*` after downgrade → `Did not find any relation named "chat_*"` (tables gone). ✓
   - `alembic upgrade head` → `Running upgrade 008 -> 009`. SUCCESS.
   - `\dt chat_*` after re-upgrade → 3 tables back. ✓

### `\d chat_messages` snippet (verbatim from PostgreSQL)

```
       Column       |           Type           | Nullable |      Default
--------------------+--------------------------+----------+-------------------
 id                 | uuid                     | not null | gen_random_uuid()
 tenant_id          | uuid                     | not null |
 created_at         | timestamp with time zone | not null | now()
 updated_at         | timestamp with time zone | not null | now()
 conversation_id    | uuid                     | not null |
 role               | text                     | not null |
 content            | text                     |          |
 tool_calls         | jsonb                    |          |
 tool_results       | jsonb                    |          |
 tokens_used        | integer                  |          |
 duration_ms        | integer                  |          |
 hallucination_flag | boolean                  | not null | false
 regenerate_count   | integer                  | not null | 0
Indexes:
    "chat_messages_pkey" PRIMARY KEY, btree (id)
    "ix_chat_messages_conv_created" btree (conversation_id, created_at)
Check constraints:
    "ck_chat_messages_role" CHECK (role = ANY (ARRAY['user'::text, 'assistant'::text, 'tool_use'::text, 'tool_result'::text]))
Foreign-key constraints:
    "fk_chat_messages_conversation_id" FOREIGN KEY (conversation_id) REFERENCES chat_conversations(id) ON DELETE CASCADE
    "fk_chat_messages_tenant_id" FOREIGN KEY (tenant_id) REFERENCES tenants(id)
```

## Overall Verification

All 5 commands from the plan's `<verification>` block exit cleanly:

| # | Command | Result |
|---|---------|--------|
| 1 | `pytest tests/unit/chat/test_chat_models.py -x -v` | 10 PASSED in 0.03s |
| 2 | `alembic current` | `009 (head)` |
| 3 | `psql -c "\dt chat_*"` | 3 tables: chat_conversations, chat_messages, chat_tool_calls |
| 4 | `grep -E "revision\|down_revision" alembic/versions/009_chat_tables.py` | `revision = "009"` + `down_revision = "008"` |
| 5 | Python column completeness assertion on ChatMessage | All 13 D-20 columns present (`required.issubset(cols)` passes) |

Additionally:
- CHAT-08 grep gate (`pytest tests/unit/chat/test_anthropic_scope.py`) still PASSES — none of the new chat files import AsyncAnthropic (correct: AsyncAnthropic only lands in plan 08-05's `app/api/v1/chat.py`).
- All 48 sibling-model tests (`tests/unit/test_metrics_models.py`, `tests/unit/test_mefi_models.py`, `tests/unit/chat/`) PASS — no regressions.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Local `.venv` missing `greenlet` library required by SQLAlchemy async engine**
- **Found during:** Task 2 first `alembic upgrade head` attempt.
- **Issue:** `ValueError: the greenlet library is required to use this function. No module named 'greenlet'`. SQLAlchemy 2.x async engine bridges sync↔async via greenlet; the project venv was missing it.
- **Fix:** `pip install greenlet` (resolved `greenlet-3.5.1`). This is a missing transitive dep of `sqlalchemy[asyncio]` that pip didn't auto-pull; the production Docker backend container has it via its image. No source change — pure runtime dep install in the local development venv.
- **Files modified:** None tracked (venv mutation only).
- **Why Rule 3, not Rule 4:** No architectural change. Greenlet IS the official sync↔async bridge SQLAlchemy 2.x documents; installing it does not alter design.

### Project-convention adjustments (no rule needed)

**2. Added `updated_at` to `chat_conversations` / `chat_messages` / `chat_tool_calls`**
- **Found during:** Task 1 cross-check against `TenantScopedMixin` definition (`app/db/base.py`).
- **Why:** The RESEARCH §5 DDL sketch (lines 894-989) omitted `updated_at` on chat_conversations and chat_messages, but `TenantScopedMixin` declares `updated_at` via `TimestampMixin`. If the migration omitted `updated_at`, the next `alembic revision --autogenerate` would surface a false-positive diff trying to ADD `updated_at` to all 3 tables.
- **Plan compliance:** The plan's `<action>` step 1 (Task 1) explicitly anticipated this: *"Add `updated_at TIMESTAMPTZ DEFAULT now() NOT NULL` to match TenantScopedMixin (so ORM model maps cleanly)."* — so this is plan-compliant, not a deviation. Documented here for traceability.

**3. Used named FK constraints (`fk_chat_*_<col>`) on all FKs**
- **Why:** The RESEARCH §5 sketch declared FKs without explicit `name=...`. The project convention (visible in `001_base_tables.py`, `004_metrics_schema.py`, `008_daily_insights.py`) names every FK so future migrations can drop them by name without ambiguity. Names follow the pattern `fk_<table>_<col>` per existing migrations.

## Authentication / Human Gates

None. Task 2 was a BLOCKING schema push — the venv `greenlet` install was a local-environment fix that did not require user authorization.

## Known Stubs

None. Plan 08-02 introduces only persistence schema; every column is wired column-for-column between ORM and DDL.

## Deferred Issues

Out-of-scope item logged in `.planning/phases/08-ai-chat/deferred-items.md` and NOT addressed in this plan:

- **Pre-existing `backend/tests/unit/test_models.py:15` ImportError.** The Phase-1-era test imports `TIMESTAMPTZ` from `sqlalchemy.dialects.postgresql`, but in this project `TIMESTAMPTZ` lives at `app.db.base`. This failure pre-dates Phase 8 and is unrelated to chat models. Logged for future cleanup; scope-boundary rule says "do not fix pre-existing failures in unrelated files."

## Threat Flags

None. Plan 08-02 adds 3 persistence tables already enumerated in the `<threat_model>` block of `08-02-PLAN.md` (T-08-01, T-08-02, T-08-05, T-08-06, T-08-DDL). No new network endpoints, no new auth paths, no new file access patterns, no schema changes at trust boundaries that the planner did not anticipate.

## Commits

| Hash | Subject | Files |
|------|---------|-------|
| `db331d32` | `test(08-02): add failing tests for chat ORM models + migration 009` | +1 test file (310 lines) |
| `63dadf24` | `feat(08-02): add chat ORM models + Alembic migration 009 (D-20 schema)` | +5 files / +1 modified (546 lines) |

A 3rd commit follows with this SUMMARY.md (+ deferred-items.md).

## Plan 08-02 Unblocks

The 3 chat tables now exist with FK + CHECK + index coverage, so downstream plans can:

- **08-03 (tools registry + handlers)** — tool handlers can persist results (no schema dependency, but tests of `get_kpi`-style tools can seed `chat_messages` rows using the factory builders from 08-01).
- **08-04 (orchestrator + hallucination guard + title generator)** — orchestrator can `INSERT` into `chat_messages` (incl. `hallucination_flag` and `regenerate_count` extensions), `chat_tool_calls` (audit per tool invocation per D-21), and UPDATE `chat_conversations.last_message_at` + `.title`.
- **08-05 (chat router + SSE endpoint)** — repository layer can `SELECT FROM chat_messages WHERE conversation_id = ?` (covered by `ix_chat_messages_conv_created`) under the auto-applied `with_loader_criteria` tenant_id filter (T-08-01 mitigation).
- **08-06 (frontend UI)** — sidebar "recent conversations" query is index-backed by `ix_chat_conversations_tenant_user_last`.

## Self-Check: PASSED

All claimed files exist on disk and every commit is present in the worktree's git log. Spot-checks:

- `[ -f backend/alembic/versions/009_chat_tables.py ]` → FOUND
- `[ -f backend/app/models/chat/__init__.py ]` → FOUND
- `[ -f backend/app/models/chat/chat_conversation.py ]` → FOUND
- `[ -f backend/app/models/chat/chat_message.py ]` → FOUND
- `[ -f backend/app/models/chat/chat_tool_call.py ]` → FOUND
- `[ -f backend/tests/unit/chat/test_chat_models.py ]` → FOUND
- `git log --oneline | grep db331d32` → FOUND (`test(08-02): add failing tests...`)
- `git log --oneline | grep 63dadf24` → FOUND (`feat(08-02): add chat ORM models...`)
- `alembic current` against live PostgreSQL → `009 (head)` ✓
- `\dt chat_*` against live PostgreSQL → 3 tables ✓
