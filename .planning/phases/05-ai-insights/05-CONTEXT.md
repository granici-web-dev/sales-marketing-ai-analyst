# Phase 5: AI Insights - Context

**Gathered:** 2026-05-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Fourth and final link in the PIPE-01 daily pipeline chain. After `detect_anomalies` writes `detected_problems` rows, `generate_daily_insights` calls Claude Sonnet 4.5, transforms those anomalies into a structured Romanian business report, and writes one row to `daily_insights` per day per tenant.

**This phase delivers:**
- `backend/alembic/versions/008_daily_insights.py` — Alembic migration for `daily_insights` table
- `backend/app/models/insights/daily_insight.py` — DailyInsight ORM model
- `backend/app/schemas/insights/daily_insight_schema.py` — `DailyInsightResponse` Pydantic schema (rich SPEC.md version)
- `backend/app/services/insights/prompt_builder.py` — system prompt + user message construction
- `backend/app/services/insights/insight_service.py` — Claude API calls, retry logic, number cross-check validation
- `backend/app/services/repositories/insight_repository.py` — upsert to `daily_insights`
- `backend/app/tasks/etl/generate_daily_insights.py` — Celery task (4th chain link)
- `celery_app.py` update: add task to include list + new beat entry at 06:00 Europe/Bucharest
- `pyproject.toml` update: add `anthropic>=0.30` to dependencies

**Does NOT include:** Phase 6 API endpoints to expose insights, Phase 7 frontend rendering, AI Chat (Phase 8). Number validation is server-side only — no client-side validation.

</domain>

<decisions>
## Implementation Decisions

### Output Schema (DailyInsightResponse)

