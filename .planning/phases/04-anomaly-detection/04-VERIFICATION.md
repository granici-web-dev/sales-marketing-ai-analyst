---
phase: 04-anomaly-detection
verified: 2026-05-28T20:00:00Z
status: human_needed
score: 7/7 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 5/7
  gaps_closed:
    - "Migration 007 DDL now includes detected_at TIMESTAMPTZ column — ORM model and migration are in sync (CR-01 closed by Plan 04-05 commit adaeedaa)"
    - "_get_junk_ids() now scopes query to kpi_date via AND created_date_local = :kpi_date — unbounded all-time set defect fixed (CR-02 closed by Plan 04-05 commit 75f91c23)"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Live database round-trip: apply alembic upgrade head, run detect_anomalies.apply(args=[tenant_id_str]), query detected_problems table"
    expected: "At least one row written per triggered rule; SyncRun(source='anomaly', status='success') recorded; no UndefinedColumn or ProgrammingError exceptions"
    why_human: "Requires Docker Compose stack with PostgreSQL running; 3 live-DB integration tests are skipped without TEST_DATABASE_URL"
  - test: "ROADMAP SC#2 — Seed a lead created inside business hours (e.g. 14:00 Bucharest) with time_to_first_touch_minutes=360; verify slow_first_touch fires with severity='high'. Then seed a lead created outside business hours (e.g. 21:30 Bucharest) with time_to_first_touch_minutes=0; verify it does NOT fire."
    expected: "Inside-hours lead with 6h delay → detected_problems row with rule_id='slow_first_touch', severity='high'. Outside-hours lead with adjusted time=0 → no row."
    why_human: "test_slow_first_touch_not_triggered_for_junk_leads is SKIPPED pending TEST_DATABASE_URL; business hours boundary logic requires live DB with real timestamps to verify the 0-minute path"
  - test: "ROADMAP SC#6 — Seed 25%+ of yesterday's leads as lifecycle='junk' in the DB; run detect_anomalies; verify (a) junk_lead_quality row fires with severity='low' and estimated_loss_ron > 0, and (b) the junk leads' external_ids do NOT appear in slow_first_touch context_json.lead_ids"
    expected: "junk_lead_quality detected_problems row present; slow_first_touch context_json (if present) contains no junk external_ids"
    why_human: "test_slow_first_touch_not_triggered_for_junk_leads and test_detected_problems_upsert_idempotent are SKIPPED; live DB required to verify end-to-end junk exclusion"
---

# Phase 4: Anomaly Detection Verification Report (Re-verification)

**Phase Goal:** Rule-based engine consumes metrics and conformed lead views to write structured `detected_problems` rows with severity, current vs expected values, and an estimated loss in RON — these become Claude's input.
**Verified:** 2026-05-28T20:00:00Z
**Status:** human_needed
**Re-verification:** Yes — after Plan 04-05 gap closure (CR-01, CR-02)

## Re-verification Summary

Previous verification (2026-05-28T18:00:00Z) returned `gaps_found` with 5/7 truths verified. Two blockers were identified:

- **CR-01:** Migration 007 missing `detected_at` TIMESTAMPTZ column that ORM model declared
- **CR-02:** `_get_junk_ids()` lacked date filter — returned all-time junk leads

