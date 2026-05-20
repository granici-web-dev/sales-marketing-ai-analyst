---
phase: 1
slug: foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-20
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio 1.2.0 (asyncio_mode=auto) |
| **Config file** | `backend/pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `cd backend && pytest tests/unit -x --tb=short` |
| **Full suite command** | `cd backend && pytest --cov=app --cov-report=term-missing` |
| **Estimated runtime** | ~30 seconds (unit), ~90 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && pytest tests/unit -x --tb=short`
- **After every plan wave:** Run `cd backend && pytest --cov=app --cov-report=term-missing`
- **Before `/gsd:verify-work`:** Full suite must be green + Docker smoke test (`curl http://localhost:8000/healthz` returns 200)
- **Max feedback latency:** 30 seconds (unit only)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 1-??-01 | docker-compose | 1 | INFRA-01 | — | All 6 services start healthy | smoke | `curl http://localhost:8000/healthz` | ❌ W0 | ⬜ pending |
| 1-??-02 | db-models | 1 | INFRA-02 | — | tenant_id NOT NULL + TIMESTAMPTZ | unit | `pytest tests/unit/test_models.py -x` | ❌ W0 | ⬜ pending |
| 1-??-03 | db-session | 1 | INFRA-03 | T-1-03 | Query without tenant raises TenantIsolationError | unit | `pytest tests/unit/test_tenant_isolation.py -x` | ❌ W0 | ⬜ pending |
| 1-??-04 | celery | 1 | INFRA-04 | — | celery-redbeat keys in Redis | integration | `pytest tests/integration/test_celery.py::test_redbeat_alive -x` | ❌ W0 | ⬜ pending |
| 1-??-05 | celery | 1 | INFRA-05 | T-1-05 | worker_process_init disposes engine | unit | `pytest tests/unit/test_worker_init.py -x` | ❌ W0 | ⬜ pending |
| 1-??-06 | logging | 1 | INFRA-06 | T-1-06 | JSON log has tenant_id; no PII | unit | `pytest tests/unit/test_logging.py -x` | ❌ W0 | ⬜ pending |
| 1-??-07 | auth | 2 | AUTH-01 | T-1-07 | POST /auth/login → 200 + access_token + HttpOnly cookie | integration | `pytest tests/integration/test_auth.py::test_login_success -x` | ❌ W0 | ⬜ pending |
| 1-??-08 | auth | 2 | AUTH-02 | T-1-08 | POST /auth/refresh → 200 + new token + rotated cookie | integration | `pytest tests/integration/test_auth.py::test_refresh_rotates -x` | ❌ W0 | ⬜ pending |
| 1-??-09 | frontend | 2 | AUTH-03 | T-1-09 | GET /dashboard without token → redirect to /login | manual | Browser check (AUTH-03 is proxy.ts — no backend test) | ❌ — manual | ⬜ pending |
| 1-??-10 | frontend | 2 | UI-01 | — | ro.json has sidebar + login strings | unit | `pytest tests/unit/test_i18n.py -x` or key presence check | ❌ W0 | ⬜ pending |
| 1-??-11 | migrations | 1 | PIPE-04 | — | pipeline_runs table exists after alembic upgrade head | integration | `pytest tests/integration/test_migrations.py::test_tables_exist -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/__init__.py` + `backend/tests/unit/__init__.py` + `backend/tests/integration/__init__.py`
- [ ] `backend/tests/conftest.py` — shared fixtures: `db_session`, `async_client` (FastAPI AsyncClient), `test_tenant`
- [ ] `backend/tests/unit/test_tenant_isolation.py` — D-06 failing test (INFRA-03, SC#6); test exists BEFORE enforcement code
- [ ] `backend/tests/unit/test_models.py` — INFRA-02 schema inspection via SQLAlchemy introspection
- [ ] `backend/tests/unit/test_logging.py` — INFRA-06 (JSON output, tenant_id present, no PII)
- [ ] `backend/tests/unit/test_worker_init.py` — INFRA-05 (engine dispose/recreate on fork)
- [ ] `backend/tests/integration/test_auth.py` — AUTH-01, AUTH-02
- [ ] `backend/tests/integration/test_migrations.py` — PIPE-04, SC#2
- [ ] `backend/tests/integration/test_celery.py` — INFRA-04, SC#4
- [ ] Framework install: `uv pip install pytest pytest-asyncio==1.2.0 pytest-cov httpx factory-boy`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| /dashboard redirects unauthenticated requests to /login | AUTH-03 | proxy.ts runs in Node.js — no FastAPI endpoint to test | Open browser, navigate to http://localhost:3000/dashboard without login cookie, verify redirect to /login |
| Sidebar shows Romanian navigation labels | UI-01 | Visual/locale check | Open http://localhost:3000/login — verify "Vânzări", "Marketing" etc. in sidebar nav |
| Flower UI accessible | INFRA-01 (Flower) | Browser-only | Open http://localhost:5555 — verify Celery Flower dashboard loads |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s (unit suite)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
