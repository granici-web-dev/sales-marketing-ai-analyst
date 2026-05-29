# Phase 8: AI Chat - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-29
**Phase:** 08-ai-chat
**Areas discussed:** Tool scope for MVP1, Hallucination guard strictness, Streaming protocol + tool-use transparency, Conversation + UX shape

---

## Tool Scope for MVP1

| Option | Description | Selected |
|--------|-------------|----------|
| All 12 from docs/CHAT.md (Recommended) | Tier 1-4 complete: get_kpi, get_funnel_data, get_salesperson_performance, get_leads, compare_periods, get_loss_reasons, get_lead_categories_breakdown, get_showroom_performance, get_recent_insight, explain_metric, get_stuck_leads, get_trend. Most backed by existing Phase 3 services / Phase 6 read services — incremental cost is low. SC#2 (≥3 distinct tools in one turn) becomes easy. | ✓ |
| Tier 1 + Tier 2 only (10 tools) | Skip Tier 4 (get_stuck_leads, get_trend) — they're aggregations the CEO can also see on dashboards. Hits the SPEC.md '≥10 tools' target exactly. Adds them in Phase 9 if pilot demand exists. | |
| Tier 1 + key Tier 2 (8 tools) | Drop get_loss_reasons (no clean data — estimated_value is NULL for all leads per Phase 3 finding), get_showroom_performance (Sofa Belle has 3 showrooms but data quality unclear), get_stuck_leads, get_trend. Below ROADMAP target of 10 — would need adjustment. | |

**User's choice:** All 12 from docs/CHAT.md
**Notes:** Backend reuse matrix (CONTEXT.md code_context section) shows 11 of 12 wrap existing Phase 3/5/6 services; only get_leads / get_loss_reasons / get_showroom_performance / get_stuck_leads need thin new repository queries. Risk: get_loss_reasons + revenue figures are unreliable because `estimated_value` is NULL — the tool must return counts + pct, omit revenue.

---

## Hallucination Guard Strictness

| Option | Description | Selected |
|--------|-------------|----------|
| Strict: reject + regenerate (Recommended) | Extract numbers, cross-check against tool_results + derived + common-knowledge. On mismatch: notice Claude + force regenerate. Max 1 retry. On 2nd failure: stream a fallback Romanian message. Aligns with CHAT-05/CHAT-10 'zero hallucinated numbers' literal SC. Cost: +1 round-trip on failures, but failures should be rare. | ✓ |
| Soft: log + flag, pass through | Per docs/CHAT.md §6 MVP1 strategy. Detect hallucinations, set chat_messages.hallucination_flag=TRUE, log to Sentry, ship as-is. Lower latency, risk: CEO sees bad numbers. | |
| Hybrid: strict on $, soft on % | Strict on monetary values, soft on percentages and counts. Pragmatic but adds two code paths. | |

**User's choice:** Strict
**Notes:** Overrides docs/CHAT.md §6 MVP1-strategy default. Pilot CEO must not see bad numbers. NUMBER_PATTERN reused from Phase 5 (`backend/app/services/insights/number_validator.py`). Tolerance ±1% per ROADMAP SC#4. Guard runs server-side AFTER stream completes — first stream may be discarded visually if guard rejects (UX hiccup accepted for accuracy). See CONTEXT.md D-05..D-08.

---

## Streaming Protocol + Tool-Use Transparency

| Option | Description | Selected |
|--------|-------------|----------|
| SSE custom events + transparent tool names (Recommended) | Discrete SSE events (tool_use, tool_result, assistant_chunk, regenerate_notice, done, error) per docs/CHAT.md §7. Frontend renders tool calls as visible pills: '🔍 get_funnel_data · 30 zile'. Pills collapse on done. Aids trust + debugging during pilot. | ✓ |
| SSE custom events + opaque indicator | Same SSE protocol, but frontend shows only 'Se gândește...' / 'Caut datele...' spinner. Cleaner UX for owner. Tool details still in audit log. | |
| Pure Anthropic stream passthrough + post-hoc tool summary | Backend pipes Anthropic stream directly. Tool calls show retroactively after message completes. Simpler backend, loses real-time feedback. | |

**User's choice:** SSE custom events + transparent tool names
**Notes:** Owner + analyst dual-persona target. Transparency signals trust ('I see it actually queried the data'). Tool pills implemented as inline elements above in-progress message text, collapse to '🔧 3 unelte folosite' after done event. See CONTEXT.md D-09..D-12.

---

## Conversation + UX Shape

| Option | Description | Selected |
|--------|-------------|----------|
| ChatGPT-style: persistent list, AI-titles, archive (Recommended) | Single global list. Title: Claude generates 4-6 word Romanian summary after turn 1 (cheap separate call, Haiku preferred). Delete = soft archive. History window: last 20 messages. Suggestions: 5 hardcoded curated + injection of today's top 2 daily_insights problems. Inline links: '[Sales Dashboard](/sales)' markdown without date params. | ✓ |
| Ephemeral chats, no persistence | Single 'current conversation' — reopen = fresh. Fails CHAT-03. | |
| ChatGPT-style with date-aware links + Claude auto-titles | Same as option 1 but links carry date range from question context. Higher fidelity, more prompt-engineering surface. | |
| Custom: tell me what fits | Free-text. | |

**User's choice:** ChatGPT-style: persistent list, AI-titles, archive
**Notes:** Date-aware links deferred to Phase 9 polish (D-18). Single owner user MVP1 — `user_id` from `get_current_user`. Archive via existing `archived` column from SPEC.md schema. Mobile responsiveness (Phase 7 D-17 NON-NEGOTIABLE) carries forward — conversation sidebar slides over as Sheet on < 768px. Title generator times out at 3s, falls back to truncated first message. Suggested-question endpoint never returns < 5 chips (fault tolerance on daily_insights lookup). See CONTEXT.md D-13..D-19.

---

## Claude's Discretion

The user explicitly deferred these to Claude during planning:
- Exact wording of static suggested-question chips beyond the 5 examples in D-17.
- Tool pill icon glyphs (lucide-react icons per tool — `Calculator`, `Funnel`, `Users`, etc.).
- Specific Tailwind classes for tool pills, message bubbles, sidebar item hover/active states.
- Whether to emit an SSE `keepalive` heartbeat event every ~15s for long-running tool chains.
- Title generator model preference: Haiku 4.5 if wired, else Sonnet 4.5.
- Whether to add a `react-markdown` plugin for syntax-highlighting code blocks (likely skip — chat is data-Q&A).
- Exact text of Romanian error messages, fallback messages, and empty-state copy beyond what's specified in D-* notes.

## Deferred Ideas

Captured in CONTEXT.md `<deferred>` section. Highlights:
- Date-aware inline dashboard links → Phase 9 polish
- Voice input/output (Web Speech API) → Phase 9+
- Chat analytics dashboard → Phase 9+
- Per-user persona setting → Iteration 4 (multi-user)
- Conversation summarization of older messages → Iteration 2 cost optimization
- ML-driven suggested questions → Iteration 2+
- RAG on product catalog → Iteration 3+
- Proactive chat messages → Phase 9+
- Hard delete (vs soft archive) → Iteration 4 GDPR retention
- `cost_usd` column on chat_messages → Phase 9 if budget analysis priority
- Model tier split (Haiku for tools/title, Sonnet for final answer) → evaluate after pilot
- Stop/cancel button mid-stream UI → Phase 9 polish
