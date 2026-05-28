# Phase 5: AI Insights - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-28
**Phase:** 05-ai-insights
**Areas discussed:** Output schema richness, Input data scope, Action item ownership, Zero-anomaly behavior

---

## Output Schema Richness

### Q1: Schema selection

| Option | Description | Selected |
|--------|-------------|----------|
| Rich — SPEC.md schema | positives[], warnings[], weekly_action_plan[], expected_outcome, category, id on problems | ✓ |
| Lean — REQUIREMENTS.md schema | problems[] + summary_ro + generated_at only | |
| Middle ground | Rich schema with positives/warnings as Optional fields | |

**User's choice:** Rich SPEC.md schema
**Notes:** Phase 5 is the product's core value. The SPEC.md schema is what Sofa Belle actually pays for — not just a problem dump, but wins + signals + a flat to-do list for the team.

---

### Q2: Top-3 problems enforcement

| Option | Description | Selected |
|--------|-------------|----------|
| Hard max 3 in Pydantic validator | max_length=3, prioritize by estimated_loss_ron | ✓ |
| Soft guidance (1-5 allowed) | System prompt says "prefer top 3" | |
| You decide | No hard constraint | |

**User's choice:** Hard max 3
**Notes:** Focus is more important than completeness for this daily report.

---

### Q3: weekly_action_plan[] composition

| Option | Description | Selected |
|--------|-------------|----------|
| Claude synthesizes independently | 5-7 flat prioritized action strings | ✓ |
| Derived by code from per-problem actions | InsightService flattens problems[].actions[] | |
| Drop for MVP1 | Remove weekly_action_plan[] | |

**User's choice:** Claude synthesizes it independently
**Notes:** The flat list is the manager-ready summary to copy-paste into a team WhatsApp or daily standup. Claude generating it independently gives it more context and prioritization intelligence.

---

### Q4: problems[].id content

| Option | Description | Selected |
|--------|-------------|----------|
| Source rule_id from detected_problems | e.g. "slow_first_touch" — traceable link to anomaly | ✓ |
| Claude-generated slug | More human-readable but loses traceability | |
| You decide | Planner picks based on Phase 6 API needs | |

**User's choice:** Source rule_id from detected_problems
**Notes:** Enables Phase 6 API and Phase 7 UI to deep-link from insight → anomaly row → affected leads.

---

## Input Data Scope

### Q1: Per-invocation user message content

| Option | Description | Selected |
|--------|-------------|----------|
| Anomalies + KPI summary | detected_problems[] + compact daily_kpi snapshot | ✓ |
| Anomalies only | detected_problems rows only | |
| Full SPEC.md input | tenant + period + metrics + yoy + detected_problems | |

**User's choice:** Anomalies + KPI summary
**Notes:** Claude needs the supporting numbers to write descriptions with real figures, but the full SPEC.md input is overkill for MVP1.

---

### Q2: KPI snapshot time window

| Option | Description | Selected |
|--------|-------------|----------|
| Yesterday only | WoW/MoM delta columns already on daily_kpi | ✓ |
| Last 7 days rolling | 7× more data, trend context | |
| Yesterday + WoW comparison row | Two rows: yesterday + same weekday -7d | |

**User's choice:** Yesterday only
**Notes:** WoW/MoM delta columns baked into daily_kpi already provide comparison context without fetching multiple rows.

---

### Q3: Cached system prompt vs. fresh user message

| Option | Description | Selected |
|--------|-------------|----------|
| System: instructions + Sofa Belle context + schema | Maximizes cache hits, ~500 tokens change daily | ✓ |
| System: instructions only | All tenant data goes in user message | |
| Two-block system prompt with selective caching | Granular invalidation if tenant config changes | |

**User's choice:** System (cached) = instructions + Sofa Belle facts + output schema; User (fresh) = KPI snapshot + detected_problems[]
**Notes:** Maximum caching benefit — only the daily data changes.

---

### Q4: System prompt location in codebase

| Option | Description | Selected |
|--------|-------------|----------|
| Python string constant in prompt_builder.py | Testable, no file I/O, build_system_prompt(tenant_config) | ✓ |
| External .txt / .jinja2 file | Editable without Python changes | |
| DB column on tenants table | Tenant-specific, editable without deploy | |

**User's choice:** Python string constant in prompt_builder.py
**Notes:** Mirrors how AnomalyService handles thresholds. Testable and no runtime file I/O risk.

