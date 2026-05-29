# Phase 8: AI Chat — Pattern Map

**Mapped:** 2026-05-29
**Files analyzed:** 71 new + 6 modified (77 total)
**Analogs found:** 65 / 77 (12 NEW PATTERN: SSE handler, orchestrator, hallucination guard, tool registry, frontend SSE consumer hook, chat input, markdown renderer, dashboard link pill, tool pill, conversation sidebar, message bubble, thinking indicator — all have implementation sketches in RESEARCH.md)

---

## File Classification

### Backend — Schema & Persistence

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|-------------------|------|-----------|----------------|-------|
| `backend/alembic/versions/009_chat_tables.py` | migration | DDL | `backend/alembic/versions/008_daily_insights.py` | role-match |
| `backend/app/models/chat/__init__.py` | model package init | — | `backend/app/models/insights/__init__.py` | exact |
| `backend/app/models/chat/chat_conversation.py` | ORM model | tenant-scoped | `backend/app/models/insights/daily_insight.py` | role-match |
| `backend/app/models/chat/chat_message.py` | ORM model | tenant-scoped + FK CASCADE | `backend/app/models/insights/daily_insight.py` + `backend/app/models/anomaly/detected_problem.py` | role-match |
| `backend/app/models/chat/chat_tool_call.py` | ORM model | tenant-scoped + FK CASCADE | `backend/app/models/insights/daily_insight.py` | role-match |
| `backend/app/models/__init__.py` | model registry | — | (modify in place) | self |

### Backend — Schemas

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|-------------------|------|-----------|----------------|-------|
| `backend/app/schemas/chat/__init__.py` | schema package init | — | `backend/app/schemas/insights/__init__.py` | exact |
| `backend/app/schemas/chat/conversation.py` | Pydantic v2 DTO | request/response | `backend/app/schemas/insights/daily_insight_schema.py` | role-match |
| `backend/app/schemas/chat/message.py` | Pydantic v2 DTO | request/response | `backend/app/schemas/insights/daily_insight_schema.py` | role-match |
| `backend/app/schemas/chat/sse_events.py` | Pydantic v2 DTO | SSE event-driven | NEW PATTERN — no SSE schemas exist | NEW |

### Backend — Services (Orchestrator + Guard)

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|-------------------|------|-----------|----------------|-------|
| `backend/app/services/chat/__init__.py` | service package init | — | `backend/app/services/insights/__init__.py` | exact |
| `backend/app/services/chat/orchestrator.py` | service (Claude loop) | streaming + tool-use | `backend/app/services/insights/insight_service.py` | role-match (single-shot → streaming) |
| `backend/app/services/chat/prompt_builder.py` | service (prompt) | static + interpolation | `backend/app/services/insights/prompt_builder.py` | exact |
| `backend/app/services/chat/hallucination_guard.py` | service (validator) | text → list of violations | `backend/app/services/insights/number_validator.py` | role-match (extended) |
| `backend/app/services/chat/title_generator.py` | service (cheap Claude) | fire-and-forget request-response | `backend/app/services/insights/insight_service.py` (simplified) | role-match (NEW PATTERN: asyncio.create_task fire-and-forget) |

### Backend — Tool Handlers (12 tools + base)

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|-------------------|------|-----------|----------------|-------|
| `backend/app/services/chat/tools/__init__.py` | TOOLS_REGISTRY | dict lookup | NEW PATTERN — see RESEARCH §"Tool registry + Tool dataclass" | NEW |
| `backend/app/services/chat/tools/base.py` | Tool dataclass | protocol | NEW PATTERN — see RESEARCH §4 | NEW |
| `backend/app/services/chat/tools/get_kpi.py` | tool handler | read → dict | `backend/app/services/dashboards/dashboard_read_service.py` (DailyKpiService wrap) | role-match |
| `backend/app/services/chat/tools/get_funnel_data.py` | tool handler | read → dict | `backend/app/services/dashboards/dashboard_read_service.py:get_sales_dashboard` | exact |
| `backend/app/services/chat/tools/get_salesperson_performance.py` | tool handler | read → dict | `backend/app/services/dashboards/dashboard_read_service.py:get_salespeople_dashboard` | exact |
| `backend/app/services/chat/tools/get_leads.py` | tool handler | read → dict (new query) | `backend/app/services/dashboards/dashboard_read_service.py` (text query pattern lines 439-449) | role-match |
| `backend/app/services/chat/tools/compare_periods.py` | tool handler | 2× read + delta | `backend/app/services/dashboards/dashboard_read_service.py:get_sales_dashboard` (twice) | role-match |
| `backend/app/services/chat/tools/get_loss_reasons.py` | tool handler | read (new text query) | `backend/app/services/dashboards/dashboard_read_service.py` text-query pattern | role-match |
| `backend/app/services/chat/tools/get_lead_categories_breakdown.py` | tool handler | read → dict | `backend/app/services/dashboards/dashboard_read_service.py:get_marketing_dashboard` | exact |
| `backend/app/services/chat/tools/get_showroom_performance.py` | tool handler | read (new query group by showroom) | `backend/app/services/dashboards/dashboard_read_service.py` text-query pattern | role-match |
| `backend/app/services/chat/tools/get_recent_insight.py` | tool handler | read → dict | `backend/app/services/insights/insight_read_service.py` | exact |
| `backend/app/services/chat/tools/explain_metric.py` | tool handler | pure dict lookup | NEW PATTERN — static metric glossary, no DB | NEW |
| `backend/app/services/chat/tools/get_stuck_leads.py` | tool handler | read → dict | `backend/app/services/dashboards/dashboard_read_service.py:get_stuck_offers` (lines 496-545) | exact |
| `backend/app/services/chat/tools/get_trend.py` | tool handler | read → dict (time series) | `backend/app/services/metrics/daily_kpi_service.py` | role-match |

### Backend — Repositories

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|-------------------|------|-----------|----------------|-------|
| `backend/app/services/chat/repositories/__init__.py` | repo package init | — | `backend/app/services/repositories/__init__.py` | exact |
| `backend/app/services/chat/repositories/conversation_repository.py` | repository | UPSERT + list | `backend/app/services/repositories/insight_repository.py` | role-match |
| `backend/app/services/chat/repositories/message_repository.py` | repository | INSERT + history fetch | `backend/app/services/repositories/insight_repository.py` | role-match |
| `backend/app/services/chat/repositories/tool_call_repository.py` | repository | INSERT (audit) | `backend/app/services/repositories/insight_repository.py` | role-match |

### Backend — Router

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|-------------------|------|-----------|----------------|-------|
| `backend/app/api/v1/chat.py` | router | 5 endpoints incl. SSE StreamingResponse | `backend/app/api/v1/insights.py` (rate-limit + auth + Romanian errors) | role-match (NEW PATTERN for SSE endpoint — RESEARCH §1 sketch) |
| `backend/app/api/v1/router.py` | router registry | — | (modify in place — exact pattern lines 5-12) | self |

