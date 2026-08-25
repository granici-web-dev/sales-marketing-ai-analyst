# PRINCIPLES.md

Engineering posture of this project, reverse-engineered from the code on
**2026-08-25** (`/rigorous document`). Descriptive, not aspirational: every rule
below is what the codebase already does, with the counts that support it. Re-run
`document` when the posture shifts.

Sampled: 111 files / 13 225 lines under `backend/app`, 58 test files / 16 869
lines under `backend/tests`, 85 files / 7 737 lines under `frontend/src`.

---

## Engineering posture

- **The main risk is shipping wrong numbers, not shipping slowly.** The product
  tells a business owner where money is leaking; a plausible wrong figure is
  worse than a missing one. Two mechanisms exist purely for this: the
  hallucination guard on chat answers and the ±2 % cross-check on generated
  insights, both of which refuse output rather than pass an unverified number.
- **Design properly the first time.** Every phase has a written plan, a research
  document and a verification record under `.planning/` before code lands. The
  ratio is unusual and deliberate: planning artifacts outnumber source files.
- **Missing data is stated, never defaulted.** `visits_count` is nullable
  because NULL and zero mean different things (migration 006). A rendered `0`
  reads as a collapse; "no data" reads as a gap.

## Comments and naming

- **Comment density is high and deliberate — 7 % comment lines plus ~339
  docstrings across 111 files.** This is the opposite of the "zero comments by
  default" posture. Do not strip comments to match a general style guide.
- **Comments carry decision IDs.** `D-04`, `INFRA-05`, `T-08-01b`, `CR-01`,
  `AI-06`, `METR-03` appear inline and point at the plan or threat model that
  the code implements. A comment that cites a decision is load-bearing: it is
  the only link between the code and the reason it looks that way.
- **Module docstrings explain the WHY of the whole file**, including the
  approach that was rejected. Example: `source_kpi_service` documents that
  source 1 (Google) is absent from the client's data and that designer is a
  status rather than a source — both are facts you would otherwise rediscover
  by reading a query and guessing.
- **Long, explicit names.** `calculate_daily_kpis`, `detect_and_record_history`,
  `_on_worker_process_init`. Abbreviations appear only in loop variables.

## Abstractions

- **Concrete first.** Five occurrences of `ABC` / `Protocol` / `Generic` across
  111 files. The only real abstraction is `BaseIntegration`
  (`authenticate` / `sync` / `health_check`), and it exists because a second
  data source is a stated roadmap item, not a hypothetical.
- **No factories, no managers, no suffix disease.** Services are named for what
  they compute: `DailyKpiService`, `SourceKpiService`, `AnomalyService`.
- **Files stay small: 119 lines on average.** Five exceed 350 —
  `anomaly_service` (766), `orchestrator` (587), `dashboard_read_service` (578),
  `api/v1/chat` (536), `salesperson_kpi_service` (366). These are the exception
  and each is a single cohesive unit, not a grab bag.
- **Repositories own SQL, services own arithmetic, tasks own scheduling.** Chat
  keeps its own repositories under `services/chat/repositories/` rather than
  sharing the generic ones, because its tenancy predicate also carries
  `user_id`.

## Error handling

- **Validate at boundaries, trust the inside.** 14 Pydantic schema modules cover
  HTTP bodies and third-party payloads. Internal helpers assume their callers
  obeyed the types; there is no defensive `if not arg: return` in pure
  functions.
- **Boundary failures become `HTTPException` (23 sites); broken internal
  invariants raise `ValueError` (21 sites).** Malformed `tenant_id` at a Celery
  task entry raises rather than defaulting.
- **A broad `except` is allowed, but never silent.** 66 `except` sites, of which
  **28 carry an explicit `# noqa: BLE001`** plus a comment saying why the broad
  catch is correct there. Zero bare `except: pass` remain. Swallowing an error
  without a log line is the one form of error handling this codebase rejects.
- **Errors reaching a user are in Romanian and say what to do**, not what broke:
  `"Așteaptă răspunsul curent înainte de a trimite alt mesaj."` Stack traces
  stay in structlog.
- **Log lines never carry PII.** Names, phone numbers, e-mail addresses and
  transcript content are excluded by rule; opaque IDs are logged instead. There
  is no scrubbing processor, so this is discipline enforced at call sites and by
  a test that walks the AST of `app/`.

## Raw SQL

- **SQLAlchemy is present, but analytics queries are raw `text()` — 41 sites.**
  The metric queries are window functions and CTEs over a view; expressing them
  through the ORM would obscure them. This is a committed choice, not drift.
- **Parameters are always bound, never interpolated.** Where an *identifier*
  must vary (a GROUP BY column), it comes from a static dict that raises
  `KeyError` on an unknown key, because an identifier cannot be bound.
- **Every tenant-scoped query filters `tenant_id` explicitly** in Core selects,
  which bypass the `with_loader_criteria` seam.

## Discipline

- **Zero `TODO` / `FIXME` / `XXX` in `backend/app`.** Unfinished work lives in
  `.planning/`, not in the source.
- **Migrations lead, models follow.** The schema changes in a numbered Alembic
  revision first; the ORM model is updated to match. When they disagree, the
  migration is right.
- **Fixes cite the review finding they close.** Commit subjects carry the phase
  and the identifier: `fix(08-08): close CR-02, CR-03, CR-05 + WR-10`.
- **A test that passes for the wrong reason is treated as a defect.** Guards
  that iterate a collection assert the collection is non-empty first, after a
  stub suite spent months green while checking nothing.
