---
phase: 03-metrics-engine
plan: "01"
subsystem: testing
tags: [tdd, metrics, phase3, wave0, test-stubs]
dependency_graph:
  requires: []
  provides:
    - backend/tests/unit/test_daily_kpi_service.py
    - backend/tests/unit/test_salesperson_kpi_service.py
    - backend/tests/unit/test_source_kpi_service.py
    - backend/tests/unit/test_business_hours.py
    - backend/tests/unit/test_metrics_repository.py
    - backend/tests/unit/test_calculate_daily_kpis.py
    - backend/tests/unit/test_migration_004.py
    - backend/tests/unit/test_metrics_models.py
    - backend/tests/factories/metrics_factory.py
  affects:
    - plans/03-02 (migration + models must pass these tests)
    - plans/03-03 (services + repository must pass these tests)
    - plans/03-04 (Celery task must pass these tests)
tech_stack:
  added: []
  patterns:
    - RED-state TDD test stubs (AsyncMock pattern from test_mefi_repository.py)
    - AST-based migration inspection (from test_migration_003.py)
    - factory-boy Factory with Meta.model=dict for plain row dicts
key_files:
  created:
    - backend/tests/unit/test_daily_kpi_service.py
    - backend/tests/unit/test_salesperson_kpi_service.py
    - backend/tests/unit/test_source_kpi_service.py
    - backend/tests/unit/test_business_hours.py
    - backend/tests/unit/test_metrics_repository.py
    - backend/tests/unit/test_calculate_daily_kpis.py
    - backend/tests/unit/test_migration_004.py
    - backend/tests/unit/test_metrics_models.py
    - backend/tests/factories/metrics_factory.py
  modified: []
decisions:
  - "D-04 locked in test_source_kpi_service: assert exactly 7 source categories per day"
  - "D-11 locked in test_daily_kpi_service: NULL deltas on missing prior — never zero"
  - "Pitfall 5 locked in test_metrics_repository: SourceDailyKpi uses 3-col conflict target"
  - "Pitfall 6 locked in test_metrics_repository: ValueError raised on missing tenant_id"
  - "D-07 locked in test_business_hours: Mon-Sun 09:00-19:00 Europe/Bucharest DST-safe"
  - "D-10 locked in test_calculate_daily_kpis: default to yesterday Bucharest, not UTC"
  - "Schema Gap 1-5 locked in test_migration_004: WoW/MoM deltas, data_completeness_pct, BUSINESS_HOURS_PATCH, mefi_lead_history join"
metrics:
  duration_minutes: 8
  completed_at: "2026-05-25T21:52:21Z"
  tasks_completed: 2
  files_created: 9
  files_modified: 0
  commits: 2
---

# Phase 3 Plan 01: RED-State Test Stubs Summary

**One-liner:** Eight RED-state pytest test files + metrics factory locking all Phase 3 service/repository/task/migration contracts before any implementation exists.

## What Was Built

Wave 0 / Nyquist gate for Phase 3 Metrics Engine. All 8 test files plus the metrics factory are now in place as contract-locking RED stubs. Plans 02/03/04 must turn these tests GREEN.

### Task 1 — Service-layer tests + business-hours + factory (commit: 48868294)

| File | Tests | Coverage |
|------|-------|----------|
| `test_daily_kpi_service.py` | 8 | METR-02 (conversion rates), METR-05 (WoW/MoM deltas), D-11 (NULL not zero), D-16 (Decimal not float) |
| `test_salesperson_kpi_service.py` | 7 | METR-04 (per-salesperson), METR-06 (data_completeness_pct), D-05 (NULL no history), D-17 (is_active filter) |
| `test_source_kpi_service.py` | 7 | METR-03 (7 categories), D-02 (designer detection), D-03 (TikTok→mail_fb_ig), D-04 (7 rows per day) |
| `test_business_hours.py` | 8 | D-06 (business-hours adjusted), D-07 (Mon-Sun 09:00-19:00 Bucharest), DST spring-forward |
| `metrics_factory.py` | N/A | Factory builders: DailyKpiRowFactory, SalespersonKpiRowFactory, SourceKpiRowFactory, make_seven_source_rows |

### Task 2 — Repository, task, migration, model tests (commit: 559946a1)

