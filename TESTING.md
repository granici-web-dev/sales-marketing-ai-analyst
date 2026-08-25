# TESTING.md

Reverse-engineered from the test suite on **2026-08-25**
(`/rigorous document`). Describes what the tests do, not what they should.

Backend: 58 test files, 16 869 lines — **more test code than application code**
(13 225 lines). 43 unit, 14 integration, 1 adversarial.
Frontend: 6 test files against 85 source files.
Current state: **511 passed, 1 skipped**, ~5 s.

---

## What is worth testing here

- **Metric arithmetic.** Conversion rates, funnel stages, per-salesperson
  aggregates. These are the product; a wrong number here is the failure mode
  that matters.
- **Tenancy and ownership predicates.** Every repository read and write is
  covered for cross-user and cross-tenant leakage. `test_cross_user_isolation`
  asserts that a probing request never reaches the orchestrator at all.
- **Ordering that has security or cost consequences.** The stream lock is taken
  before the rate-limit counter; a 409 must not spend a token. Assert the order,
  not just the status code — both orders return the same code.
- **Transaction boundaries.** Audit rows must survive a later failure in the
  same turn. Assert the commits, not the inserts: a flush is not a save.
- **Contracts against the schema.** A sweep over `Base.registry` asserts every
  tenant-scoped model carries `tenant_id NOT NULL` and TIMESTAMPTZ timestamps.
- **Source-level rules no runtime check can enforce.** An AST walk over `app/`
  fails if a log call takes a PII keyword; a path scan fails if `celery_app`
  imports `app.db` at module level.

## What is not worth testing

- Framework behavior, Pydantic validation of its own types, SQLAlchemy itself.
- Getters, dataclass construction, pure formatting helpers with no branches.
- The Anthropic SDK. Its responses are fixtures under
  `tests/fixtures/anthropic_responses/`.

## Mocking policy

**Hybrid, split by directory.**

- `tests/unit/` mocks everything external: `AsyncSession`, Redis, Celery,
  `AsyncAnthropic`. 837 uses of `AsyncMock` / `MagicMock`. These run with no
  services up and finish in seconds.
- `tests/integration/` needs a real Postgres via `TEST_DATABASE_URL` and skips
  cleanly without it. This is where tenancy isolation is proven, because a
  mocked session cannot demonstrate that a predicate reached SQL.
- `tests/adversarial/` holds hostile-input cases.

A mocked session proves the code called what you expected. It cannot prove the
database agreed. Anything whose correctness depends on the query itself belongs
in `integration/`.

## Guard the guard

Any assertion that iterates a collection must first assert the collection is
non-empty. This is a rule with history: `test_models.py` sat green for months
while checking nothing, and a PII test asserted that strings it never logged
were absent from the output.

New guards are verified by mutation, not by passing: revert the fix, confirm the
test fails, restore it. A test written after the fix and never seen red is not
yet known to work.

## Layout and naming

- Parallel tree: `backend/tests/{unit,integration,adversarial}/`, mirroring
  `app/` where it helps. Chat has its own subdirectory in both.
- Files `test_<module>.py`; classes `Test<Behavior>`; functions
  `test_<what_must_hold>`.
- Some names carry the requirement ID they cover
  (`test_r13_cr02_stream_lock_conflict_does_not_burn_rate_limit`). Useful when a
  review finding needs tracing to its regression; not required.
- Test docstrings state the failure being prevented, in business terms — "a user
  on a flaky connection could lock themselves out of their own chat" rather than
  "checks INCR order".

## Fixtures and factories

`factory-boy` under `tests/factories/`, `freezegun` for time, `respx` for
outbound httpx. Fixtures that mutate global state (log handlers, structlog
context, `ContextVar`s) restore it in `finally` — several tests swap the root
logger's handlers, and one that forgot to restore would change every test after
it.

## Coverage posture

No numeric target and no coverage gate. Coverage is judged by whether the risky
paths have a test that has been seen to fail. `pytest-cov` is installed;
`.coverage` is ignored.

## Suite runtime

Backend unit suite: ~5 s, and it should stay in that range — it is run
constantly during work. Integration is slower and needs a database. No upper
bound is enforced anywhere, because nothing runs the suite automatically.

## Gaps, stated plainly

- **No CI.** Nothing runs any of this on a push. Phase 9.
- **Frontend is thin**: 6 test files for 85 source files. Covered: the SSE
  parser, the API client's refresh-and-retry path, a few components. Not
  covered: most of the dashboard.
- **No end-to-end tests.** A Playwright spec exists at
  `frontend/tests/e2e/chat.spec.ts`, but Playwright is not in `package.json`, so
  it has never run.
- **One skip is legitimate**: a tenancy test that needs a live database and is
  covered in the integration suite.