---

## Action Item Ownership

### Q1: action.owner — real names or generic roles?

| Option | Description | Selected |
|--------|-------------|----------|
| Real names, injected via system prompt | 6 salespeople + Marketing Sofa + generic fallbacks | ✓ |
| Generic roles only | Manager, Echipa de vânzări, Marketing, Vânzător responsabil | |
| Mixed: rule-specific names + generic fallback | Rep-linked rules use names; systemic rules use roles | |

**User's choice:** Real names injected via system prompt
**Notes:** More actionable — the owner reads the report and knows exactly who to talk to.

---

### Q2: action.deadline format

| Option | Description | Selected |
|--------|-------------|----------|
| Relative Romanian labels | 'Azi', 'Mâine', 'Săptămâna aceasta', 'Luna aceasta' | ✓ |
| Specific ISO dates (YYYY-MM-DD) | Precise, requires today's date injection | |
| Both: relative label + ISO date | Nested {label, date} object | |

**User's choice:** Relative Romanian labels
**Notes:** Natural to read in a morning briefing; owner acts the same day.

---

### Q3: Actions per problem count

| Option | Description | Selected |
|--------|-------------|----------|
| 2-3 per problem, system prompt enforces | Focused, 6-9 total actions with max 3 problems | ✓ |
| As many as needed (1-5, Claude decides) | Claude picks the right number | |
| Exactly 2 per problem | Hard Pydantic constraint | |

**User's choice:** 2-3 per problem — system prompt instructs "fiecare problemă are 2-3 acțiuni concrete"
**Notes:** Avoids action fatigue while still being thorough.

---

### Q4: action.expected_outcome content

| Option | Description | Selected |
|--------|-------------|----------|
| Measurable metric + target value | 'Rata de răspuns crește de la 3h la sub 2h' | ✓ |
| Qualitative outcome description | 'Clienții contactați vor fi mai receptivi' | |
| You decide | No constraint on format | |

**User's choice:** Measurable metric + target value
**Notes:** Ties each action to a verifiable number. Matches the product's core value proposition.

---

## Zero-Anomaly Behavior

### Q1: Zero anomalies — still call Claude?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — generate a positive-only report | Uses positives[] + weekly_action_plan | ✓ |
| Skip — don't write to daily_insights | Saves ~$0.05 on a good day | |
| Generate a minimal template-based summary | No Claude call, template-generated | |

**User's choice:** Generate positive-only report
**Notes:** Sofa Belle needs a report every morning. A "perfect day" is worth celebrating with a positives[] report. Consistent UX — no mysterious gaps.

---

### Q2: AI-07 failure fallback structure

| Option | Description | Selected |
|--------|-------------|----------|
| Same DailyInsightResponse, problems[] from detected_problems | status='fallback', no recommended_actions | ✓ |
| Separate fallback schema | Different payload structure for failures | |
| Raw response preserved, no structure | Generic failure message | |

**User's choice:** Same schema, problems[] built from detected_problems directly
**Notes:** Frontend doesn't need to handle two payload shapes. Status column distinguishes AI-generated from fallback.

---

### Q3: Status column state machine

| Option | Description | Selected |
|--------|-------------|----------|
| 'success' | 'failed' | 'fallback' — 3 states | Distinct 'fallback' state for frontend banner | ✓ |
| Boolean is_fallback column | Separate boolean alongside status | |
| Flag in payload_json | is_fallback: bool in DailyInsightResponse | |

**User's choice:** Three-state status column: 'success' | 'failed' | 'fallback'
**Notes:** Clean state machine. Phase 6 API returns status alongside payload; Phase 7 shows banner when status != 'success'.

---

## Claude's Discretion

- `positives[]` count: Claude decides (0-3, no hard constraint)
- `warnings[]` count: Claude decides
- Exact text of the system prompt beyond structural requirements
- Which specific daily_kpi fields to include in the KPI snapshot (~500 token budget)

## Deferred Ideas

- Streaming insights generation → Phase 8 (AI Chat) or future phase
- Multi-tenant prompt personalization → Iteration 4 multi-tenancy phase
- Insight quality feedback loop (thumbs up/down) → Future iteration
- YoY comparison in input data → Deferred (only 12 months of data available in MVP1)
- Parallel per-problem Claude calls → Not needed for 1-3 problems; revisit at scale
