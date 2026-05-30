# Phase 9 — Polish & Deploy: Backlog

Tech-debt and polish items deferred from earlier phases. Each item is a
design change candidate for Phase 9 ("Polish & Deploy" in
[ROADMAP.md](../.planning/ROADMAP.md#phase-9-polish--deploy)) — not a bug fix.
Triage at Phase 9 kickoff.

---

## Design change: structured `weekly_action_plan`

**Status:** Proposed — not committed.
**Cost:** Medium (schema migration + prompt change + UI refactor + 1-2 test
updates).
**Identified during:** Phase 7 insights UI implementation
(2026-05-29) — observed that the rich payload Claude generates per problem
is far more structured than the flat plan items rendered as a separate
section.

### Current design (intentional, not accidental)

- Schema: [`DailyInsightResponse.weekly_action_plan: list[str]`](../backend/app/schemas/insights/daily_insight_schema.py)
  (5-7 plain strings, `min_length=1`).
- Prompt: [`prompt_builder.py:59`](../backend/app/services/insights/prompt_builder.py)
  explicitly tells Claude *"5-7 acțiuni prioritizate, concise, gata de copiat
  în WhatsApp sau standup. Sintetizează independent din toate problemele și
  pozitivele — nu copia mecanic din problems[].actions[]."* — i.e. plain
  strings, by design, for WhatsApp/standup copy-paste.
- Structured ActionItems already exist under
  [`Problem.actions`](../backend/app/schemas/insights/daily_insight_schema.py)
  (`order`, `description`, `owner`, `deadline`, `expected_outcome`) — but
  only inside each problem card, not in the weekly synthesis section.

### Proposed change

Upgrade `weekly_action_plan` from `list[str]` to `list[WeeklyActionItem]`
where each item carries owner / deadline / expected_outcome — so the weekly
plan section renders the same structured information that problem actions
already do.

```python
class WeeklyActionItem(BaseModel):
    action: str
    owner: str                       # Sofa Belle salesperson name or role
    deadline: Literal["Azi", "Mâine", "Săptămâna aceasta"]
    expected_outcome: str            # measurable metric + target
```

### Trade-off (must decide before committing)

| Current (flat strings) | Proposed (structured items) |
|---|---|
| Copy-paste-able into WhatsApp / standup in one swipe | Owner accountability surfaced — manager sees who owns each weekly action |
| Forces Claude to write self-contained one-liners | Same information already in `Problem.actions` — risk of duplication |
| Render: 1 plain `<ol>` | Render: card-list with owner badge + deadline label + outcome footnote (mirror of problem-card.tsx pattern) |
| Lower token output cost | Slightly higher token cost per insight |

The "WhatsApp copy-paste" affordance is the main thing being given up. If
managers actually use the weekly plan that way in production, the design
change is a regression. If they don't (or if owner-attribution is more
valuable than copy-paste), it's an upgrade.

### Validate first

Before implementing, observe how the weekly plan section is actually used
in 2-4 weeks of Phase 7 production data. If nobody copy-pastes it into
WhatsApp and managers complain about not seeing owners, ship the change.
Otherwise drop the item.

### If shipping — change inventory

1. **Schema:** [`backend/app/schemas/insights/daily_insight_schema.py`](../backend/app/schemas/insights/daily_insight_schema.py) — add
   `WeeklyActionItem`, change `DailyInsightResponse.weekly_action_plan` type.
2. **Prompt:** [`backend/app/services/insights/prompt_builder.py:59`](../backend/app/services/insights/prompt_builder.py) — rewrite the
   weekly_action_plan instructions to ask for the structured shape; remove
   the "WhatsApp copy-paste" framing.
3. **Number validator:** [`backend/app/services/insights/number_validator.py`](../backend/app/services/insights/number_validator.py) —
   audit whether any validation currently inspects weekly_action_plan
   strings; update for the new structure.
4. **Frontend type:** [`frontend/src/hooks/useInsights.ts`](../frontend/src/hooks/useInsights.ts) — change
   `InsightPayload.weekly_action_plan` from `string[]` to a structured type
   matching the backend.
5. **Frontend component:** [`frontend/src/components/dashboards/insights/weekly-action-plan.tsx`](../frontend/src/components/dashboards/insights/weekly-action-plan.tsx) —
   refactor from `string[]` → object list; mirror the layout of
   [`problem-card.tsx`](../frontend/src/components/dashboards/insights/problem-card.tsx) (owner badge + deadline label + outcome line).
6. **Tests:** update Phase 5 insight tests that assert on
   `weekly_action_plan[0]` as a string; add a snapshot covering the new
   shape end-to-end.
7. **Existing rows:** historical `daily_insights` rows in production carry
   the old flat-string payload. Either (a) a one-off backfill script
   regenerates them through Claude with the new prompt, or (b) the
   frontend handles both shapes during a transition window. Decide which
   at Phase 9 kickoff.

### Out of scope here

- Adding more ActionItem fields (severity, blockers, etc.) — separate
  discussion.
- Reworking `Problem.actions` — already structured; this item is only
  about the weekly plan.

---

## Period-level rate deltas (WoW/MoM for conversion rates)

**Status:** Proposed — deferred from the Phase 3 contract-counting hotfix (2026-05-30).
**Cost:** Medium (read-service aggregation + test updates).
**Identified during:** Phase 3 hotfix — switching contracts to the event model
([03-HOTFIX-contract-counting-PLAN.md](../.planning/phases/03-metrics-engine/03-HOTFIX-contract-counting-PLAN.md)).

The stored `*_wow_delta` / `*_mom_delta` columns on `daily_kpi` compare a single
day's stored conversion rate to the rate 7/30 days prior. For contract-involving
rates (`o_to_c`, `l_to_c`), the daily-grain rate is now an event-numerator /
cohort-denominator artifact (contracts signed that day ÷ offers among that day's
new leads), so the day-over-day **rate** deltas are noisy and not meaningful.

Count deltas (leads, revenue) are left as-is in the hotfix — they are valid.

**Proposed change:** compute WoW/MoM **rate** deltas at the period level in
`dashboard_read_service` — compare this-period funnel ratio (from summed counts)
against the prior equal-length period's ratio — instead of reading the last-day
stored rate delta. Consider dropping or repurposing the stored daily rate-delta
columns once period-level deltas are the source of truth.

---

## MEFI transition history capture (enable event-based offers + durable timestamps)

**Status:** Proposed — deferred from the Phase 3 contract-counting hotfix (2026-05-30).
**Cost:** Large (ETL change + possibly a new transition-log table; depends on MEFI API capabilities).
**Identified during:** Phase 3 hotfix — see
[03-HOTFIX-contract-counting-PLAN.md §8](../.planning/phases/03-metrics-engine/03-HOTFIX-contract-counting-PLAN.md).

`raw_mefi_leads.status_changed_at` holds only the **last** status change, so it is
reliable for terminal statuses (contracts/won) but is **overwritten** once a lead
progresses past an intermediate stage — losing the offer timestamp. And
`mefi_lead_history.changed_at` is written at **sync-detection time**
([mefi_repository.py:120,131](../backend/app/services/repositories/mefi_repository.py#L120)),
not MEFI's real transition time, so it is unusable for historical "when did it
transition" questions. Consequence: **offers cannot be counted event-based**
("offers sent in period") and stay creation-cohort as a known limitation.

**Proposed change:** capture real per-transition timestamps so any funnel stage
(not just terminal) can be counted by the date it actually occurred. Two avenues:
1. Investigate whether MEFI exposes a status-history / audit endpoint (per
   CLAUDE.md, MEFI currently exposes lead endpoints only — confirm).
2. If not, build our own durable transition log: on each incremental sync, record
   the real `status_changed_at` value (from MEFI) alongside the detected
   transition, instead of `datetime.now(UTC)`. Going-forward only — historical
   transition timestamps are unrecoverable.

Unlocks: event-based offers, event-based intermediate-stage metrics, and accurate
funnel velocity (time-in-stage) analytics.

---

## `estimated_value` NULL for 100% of leads — revenue metrics unverifiable

**Status:** Proposed — investigate in the next 1–2 days (separate track from the contract-counting hotfix).
**Cost:** Unknown until root-caused (could be a MEFI API gap, a sync bug, or a custom-field name mismatch).
**Identified during:** Phase 3 hotfix ground-truth capture (2026-05-30) — see
[03-HOTFIX-GROUND-TRUTH.md](../.planning/phases/03-metrics-engine/03-HOTFIX-GROUND-TRUTH.md).

`raw_mefi_leads.estimated_value` is **NULL for all 1238 leads** (and all 72
contracts). Consequence: `revenue`, `avg_deal_size`, revenue time-series, CAC,
ROAS, and any revenue-based insight/anomaly are unavailable across the whole
product — independent of cohort-vs-event counting.

**Investigate, in order:**
1. Does the MEFI API actually return a deal/estimated value field for leads? (Check
   a raw payload sample in `raw_mefi_leads.raw_payload` / `custom_fields_raw`.)
2. If MEFI sends it under a custom-field key, is our extraction mapping the wrong
   key? (Mefi integration custom-field extraction — `services/integrations/mefi.py`
   + `docs/api-references/mefi/custom-fields.md`.)
3. If MEFI does not expose deal value at all, this is a product/data limitation to
   surface to the client (manual entry? a different field?).

Until resolved, revenue-dependent UI should show "N/A" honestly rather than 0.