| File | Tests | Coverage |
|------|-------|----------|
| `test_metrics_repository.py` | 9 | METR-01 SC#1 (idempotent UPSERT), Pitfall 5 (3-col source conflict), Pitfall 6 (tenant_id validation) |
| `test_calculate_daily_kpis.py` | 6 | D-10 (yesterday Bucharest default), D-12 (optional date), PIPE-02 (retry+chain halt) |
| `test_migration_004.py` | 13 | All 5 Schema Gaps: WoW/MoM deltas, data_completeness_pct, BUSINESS_HOURS_PATCH, mefi_lead_history join, UNIQUE constraints |
| `test_metrics_models.py` | 10 | UniqueConstraint names for all 3 models, 2-col vs 3-col keys, tenant_scoped columns |

## RED State Confirmation

| Test File | RED Mechanism | Status |
|-----------|--------------|--------|
| test_daily_kpi_service.py | ImportError (app.services.metrics.daily_kpi_service) deferred in helper | RED ✓ |
| test_salesperson_kpi_service.py | ImportError deferred in helper | RED ✓ |
| test_source_kpi_service.py | ImportError deferred in helper | RED ✓ |
| test_business_hours.py | ImportError at module level (desired — fails at collection) | RED ✓ |
| test_metrics_repository.py | ImportError deferred in helper | RED ✓ |
| test_calculate_daily_kpis.py | ImportError deferred inside test methods | RED ✓ |
| test_migration_004.py | pytest.fail() — migration file does not exist | RED ✓ |
| test_metrics_models.py | ImportError caught in try/except → _require_*() fail | RED ✓ |

## Decisions Made

1. `test_business_hours.py` uses module-level import (not deferred) to make the file RED at pytest collection — this is the desired behavior per plan specification.
2. `test_migration_004.py` uses pytest.fail() with migration-not-found message (same pattern as test_migration_003.py) — not ImportError — because the migration file doesn't exist, not just not importable.
3. `test_metrics_models.py` uses try/except at module level (not deferred) + `_require_*()` helpers — same pattern as test_mefi_models.py.
4. D-07 DST test uses `ZoneInfo("UTC")` timestamps with exact UTC values to avoid ambiguity during Romanian spring-forward transition.
5. `make_seven_source_rows()` returns categories in canonical D-04 order: `mail_fb_ig | telefon | whatsapp | site | designer | alte | google`.

## Deviations from Plan

None — plan executed exactly as written.

All 8 test files created per specification. All acceptance criteria met. RED state confirmed for all files.

## Threat Flags

None. This plan creates test files only — no new network endpoints, auth paths, or schema changes introduced.

## Known Stubs

None. Test files are intentionally RED stubs (Wave 0 purpose). The stub state is by design — these files will be turned GREEN by Plans 02/03/04.

## Self-Check: PASSED

- [x] `test_daily_kpi_service.py` exists with TestConversionRates, TestWoWMoMDeltas
- [x] `test_salesperson_kpi_service.py` exists with test_inactive_salesperson_excluded, test_data_completeness_pct
- [x] `test_source_kpi_service.py` exists with test_seven_source_rows_per_day, test_designer_category_overrides_source_id
- [x] `test_business_hours.py` exists with test_dst_spring_forward_bucharest, test_end_before_start_returns_zero, module-level import
- [x] `metrics_factory.py` exists with DailyKpiRowFactory, SalespersonKpiRowFactory, SourceKpiRowFactory, make_seven_source_rows
- [x] `factories/__init__.py` exists
- [x] `test_metrics_repository.py` exists with test_raises_when_tenant_id_missing, test_source_uses_three_column_conflict_target, test_upsert_idempotent_same_date
- [x] `test_calculate_daily_kpis.py` exists with tasks.etl.calculate_daily_kpis, test_default_calculation_date_is_yesterday_bucharest
- [x] `test_migration_004.py` exists with MIGRATION_PATH, 004_metrics_schema.py, leads_total_wow_delta, data_completeness_pct, BUSINESS_HOURS_PATCH, mefi_lead_history
- [x] `test_metrics_models.py` exists with uq_daily_kpi_tenant_date, uq_salesperson_daily_kpi_tenant_sp_date, uq_source_daily_kpi_tenant_source_date
- [x] All files begin with `from __future__ import annotations`
- [x] All files parse as valid Python (ast.parse passes)
- [x] Commits 48868294, 559946a1 both exist in git log
- [x] 63 tests collected (excluding test_business_hours.py which errors at import — correct RED behavior)