### Backend — Tests

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|-------------------|------|-----------|----------------|-------|
| `backend/tests/unit/test_chat_prompt_builder.py` | unit test | snapshot | `backend/tests/unit/test_prompt_builder.py` | exact |
| `backend/tests/unit/test_hallucination_guard.py` | unit test | crafted inputs | `backend/tests/unit/test_number_validator.py` | exact |
| `backend/tests/unit/test_chat_tools_registry.py` | unit test | introspection | NEW PATTERN — registry shape test | NEW (small) |
| `backend/tests/unit/test_chat_tool_handlers.py` | unit test | mock wrapped service | `backend/tests/unit/test_dashboard_read_service.py` | role-match |
| `backend/tests/unit/test_chat_orchestrator.py` | unit test | AsyncAnthropic mock + tool-loop | `backend/tests/unit/test_insight_service.py` | exact |
| `backend/tests/unit/test_chat_router.py` | unit test | rate-limit + grep gate | `backend/tests/unit/test_insights_router.py` (lines 84-102) | exact |
| `backend/tests/unit/test_title_generator.py` | unit test | timeout + fallback | `backend/tests/unit/test_insight_service.py` (mocked AsyncAnthropic) | role-match |
| `backend/tests/integration/test_chat_history.py` | integration test | round-trip persistence | `backend/tests/integration/test_generate_daily_insights_task.py` | role-match |
| `backend/tests/integration/test_chat_orchestrator.py` | integration test | E2E mocked Claude | `backend/tests/integration/test_generate_daily_insights_task.py` | role-match |
| `backend/tests/adversarial/test_chat_adversarial.py` | adversarial test | YAML-driven, env-gated | NEW PATTERN — no adversarial harness exists | NEW |
| `backend/tests/adversarial/adversarial_chat_questions.yaml` | YAML fixture | data | NEW PATTERN | NEW |
| `backend/tests/factories/chat_factory.py` | test factory | dict builders | `backend/tests/factories/insight_factory.py` | exact |

### Frontend — Page + Hook

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|-------------------|------|-----------|----------------|-------|
| `frontend/src/app/(dashboard)/chat/page.tsx` | page (rebuild from placeholder) | client component + Suspense | `frontend/src/app/(dashboard)/insights/page.tsx` | role-match |
| `frontend/src/hooks/useChat.ts` | hook (SSE consumer + TanStack) | streaming + mutation | `frontend/src/hooks/useInsights.ts` + RESEARCH §7 sketch | NEW PATTERN (fetch+ReadableStream — RESEARCH §7) |

### Frontend — Chat Components

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|-------------------|------|-----------|----------------|-------|
| `frontend/src/components/chat/conversations-list.tsx` | component | list + TanStack Query | `frontend/src/components/sidebar.tsx` (existing nav sidebar) | role-match |
| `frontend/src/components/chat/conversation-item.tsx` | component | row + kebab menu | `frontend/src/components/dashboards/insights/problem-card.tsx` (Collapsible header pattern) | role-match |
| `frontend/src/components/chat/chat-main.tsx` | component | wrapper + state owner | `frontend/src/app/(dashboard)/insights/page.tsx` (Content wrapper) | role-match |
| `frontend/src/components/chat/chat-header.tsx` | component | title + kebab | `frontend/src/components/dashboards/insights/problem-card.tsx` (header row) | role-match |
| `frontend/src/components/chat/message-list.tsx` | component | scrollable + autoscroll | NEW PATTERN — no streaming list exists | NEW |
| `frontend/src/components/chat/message-bubble.tsx` | component | user/assistant variants | `frontend/src/components/dashboards/insights/problem-card.tsx` (Card+CardContent) | role-match |
| `frontend/src/components/chat/tool-pill.tsx` | component | inline indicator | NEW PATTERN — no analog | NEW |
| `frontend/src/components/chat/tool-pills-row.tsx` | component | Collapsible wrapper | `frontend/src/components/dashboards/insights/problem-card.tsx` (Collapsible) | role-match |
| `frontend/src/components/chat/thinking-indicator.tsx` | component | 3-dot pulse | NEW PATTERN | NEW (trivial) |
| `frontend/src/components/chat/suggested-questions.tsx` | component | chip row + TanStack Query | `frontend/src/components/dashboards/insights/weekly-action-plan.tsx` (list of items) | role-match |
| `frontend/src/components/chat/chat-input.tsx` | component | textarea + send | NEW PATTERN — no auto-growing textarea analog | NEW |
| `frontend/src/components/chat/markdown-renderer.tsx` | component | react-markdown wrapper | NEW PATTERN — no markdown rendering analog (positive-card.tsx uses plain string) | NEW |
| `frontend/src/components/chat/dashboard-link-pill.tsx` | component | inline link | NEW PATTERN | NEW (trivial) |
| `frontend/src/components/chat/welcome-card.tsx` | component | centered card | `frontend/src/app/(dashboard)/chat/page.tsx` (current placeholder, MessageSquare centered layout) | role-match (replace placeholder) |
| `frontend/src/lib/tool-pill-hints.ts` | utility | pure helpers | `frontend/src/lib/formatters.ts` | role-match |

### Frontend — New shadcn primitives (radix-umbrella manual)

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|-------------------|------|-----------|----------------|-------|
| `frontend/src/components/ui/alert-dialog.tsx` | shadcn primitive | dialog | `frontend/src/components/ui/sheet.tsx` (radix-umbrella manual pattern, Phase 7) | role-match |
| `frontend/src/components/ui/textarea.tsx` | shadcn primitive | native textarea wrapper | `frontend/src/components/ui/input.tsx` | role-match |
| `frontend/src/components/ui/dropdown-menu.tsx` | shadcn primitive | menu | `frontend/src/components/ui/popover.tsx` or `frontend/src/components/ui/sheet.tsx` (radix-umbrella) | role-match |

### Frontend — Tests

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|-------------------|------|-----------|----------------|-------|
| `frontend/src/hooks/useChat.test.ts` | unit test | SSE parser | NEW PATTERN — no existing hook tests yet (Phase 7 deferred) | NEW |
| `frontend/src/components/chat/markdown-renderer.test.tsx` | unit test | allowed-elements whitelist | NEW PATTERN | NEW |
| `frontend/src/components/chat/thinking-indicator.test.tsx` | unit test | 3 states | NEW PATTERN | NEW |

### Frontend — i18n

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|-------------------|------|-----------|----------------|-------|
| `frontend/messages/ro.json` | i18n | namespace | (modify — extend existing `chat` placeholder into full namespace) | self |
| `frontend/messages/en.json` | i18n | namespace | (modify in parallel) | self |
| `frontend/package.json` | manifest | dependency | (modify — add `react-markdown@^9`, `remark-gfm@^4`) | self |

### Docs

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|-------------------|------|-----------|----------------|-------|
| `CLAUDE.md` | doc edit (D-25 documented exception) | text | (modify in place — add note under "Backend никогда не дёргает третьи API синхронно" §5) | self |
| `backend/tests/adversarial/README.md` | doc | text | NEW PATTERN | NEW (trivial) |

---

## Pattern Assignments

### Backend — Schema & Persistence

#### `backend/alembic/versions/009_chat_tables.py` (migration, DDL)

**Analog:** `backend/alembic/versions/008_daily_insights.py`

**Header pattern** (lines 1-38):
```python
from __future__ import annotations

"""Create chat_conversations, chat_messages, chat_tool_calls.

Revision ID: 009
Revises: 008
Create Date: 2026-05-29
...
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None
```

**TenantScopedMixin columns pattern** (008_daily_insights.py lines 43-63):
```python
sa.Column("id", UUID(as_uuid=True), primary_key=True,
          server_default=sa.text("gen_random_uuid()"), nullable=False),
sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
sa.Column("created_at", sa.TIMESTAMP(timezone=True),
          server_default=sa.text("now()"), nullable=False),
sa.Column("updated_at", sa.TIMESTAMP(timezone=True),
          server_default=sa.text("now()"), nullable=False),
```

**FK + UniqueConstraint** (008_daily_insights.py lines 89-99):
```python
sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"],
                         name="fk_daily_insights_tenant_id"),
sa.UniqueConstraint("tenant_id", "date", name="uq_daily_insights_tenant_date"),
```

**Index pattern** (008_daily_insights.py lines 103-107):
```python
op.create_index("ix_daily_insights_tenant_date",
                "daily_insights", ["tenant_id", "date"])
```