Plan 04-05 (commits `adaeedaa`, `75f91c23`) closed both defects. This re-verification confirms both fixes are present and that all 23 unit tests remain GREEN.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | detect_anomalies Celery task exists with name='tasks.etl.detect_anomalies' | VERIFIED | Runtime: `detect_anomalies.name == 'tasks.etl.detect_anomalies'` confirmed |
| 2 | AnomalyService has 5 detect_* methods + run_all_rules() orchestrator | VERIFIED | 5 methods confirmed: detect_slow_first_touch, detect_stuck_offer, detect_showroom_traffic_drop, detect_underperforming_salesperson, detect_junk_lead_quality; run_all_rules present |
| 3 | Migration 007 creates detected_problems with UNIQUE(tenant_id, date, rule_id) | VERIFIED | File exists; UniqueConstraint on (tenant_id, date, rule_id); down_revision='006' |
| 4 | Migration 007 DDL matches ORM model columns exactly — detected_at present | VERIFIED | grep -c detected_at returns 2 in migration (column definition + comment); ORM model column confirmed at lines 91-93 of detected_problem.py; both have TIMESTAMPTZ server_default=now() nullable=False |
| 5 | All 23 unit tests for AnomalyService and AnomalyRepository pass GREEN | VERIFIED | pytest run: 23 passed in 0.06s (18 service + 5 repository); confirmed by live pytest invocation |
| 6 | detect_anomalies wired as third link in daily_pipeline() and in celery_app include list | VERIFIED | sync_mefi_leads.py: detect_anomalies.si(tenant_id) is third chain link; celery_app.py: "app.tasks.etl.detect_anomalies" in include list confirmed |
| 7 | _get_junk_ids() correctly scopes junk lead exclusion to the target date | VERIFIED | Line 117-119 in anomaly_service.py: query includes `AND created_date_local = :kpi_date` with `kpi_date=kpi_date` in bindparams; CR-02 fix confirmed by grep and ast.parse |

**Score:** 7/7 truths verified

### Closed Gaps (from previous verification)

