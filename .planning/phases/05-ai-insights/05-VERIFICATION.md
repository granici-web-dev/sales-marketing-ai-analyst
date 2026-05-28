---
phase: 05-ai-insights
verified: 2026-05-28T16:45:00Z
status: human_needed
score: 5/7 roadmap success criteria verifiable automatically
overrides_applied: 0
overrides:
  - must_have: "payload_json validates against DailyInsightResponse schema with summary_ro and recommended_actions fields; invalid structures rejected by messages.parse()"
    reason: "ROADMAP SC#2 field names (summary_ro, recommended_actions) are shorthand from an earlier REQUIREMENTS.md draft. SPEC.md Section 10 (the canonical schema source) uses 'summary', 'actions', 'positives', 'warnings', 'weekly_action_plan'. CONTEXT.md D-01 explicitly overrides AI-03/REQUIREMENTS: 'Use the rich SPEC.md schema, not the leaner REQUIREMENTS.md schema.' The implementation uses tool-use forced JSON (not messages.parse), which AI-SPEC §2 line 536 confirms is the production-grade approach: 'The SDK does not have a messages.parse(output_format=...) method — the REQUIREMENTS.md reference is aspirational shorthand.' All 36 unit tests GREEN."
    accepted_by: "gsd-verifier automated analysis"
    accepted_at: "2026-05-28T16:45:00Z"
human_verification:
  - test: "Trigger generate_daily_insights task with a live ANTHROPIC_API_KEY and verify daily_insights row"
    expected: "Row written with status='success' (or 'fallback'), payload_json validated by DailyInsightResponse.model_validate(), input_tokens > 0, output_tokens > 0, cost_usd > 0"
    why_human: "Requires a live Anthropic API key and running PostgreSQL. Cannot test Claude API round-trips without real credentials."
  - test: "Inspect payload_json.summary and payload_json.problems[*].description in a live-generated row"
    expected: "Text is in Romanian; contains 'RON' and at least one of vânzări|comenzi|oferte|clienți|magazin in summary or descriptions"
    why_human: "Romanian language content verification requires live Claude call. The system prompt is in Romanian and instructs Romanian output, but the actual Claude response cannot be checked without running the pipeline."
  - test: "Run generate_daily_insights twice with the same date and same system prompt; inspect usage on the second call"
    expected: "Second call shows cache_read_input_tokens > 0 in response.usage (prompt caching active per D-07)"
    why_human: "Prompt caching verification requires two live Claude API calls to confirm the cache_read_input_tokens counter increments."
  - test: "Verify that with daily_insights.status='fallback', a future Phase 6 API endpoint returns the algorithmic anomaly list with a failure notice flag"
    expected: "GET /api/v1/insights/today returns DailyInsightResponse from fallback path with a failure_notice: true flag or equivalent"
    why_human: "Phase 6 HTTP API does not exist yet (not started). SC#7 requires Phase 6 + Phase 7 to be verifiable. The backend data layer (daily_insights table + fallback status field) is confirmed present; the API query layer is Phase 6 scope."
---

# Phase 5: AI Insights Verification Report

**Phase Goal:** Generate daily AI insights via Claude Sonnet 4.5 from anomaly data — InsightService, prompt builder, Celery task wired into PIPE-01 daily pipeline chain.
**Verified:** 2026-05-28T16:45:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

All backend components are fully implemented and substantive. 36/36 unit tests pass. The Celery task is wired as the 4th link in PIPE-01. Four items require human testing with live credentials: (1) actual Claude API round-trip, (2) Romanian language content verification, (3) prompt caching active confirmation, and (4) SC#7 which depends on Phase 6 API (not yet built).

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | generate_daily_insights Celery task reads detected_problems and writes daily_insights at 06:00 | VERIFIED | Task registered: name="tasks.etl.generate_daily_insights"; beat entry "daily-insights-generation" at crontab(hour=6, minute=0) in celery_app.py; full _generate_async() reads DetectedProblem, writes DailyInsight |
| 2 | payload_json validates against DailyInsightResponse Pydantic schema; invalid structures rejected before DB write | VERIFIED (override) | DailyInsightResponse uses SPEC.md schema (not REQUIREMENTS.md shorthand); model_validate() called before upsert; 4-problem payload raises ValidationError confirmed in test + live check; see override note |
| 3 | Insight text is in Romanian; system prompt enforces Romanian with Sofa Belle domain context | ? HUMAN | System prompt is fully in Romanian with Sofa Belle roster, funnel context, deadline labels; actual Claude output cannot be verified without live API call |
| 4 | Number cross-check validates narrative numbers ±2% against input; retries up to 2 times on mismatch | VERIFIED | cross_check() confirmed: 47320 vs 5000 → False; 5050 vs 5000 → True; InsightService retry loop 0,1,2 implemented; all 7 number_validator tests GREEN |
| 5 | input_tokens, output_tokens, cost_usd logged; prompt caching active on second call | PARTIAL | cost computation verified (_compute_cost(3000in,2000out)=Decimal("0.039")); token fields wired in result_dict and final_row; cache_control={"type":"ephemeral"} on last system block confirmed; cache_read_input_tokens tracking requires live API call |
| 6 | Claude API called ONLY from Celery tasks, never HTTP handlers | VERIFIED | grep app/api/ for AsyncAnthropic/client.messages returns zero matches; test_no_claude_calls_in_http_handlers PASSED |
| 7 | With status='failed'/'fallback', Insights page returns algorithmic anomaly list with failure notice | ? HUMAN | daily_insights table has status column with 'fallback' and 'failed' values; InsightService._build_fallback() constructs DailyInsightResponse from detected_problems; Phase 6 API endpoint does not exist yet — SC#7 UI behavior is Phase 6/7 scope |