**Full 3-table DDL excerpt for chat:** See RESEARCH §5 (`Alembic migration 009 (D-20)`) — paste verbatim. Key extensions:
- `chat_messages.conversation_id` has `ondelete="CASCADE"` (RESEARCH lines 952-953)
- `chat_messages` has CHECK constraint `role IN ('user','assistant','tool_use','tool_result')` (RESEARCH line 955)
- `chat_messages.hallucination_flag` + `regenerate_count` columns (D-20 extension beyond SPEC.md)
- Descending index on `last_message_at` via `sa.text("last_message_at DESC")` (RESEARCH line 932)

---

#### `backend/app/models/chat/chat_conversation.py` (ORM model)

**Analog:** `backend/app/models/insights/daily_insight.py`

**Header + imports** (daily_insight.py lines 1-37):
```python
from __future__ import annotations

"""SQLAlchemy ORM model for chat_conversations table."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin, TIMESTAMPTZ
```

**Class pattern** (daily_insight.py lines 40-91):
```python
class ChatConversation(Base, TenantScopedMixin):
    """One conversation per (tenant, user). archived=true for soft-delete (D-15)."""

    __tablename__ = "chat_conversations"

    user_id: Mapped[UUID] = mapped_column(...)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_message_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
```

Apply identical pattern to `chat_message.py` (add `conversation_id`, `role`, `content`, `tool_calls JSONB`, `tool_results JSONB`, `tokens_used`, `duration_ms`, `hallucination_flag`, `regenerate_count`) and `chat_tool_call.py` (add `message_id` with `ondelete="CASCADE"`, `tool_name`, `input_args JSONB`, `output_data JSONB`, `error`).

**JSONB column pattern** (daily_insight.py line 74):
```python
payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```

---

#### `backend/app/models/__init__.py` (model registry — modify)

**Analog (self):** Current file lines 24-28 — Phase 5 pattern.

**Apply Phase 8 addition pattern:**
```python
# Phase 8 models — AI chat (chat_conversations, chat_messages, chat_tool_calls)
from app.models.chat import (  # noqa: F401 — Alembic autogenerate discovery
    ChatConversation,
    ChatMessage,
    ChatToolCall,
)
```

Also append to `__all__`.

---

### Backend — Schemas

#### `backend/app/schemas/chat/conversation.py` / `message.py` (Pydantic v2 DTOs)

**Analog:** `backend/app/schemas/insights/daily_insight_schema.py`

**Class pattern** (daily_insight_schema.py lines 35-49):
```python
class ConversationOut(BaseModel):
    """Single conversation envelope returned by GET /chat/conversations."""

    id: UUID
    title: str | None
    created_at: datetime
    last_message_at: datetime
    archived: bool
```

**Decimal field convention** (daily_insight_schema.py line 48 + module docstring D-19):
- Monetary/numeric tool fields: `Decimal` not `float` (DATA-04 carries forward).
- Serialize via `model_dump(mode="json")` which emits Decimal as str.

**Literal-constrained field** (daily_insight_schema.py line 31):
```python
deadline: Literal["Azi", "Mâine", "Săptămâna aceasta", "Luna aceasta"]
```
Apply to `MessageOut.role: Literal["user", "assistant"]`.

---

#### `backend/app/schemas/chat/sse_events.py` (NEW PATTERN — SSE event envelopes)

**Analog:** NEW PATTERN — no existing SSE schemas.

**Source:** D-09 schema list in CONTEXT.md + RESEARCH §1 inline `_sse_format` function.

**Implementation sketch** (assemble per D-09):
```python
from __future__ import annotations
from typing import Literal
from uuid import UUID
from pydantic import BaseModel

class ConversationMetaEvent(BaseModel):
    conversation_id: UUID
    message_id_user: UUID
    message_id_assistant: UUID

class ToolUseEvent(BaseModel):
    tool_use_id: str
    name: str
    input: dict

class ToolResultEvent(BaseModel):
    tool_use_id: str
    output_preview: str
    duration_ms: int
    error: bool | None = None

class AssistantChunkEvent(BaseModel):
    text: str

class RegenerateNoticeEvent(BaseModel):
    reason: Literal["hallucination_guard"]

class DoneEvent(BaseModel):
    message_id: UUID
    total_input_tokens: int
    total_output_tokens: int
    duration_ms: int
    hallucination_flag: bool

class ErrorEvent(BaseModel):
    code: str
    message_ro: str
```

---

### Backend — Orchestrator + Guard

#### `backend/app/services/chat/orchestrator.py` (service, streaming + tool-use)

**Analog:** `backend/app/services/insights/insight_service.py` (constructor, AsyncAnthropic patch target, structlog binding, cost formula) + NEW PATTERN for streaming loop (RESEARCH §2).

**Module-level AsyncAnthropic import** (insight_service.py lines 26-28):
```python
# AsyncAnthropic imported at module level for testability (patch target).
# Instantiated ONLY inside method body per INFRA-05 (never at module level).
from anthropic import AsyncAnthropic
```

**Module-level model constants** (insight_service.py lines 30-34):
```python
MODEL = "claude-sonnet-4-5"  # LOCKED (CLAUDE.md, STATE.md)
MAX_TOKENS = 4096
TEMPERATURE = 0.3  # chat uses 0.3 — slightly higher than Phase 5's 0.2 (D-30 / RESEARCH §2)
MAX_TOOL_ROUNDS = 5  # D-30 hard cap
```

**Constructor + structlog bind** (insight_service.py lines 49-52):
```python
def __init__(self, session: AsyncSession, tenant_id: UUID, user_id: UUID) -> None:
    self._session = session
    self._tenant_id = tenant_id
    self._user_id = user_id
    self._log = log.bind(tenant_id=str(tenant_id), service="chat_orchestrator")
```

**Per-method AsyncAnthropic instantiation (INFRA-05 / D-29)** (insight_service.py line 92):
```python
client = AsyncAnthropic(api_key=settings.anthropic_api_key)
```

**Cost formula** (insight_service.py lines 186-202):
```python
@staticmethod
def _compute_cost(usage: object | None) -> Decimal:
    if usage is None:
        return Decimal("0")
    input_tok = (usage.input_tokens or 0) if hasattr(usage, "input_tokens") else 0
    output_tok = (usage.output_tokens or 0) if hasattr(usage, "output_tokens") else 0
    return Decimal(str((input_tok / 1_000_000) * 3.0 + (output_tok / 1_000_000) * 15.0))
```

**Multi-turn tool loop (NEW PATTERN):** Use RESEARCH §2 verbatim (lines 552-716). Key elements:
- Async generator yielding `(event_name, payload)` tuples
- `async with client.messages.stream(...) as stream: async for event in stream:` (RESEARCH line 603-624)
- `disconnect_probe()` check (D-12) at top of inner loop (RESEARCH line 612-613)
- `asyncio.gather` for parallel tool execution (RESEARCH line 650)
- Outer `for guard_attempt in (0, 1):` retry loop (RESEARCH line 598, D-07)
- `tool_results_for_claude` list with `is_error` flag (RESEARCH line 663-668, D-21)

---

#### `backend/app/services/chat/prompt_builder.py` (Romanian system prompt builder)

**Analog:** `backend/app/services/insights/prompt_builder.py`

**SYSTEM_PROMPT_TEXT pattern** (prompt_builder.py lines 23-61): module-level Romanian string constant.

**Sofa Belle facts to inject** (carry verbatim from prompt_builder.py lines 32-50):
```
Companie: Sofa Belle — mobilă premium, 3 showroom-uri (Brașov, București, Cluj-Napoca)...
Showroom este canalul principal de conversie (29.5% din lead-uri, 55% din contracte, 10.8% conversie L→C)...
Echipa de vânzări (6 persoane):
- Roibu Valeria
- Raileanu Leon (best performer: 8.3% conversie L→C)
- Godja Adina Maria
- Dragoi Mihaela (atenție: 351 lead-uri, 2.8% conversie — cu mult sub media echipei de 5.8%)
- Zagrian Emilia
- Moaca Andreea
```