| Gap | Previous Status | Current Status | Evidence |
|-----|----------------|----------------|----------|
| CR-01: Migration 007 missing detected_at column | FAILED | VERIFIED | `detected_at` column present in upgrade() after `updated_at`, before `date`; sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False |
| CR-02: _get_junk_ids() unbounded all-time query | FAILED | VERIFIED | SQL query now: `WHERE tenant_id = :tenant_id AND created_date_local = :kpi_date`; bindparams includes kpi_date |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/tests/factories/anomaly_factory.py` | factory-boy fixtures | VERIFIED | DetectedProblemRowFactory, LeadWithNoTouchFactory, StuckOfferLeadFactory, make_detected_problem_row, make_daily_kpi_baseline_rows all importable |
| `backend/tests/unit/test_anomaly_service.py` | 18 unit tests GREEN | VERIFIED | 18 tests passing; all 5 rule methods + run_all_rules covered |
| `backend/tests/unit/test_anomaly_repository.py` | 5 unit tests GREEN | VERIFIED | 5 tests passing; UPSERT guard, 3-col conflict target, WR-04 commit pattern |
| `backend/tests/integration/test_detect_anomalies_task.py` | Integration tests | PARTIAL | 5 tests collected; 2 non-DB PASS; 3 live-DB SKIP (require TEST_DATABASE_URL) |
| `backend/alembic/versions/007_detected_problems.py` | Migration with all columns + UNIQUE constraint | VERIFIED | 13 columns present (including detected_at); UniqueConstraint(tenant_id,date,rule_id); two performance indexes; downgrade() drops in reverse order; down_revision='006' |
| `backend/app/models/anomaly/detected_problem.py` | DetectedProblem ORM model | VERIFIED | All 13 columns present; UniqueConstraint matches migration; estimated_loss_ron as Numeric(12,2); detected_at as TIMESTAMPTZ server_default="now()" |
| `backend/app/models/anomaly/__init__.py` | Package init | VERIFIED | Exports DetectedProblem |
| `backend/app/services/anomaly/anomaly_service.py` | AnomalyService with 5 rules + orchestrator | VERIFIED | All 5 detect methods; run_all_rules calls _get_junk_ids once (D-11); JUNK_RATE_THRESHOLD=0.25; SLOW_FIRST_TOUCH_THRESHOLD_MINUTES=300; context_json keys junk_count/total_leads match model docstring |
| `backend/app/services/repositories/anomaly_repository.py` | AnomalyRepository UPSERT | VERIFIED | 3-col conflict target on (tenant_id, date, rule_id); ValueError guard on missing/None tenant_id; no session.commit() inside method |
| `backend/app/tasks/etl/detect_anomalies.py` | detect_anomalies Celery task | VERIFIED | NullPool; deferred imports; WR-06 stale SyncRun cleanup; WR-04 single commit after all upserts; autoretry without manual self.retry() |
| `backend/app/tasks/etl/sync_mefi_leads.py` | Extended daily_pipeline() | VERIFIED | detect_anomalies.si(tenant_id) is third chain link |
| `backend/app/tasks/celery_app.py` | Updated include list | VERIFIED | "app.tasks.etl.detect_anomalies" in include list |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| detect_anomalies.py | AnomalyService | deferred import inside _detect_async() | VERIFIED | `from app.services.anomaly.anomaly_service import AnomalyService` inside _detect_async body |
| detect_anomalies.py | AnomalyRepository | deferred import inside _detect_async() | VERIFIED | `from app.services.repositories.anomaly_repository import AnomalyRepository` inside _detect_async body |
| detect_anomalies.py | SyncRun (source="anomaly") | ORM instance add + commit | VERIFIED | `SyncRun(source="anomaly", status="running")` created; updated to "success"/"failed" |
| sync_mefi_leads.py daily_pipeline() | detect_anomalies | from import + chain .si() | VERIFIED | `detect_anomalies.si(tenant_id)` as third link in chain() |
| anomaly_repository.py | DetectedProblem model | deferred import inside upsert | VERIFIED | `from app.models.anomaly.detected_problem import DetectedProblem` inside upsert body |
| anomaly_service.py | v_mefi_leads_active | text() query with tenant_id filter | VERIFIED | _db_fetch_slow_leads, _db_fetch_stuck_leads, _db_fetch_junk_counts all include WHERE tenant_id = :tenant_id |
| anomaly_service.py | v_mefi_leads_junk | text() query with tenant_id + date filter | VERIFIED | _get_junk_ids: WHERE tenant_id = :tenant_id AND created_date_local = :kpi_date (CR-02 fix) |
| anomaly_service.py | DailyKpi model | ORM select with tenant_id filter | VERIFIED | _db_fetch_trailing_metrics, _db_fetch_current_kpi |
| migration 007 | migration 006 | down_revision = '006' | VERIFIED | down_revision = "006" confirmed in file |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| detect_slow_first_touch | slow_leads | v_mefi_leads_active via _db_fetch_slow_leads | Yes — parameterized text query, async execute, fetchall | FLOWING |
| detect_stuck_offer | stuck_leads | v_mefi_leads_active via _db_fetch_stuck_leads | Yes — parameterized text query, async execute, fetchall | FLOWING |
| detect_showroom_traffic_drop | baseline_rows, current_kpi | DailyKpi via ORM select | Yes — ORM select with date and tenant_id predicates | FLOWING |
| detect_underperforming_salesperson | salesperson_kpis | SalespersonDailyKpi via ORM select | Yes — ORM select with date and tenant_id predicates | FLOWING |
| detect_junk_lead_quality | junk_count, total_leads | v_mefi_leads_junk + v_mefi_leads_active | Yes — two parameterized COUNT queries | FLOWING |
| _get_junk_ids | junk_ids set | v_mefi_leads_junk | Yes — parameterized with tenant_id AND created_date_local = kpi_date (CR-02 fix) | FLOWING |
| AnomalyRepository.upsert_detected_problem | detected_problems row | pg_insert ON CONFLICT DO UPDATE | Yes — real upsert with 3-col conflict target | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| detect_anomalies task name | `from app.tasks.etl.detect_anomalies import detect_anomalies; detect_anomalies.name` | tasks.etl.detect_anomalies | PASS |
| AnomalyService 5 detect methods | `inspect.getmembers` check | 5 detect_* methods confirmed | PASS |
| 23 unit tests GREEN | pytest tests/unit/test_anomaly_service.py tests/unit/test_anomaly_repository.py | 23 passed in 0.06s | PASS |
| 2 non-DB integration tests | pytest tests/integration/test_detect_anomalies_task.py | 2 passed, 3 skipped | PASS |
| Migration 007 detected_at column present | grep -c detected_at 007_detected_problems.py | 2 (column def + comment) | PASS |
| _get_junk_ids date filter | grep created_date_local anomaly_service.py | match in _get_junk_ids body | PASS |
| context_json keys junk_count/total_leads | grep junk_count + total_leads anomaly_service.py | matches in detect_junk_lead_quality return dict | PASS |
| celery_app include list | grep in celery_app.py | "app.tasks.etl.detect_anomalies" present | PASS |
| daily_pipeline chain | inspect.getsource(daily_pipeline) | detect_anomalies.si(tenant_id) as third link | PASS |
| No debt markers (TBD/FIXME/XXX) | grep in all Phase 4 files | no matches | PASS |

### Probe Execution

No probe scripts declared or conventionally present for this phase.

Step 7c: SKIPPED (no probe scripts).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| ANOM-01 | 04-01, 04-02, 04-03, 04-04 | Anomaly detection writes to detected_problems with severity, metric, current_value, expected_value, estimated_loss_ron | SATISFIED | DetectedProblem model has all required columns; AnomalyRepository upserts via 3-col UPSERT; detect_anomalies task writes SyncRun(source="anomaly") |
| ANOM-02 | 04-01, 04-03 | Leads with no contact attempt > 4 hours (REQUIREMENTS) / 5 hours (ROADMAP SC#2 / D-20) | SATISFIED with documented deviation | slow_first_touch implemented with SLOW_FIRST_TOUCH_THRESHOLD_MINUTES=300 (5h); REQUIREMENTS.md says "4 hours" but ROADMAP SC#2 and CONTEXT D-20 override to 5h; deviation documented in plan comments and service docstring |
| ANOM-03 | 04-01, 04-03 | Offers with no activity > 14 days (REQUIREMENTS) / 15 days (ROADMAP SC#3 / D-20) | SATISFIED with documented deviation | stuck_offer implemented with STUCK_OFFER_DAYS=15; REQUIREMENTS.md says "14 days"; ROADMAP SC#3 and D-20 override to 15 days |
| ANOM-04 | 04-01, 04-03 | L→V conversion drops > 30% (REQUIREMENTS) / 35% (ROADMAP SC#4 / D-20) | SATISFIED with documented deviation | showroom_traffic_drop implemented with SHOWROOM_DROP_THRESHOLD=0.65 (35% drop); REQUIREMENTS.md says "30%"; ROADMAP SC#4 and D-20 override to 35% |
| ANOM-05 | 04-01, 04-03 | REQUIREMENTS: "O→C conversion rate drops > 20% vs baseline → closing problem"; ROADMAP SC#5: salesperson win rate 30% below team avg | SATISFIED per ROADMAP | underperforming_salesperson implemented per ROADMAP SC#5; REQUIREMENTS ANOM-05 describes a system-level "closing problem" that was superseded by the per-salesperson rule in the ROADMAP redesign; ROADMAP is the authoritative contract |
| ANOM-06 | 04-01, 04-03 | Salesperson KPI 30%+ below team average (REQUIREMENTS ANOM-06 maps to what plans call underperforming_salesperson under ANOM-05) | SATISFIED | underperforming_salesperson rule implemented; severity "medium"; context_json includes salesperson_ids list (D-03) |
| ANOM-07 | 04-01, 04-03, 04-05 | Junk leads excluded from all rules; junk rate > 20% (REQUIREMENTS) / 25% (ROADMAP SC#6 / D-20) flags quality issue | SATISFIED | JUNK_RATE_THRESHOLD=0.25 (25%); junk_lead_quality rule fires when junk rate >= 25%; _get_junk_ids() now date-scoped (CR-02 closed); junk exclusion passed to detect_slow_first_touch via run_all_rules |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/tests/unit/test_anomaly_service.py` | 676 | `assert_called_once()` is a no-op (not a real assert method on Mock) | WARNING | test_junk_ids_computed_once passes regardless of actual _get_junk_ids call count; D-11 efficiency invariant is unverifiable via this test; should be `mock_get_junk_ids.assert_called_once()` followed by a real assert |
| `backend/app/services/anomaly/__init__.py` | 3 | Module-level `from app.services.anomaly.anomaly_service import AnomalyService` breaks strict INFRA-05 deferred-import pattern | INFO | Currently safe (detect_anomalies.py uses full path import, not package import); fragile for future developers who might import `from app.services.anomaly import AnomalyService` in task files |
| `backend/app/services/anomaly/anomaly_service.py` | 340, 514, 572-575, 663 | `float()` conversions for percentage/rate values stored in context_json JSONB | INFO | Non-monetary values (worst_hours_elapsed, drop_pct, win_rate, junk_rate) stored as float in JSONB for readability; estimated_loss_ron is correctly Decimal throughout; no blocking risk |

