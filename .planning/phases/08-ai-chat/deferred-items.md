Pre-existing test_models.py import error:
- File: backend/tests/unit/test_models.py:15
- Error: ImportError: cannot import name 'TIMESTAMPTZ' from 'sqlalchemy.dialects.postgresql'
- Cause: Phase-1 test that pre-dates our work — TIMESTAMPTZ is exported by app.db.base, not sqlalchemy.dialects.postgresql.
- Out of scope for plan 08-02 (scope-boundary rule). Logged for future cleanup.

Pre-existing test_insights_router.py rate-limit failures (Plan 08-05 discovery):
- File: backend/tests/unit/test_insights_router.py::test_refresh_rate_limit_first_call_enqueues
- File: backend/tests/unit/test_insights_router.py::test_refresh_rate_limit_second_call_returns_429
- Error: `AttributeError: 'Query' object has no attribute 'isoformat'` at app/api/v1/insights.py:75
- Cause: tests call `refresh_insights()` directly without supplying `target_date` — the FastAPI Query default object leaks through to the handler body. Pre-dates Phase 8 (verified by stashing all 08-05 changes — failure reproduces on the prior commit base). Confirmed unrelated to chat router work.
- Out of scope for plan 08-05 (scope-boundary rule). Logged for future cleanup. Phase 6 / insights router author should fix by either patching the test to pass `target_date=None` explicitly or by adding `target_date = None if isinstance(target_date, Query) else target_date` defensive coercion in the handler.