**cache_control system blocks pattern** (prompt_builder.py lines 64-86):
```python
def build_system_prompt() -> list[dict]:
    return [
        {"type": "text", "text": SYSTEM_PROMPT_TEXT},
        {"type": "text",
         "text": "Format de răspuns: text Markdown în română...",
         "cache_control": {"type": "ephemeral"}},  # D-27 — cache on last block
    ]
```

**Chat extension (per D-26):** add a "MVP1 data limitations" block listing `estimated_value=NULL`, no Meta/Google/TikTok/GA4/GSC, no call transcripts → Claude must defer honestly per CHAT-05.

---

#### `backend/app/services/chat/hallucination_guard.py` (number + entity + link checker)

**Analog:** `backend/app/services/insights/number_validator.py`

**Reused verbatim** (number_validator.py lines 28-30):
```python
NUMBER_PATTERN = re.compile(r"\b(\d[\d.,]*\d|\d)\b")
```

**Romanian normalization (verbatim reuse)** (number_validator.py lines 33-84): `extract_numbers_from_text(text)` handles `23.400 → 23400`, `8,3 → 8.3`, `5050 → 5050`. Import directly:
```python
from app.services.insights.number_validator import NUMBER_PATTERN, extract_numbers_from_text
```

**Tolerance check pattern** (number_validator.py lines 205-211):
```python
tolerance = abs(ref) if abs(ref) > 1e-9 else 1e-9
if abs(number - ref) / tolerance <= 0.01:  # D-06: ±1% (chat tightens Phase 5's ±2%)
    matched = True
```

**Skip rules pattern (lift from number_validator.py lines 197-203):**
```python
if number <= 10:
    continue  # small counts — LM-11 list-marker guard
if 1900 <= number <= 2100:
    continue  # calendar years
```

**Recursive tool-result walker (NEW PATTERN):** RESEARCH §3 lines 735-749 — `_extract_numbers_recursive(value)` walks dict/list/str/int/float. Use verbatim.

**Derived numbers (NEW PATTERN):** RESEARCH §3 lines 752-765 — `_compute_derived(base)` produces pairwise `%`, `sum`, `diff`, quantized to 1 decimal.

**Link whitelist** (RESEARCH §3 lines 797-802, D-18a):
```python
ALLOWED_HREFS = {"/sales", "/salespeople", "/marketing", "/insights", "/chat", "#"}
for m in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", response_text):
    if m.group(2) not in ALLOWED_HREFS:
        unsupported.append(f"link:{m.group(2)}")
```

**Entity whitelist regex** (RESEARCH §3 lines 809-813):
```python
for m in re.finditer(
    r"\b([A-ZĂÂÎȘȚ][a-zăâîșț]+ [A-ZĂÂÎȘȚ][a-zăâîșț]+(?: [A-ZĂÂÎȘȚ][a-zăâîșț]+)?)\b",
    response_text,
):
    if m.group(1) not in ALL_NAMES:
        unsupported.append(f"entity:{m.group(1)}")
```

**Allowed-entity sources:** `mefi_salespeople` table query (full names from Phase 2 `MefiSalesperson`), showroom names = `{"Brașov", "București", "Cluj"}` (per RESEARCH D-06), 11 source categories from `MEFI_SOURCE_ID_TO_NAME` (dashboard_read_service.py lines 36-47).

---

#### `backend/app/services/chat/title_generator.py` (fire-and-forget Claude Haiku)

**Analog:** `backend/app/services/insights/insight_service.py` (simplified — no tools, no guard)

**Imports + module setup** (insight_service.py lines 26-36):
```python
from anthropic import AsyncAnthropic
import structlog, asyncio
log = structlog.get_logger(__name__)
```

**Fire-and-forget detach pattern (NEW PATTERN — LM-8):** RESEARCH §6 lines 994-1043 — `_pending: set[asyncio.Task]` module-level set + `task.add_done_callback(_pending.discard)`. Use verbatim.

**Model fallback chain** (RESEARCH lines 1003-1004):
```python
TITLE_MODEL_PRIMARY = "claude-haiku-4-5"
TITLE_MODEL_FALLBACK = "claude-sonnet-4-5"
TITLE_TIMEOUT_S = 3.0
```

**Timeout pattern** (RESEARCH lines 1026-1031):
```python
resp = await asyncio.wait_for(
    client.messages.create(model=model, max_tokens=40, temperature=0.3,
                            messages=[{"role": "user", "content": prompt}]),
    timeout=TITLE_TIMEOUT_S,
)
```

**Romanian prompt** (RESEARCH lines 1019-1023):
```python
prompt = (
    "Generează un titlu de 4-6 cuvinte în română pentru această conversație, descriind "
    "tema principală. Răspunde DOAR cu titlul, fără punctuație finală sau ghilimele.\n\n"
    f"Întrebare utilizator: {first_user}\n\nRăspuns asistent: {first_assistant[:500]}"
)
```

---

### Backend — Tool Handlers

#### `backend/app/services/chat/tools/base.py` + `__init__.py` (Tool dataclass + TOOLS_REGISTRY)

**Analog:** NEW PATTERN — RESEARCH §4 lines 821-855 verbatim.

```python
# base.py
from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from uuid import UUID
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

@dataclass(frozen=True)
class Tool:
    name: str
    definition: dict[str, Any]  # Anthropic ToolParam dict
    input_schema: type[BaseModel]
    handler: Callable[[UUID, AsyncSession, BaseModel], Awaitable[dict]]
```

**Handler signature contract (LM-3):** every handler must be `async def _handler(tenant_id: UUID, session: AsyncSession, inp: <SpecificInput>) -> dict`. Enforce via `test_chat_tools_registry.py`.

---

#### `backend/app/services/chat/tools/get_kpi.py` (and similar 11) (tool handler)

**Analog:** `backend/app/services/dashboards/dashboard_read_service.py` (constructor pattern + `tenant_id` filter)

**Constructor + tenant_id filter** (dashboard_read_service.py lines 61-63 + line 97):
```python
class DashboardReadService:
    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def get_sales_dashboard(self, from_date, to_date):
        stmt = select(...).where(
            DailyKpi.tenant_id == self._tenant_id,   # T-06-02-01 — mandatory
            DailyKpi.date >= from_date,
            DailyKpi.date <= to_date,
        )
```

**Tool handler template (RESEARCH §4 lines 859-892):**
```python
# get_kpi.py
class GetKpiInput(BaseModel):
    date_from: date = Field(..., description="Start date (inclusive)")
    date_to: date = Field(..., description="End date (inclusive)")
    metrics: list[str] = Field(..., description="Metric names: revenue, contracts, leads, avg_deal_size, conversion_rate")

async def _handler(tenant_id: UUID, session: AsyncSession, inp: GetKpiInput) -> dict:
    svc = DailyKpiService(session, tenant_id)
    return await svc.aggregate_for_range(inp.date_from, inp.date_to, metrics=inp.metrics)

TOOL = Tool(
    name="get_kpi",
    definition={
        "name": "get_kpi",
        "description": "Returns aggregated KPI values for a date range. Use when user asks about revenue, contracts, deal size, conversion.",
        "input_schema": GetKpiInput.model_json_schema(),
    },
    input_schema=GetKpiInput,
    handler=_handler,
)
```

**LM-10 guard:** use `Field(..., description=...)` for required fields (avoid leaking defaults to Anthropic JSON Schema).