**Debt marker gate:** No TBD, FIXME, or XXX markers found in any Phase 4 production files. Gate PASSED.

**Pre-existing test failures (not regressions from Phase 4):**
- `tests/unit/test_source_kpi_service.py` — 5 failures (test stubs created in Phase 3-01 commit `48868294`; unrelated to Phase 4)
- `tests/unit/test_tenant_isolation.py` — 1 failure (stub from Phase 1-01 commit `fe9d24aa`; unrelated to Phase 4)
- `tests/unit/test_models.py` — ImportError (pre-existing since Phase 1; unrelated to Phase 4)

### Human Verification Required

#### 1. Live Database Round-Trip

**Test:** Apply `alembic upgrade head`, run `detect_anomalies.apply(args=[tenant_id_str])` with a valid tenant UUID, query `SELECT * FROM detected_problems` and `SELECT * FROM sync_runs WHERE source='anomaly'`
**Expected:** SyncRun with status='success', records_synced >= 0, duration_ms > 0; no UndefinedColumn or ProgrammingError exceptions from PostgreSQL
**Why human:** Requires Docker Compose + PostgreSQL; 3 live-DB integration tests are SKIPPED without TEST_DATABASE_URL

#### 2. ROADMAP SC#2 — Business Hours Boundary for slow_first_touch