**Score:** 5/7 truths verifiable automatically; 2 require human testing

### Deferred Items

Items not yet met but explicitly addressed in later milestone phases.

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | Insights page query returns algorithmic fallback with failure notice when status='failed' (SC#7) | Phase 6 | ROADMAP Phase 6 SC#4: "GET /api/v1/insights/today returns DailyInsightResponse payload from daily_insights"; ROADMAP Phase 7 SC#4: "a 'Generation failed' notice + algorithmic anomaly fallback when applicable" |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/schemas/insights/daily_insight_schema.py` | DailyInsightResponse Pydantic schema | VERIFIED | ActionItem, Problem, Positive, Warning, DailyInsightResponse exported; max_length=3 on problems; Decimal for estimated_loss_ron; validated in 8 unit tests |
| `backend/app/services/insights/prompt_builder.py` | build_system_prompt() + build_user_message() | VERIFIED | 2-block list with cache_control={"type":"ephemeral"} on last block; Dragoi Mihaela, Raileanu Leon in text; top-3 by estimated_loss_ron; PII-stripped context_json |
| `backend/app/services/insights/number_validator.py` | extract_numbers_from_text() + cross_check() | VERIFIED | Romanian format (23.400→23400, 8,3→8.3, 5050→5050); ±2% tolerance; 7 unit tests GREEN |
| `backend/app/services/insights/insight_service.py` | InsightService with run(), _build_fallback(), _compute_cost() | VERIFIED | MODEL="claude-sonnet-4-5" locked; _MAX_CLAUDE_RETRIES=2; tool-use forced JSON; fallback constructs DailyInsightResponse; 7 unit tests GREEN |
| `backend/app/services/repositories/insight_repository.py` | InsightRepository with upsert_daily_insight() | VERIFIED | ON CONFLICT (tenant_id, date) DO UPDATE; tenant_id validation raises ValueError; no commit (WR-04); 4 unit tests GREEN |
| `backend/app/models/insights/daily_insight.py` | DailyInsight ORM model | VERIFIED | All 12 columns (8 domain + 4 from mixin); UniqueConstraint(tenant_id, date); cost_usd Numeric(10,6); raw_response Text |
| `backend/alembic/versions/008_daily_insights.py` | DDL for daily_insights table | VERIFIED | revision="008", down_revision="007"; all 12 columns; UniqueConstraint uq_daily_insights_tenant_date; ix_daily_insights_tenant_date index |
| `backend/app/tasks/etl/generate_daily_insights.py` | 4th PIPE-01 Celery task | VERIFIED | name="tasks.etl.generate_daily_insights"; NullPool + asyncio.run(_generate_async); InsightService + InsightRepository wired; WR-06 stale SyncRun cleanup; D-14 state machine |
| `backend/app/tasks/celery_app.py` | Updated include list + beat entry | VERIFIED | "app.tasks.etl.generate_daily_insights" in include list; RedBeatSchedulerEntry "daily-insights-generation" at crontab(hour=6, minute=0) |
| `backend/app/core/config.py` | anthropic_api_key field | VERIFIED | anthropic_api_key: str = "" present (optional default for tests, required for production) |
| `backend/pyproject.toml` | anthropic>=0.30,<1 dependency | VERIFIED | "anthropic>=0.30,<1" in [project] dependencies |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| sync_mefi_leads.daily_pipeline() | generate_daily_insights | generate_daily_insights.si(tenant_id) in chain() | WIRED | Line 332 of sync_mefi_leads.py: `generate_daily_insights.si(tenant_id)` as 4th chain element |
| generate_daily_insights.py | InsightService | deferred import inside _generate_async() | WIRED | Line 93: `from app.services.insights.insight_service import InsightService` inside function body |
| generate_daily_insights.py | InsightRepository | deferred import inside _generate_async() | WIRED | Line 94: `from app.services.repositories.insight_repository import InsightRepository` inside function body |
| InsightService.run() | DailyInsightResponse | deferred import inside method body | WIRED | Line 72: `from app.schemas.insights.daily_insight_schema import DailyInsightResponse` |
| InsightService.run() | number_validator.cross_check | via _numbers_match() | WIRED | Line 210: `from app.services.insights.number_validator import cross_check` |
| InsightRepository.upsert_daily_insight() | DailyInsight ORM | deferred import | WIRED | Line 69: `from app.models.insights.daily_insight import DailyInsight` |
| celery_app.py include list | generate_daily_insights module | "app.tasks.etl.generate_daily_insights" | WIRED | Confirmed in include list; task loads correctly |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| InsightService.run() | problems_rows | _fetch_detected_problems() → DetectedProblem SELECT WHERE tenant_id+date ORDER BY estimated_loss_ron DESC LIMIT 3 | Yes — real ORM query | FLOWING |
| InsightService.run() | kpi_row | _fetch_kpi_snapshot() → DailyKpi SELECT WHERE tenant_id+date | Yes — real ORM query | FLOWING |
| generate_daily_insights._generate_async() | result_dict | InsightService.run() → Claude API | Real API call (requires live key) | FLOWING |
| InsightRepository.upsert_daily_insight() | final_row | assembled from result_dict in task | Real data from result_dict | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| DailyInsightResponse rejects 4-problem payload | `DailyInsightResponse.model_validate({...4 problems...})` | ValidationError raised | PASS |
| build_system_prompt() last block has cache_control | `blocks[-1]['cache_control']` | `{'type': 'ephemeral'}` | PASS |
| Sofa Belle roster in system prompt | Grep for "Dragoi Mihaela", "Raileanu Leon" | Both found | PASS |
| extract_numbers_from_text("23.400 RON") | Python direct | 23400.0 in results | PASS |
| extract_numbers_from_text("8,3% conversie") | Python direct | 8.3 in results | PASS |
| cross_check(47320 vs ref=5000) | Python direct | False (correct — mismatch) | PASS |
| cross_check(5050 vs ref=5000) | Python direct | True (correct — within ±2%) | PASS |
| InsightService._compute_cost(3000in, 2000out) | Python direct | Decimal("0.039") | PASS |
| InsightRepository raises ValueError on missing tenant_id | Python direct | ValueError raised | PASS |
| InsightRepository raises ValueError on cross-tenant write | Python direct | ValueError raised | PASS |
| generate_daily_insights task name | `generate_daily_insights.name` | "tasks.etl.generate_daily_insights" | PASS |
| AI-09: no Anthropic calls in app/api/ | `grep -rn "AsyncAnthropic\|client.messages" app/api/` | 0 matches | PASS |
| test_no_claude_calls_in_http_handlers | pytest -k test_no_claude... | PASSED | PASS |
| 36 unit tests | pytest tests/unit/test_daily_insight_schema.py tests/unit/test_prompt_builder.py tests/unit/test_insight_service.py tests/unit/test_number_validator.py tests/unit/test_insight_repository.py | 36 passed in 0.22s | PASS |

### Probe Execution

No probe scripts defined for Phase 5 (batch service with Celery — not a standalone CLI with testable probe scripts).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| AI-01 | 05-01, 05-04 | Celery task at 06:00 Europe/Bucharest reads detected_problems, generates insights | SATISFIED | Task registered; beat entry at crontab(hour=6); InsightService._fetch_detected_problems() reads detected_problems |
| AI-02 | 05-01, 05-03 | Structured JSON output via Pydantic schema (implementation: tool-use + model_validate) | SATISFIED (override) | Tool-use forced JSON is the production-grade implementation; messages.parse() is aspirational shorthand per AI-SPEC §2 line 536; all schema tests GREEN |
| AI-03 | 05-01, 05-03 | DailyInsightResponse schema with problems, summary, recommended_actions | SATISFIED (override) | CONTEXT.md D-01 explicitly selects SPEC.md schema (summary, actions) over REQUIREMENTS.md shorthand (summary_ro, recommended_actions); validated by 8 schema tests |
| AI-04 | 05-01, 05-03 | System prompt includes Sofa Belle domain context: industry, deal size, cycle, 4h response target, Romanian tone | SATISFIED | SYSTEM_PROMPT_TEXT contains: deal size >20.000 RON, cycle 2 săptămâni–2 luni, funnel stages, business hours context, Romanian professional tone |
| AI-05 | 05-01, 05-03 | temperature=0.2; system prompt uses prompt caching (cache_control) | SATISFIED | TEMPERATURE=0.2 confirmed in insight_service.py; build_system_prompt() returns 2-block list with cache_control={"type":"ephemeral"} on last block |
| AI-06 | 05-01, 05-03 | Post-generation number validation with regex, ±2% tolerance, up to 2 retries on mismatch | SATISFIED | NUMBER_PATTERN + extract_numbers_from_text() + cross_check() + _MAX_CLAUDE_RETRIES=2 in retry loop; 7 number_validator tests GREEN |
| AI-07 | 05-01, 05-03 | On 3 failed generations: save raw response, set status='fallback', surface algorithmic fallback | SATISFIED | status='fallback' returned after exhausting retries; raw_response preserved; _build_fallback() constructs DailyInsightResponse from detected_problems |
| AI-08 | 05-01, 05-03, 05-04 | Log input_tokens, output_tokens, cost_usd per call | SATISFIED | last_usage tracked in retry loop; result_dict contains input_tokens, output_tokens, cost_usd; final_row upserts all three; _compute_cost() formula verified |
| AI-09 | 05-01, 05-03, 05-04 | Claude API called ONLY from Celery tasks — never HTTP handlers | SATISFIED | grep app/api/ returns 0 matches; test_no_claude_calls_in_http_handlers PASSED |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| insight_service.py | 28 | `from anthropic import AsyncAnthropic` at module level | Info | AI-SPEC Pitfall 1 warns against module-level INSTANTIATION (not import). The class is imported at module level for test patchability, instantiated only inside run() body. Since InsightService itself is imported deferred inside _generate_async(), this module-level import is not loaded at Celery worker fork time. The SUMMARY explicitly documents this reconciliation. Not a blocker. |

No TBD, FIXME, XXX, TODO, HACK, or PLACEHOLDER markers found in any Phase 5 production files.

### Human Verification Required

#### 1. Live Claude API Round-Trip

**Test:** Set `ANTHROPIC_API_KEY` in .env, run `docker compose up -d`, then call `generate_daily_insights.apply(args=[settings.sofa_belle_tenant_id])` or trigger via Celery CLI. Query `SELECT status, payload_json, input_tokens, output_tokens, cost_usd FROM daily_insights WHERE tenant_id = '00000000-0000-0000-0000-000000000001' ORDER BY created_at DESC LIMIT 1`.
**Expected:** Row exists with `status IN ('success', 'fallback')`, `payload_json IS NOT NULL`, `input_tokens > 0`, `output_tokens > 0`, `cost_usd > 0`.
**Why human:** Requires a live Anthropic API key and running PostgreSQL + Celery worker.

#### 2. Romanian Language Content Verification (SC#3)

**Test:** Inspect `payload_json->>'summary'` and `payload_json->'problems'->0->>'description'` from a live-generated row.
**Expected:** Text is in Romanian; contains "RON" and at least one of: vânzări, comenzi, oferte, clienți, magazin.
**Why human:** Romanian language sniff requires live Claude API call to produce actual content. The system prompt enforces Romanian output and includes Sofa Belle domain vocabulary, but the actual response cannot be examined without running the pipeline.

#### 3. Prompt Caching Active (SC#5 partial)

**Test:** Run `generate_daily_insights` task twice for the same date. Inspect `raw_response` or add logging to capture `response.usage.cache_read_input_tokens` on the second call.
**Expected:** Second call shows `cache_read_input_tokens > 0` (Anthropic prompt caching active for the stable system blocks).
**Why human:** Requires two live Anthropic API calls with the same system prompt to verify the cache_read_input_tokens counter increments. Cache behavior depends on Anthropic's server-side caching state.

#### 4. Phase 6 UI Fallback (ROADMAP SC#7)

**Test:** After Phase 6 Backend HTTP API is built — `GET /api/v1/insights/today` when `daily_insights.status='fallback'`.
**Expected:** Response contains the algorithmic anomaly list constructed by `_build_fallback()`, plus a failure_notice flag set to true.
**Why human:** Phase 6 HTTP API does not exist yet. The data layer (daily_insights.status column, _build_fallback() producing DailyInsightResponse from detected_problems) is fully implemented and verified. The API query layer and response schema are Phase 6 scope.

### Gaps Summary

No blocking gaps. All Phase 5 backend code is fully implemented, substantive, and wired. The four human verification items are:
- Items 1-3: require a live Anthropic API key to execute (normal for a paid AI service integration)
- Item 4: deferred to Phase 6 which does not exist yet

The `ROADMAP SC#2` schema field naming deviation (`summary_ro` → `summary`, `recommended_actions` → `actions`) and `messages.parse()` vs tool-use are not defects — both are explicitly overridden by CONTEXT.md D-01 and documented in AI-SPEC §2.

---

_Verified: 2026-05-28T16:45:00Z_
_Verifier: Claude (gsd-verifier)_