#### `backend/app/services/chat/tools/get_stuck_leads.py`

**Analog:** `backend/app/services/dashboards/dashboard_read_service.py:get_stuck_offers` (lines 496-545).

**Stuck-offer query template** (dashboard_read_service.py lines 513-540):
```python
text_sql = text("""
    SELECT l.external_id,
           EXTRACT(EPOCH FROM (now() - MAX(h.changed_at))) / 86400 AS days_stuck,
           sp.full_name AS salesperson_name
    FROM v_mefi_leads_active l
    JOIN mefi_lead_history h ON h.lead_id = l.id
    LEFT JOIN mefi_salespeople sp ON sp.id = l.salesperson_id
    WHERE l.tenant_id = :tid
      AND h.changed_at < now() - INTERVAL ':days days'
    GROUP BY l.external_id, sp.full_name
    ORDER BY days_stuck DESC NULLS LAST
    LIMIT 50
""").bindparams(bindparam("tid", type_=PG_UUID(as_uuid=True)))
```

**LM-4 guard (text-query tenancy):** `text()` queries do NOT trigger `with_loader_criteria`. Bind `tenant_id` explicitly via `:tid` parameter (Phase 6 Pitfall 5).

#### `backend/app/services/chat/tools/explain_metric.py` (NEW PATTERN — static glossary)

**Analog:** NEW PATTERN — no DB hit. Pure Python dict lookup.

**Glossary entries (from CONTEXT specifics):** CAC, ROAS, CPL, Conversie L→V, Conversie L→C, AOV/Cec mediu, TTFT, Data Completeness, Stuck Offer (≥9 entries, Romanian definitions).

---

### Backend — Repositories

#### `backend/app/services/chat/repositories/conversation_repository.py`

**Analog:** `backend/app/services/repositories/insight_repository.py`

**Constructor + cross-tenant guard** (insight_repository.py lines 32-67):
```python
class ConversationRepository:
    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def insert_conversation(self, row: dict) -> UUID:
        if "tenant_id" not in row or row["tenant_id"] is None:
            raise ValueError("ConversationRepository: row missing tenant_id")
        if row["tenant_id"] != self._tenant_id:
            raise ValueError("ConversationRepository: cross-tenant write blocked")
        ...
```

**Pitfall 6 / WR-04 enforcement:** repos validate `tenant_id` because Core INSERT bypasses `with_loader_criteria`. Apply to all 3 chat repos.

**No-commit policy** (insight_repository.py line 78): caller commits atomically. Apply same to chat repos.

---

### Backend — Router

#### `backend/app/api/v1/chat.py` (5 endpoints incl. SSE)

**Analog:** `backend/app/api/v1/insights.py` (rate-limit + auth + Romanian errors) + NEW PATTERN for SSE.

**Router setup** (insights.py lines 1-19):
```python
from __future__ import annotations
from datetime import date, datetime, timezone
from uuid import UUID
import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.db.deps import get_session
from app.schemas.auth import UserOut

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])
```

**Rate-limit pattern** (insights.py lines 74-87, D-24):
```python
RATE_LIMIT_TTL = 3600
RATE_LIMIT_MAX = 30  # D-24 — 30 messages/hour per user

async with aioredis.from_url(settings.redis_url, decode_responses=True) as r:
    # NOTE: for counted rate-limit use INCR + EXPIRE instead of SET NX (which is binary)
    count_key = f"chat:rate:{current_user.id}:hour"
    count = await r.incr(count_key)
    if count == 1:
        await r.expire(count_key, RATE_LIMIT_TTL)
    if count > RATE_LIMIT_MAX:
        ttl = await r.ttl(count_key)
        raise HTTPException(
            status_code=429,
            detail="Ai trimis prea multe mesaje. Așteaptă câteva minute și încearcă din nou.",
            headers={"Retry-After": str(max(ttl, 0))},
        )
```

**Stream-lock pattern (D-11, 409 Conflict):**
```python
lock_key = f"chat:stream:{conversation_id}"
async with aioredis.from_url(settings.redis_url, decode_responses=True) as r:
    was_set = await r.set(lock_key, "1", nx=True, ex=180)  # 3-min TTL covers long tool chains
    if not was_set:
        raise HTTPException(
            status_code=409,
            detail="Așteaptă răspunsul curent înainte de a trimite alt mesaj.",
        )
# release in finally inside generator
```

**SSE StreamingResponse (NEW PATTERN):** Use RESEARCH §1 lines 478-547 verbatim. Key elements:
- `async def event_generator():` async generator inside the handler
- `yield _sse_format(event_name, payload)` per emitted event
- `return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})` (LM-5 mitigation)
- `def _sse_format(event_name, data)` returns `f"event: {event_name}\ndata: {json.dumps(...)}\n\n"`

**D-25 documented exception docstring** (RESEARCH lines 480-488): top-of-file docstring explaining why `AsyncAnthropic` is allowed here (paste verbatim).

---

#### `backend/app/api/v1/router.py` (modify)

**Analog (self):** lines 5-12.

**Apply pattern:**
```python
from app.api.v1 import auth, chat, dashboards, health, insights, sync
...
api_router.include_router(chat.router)
```

---

### Backend — Tests

#### `backend/tests/unit/test_chat_router.py` (rate-limit + grep gate)

**Analog:** `backend/tests/unit/test_insights_router.py` (lines 84-102 grep gate, lines 17-49 rate-limit)

**Grep gate INVERSE pattern (CHAT-08 / D-39)** — Phase 5 asserts `AsyncAnthropic NOT in insights.py`; chat asserts `AsyncAnthropic IS in chat.py AND NOT in any other app/api/ file`:
```python
@pytest.mark.asyncio
async def test_chat08_async_anthropic_only_in_chat() -> None:
    import importlib, sys, pathlib
    module = importlib.import_module("app.api.v1.chat")
    source = open(module.__file__).read()
    assert "AsyncAnthropic" in source, "CHAT-08: chat.py MUST import AsyncAnthropic"

    api_v1_dir = pathlib.Path(module.__file__).parent
    for py_file in api_v1_dir.glob("*.py"):
        if py_file.name in ("chat.py", "__init__.py", "router.py"):
            continue
        text = py_file.read_text()
        assert "AsyncAnthropic" not in text, (
            f"CHAT-08 violation: AsyncAnthropic found in {py_file.name}"
        )
```

**Rate-limit pattern** (test_insights_router.py lines 17-81): two tests — first call succeeds, second returns 429 with `Retry-After`. Mirror for `POST /chat/conversations/{id}/messages`.

---

#### `backend/tests/unit/test_chat_orchestrator.py`

**Analog:** `backend/tests/unit/test_insight_service.py` lines 39-49, 139-149.

**Service builder pattern** (test_insight_service.py lines 39-49):
```python
def _make_orchestrator(mock_session=None):
    from app.services.chat.orchestrator import ChatOrchestrator
    session = mock_session or AsyncMock()
    return ChatOrchestrator(session, TENANT_ID, USER_ID)
```

**AsyncAnthropic mock pattern** (test_insight_service.py lines 139-143):
```python
with patch("app.services.chat.orchestrator.AsyncAnthropic") as mock_cls:
    mock_client = AsyncMock()
    mock_cls.return_value = mock_client
    # Mock the streaming context manager
    mock_stream = AsyncMock()
    mock_client.messages.stream.return_value.__aenter__.return_value = mock_stream
    ...
```

For streaming events (NEW for Phase 8): `mock_stream` must be an async iterator yielding `MagicMock` events with `type`, `delta`, `content_block`, etc. Build small fixture helpers.

---

#### `backend/tests/unit/test_hallucination_guard.py`

**Analog:** `backend/tests/unit/test_number_validator.py`