**Test:** Seed a lead with `created_date_local = yesterday` and `time_to_first_touch_minutes = 360` (created inside business hours, 6h delay); run detect_anomalies; verify slow_first_touch row exists. Seed another lead with `time_to_first_touch_minutes = 0` (adjusted outside-hours creation); verify no slow_first_touch row for it.
**Expected:** Inside-hours lead with 6h+ delay → detected_problems row with rule_id='slow_first_touch', severity='high'. Outside-hours lead with time=0 → excluded from qualifying set, no spurious row.
**Why human:** Live DB required; `test_slow_first_touch_not_triggered_for_junk_leads` SKIPPED pending TEST_DATABASE_URL

#### 3. ROADMAP SC#6 — End-to-End Junk Exclusion

**Test:** Seed 25%+ of yesterday's leads as `lifecycle='junk'` in raw_mefi_leads (so v_mefi_leads_junk returns them); run detect_anomalies; verify (a) junk_lead_quality detected_problems row fires with severity='low' and estimated_loss_ron > 0, and (b) the junk leads' external_ids do NOT appear in slow_first_touch context_json.lead_ids (if slow_first_touch fires at all)
**Expected:** junk_lead_quality row present; no cross-contamination from junk external_ids into slow_first_touch results
**Why human:** `test_slow_first_touch_not_triggered_for_junk_leads` and `test_detected_problems_upsert_idempotent` are SKIPPED; live DB required to verify end-to-end date-scoped junk exclusion behavior after CR-02 fix

### Gaps Summary

No gaps. Both CR-01 (missing `detected_at` column in migration 007) and CR-02 (unbounded `_get_junk_ids()` query) were closed by Plan 04-05. All 7 observable truths are VERIFIED. All 23 unit tests pass GREEN. All key links are WIRED. No debt markers found.

Status is `human_needed` — not `passed` — because three live-database integration tests (SC#2 business hours boundary, SC#6 end-to-end junk exclusion, and the full database round-trip) cannot be verified without TEST_DATABASE_URL. These tests are SKIPPED, not failed. The automated verification layer is fully satisfied.

---

_Verified: 2026-05-28T20:00:00Z_
_Verifier: Claude (gsd-verifier)_
