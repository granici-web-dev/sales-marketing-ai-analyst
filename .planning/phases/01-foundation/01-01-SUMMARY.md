---
phase: 01-foundation
plan: "01"
subsystem: backend/tests
tags: [testing, tdd, tenant-isolation, auth, migrations, celery, healthz, wave-0]
dependency_graph:
  requires: []
  provides:
    - backend/tests/conftest.py (shared fixtures: async_client, db_session, test_tenant)
    - backend/tests/unit/test_tenant_isolation.py (D-06 failing test — SC#6 gate)
    - backend/tests/unit/test_models.py (INFRA-02 schema inspection contracts)
    - backend/tests/unit/test_logging.py (INFRA-06 PII guard contracts)
    - backend/tests/unit/test_worker_init.py (INFRA-05 fork-safety contracts)
    - backend/tests/integration/test_auth.py (AUTH-01, AUTH-02 contracts)
    - backend/tests/integration/test_migrations.py (PIPE-04, SC#2 contracts)
    - backend/tests/integration/test_celery.py (INFRA-04, SC#4 contracts)
    - backend/tests/integration/test_health.py (INFRA-01, SC#1 contracts)
    - backend/pyproject.toml (pytest asyncio_mode=auto config)
  affects:
    - All Wave 1 implementation plans (01-02 through 01-07): these test contracts define the interfaces implementation must satisfy
tech_stack:
  added: []
  patterns:
    - pytest-asyncio 1.2.0 with asyncio_mode=auto in pyproject.toml
    - try/except ImportError pattern for pre-implementation test stubs
    - httpx.AsyncClient + ASGITransport for in-process FastAPI testing
    - pytestmark=pytest.mark.skip for stub files (except D-06 test which is NOT skipped)
key_files:
  created:
    - backend/tests/__init__.py
    - backend/tests/unit/__init__.py
    - backend/tests/integration/__init__.py
    - backend/tests/conftest.py
    - backend/tests/unit/test_tenant_isolation.py
    - backend/tests/unit/test_models.py
    - backend/tests/unit/test_logging.py
    - backend/tests/unit/test_worker_init.py
    - backend/tests/integration/test_auth.py
    - backend/tests/integration/test_migrations.py
    - backend/tests/integration/test_celery.py
    - backend/tests/integration/test_health.py
    - backend/pyproject.toml
  modified: []
decisions:
  - "D-06 test (test_query_without_tenant_context_raises) uses pytest.fail() not pytest.skip() when imports are missing — preserves the test's required-failing status for CI"
  - "pytestmark=pytest.mark.skip applied at module level to test_models.py, test_logging.py, test_worker_init.py — but NOT test_tenant_isolation.py (D-06 required)"
  - "test_celery_worker_pings marked with @pytest.mark.skip(reason='Requires running worker') as a manual gate test"
  - "test_query_with_tenant_context_succeeds marked with @pytest.mark.skip(reason='Requires live DB') — only the negative test (D-06) is unsuppressed"
metrics:
  duration: "5 minutes"
  completed: "2026-05-21"
  tasks_completed: 3
  tasks_total: 3
  files_created: 13
  files_modified: 0
---

# Phase 1 Plan 01: Test Infrastructure (Wave 0 Gate) Summary

Wave 0 test stubs written before any implementation exists — 12 test files + conftest.py + pyproject.toml defining the contracts that implementation plans (Wave 1: 01-02 through 01-07) must satisfy.

## What Was Built

**Test infrastructure skeleton for Phase 1 Foundation** — pytest-asyncio configuration, shared fixtures, and 8 test files covering all 11 Phase 1 requirements (INFRA-01..06, AUTH-01..02, PIPE-04, UI-01 partial).

Key deliverable: **D-06 required failing test** (`test_query_without_tenant_context_raises` in `test_tenant_isolation.py`) — this is the SC#6 gate test that proves the SQLAlchemy `with_loader_criteria` enforcement seam is required and will be tested before implementation is written. It is explicitly NOT skipped.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Test infrastructure — __init__.py, conftest.py, pyproject.toml | 25242a5 | backend/tests/__init__.py, backend/tests/unit/__init__.py, backend/tests/integration/__init__.py, backend/tests/conftest.py, backend/pyproject.toml |
| 2 | Unit test stubs — D-06, models, logging, worker init | fe9d24a | backend/tests/unit/test_tenant_isolation.py, test_models.py, test_logging.py, test_worker_init.py |
| 3 | Integration test stubs — auth, migrations, celery, healthz | d5c8cbc | backend/tests/integration/test_auth.py, test_migrations.py, test_celery.py, test_health.py |

## Test Contract Summary

### Unit Tests (no DB required)

| File | Requirement | Key Test | Status |
|------|-------------|----------|--------|
| test_tenant_isolation.py | INFRA-03, D-06, SC#6 | test_query_without_tenant_context_raises | NOT SKIPPED — active failing gate |
| test_models.py | INFRA-02 | test_tenant_id_not_null, test_tenant_model_has_no_tenant_id | Skipped until impl |
| test_logging.py | INFRA-06 | test_no_pii_in_log_output | Skipped until impl |
| test_worker_init.py | INFRA-05 | test_worker_process_init_disposes_engine | Skipped until impl |

### Integration Tests (require DB / Redis)

| File | Requirements | Key Test | Status |
|------|-------------|----------|--------|
| test_auth.py | AUTH-01, AUTH-02 | test_login_success, test_refresh_rotates | Skips if app=None |
| test_migrations.py | PIPE-04, SC#2 | test_tables_exist | Skips if DATABASE_URL not set |
| test_celery.py | INFRA-04, SC#4 | test_redbeat_alive | Skips if REDIS_URL not set |
| test_health.py | INFRA-01, SC#1 | test_healthz_returns_200 | Skips if app=None |

## Deviations from Plan

None — plan executed exactly as written.

The plan specified `pytestmark = pytest.mark.skip(reason="Stubs — implementation pending")` for all unit test files except `test_tenant_isolation.py`. This was implemented precisely. The D-06 test (`test_query_without_tenant_context_raises`) uses `pytest.fail()` when imports are missing (not `pytest.skip()`) to preserve its required-failing status when the enforcement code is absent.

## Known Stubs

The "implementation pending" skips in integration tests are intentional design — this is a Wave 0 plan whose purpose is to write test contracts before implementation. The skips will automatically lift once Wave 1 implementation plans complete (app modules become importable).

The only stub concern: `test_query_without_tenant_context_raises` will fail with `pytest.fail()` (not a skip) until `app.db.session.AsyncSessionLocal`, `app.models.user.User`, `app.core.exceptions.TenantIsolationError`, and `app.core.tenancy._tenant_id_var` are implemented. This is correct and expected per D-06 and SC#6.

## Threat Flags

None — this plan creates only test files. No network endpoints, auth paths, file access patterns, or schema changes introduced.

The threat model mitigations from the plan were verified:
- **T-01-SC:** `test_query_without_tenant_context_raises` has NO `@pytest.mark.skip` decorator — confirmed.
- **T-01-ID:** `test_no_pii_in_log_output` asserts that `"Ion Popescu"`, `"0721000000"`, `"ion@test.ro"` do NOT appear in JSON log output — confirmed.

## Self-Check: PASSED

All 13 created files exist:

- backend/tests/__init__.py: FOUND
- backend/tests/unit/__init__.py: FOUND
- backend/tests/integration/__init__.py: FOUND
- backend/tests/conftest.py: FOUND
- backend/tests/unit/test_tenant_isolation.py: FOUND
- backend/tests/unit/test_models.py: FOUND
- backend/tests/unit/test_logging.py: FOUND
- backend/tests/unit/test_worker_init.py: FOUND
- backend/tests/integration/test_auth.py: FOUND
- backend/tests/integration/test_migrations.py: FOUND
- backend/tests/integration/test_celery.py: FOUND
- backend/tests/integration/test_health.py: FOUND
- backend/pyproject.toml: FOUND

All 3 commits exist: 25242a5, fe9d24a, d5c8cbc
