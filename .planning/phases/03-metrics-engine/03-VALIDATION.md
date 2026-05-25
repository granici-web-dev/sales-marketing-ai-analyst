---
phase: 3
slug: metrics-engine
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-25
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.4.2 + pytest-asyncio 1.2.0 |
| **Config file** | `backend/pytest.ini` |
| **Quick run command** | `pytest tests/unit/test_metrics*.py -x` |
| **Full suite command** | `pytest --cov=app --cov-report=term-missing` |
| **Estimated runtime** | ~30 seconds (unit only), ~90 seconds (full with integration) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/unit/test_metrics*.py -x`
- **After every plan wave:** Run `pytest --cov=app --cov-report=term-missing` (full suite, ≥70% coverage on `services/metrics/`)
- **Before `/gsd:verify-work`:** Full suite must be green + SC#1–SC#6 manually verified
- **Max feedback latency:** 30 seconds (unit quick run)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 0 | METR-01..06 | — | N/A | stub | `pytest tests/unit/test_metrics*.py -x` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 1 | METR-01 | — | N/A | unit | `pytest tests/unit/test_calculate_daily_kpis.py -x` | ❌ W0 | ⬜ pending |
| 03-03-01 | 03 | 1 | METR-02 | — | zero-division returns NULL not error | unit | `pytest tests/unit/test_daily_kpi_service.py::test_conversion_rates_zero_denominator -x` | ❌ W0 | ⬜ pending |
| 03-04-01 | 04 | 1 | METR-03 | — | N/A | unit | `pytest tests/unit/test_source_kpi_service.py::test_designer_detection -x` | ❌ W0 | ⬜ pending |
| 03-05-01 | 05 | 1 | METR-04 | — | N/A | unit | `pytest tests/unit/test_salesperson_kpi_service.py -x` | ❌ W0 | ⬜ pending |
| 03-06-01 | 06 | 2 | METR-05 | — | NULL delta on missing prior (not zero imputation) | unit | `pytest tests/unit/test_daily_kpi_service.py::test_wow_delta_null_on_missing_prior -x` | ❌ W0 | ⬜ pending |
| 03-07-01 | 07 | 2 | METR-06 | — | N/A | unit | `pytest tests/unit/test_salesperson_kpi_service.py::test_data_completeness_pct -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/unit/test_calculate_daily_kpis.py` — task-level unit tests (mocked services)
- [ ] `backend/tests/unit/test_daily_kpi_service.py` — conversion rates, WoW/MoM deltas, zero-division guards
- [ ] `backend/tests/unit/test_salesperson_kpi_service.py` — per-rep metrics, time_to_first_touch, data_completeness_pct
- [ ] `backend/tests/unit/test_source_kpi_service.py` — source categorization, designer detection
- [ ] `backend/tests/unit/test_business_hours.py` — business-hours arithmetic edge cases
- [ ] `backend/tests/unit/test_metrics_repository.py` — UPSERT idempotency, tenant_id validation
- [ ] `backend/tests/unit/test_migration_004.py` — migration validation (follows 003 pattern)
- [ ] `backend/tests/factories/metrics_factory.py` — metric row builders extending Phase 2 factories

---

## Critical Edge Case Tests

| Test Name | Requirement | Coverage |
|-----------|-------------|---------|
| `test_business_hours_lead_created_outside_hours` | METR-04 | Lead created 20:00 → first touch 09:30 next day → correct business minutes |
| `test_business_hours_lead_created_at_close` | METR-04 | Lead created at 19:00 → first touch 09:01 next day → 1 minute |
| `test_business_hours_dst_spring_forward` | METR-04 | Lead created night before spring-forward → correct minutes |
| `test_conversion_rate_zero_denominator` | METR-02 | 0 leads in category → conversion = NULL (not ZeroDivisionError) |
| `test_designer_category_overrides_source_id` | METR-03 | Lead source_id=2 but has status_24 in history → categorized as designer |
| `test_upsert_idempotent_same_date` | METR-01 | Running task twice for same date → same row count (no duplicates) |
| `test_wow_delta_null_on_missing_row` | METR-05 | No D-7 row in daily_kpi → wow_delta = NULL |
| `test_delta_precision_numeric` | METR-05 | Decimal precision preserved end-to-end (within 1 RON) |
| `test_inactive_salesperson_excluded` | METR-04 | is_active=False salespeople → no row in salesperson_daily_kpi |
| `test_seven_source_rows_per_day` | METR-03 | All 7 source categories emitted even when some have 0 leads |

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SC#4: Computed values match hand-rolled SQL within 1 RON | METR-01 | Requires production-like data | Run both queries against staging DB, compare outputs |
| SC#6: AT TIME ZONE used in all date grouping | METR-01 | SQL inspection needed | Grep all migration + service files for `AT TIME ZONE 'Europe/Bucharest'` |
| SC#1: Re-run for same date produces no duplicates (production) | METR-01 | Requires real Celery task execution | Trigger `calculate_daily_kpis` twice via Celery CLI, compare row counts |