Test cases (per D-06):
- Number outside ±1% tolerance → flagged
- Derived `%` from `(a/b)*100` allowed
- Romanian `23.400 RON` parsed correctly (existing Phase 5 test)
- `21.5%` allowed if it matches `21.5` ± 1% from a tool result
- Calendar year `2026` skipped
- Number `≤ 10` skipped
- Salesperson name not in whitelist → `entity:` violation
- Link `https://evil.com` → `link:` violation
- Link `/sales` → allowed
- Empty tool_results → only common-knowledge numbers allowed

---

#### `backend/tests/factories/chat_factory.py`

**Analog:** `backend/tests/factories/insight_factory.py`

Same dict-builder pattern — `make_chat_conversation()`, `make_chat_message()`, `make_chat_tool_call()` returning dicts compatible with repository UPSERT.

---

### Frontend — Page + Hook

#### `frontend/src/app/(dashboard)/chat/page.tsx` (rebuild from placeholder)

**Analog:** `frontend/src/app/(dashboard)/insights/page.tsx`

**Structure pattern** (insights/page.tsx lines 305-313):
```tsx
"use client";

import { Suspense } from "react";
import { Skeleton } from "@/components/ui/skeleton";

function ChatPageContent() {
  // useSearchParams() for ?conversation_id=
  // render split panel: ConversationsList + ChatMain
}

export default function ChatPage() {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <ChatPageContent />
    </Suspense>
  );
}
```

**Client-component declaration** (insights/page.tsx line 1): `"use client";` at top.

**useTranslations pattern** (insights/page.tsx line 33):
```tsx
const t = useTranslations("chat");
```

**TanStack Query usage** (insights/page.tsx lines 36-43): pattern for `useConversationsList()`, `useConversation(id)` hooks (to add to `useChat.ts` or new `useConversations.ts`).

---

#### `frontend/src/hooks/useChat.ts` (NEW PATTERN — SSE consumer)

**Analog:** NEW PATTERN — use RESEARCH §7 lines 1048-1150 verbatim.

**Token retrieval** (mirrors `api-client.ts` lines 11-15):
```ts
function readAccessToken(): string | null {
  if (typeof document === "undefined") return null;
  const m = document.cookie.match(/(?:^|;\s*)access_token=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : null;
}
```

**SSE parser with buffer (LM-7 mitigation)** — RESEARCH §7 lines 1067-1086: maintain `buffer` across reads, split on `\n\n`, keep tail.

**Hook shape** (RESEARCH §7 lines 1088-1150):
```ts
export function useChat(conversationId: string) {
  const [isStreaming, setIsStreaming] = useState(false);
  const [tokens, setTokens] = useState<string>("");
  const [toolPills, setToolPills] = useState<any[]>([]);
  const abortRef = useRef<AbortController | null>(null);
  const qc = useQueryClient();

  const sendMessage = useCallback(async (content: string) => { ... });
  const cancel = useCallback(() => abortRef.current?.abort(), []);
  return { sendMessage, cancel, isStreaming, tokens, toolPills };
}
```

**SSE event handling**:
- `assistant_chunk` → `setTokens(t => t + ev.data.text)`
- `tool_use` → append pill with `state: "running"`
- `tool_result` → update pill `state: error ? "error" : "done"`
- `regenerate_notice` → `setTokens("")` (D-08 reset)
- `done` → `setIsStreaming(false); qc.invalidateQueries({queryKey: ["chat","conversations"]})` (refetch title)
- `error` → surface `message_ro`

---

### Frontend — Chat Components

#### `frontend/src/components/chat/conversations-list.tsx`

**Analog:** `frontend/src/components/sidebar.tsx` (mobile Sheet pattern, Phase 7).

**TanStack Query** (mirror useInsights.ts hooks from `frontend/src/hooks/useInsights.ts`).

**Sheet pattern for mobile (D-36):** reuse Phase 7 `Sheet`/`SheetContent`/`SheetTrigger` primitives from `frontend/src/components/ui/sheet.tsx`.

---

#### `frontend/src/components/chat/conversation-item.tsx`

**Analog:** `frontend/src/components/dashboards/insights/problem-card.tsx` (header row with Badge + kebab, CollapsibleTrigger pattern).

