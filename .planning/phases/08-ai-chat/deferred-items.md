Pre-existing test_models.py import error:
- File: backend/tests/unit/test_models.py:15
- Error: ImportError: cannot import name 'TIMESTAMPTZ' from 'sqlalchemy.dialects.postgresql'
- Cause: Phase-1 test that pre-dates our work — TIMESTAMPTZ is exported by app.db.base, not sqlalchemy.dialects.postgresql.
- Out of scope for plan 08-02 (scope-boundary rule). Logged for future cleanup.