- **D-01:** Use the **rich SPEC.md schema** (Section 10), not the leaner REQUIREMENTS.md schema. `DailyInsightResponse` includes: `summary` (Romanian overview paragraph), `problems[]` (max 3), `positives[]` (what's working), `warnings[]` (weak signals), `weekly_action_plan[]` (flat prioritized list). This is the complete report Sofa Belle sees every morning.

- **D-02:** `problems[]` has **hard max 3** enforced via `max_length=3` in Pydantic. When more than 3 anomaly rules fire, InsightService selects the top 3 by `estimated_loss_ron` descending before constructing the user message. The system prompt also instructs Claude: `"Maximum 3 probleme de prioritate înaltă"`.

- **D-03:** `weekly_action_plan[]` — **Claude synthesizes it independently** as 5-7 flat prioritized action strings at the top level. It is NOT derived by code from `problems[].actions[]`. System prompt instructs: `"weekly_action_plan: 5-7 acțiuni prioritizate, concise, gata de copiat în WhatsApp sau standup"`.

- **D-04:** `problems[].id` = **source `rule_id` from `detected_problems`** (e.g., `"slow_first_touch"`, `"stuck_offer"`). Creates a traceable link from insight → anomaly row → underlying data. Phase 6 API and Phase 7 UI can use it to deep-link to the affected leads.

- **D-05:** Full `DailyInsightResponse` Pydantic schema fields (mirrors SPEC.md Section 10):
  ```python
  class ActionItem(BaseModel):
      order: int
      description: str
      owner: str           # salesperson name or role
      deadline: str        # relative Romanian label
      expected_outcome: str  # measurable metric + target

  class Problem(BaseModel):
      id: str              # rule_id from detected_problems
      severity: Literal["high", "medium", "low"]
      category: Literal["marketing", "sales", "team", "funnel"]
      title: str
      description: str     # 2-3 sentences with figures from input data
      estimated_loss_ron: Decimal
      actions: list[ActionItem]  # 2-3 items

  class Positive(BaseModel):
      title: str
      description: str
      recommendation: str

  class Warning(BaseModel):
      title: str
      description: str

  class DailyInsightResponse(BaseModel):
      summary: str                       # one overview paragraph
      problems: list[Problem] = Field(max_length=3)
      positives: list[Positive]
      warnings: list[Warning]
      weekly_action_plan: list[str]      # 5-7 flat action strings
      generated_at: datetime
  ```

### Input Data to Claude

- **D-06:** Per-invocation **user message** (fresh each day, NOT cached): compact daily_kpi snapshot from yesterday (leads_total, visits_count, offers_count, contracts_closed, l_to_v_pct, v_to_o_pct, o_to_c_pct, l_to_c_pct, wow_delta_pct for each, avg_deal_size) + `detected_problems[]` for that day (rule_id, severity, estimated_loss_ron, current_value, expected_value, context_json). Time window: **yesterday only** — the WoW/MoM delta columns already on `daily_kpi` provide comparison context.

- **D-07:** **System prompt** (cached with `cache_control`): consultant role instructions in Romanian + Sofa Belle tenant facts (industry, deal size, funnel stages, business hours, the roster — see D-09) + output JSON schema (the `DailyInsightResponse` structure). All content that does NOT change day-to-day. This maximizes cache hits — only ~500 tokens change per invocation.

- **D-08:** System prompt lives as a **Python string constant** in `app/services/insights/prompt_builder.py`. Built by a `build_system_prompt(tenant_config)` function. No file I/O, no DB query per call. Testable. Mirrors how `AnomalyService` holds its thresholds as module-level constants.

- **D-model:** Model is **`claude-sonnet-4-5`** per CLAUDE.md and STATE.md locked decision. REQUIREMENTS.md AI-01 says "Claude Sonnet 4.6" — this appears to be a typo; SPEC.md, CLAUDE.md, and STATE.md all specify `claude-sonnet-4-5`. Using `client.messages.parse()` with `output_format=DailyInsightResponse` (AI-02). Temperature: `0.2` (AI-05).

### Action Item Format

- **D-09:** `action.owner` = **real Sofa Belle salesperson names**, injected in the system prompt roster. The roster to include in system prompt:
  - Active salespeople: Roibu Valeria, Raileanu Leon, Godja Adina Maria, Dragoi Mihaela, Zagrian Emilia, Moaca Andreea
  - For marketing-category actions: Marketing Sofa
  - For systemic issues (no specific rep): Manager, Echipa de vânzări
  Claude assigns specific names for rep-linked rules (`underperforming_salesperson`, `slow_first_touch`) and generic roles for systemic rules (`showroom_traffic_drop`, `junk_lead_quality`).

- **D-10:** `action.deadline` = **relative Romanian labels** — not ISO dates. Allowed values: `"Azi"`, `"Mâine"`, `"Săptămâna aceasta"`, `"Luna aceasta"`. System prompt instructs Claude to use these labels. Natural to read in a morning briefing context. Frontend (Phase 7) renders as-is.

- **D-11:** **2-3 actions per problem** — system prompt instructs: `"fiecare problemă are 2-3 acțiuni concrete, nu mai mult"`. With max 3 problems, the report has 6-9 total actions + weekly_action_plan. No hard Pydantic constraint on action count (system prompt enforcement is sufficient).

- **D-12:** `action.expected_outcome` = **measurable metric + target value**. System prompt instructs: `"expected_outcome trebuie să numească o metrică și o valoare țintă concretă (ex: 'Rata de răspuns scade de la 3h la sub 2h')"`. Not qualitative descriptions.

### Zero-Anomaly and Failure Behavior

- **D-13:** When no anomaly rules fire (0 detected_problems rows): **generate_daily_insights still runs**. Claude receives a KPI snapshot and empty detected_problems[], and generates a positive-only report using `positives[]` and `weekly_action_plan[]`. The report confirms what's working and suggests maintenance actions. Sofa Belle gets a report every morning without gaps.

- **D-14:** `daily_insights.status` state machine: **`'success' | 'failed' | 'fallback'`**
  - `'success'` — Claude generated valid DailyInsightResponse
  - `'fallback'` — Claude failed all retries; InsightService constructed DailyInsightResponse directly from `detected_problems` (problems[] filled from anomaly rows, no `recommended_actions[]`, `summary` = "Generare AI eșuată — raport bazat pe anomalii detectate automat")
  - `'failed'` — all retries exhausted AND fallback construction itself failed (very rare)

- **D-15:** Failure fallback uses the **same DailyInsightResponse schema**. InsightService builds it from detected_problems rows: each anomaly becomes a `Problem` with `id=rule_id`, `title` from rule name, `description` from context_json summary, no `actions[]`. Phase 7 frontend reads `status != 'success'` and shows a `"Generare AI eșuată"` banner. No second schema needed.

### daily_insights Table Schema

- **D-16:** `daily_insights` table columns (new Alembic migration 008):
  - `id uuid PRIMARY KEY DEFAULT gen_random_uuid()`
  - `tenant_id uuid NOT NULL REFERENCES tenants(id)`
  - `date date NOT NULL`
  - `status text NOT NULL CHECK (status IN ('running', 'success', 'failed', 'fallback'))`
  - `payload_json jsonb` (serialized DailyInsightResponse)
  - `generated_at timestamptz`
  - `input_tokens integer`
  - `output_tokens integer`
  - `cost_usd NUMERIC(10, 6)` (AI-08)
  - `raw_response text` (last Claude response — preserved on 'failed', helps debugging)
  - `created_at timestamptz NOT NULL DEFAULT now()`
  - `updated_at timestamptz NOT NULL DEFAULT now()`
  - `UNIQUE (tenant_id, date)` — one row per tenant per day; upsert on conflict

### Locked Decisions (from Prior Phases)

- **D-17 (from Phase 4 D-15):** Chain position locked: `sync_mefi_leads → calculate_daily_kpis → detect_anomalies → generate_daily_insights`. The detect_anomalies task currently says "Phase 5: generate_daily_insights" in its docstring — this is where the chain extends.

- **D-18:** NullPool + deferred imports pattern (INFRA-05) — `generate_daily_insights.py` MUST follow the same pattern as `detect_anomalies.py`: `asyncio.run(_generate_async(...))`, all model/service imports inside the async function body.

- **D-19:** All monetary values as `Decimal` — never float. `DailyInsightResponse.problems[].estimated_loss_ron` is `Decimal`. JSON serialization via Pydantic's `model_dump(mode='json')`.

- **D-20:** **New beat entry at 06:00 Europe/Bucharest** — separate `RedBeatSchedulerEntry` in `celery_app.py`. Does NOT modify the existing 04:00 sync entry. Name: `"daily-insights-generation"`. Args: `[settings.sofa_belle_tenant_id]`.

### Dependency

- **D-21:** `anthropic` SDK is **NOT yet in `pyproject.toml`** — must be added in Phase 5. Add: `"anthropic>=0.30,<1"`. Use `anthropic.AsyncAnthropic` client inside the async task function (deferred import per D-18).

### Claude's Discretion

- `positives[]` count: Claude decides how many positives to surface (0-3). No hard constraint.
- `warnings[]` count: Claude decides. These are weak signals, not full problems.
- Exact text of the system prompt beyond the structural requirements above.
- Which daily_kpi fields to include in the compact KPI snapshot JSON (Claude's planner chooses the most informative subset within ~500 token budget).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Requirements and Schema
- `SPEC.md` § 10 (AI Insights) — System prompt draft in Romanian, full input/output schema, cost model, generation frequency. **Critical: start with SPEC.md system prompt text for prompt_builder.py.**
- `.planning/REQUIREMENTS.md` — AI-01 through AI-09 (lines 68–76)
- `docs/SOFABELLE.md` § "Specifics for AI Insights" — Domain context: long sales cycle, high-ticket, visit-driven funnel, sensitive metrics (time to first touch, stuck offers), tone guidelines (Romanian, business, no fluff), domain glossary

### Salesperson Roster
- `docs/api-references/mefi/enums.md` § "Salesperson IDs" — Active salesperson names (Roibu Valeria, Raileanu Leon, Godja Adina Maria, Dragoi Mihaela, Zagrian Emilia, Moaca Andreea) and their MEFI IDs. These names go into the system prompt (D-09). Also contains showroom and lifecycle value definitions.

### Existing Code Patterns to Follow
- `backend/app/tasks/etl/detect_anomalies.py` — **Primary pattern** for `generate_daily_insights.py`: NullPool, asyncio.run, deferred imports, autoretry, SyncRun audit trail, chain position comment
- `backend/app/tasks/celery_app.py` — Pipeline chain and beat schedule registration pattern (RedBeatSchedulerEntry, include list)
- `backend/app/services/anomaly/anomaly_service.py` — Service class structure to mirror for InsightService
- `backend/app/services/repositories/anomaly_repository.py` (if exists) — Repository UPSERT pattern for InsightRepository

### Phase 4 Context (Carry-Forward)
- `.planning/phases/04-anomaly-detection/04-CONTEXT.md` — D-15 (chain position locked), D-09/D-10 (service/repository structure), D-19 (Decimal not float), DetectedProblem model reference

### Input Models
- `backend/app/models/anomaly/detected_problem.py` — DetectedProblem ORM model (the input to Phase 5). Fields: rule_id, severity, estimated_loss_ron, current_value, expected_value, context_json

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/tasks/etl/detect_anomalies.py` — Copy as scaffold for `generate_daily_insights.py`. The task structure (decorator, asyncio.run, _generate_async, NullPool, SyncRun write, finally:dispose) is identical in shape.
- `backend/app/services/anomaly/anomaly_service.py` — InsightService follows the same class structure: constructor takes `AsyncSession`, methods are async, accepts pre-fetched data as optional kwargs for testability.
- Phase 3 MetricsRepository → Phase 4 AnomalyRepository → Phase 5 InsightRepository: same UPSERT pattern using `insert().on_conflict_do_update()`.

### Established Patterns
- **NullPool + deferred imports** (INFRA-05): Mandatory for all Celery tasks with async DB access. `asyncio.run()` creates a fresh event loop per invocation; NullPool prevents cross-loop connection reuse.
- **`autoretry_for=(Exception,), max_retries=3`**: Standard Celery task retry pattern. Claude-specific retries (up to 2 regenerations for number validation — AI-06) happen INSIDE `_generate_async()` before the Celery retry fires.
- **SyncRun audit trail** (PIPE-04): Every task writes `SyncRun(source="insights", status="running")` at start and updates to "success"/"failed" at end.
- **`UUID(tenant_id)` at task entry**: Security gate — validates string before any DB operation.

### Integration Points
- **Chain extension**: `detect_anomalies.py` has comment "Phase 5: generate_daily_insights" — that's where `generate_daily_insights.si(tenant_id)` is appended to `daily_pipeline()`.
- **celery_app.py include list**: Add `"app.tasks.etl.generate_daily_insights"` alongside the other task modules.
- **Beat schedule**: New `RedBeatSchedulerEntry` at 06:00 Europe/Bucharest — separate from the existing 04:00 sync entry.
- **anthropic SDK**: `from anthropic import AsyncAnthropic` (deferred import inside `_generate_async`). Client instantiated with `api_key=settings.anthropic_api_key`. Add `ANTHROPIC_API_KEY` to Settings and `.env.example`.

</code_context>

<specifics>
## Specific Ideas

- SPEC.md Section 10 contains a Romanian system prompt draft — use it verbatim as the starting text for `prompt_builder.py`, then extend with salesperson roster and output schema instructions (D-08).
- The SPEC.md system prompt ends with `"Format de răspuns: JSON conform schemei specificate."` — keep this and append the full DailyInsightResponse JSON schema as part of the system prompt so Claude always has the structure in the cached block.
- Number cross-check (AI-06): extract all `\d+[\.,]\d+` and standalone integers from `problems[].description` and `summary`; compare against `estimated_loss_ron` values and KPI snapshot values within ±2%. If mismatch: regenerate (up to 2 times). On 3rd failure: trigger fallback (D-14).
- `daily_insights.cost_usd` calculation: `(input_tokens / 1_000_000) * 3.0 + (output_tokens / 1_000_000) * 15.0` — Claude Sonnet 4.5 pricing from SPEC.md Section 10.
- Beat entry name: `"daily-insights-generation"` at `crontab(hour=6, minute=0)` — distinct from `"daily-mefi-sync"` at 04:00.
- `raw_response` column: store the last raw Anthropic API response text on `status='failed'` to assist debugging without re-calling the API.
- `DailyInsightResponse.generated_at` should be set to `datetime.now(UTC)` by InsightService, not by Claude (avoids timezone issues in Claude's output).

### Real Sofa Belle Data Patterns (from Phase 3 backfill — verified 2026-05-28)

These ground truth patterns MUST inform the system prompt and insight logic:

- **`estimated_value` is NULL for all 1219 leads** — Sofa Belle has not filled deal values in MEFI. Revenue-based insights (`estimated_loss_ron` from anomalies, `avg_deal_size`) use the fallback constant CLOSE_RATE_FALLBACK=0.15 and a heuristic avg_deal_size. Insight text MUST NOT present revenue figures as precise — phrase as "estimat" or avoid until Sofa Belle populates values.
- **Showroom is the dominant channel**: 360 of 1219 leads (29.5%), but delivers 55% of contracts (39/71) at ~10.8% conversion — the single most important channel to protect. System prompt should acknowledge "Showroom este canalul principal de conversie".
- **Mail is high-volume, low-quality**: 335 leads (27.5%), only 11 contracts (3.3% conversion). Insight engine should flag mail quality as a structural issue when it fires `junk_lead_quality`.
- **Salesperson imbalance**: Dragoi Mihaela has the most leads (351, ~29%) but only 10 contracts (2.8% conversion). Raileanu Leon has 265 leads and 22 contracts (8.3% conversion — the best). System prompt roster should note this asymmetry so Claude generates concrete, non-generic actions for underperforming salesperson rules.
- **Model string**: `claude-sonnet-4-5` (NOT `claude-sonnet-4-6` or any newer string — per CLAUDE.md locked decision). Verify this in `pyproject.toml` when `anthropic` SDK is added.

</specifics>

<deferred>
## Deferred Ideas

- **Streaming insights generation**: Real-time streaming of the report as it's generated — belongs in Phase 8 (AI Chat has streaming) or a future phase. Phase 5 is batch-only.
- **Multi-tenant prompt personalization**: Different system prompts per tenant based on their industry/size. MVP1 has one tenant; defer to Iteration 4 multi-tenancy phase.
- **Insight quality feedback loop**: Allow Sofa Belle owner to rate insights (thumbs up/down) to improve prompts over time. Future iteration.
- **YoY comparison in input data**: SPEC.md shows a `yoy` section in the input. Not included in D-06 for MVP1 — only 12 months of data available, no meaningful year-over-year yet.
- **Parallel problem insights**: Run Claude separately per problem in parallel. Not needed for 1-3 problems; consider if scaling to many rules.

</deferred>

---

*Phase: 05-ai-insights*
*Context gathered: 2026-05-28*