**Active state border-l pattern** (UI-SPEC accent reserved-for #3): `bg-accent/10 text-accent border-l-[3px] border-accent`.

**Touch target** (problem-card.tsx line 42): `min-h-[44px]` (NON-NEGOTIABLE per Phase 7 D-17).

---

#### `frontend/src/components/chat/message-bubble.tsx`

**Analog:** `frontend/src/components/dashboards/insights/problem-card.tsx` (Card + CardContent wrapper)

**Card pattern** (problem-card.tsx lines 36-67):
```tsx
<Card>
  <CardHeader className="pb-2 px-4 pt-4">
    {/* role label, timestamp */}
  </CardHeader>
  <CardContent className="pt-0 px-4 pb-4 space-y-3">
    {/* MarkdownRenderer for assistant, plain text for user */}
  </CardContent>
</Card>
```

**Variant width per UI-SPEC:** desktop `md:max-w-[75%]`, mobile `max-w-[90%]`.

**ARIA role pattern** (UI-SPEC):
```tsx
<div role="article" aria-label={t("messages.assistantAriaLabel")}>
```

---

#### `frontend/src/components/chat/markdown-renderer.tsx` (NEW PATTERN)

**Analog:** NEW PATTERN — use UI-SPEC §"Markdown Rendering Rules" verbatim.

**Allowed-elements whitelist** (UI-SPEC lines 337-354):
```ts
allowedElements: [
  "p", "strong", "em", "ul", "ol", "li", "a", "code",
  "table", "thead", "tbody", "tr", "th", "td", "br",
]
```

**Custom renderers** (UI-SPEC §"Custom renderers" table):
- `strong` → `<strong className="font-semibold text-accent">`
- `a` → dashboard-link-pill mapper (UI-SPEC lines 375-397)
- `table` → shadcn Table primitives wrapped in `overflow-x-auto`

**Dashboard link mapper** (UI-SPEC lines 375-410):
```tsx
const DASHBOARD_PATHS = new Set(["/sales", "/salespeople", "/marketing", "/insights", "/chat"]);

function renderLink({ href, children }) {
  if (href === "#") return <span>{children}</span>;
  if (DASHBOARD_PATHS.has(href)) return <DashboardLinkPill href={href}>{children}</DashboardLinkPill>;
  return <span className="text-muted-foreground italic">{children}</span>;
}
```

---

#### `frontend/src/components/chat/dashboard-link-pill.tsx` (NEW PATTERN)

**Analog:** NEW PATTERN — UI-SPEC §"DashboardLinkPill markup" lines 402-410:
```tsx
<Link
  href={href}
  className="inline-flex items-center gap-1 bg-accent/10 text-accent rounded-md px-2 py-0.5 text-sm hover:bg-accent/20 transition-colors"
>
  {children}
  <ChevronRight size={14} aria-hidden="true" />
</Link>
```

---

#### `frontend/src/components/chat/tool-pill.tsx` (NEW PATTERN)

**Analog:** NEW PATTERN — UI-SPEC §"Tool Pill Content Rules" lines 295-314 + helper sketch lines 318-325.

**Per-tool icon map (lucide-react)** (UI-SPEC table):
- `get_kpi` → `Calculator`
- `get_funnel_data` → `Filter`
- `get_salesperson_performance` → `Users`
- `get_leads` → `List`
- `compare_periods` → `GitCompare`
- `get_loss_reasons` → `TrendingDown`
- `get_lead_categories_breakdown` → `PieChart`
- `get_showroom_performance` → `Store`
- `get_recent_insight` → `Lightbulb`
- `explain_metric` → `BookOpen`
- `get_stuck_leads` → `Hourglass`
- `get_trend` → `LineChart`

**Hint helpers** (`frontend/src/lib/tool-pill-hints.ts` — UI-SPEC lines 319-325):
```ts
export function dayCount(dateFrom: string, dateTo: string): string;
export function periodLabel(input: { date_from: string; date_to: string }): string;
```

---

#### `frontend/src/components/chat/tool-pills-row.tsx`

**Analog:** `frontend/src/components/dashboards/insights/problem-card.tsx` (Collapsible expand/collapse)

**Collapsible pattern** (problem-card.tsx lines 36-67): `<Collapsible open={open} onOpenChange={setOpen}>` with `CollapsibleTrigger` + `CollapsibleContent`.

**Collapsed summary text** (UI-SPEC line 314 / D-10): `🔧 {n} unelte folosite` via `t("chat.tools.collapsedSummary", {count: n})` ICU plural.

---

#### `frontend/src/components/chat/thinking-indicator.tsx` (NEW PATTERN)

**Analog:** NEW PATTERN — small component. UI-SPEC §"States Matrix → ThinkingIndicator":
```tsx
<span role="status" aria-live="polite">
  <span className="inline-flex gap-1">
    <span className="motion-safe:animate-pulse">•</span>
    <span className="motion-safe:animate-pulse">•</span>
    <span className="motion-safe:animate-pulse">•</span>
  </span>
  {label && <span className="text-muted-foreground ml-2">{label}</span>}
</span>
```

States: `thinking` (no label), `looking-up` (`Caut datele...`), `verifying-numbers` (`Verific cifrele...`).

---

#### `frontend/src/components/chat/suggested-questions.tsx`

**Analog:** `frontend/src/components/dashboards/insights/weekly-action-plan.tsx` (numbered/labeled item list).

**Touch target** (UI-SPEC line 644): chip `min-h-[44px]`.

**Click → insert into input (not auto-send)** per D-17 — uses callback prop from `ChatInput`.

---

#### `frontend/src/components/chat/chat-input.tsx` (NEW PATTERN)

**Analog:** NEW PATTERN — auto-growing `<textarea>` with Send button.

**Textarea autosize:** vanilla approach — `useRef<HTMLTextAreaElement>` + `useEffect` on value: `el.style.height = "auto"; el.style.height = el.scrollHeight + "px"`.

**Keyboard shortcuts (UI-SPEC §"Keyboard shortcuts"):** Enter sends, Shift+Enter newline, Cmd/Ctrl+Enter sends.

**Send button** (UI-SPEC accent #1): `bg-accent text-accent-foreground min-h-[44px] min-w-[44px]`.

---

### Frontend — New shadcn primitives

#### `frontend/src/components/ui/alert-dialog.tsx`, `textarea.tsx`, `dropdown-menu.tsx`

**Analog:** `frontend/src/components/ui/sheet.tsx` (radix-umbrella manual wrap, Phase 7).

**Pattern:** Each file imports the relevant subpath from the `radix-ui` umbrella (`v1.4.3`), e.g.:
```tsx
import * as AlertDialogPrimitive from "@radix-ui/react-alert-dialog";
```
and re-exports a shadcn-styled wrapper. No CLI fetch — manual mirror of shadcn new-york preset.

---

### Frontend — i18n

#### `frontend/messages/ro.json` and `en.json` (modify — replace placeholder, expand namespace)

**Analog (self):** existing nav `"chat": "Chat AI"` (line 22) + placeholder `"chat": "Chat-ul AI va fi disponibil în curând."` (line 33) → **replace placeholder with full `chat` namespace from UI-SPEC §"Concrete copy block"** (UI-SPEC lines 658-738).

Full `chat` namespace keys to add: `page`, `welcome`, `sidebar`, `conversation`, `input`, `indicators`, `tools`, `suggested.static`, `messages`, `archive`, `timestamps` (~50 keys total, all listed in UI-SPEC).

---

### Docs

#### `CLAUDE.md` (D-25 documented exception)

**Analog (self):** existing section "Backend никогда не дёргает третьи API синхронно" (Core Principles #5).

**Apply pattern:** append a sub-bullet:
```markdown
### 5. Backend никогда не дёргает третьи API синхронно

- Все вызовы к MEFI/Meta/Google/TikTok/GA4/GSC — ТОЛЬКО через Celery tasks
- ...
- **Documented exception (D-25, Phase 8):** `backend/app/api/v1/chat.py` calls
  AsyncAnthropic streaming inside the FastAPI request handler. AI Chat requires
  low-latency token-by-token streaming, which is incompatible with Celery's batch
  model. All OTHER Claude calls (Phase 5 daily insights, Phase 8 D-14 title
  generation via `asyncio.create_task`) remain non-blocking from HTTP-handler
  perspective. Enforced by grep-gate test
  `backend/tests/unit/test_chat_router.py::test_chat08_async_anthropic_only_in_chat`.
```

---

## Shared Patterns

### Tenant Isolation

**Source:** `backend/app/services/dashboards/dashboard_read_service.py:61-100` (constructor + every `.where(Model.tenant_id == self._tenant_id)`).

**Apply to:** every chat ORM query (tool handlers, repositories, history fetch in orchestrator).

```python
def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
    self._session = session
    self._tenant_id = tenant_id

# In every query:
stmt = select(...).where(
    Model.tenant_id == self._tenant_id,
    # other filters
)
```

**LM-3 / LM-4 reminders:**
- Tool handlers receive `tenant_id` as first arg (`async def _handler(tenant_id, session, inp)`).
- `text()` queries bind `:tid` explicitly via `bindparam("tid", type_=PG_UUID(as_uuid=True))` (Phase 6 Pitfall 5).
- Repository writes validate `row["tenant_id"] == self._tenant_id` to defend against Core INSERT bypassing `with_loader_criteria` (insight_repository.py lines 53-67).

---

### AsyncAnthropic Instantiation (INFRA-05 / D-29)

**Source:** `backend/app/services/insights/insight_service.py:26-28, 92`

**Apply to:** `orchestrator.py`, `title_generator.py` — ANY file that calls Claude.

```python
# Module level — for test patchability
from anthropic import AsyncAnthropic

# Inside method body (NEVER module-level instantiation):
client = AsyncAnthropic(api_key=settings.anthropic_api_key)
```

---

### cache_control on System Prompt (D-27)

**Source:** `backend/app/services/insights/prompt_builder.py:76-86`

**Apply to:** `backend/app/services/chat/prompt_builder.py`.

```python
return [
    {"type": "text", "text": STABLE_PROMPT_TEXT},
    {"type": "text", "text": "...formatting hint...",
     "cache_control": {"type": "ephemeral"}},  # caches all preceding stable text
]
```

**LM-6 reminder:** without `cache_control`, every chat turn pays full input-token cost for the 1500+ system-prompt tokens.

---

### structlog Binding

**Source:** `backend/app/services/insights/insight_service.py:52, 149`

**Apply to:** every chat service, every chat router endpoint.

```python
self._log = log.bind(tenant_id=str(tenant_id), service="chat_orchestrator",
                       conversation_id=str(conversation_id))
self._log.info("chat.turn.start", message_id=str(msg_id))
```

**No PII rule:** log `tenant_id`, `conversation_id`, `message_id`, `tool_name`, `duration_ms`, token counts. NEVER log user message content, assistant text, salesperson personal details.

---

### Pydantic v2 Romanian DTO

**Source:** `backend/app/schemas/insights/daily_insight_schema.py`

**Apply to:** all chat schemas.

Patterns:
- `from __future__ import annotations`
- `from pydantic import BaseModel, Field`
- `class Foo(BaseModel):` (no `arbitrary_types_allowed` unless needed)
- Use `Literal[...]` for constrained string fields
- Use `Decimal` (not `float`) for any monetary value in tool outputs (DATA-04)
- Serialize via `model_dump(mode="json")` — Decimals emit as str (Phase 5 D-19)

---

### Rate-limit with Redis SET NX (D-24, but counted)

**Source:** `backend/app/api/v1/insights.py:78-87`

**Apply to:** `POST /chat/conversations/{id}/messages` (30/hour) and stream-lock (1 active per conversation).

**Pattern variants:**
- **Binary lock** (one stream per conversation) — `SET NX EX` (insights.py line 79).
- **Counted rate-limit** (30 messages/hour/user) — `INCR` + `EXPIRE` on first hit. Insights.py uses binary; chat extends to counted.

---

### Romanian Error Responses

**Source:** `backend/app/api/v1/insights.py:83-87`

**Apply to:** every `HTTPException` in chat.py.

```python
raise HTTPException(
    status_code=429,
    detail="Ai trimis prea multe mesaje. Așteaptă câteva minute și încearcă din nou.",
    headers={"Retry-After": str(retry_after)},
)
```

All error strings from UI-SPEC §"Copywriting Contract" table (rate-limit, concurrent-stream 409, stream error). Romanian primary.

---

### TanStack Query in Frontend

**Source:** `frontend/src/hooks/useInsights.ts` + `frontend/src/app/(dashboard)/insights/page.tsx`

**Apply to:** conversation list query (`useConversations()`), single conversation history (`useConversation(id)`), suggested-questions (`useSuggestedQuestions()`).

**Inherits from Phase 7 D-08:** `QueryClientProvider` already mounted in `(dashboard)/layout.tsx` — chat page does not re-wrap.

---

### Mobile Touch Targets (NON-NEGOTIABLE)

**Source:** Phase 7 D-17 carry-forward; `problem-card.tsx:42` (`min-h-[44px]`).

**Apply to:** Send button, conversation list items, chips, kebab menu trigger, sidebar nav items.

---

## No Analog Found

The following files are NEW PATTERNS — no close codebase analog. Each has a verified implementation sketch in RESEARCH.md or UI-SPEC.md. The planner should cite those sketches verbatim in PLAN.md actions.

| File | Role | Data Flow | Source for Pattern |
|------|------|-----------|--------------------|
| `backend/app/services/chat/orchestrator.py` (streaming loop core) | service | streaming + tool-use | RESEARCH §2 "Anthropic streaming + tools loop" (lines 552-716) |
| `backend/app/services/chat/hallucination_guard.py` (recursive walker + derived) | service | text → violations | RESEARCH §3 "Hallucination Guard" (lines 721-815) |
| `backend/app/services/chat/title_generator.py` (fire-and-forget) | service | request-response | RESEARCH §6 "Title generator" (lines 994-1043); LM-8 detach pattern |
| `backend/app/services/chat/tools/base.py` + `__init__.py` | TOOLS_REGISTRY | dict lookup | RESEARCH §4 "Tool registry + Tool dataclass" (lines 821-855) |
| `backend/app/services/chat/tools/explain_metric.py` | tool handler | pure dict | CONTEXT specifics §"Static `explain_metric` glossary content" |
| `backend/app/api/v1/chat.py` (SSE endpoint shell) | router | SSE streaming | RESEARCH §1 "FastAPI SSE endpoint shape" (lines 478-547); LM-5 X-Accel-Buffering header |
| `backend/app/schemas/chat/sse_events.py` | schema | event-driven | CONTEXT D-09 schema + assembled per Pydantic v2 |
| `frontend/src/hooks/useChat.ts` | hook | SSE consumer | RESEARCH §7 "Frontend SSE consumer" (lines 1048-1150); LM-7 chunk-boundary buffer |
| `frontend/src/components/chat/message-list.tsx` | component | scrollable + autoscroll | UI-SPEC §"States Matrix → MessageList" + D-34 autoscroll within 100px |
| `frontend/src/components/chat/markdown-renderer.tsx` | component | react-markdown wrap | UI-SPEC §"Markdown Rendering Rules" (lines 332-410) |
| `frontend/src/components/chat/dashboard-link-pill.tsx` | component | inline link | UI-SPEC lines 402-410 |
| `frontend/src/components/chat/tool-pill.tsx` | component | inline indicator | UI-SPEC §"Tool Pill Content Rules" (lines 295-325) |
| `frontend/src/components/chat/thinking-indicator.tsx` | component | 3-dot pulse | UI-SPEC §"States Matrix → ThinkingIndicator" |
| `frontend/src/components/chat/chat-input.tsx` | component | textarea + send | UI-SPEC §"Interaction Contracts → Sending a message" + §"Keyboard shortcuts" |
| `backend/tests/adversarial/test_chat_adversarial.py` + `.yaml` | adversarial harness | YAML-driven | CONTEXT D-40 + RESEARCH §Open Decision #7 (env-gated `RUN_ADVERSARIAL=1`) |

---

## Key Patterns Identified (Cross-Cutting Summary)

1. **All chat services follow Phase 5 InsightService shape:** constructor `(session, tenant_id, ...)` + module-level constants (`MODEL`, `MAX_TOKENS`, `TEMPERATURE`) + `AsyncAnthropic` instantiated inside method bodies + `structlog.bind(tenant_id=str(tenant_id))`.

2. **All chat ORM models follow Phase 5 DailyInsight shape:** inherit `Base, TenantScopedMixin`, define `__tablename__`, use `Mapped[]` + `mapped_column(JSONB, …)`, register in `app/models/__init__.py` for Alembic autogenerate.

3. **All chat ORM queries filter by `tenant_id` explicitly** (T-06-02-01) — defense-in-depth even with `with_loader_criteria` listener active, because `text()` and Core INSERT bypass it (LM-4 / Pitfall 6).

4. **All Romanian error messages use the UI-SPEC §Copywriting Contract verbatim** — i18n in frontend, Python string in backend HTTPException.

5. **All new Claude calls (orchestrator + title_generator) use `cache_control: {type: "ephemeral"}` on the last system block** (D-27, Phase 5 pattern) — without it, costs balloon 5× (LM-6).

6. **All chat tool handlers wrap an existing Phase 3/5/6 service** (D-03) — only `get_leads`, `get_loss_reasons`, `get_showroom_performance` need NEW thin queries on `v_mefi_leads_active` using the `text() + :tid bindparam` pattern from `dashboard_read_service.py:439-449`.

7. **Frontend chat page inherits Phase 7 dashboard chrome:** `QueryClientProvider` (D-08), `Sheet` mobile pattern (D-17), 44px touch targets (D-17), shadcn new-york preset.

---

## Metadata

**Analog search scope:**
- `backend/app/api/v1/`
- `backend/app/services/insights/`
- `backend/app/services/dashboards/`
- `backend/app/services/anomaly/`
- `backend/app/services/metrics/`
- `backend/app/services/repositories/`
- `backend/app/models/insights/`
- `backend/app/models/anomaly/`
- `backend/app/models/__init__.py`
- `backend/app/schemas/insights/`
- `backend/alembic/versions/`
- `backend/tests/unit/`, `backend/tests/integration/`, `backend/tests/factories/`
- `frontend/src/app/(dashboard)/insights/`, `frontend/src/app/(dashboard)/chat/`
- `frontend/src/components/dashboards/insights/`
- `frontend/src/components/ui/`
- `frontend/src/hooks/`
- `frontend/src/lib/api-client.ts`
- `frontend/messages/ro.json`, `en.json`

**Files scanned:** ~45 (read in full or via Grep-narrowed sections)

**Pattern extraction date:** 2026-05-29
