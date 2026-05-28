---
phase: 6
slug: backend-api
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-28
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio |
| **Config file** | `backend/pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `cd backend && pytest tests/unit/test_dashboard_read_service.py tests/unit/test_insight_read_service.py tests/unit/test_health_read_service.py -x` |
| **Full suite command** | `cd backend && pytest --cov=app --cov-report=term-missing --cov-fail-under=70` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && pytest tests/unit/test_dashboard_read_service.py tests/unit/test_insight_read_service.py tests/unit/test_health_read_service.py -x`
- **After every plan wave:** Run `cd backend && pytest --cov=app --cov-report=term-missing --cov-fail-under=70`
- **Before `/gsd:verify-work`:** Full suite must be green with coverage >= 70%
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | AUTH-03 | T-06-01-01 | 401 on invalid/expired/missing JWT | unit | `pytest tests/unit/test_dashboard_schemas.py -x` | ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 1 | DATA-04 | T-06-01-03 | Decimal fields serialize as strings not floats | unit | `pytest tests/unit/test_dashboard_schemas.py -x` | ❌ W0 | ⬜ pending |
| 06-02-01 | 02 | 2 | SALE-01..07, SALES-01..04, MARK-01..04, UI-06, PIPE-04 | T-06-02-01 | Reads only tenant's rows; no cross-tenant bleed | unit | `pytest tests/unit/test_dashboard_read_service.py tests/unit/test_health_read_service.py -x` | ❌ W0 | ⬜ pending |
| 06-03-01 | 03 | 2 | INSI-01, INSI-02, INSI-03, INSI-04, INSI-05, INSI-06 | T-06-03-01 | 404 on missing date; 429 + Retry-After on rate limit exceeded | unit | `pytest tests/unit/test_insight_read_service.py tests/unit/test_insights_router.py -x` | ❌ W0 | ⬜ pending |
| 06-04-01 | 04 | 3 | SALE-01..07, SALES-01..04, MARK-01..04, INSI-01..06, UI-06, PIPE-04 | T-06-04-02 | Full stack: auth, schema validation, Decimal serialization | integration | `pytest tests/integration/test_phase6_endpoints.py -x` | ❌ W0 | ⬜ pending |
| 06-04-02 | 04 | 3 | All Phase 6 reqs | T-06-04-02 | No regressions from Phases 1–5; AI-09 compliant | integration | `pytest --cov=app --cov-report=term-missing --cov-fail-under=70 -q` | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_dashboard_read_service.py` — RED stubs for SALE-01..07, SALES-01..04, MARK-01..04
- [ ] `tests/unit/test_insight_read_service.py` — RED stubs for INSI-01, INSI-02, INSI-04, INSI-05, INSI-06
- [ ] `tests/unit/test_health_read_service.py` — RED stubs for UI-06, PIPE-04
- [ ] `tests/unit/test_dashboard_schemas.py` — RED stubs for DATA-04 Decimal serialization
- [ ] `tests/unit/test_insights_router.py` — RED stubs for INSI-03 rate limit (allow + 429)
- [ ] `tests/factories/dashboard_factory.py` — factory class for daily_kpi, salesperson, source rows
- [ ] `tests/integration/test_api_auth.py` — integration tests for AUTH-03: 401 on unauthenticated requests

*Note: pytest and pytest-asyncio are already installed in `backend/pyproject.toml`. No framework installation needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Revenue fields display as formatted currency strings in frontend | DATA-04 | UI rendering not tested in backend suite | After Phase 7 frontend: check that revenue values appear as "RON 85,000.00" not "85000" |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
