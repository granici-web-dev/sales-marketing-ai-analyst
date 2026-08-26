# Review backlog

Everything the 2026-08-25 review turned up, in the order it is worth doing.
Three passes: `rigorous audit` (defects), `architect` (structure), `critique`
(what can be cut). Full write-ups are in the two published reports; this file is
the actionable residue.

Each item states where it is, what happens if it is left, and what the fix costs.
Nothing here is speculative — every claim was measured against the code.

---

## Done

- [x] **next 16.2.6 → 16.2.11** — closed seven advisories including the
      Middleware / Proxy bypass that route protection depends on. Production
      advisories 17 → 8. Commit `7e31911`.
- [x] **Commit `pnpm-lock.yaml`** — it was gitignored and had never been
      committed while 30 of 38 dependencies sit on caret ranges. Commit `7e31911`.

- [x] **Route protection was never running.** `proxy.ts` sat at the project
      root while the app lives under `src/`; Next looks for it beside `app/`.
      It was never loaded, and neither was the token check — `/agents`,
      `/sales`, `/insights` and `/settings` all returned 200 with full page
      content and no cookie at all. This is the same layer the Next advisory
      patched in `7e31911` was about: bypassing a proxy means nothing when the
      proxy does not run. Moved to `src/proxy.ts`. Commit `98cbd03`.

- [x] **`next-intl` middleware broke `/login` once the proxy started running.**
      It rewrote `/login` to `/ro/login`, and no `[locale]` segment exists —
      routes live in the `(auth)` and `(dashboard)` groups. With
      `localePrefix: "never"` the locale comes from `src/i18n/request.ts` and
      the middleware is not needed; removed, token check kept. Commit `98cbd03`.

- [x] **An unset `JWT_SECRET_KEY` looked exactly like a bad token.** The
      frontend has no `.env` at all, so the variable was undefined;
      `process.env.JWT_SECRET_KEY!` is a TypeScript assertion and checks
      nothing at runtime, so `jwtVerify` received the encoding of the string
      "undefined" and rejected every valid token. A person with the correct
      password would loop back to the login page with no message and no log
      line. Now a missing secret throws with an explanation, because a
      configuration fault must not behave like a wrong password. Added
      `frontend/.env.example`. Commit `3d7c0b2`.

- [x] **Two sources of truth for the tenant.** The eight endpoints in
      `dashboards.py`, `insights.py`, `health.py` and `sync.py` now call
      `require_tenant_id()` like chat and every Celery task; nothing reads
      `settings.sofa_belle_tenant_id` on the request path any more. A source
      sweep (`tests/unit/test_tenancy_source.py`) fails if the name comes back,
      and the one unit test that called a handler directly now sets the tenant
      itself and asserts the enqueued task received *that* tenant — an
      assertion that fails against the old code. Commit `ed77345`.

- [x] **The daily schedule can fail to register and say nothing.** Replaced the
      bare `pass` with `logger.exception("beat.schedule_registration_failed")`,
      and corrected the comment that claimed a second, authoritative
      registration site exists. It does not. Commit `65ec90b`.

- [x] **Python dependencies have never been checked.** `pip-audit` is in the
      dev extras and has been run. Commit `a506afd`. Result below.

- [x] **Five advisories in starlette, on the HTTP layer.** starlette 1.0.1 →
      1.6.0, pinned directly in `pyproject.toml` because fastapi asks only for
      `>=0.46` and would install the vulnerable version again. Closes
      PYSEC-2026-248 (`request.url` rebuilt from an unvalidated path) and
      PYSEC-2026-249 (form limits ignored for urlencoded bodies), both on the
      request path of every endpoint. Verified by request, not only by suite:
      the app boots on 1.6.0, `/healthz` and `/health/data` answer 200, a
      protected route without a token answers 401, login issues a token, an
      authenticated dashboard returns real funnel numbers, and CORS preflight
      passes. `pydantic-settings` 2.14.1 → 2.15.0 in the same pass; its finding
      needs `secrets_dir`, which this project does not use, so no floor was
      raised for it. Audit 12 findings → 6, all remaining in `pip`,
      `setuptools` and `pytest` — tooling, not shipped. Commit `7f11226`.

- [x] **Access token is readable by any script, and travels over plain HTTP.**
      Gone with the token. The cabinet no longer issues one: identity comes
      from the engine, whose cookie is `HttpOnly; SameSite=Strict` and which
      no script can read. `api-client.ts` stopped reading cookies, the refresh
      interceptor went with the tokens it refreshed, and `jose` left
      `package.json`. The non-HttpOnly cookie existed *because* client code had
      to read it; removing the reader removed the reason.

- [x] **`/health/data` has no authentication, and now no tenant either.** It
      requires a session like every other endpoint. It was the last one that
      did not, and it held together only because the tenant came from config.

- [x] **The green test number covered unit tests only.** The whole suite is
      green: 537 passed, 0 failed. Four stale-red integration tests were
      repaired — two asserted the old public `/health/data`, one patched
      `daily_pipeline` (a name the handler stopped calling), and the AI-09
      grep gate did not know about the documented chat exception and was
      failing on `chat.py`'s own comments explaining why it is one. 36 tests
      still skip for want of `TEST_DATABASE_URL`.

---

## Before the next deploy

- [ ] **Linking a client is a manual SQL statement.** A client of the engine
      reaches the analyst only once `tenants.engine_tenant_id` points at their
      engine tenant, and nothing sets it. Deliberate — an analyst tenant with
      no CRM sync is an empty cabinet, and creating one on first login would
      let someone in to guess whether it is broken. But the step lives in a
      comment, and a comment is not a procedure.
      *Fix:* a command that links by client, and a check at startup that says
      out loud how many tenants are unlinked.

- [ ] **Nothing proves route protection is switched on.** All three findings
      above shared one cause: the file was not running, and code that does not
      run does not fail. Moving, renaming or misplacing `src/proxy.ts` again
      silently disables authentication for the whole dashboard, and every test
      in the suite stays green.
      *Fix:* a test that asserts an unauthenticated request to a protected
      route redirects to `/login` — against the running app, not against the
      file's contents. A source-level check that `proxy.ts` sits beside `app/`
      is the cheap half and catches the original mistake; only a request
      catches the other two.

---

## Before CI can be trusted

- [ ] **54 `noqa` markers suppress rules that are not enabled.** 28
      `# noqa: BLE001`, 26 `# noqa: PLC0415`; `[tool.ruff.lint] select` lists
      `E F I N UP S B A COM C4 PT RET SIM TID` — no `BLE`, no `PLC`. The
      broad-catch discipline is real as a convention and unenforced as
      configuration, while the markers make it look enforced.
      *Fix:* add `BLE` and `PLC` to `select`.

- [ ] **Linter output is 1 033 lines, of which a handful matter.** 344 `E402`
      (almost all from `from __future__ import annotations` sitting above the
      module docstring), 91 `E501`, 38 `B008` (which is `Depends()` and
      `Query()`, the FastAPI idiom, not a defect), 12 real `F401`.
      Nothing breaks, but a linter with that output will never be a gate, and the
      thirteenth real finding is invisible inside it.
      *Fix:* `B008` into `ignore` with a note about FastAPI, settle the
      docstring/`__future__` order, run `ruff check --fix` for the 190 automatic
      ones.

- [ ] **`mypy` is configured `strict = true` and is not installed.** Never run,
      so the size of the debt is unknown.
      *Fix:* add it to dev extras and run it once to find out. If the debt is
      large, either lower strictness to something true or enable per-module.
      Declared-and-unchecked is worse than honestly off.

- [ ] **No CI at all.** No `.github/workflows`, nothing. 511 backend tests and 53
      frontend tests run only when someone runs them.
      *Blocked on:* the three items above, otherwise the gate is red on arrival.
      Phase 9.

---

## Worth doing, no hurry

- [ ] **Dashboard date ranges are unbounded and unordered.**
      `backend/app/api/v1/dashboards.py`, three endpoints. No ceiling on the
      period, no check that `from <= to`, no rate limit (unlike chat and insights
      refresh). Authenticated-only, one tenant, one row per day per table — a
      200-year request is ~73 000 rows, so this is cheap to abuse and cheap to
      survive. Matters more under multi-tenancy.
      *Fix:* `from <= to` plus a maximum period in the Pydantic schema.

- [ ] **MEFI request interval is roughly three times too fast.**
      `_REQUEST_INTERVAL = 0.35` in `services/integrations/mefi.py`. The binding
      limit is the per-IP burst, 10 requests / 10 s ≈ 1 req/s, not the token's
      600/min. Measured: at 0.35 s the 429 lands on the 11th request every time.
      Retries are handled correctly (up to 20, exponential, `Retry-After`
      honoured), so this costs time and log noise rather than availability.
      *Fix:* raise to 1.2 s.

- [ ] **Eight transitive advisories remain**, all through `next` itself:
      `postcss@8.4.31` (4), `nanoid` (2), `sharp` (1), `@babel/core` (1). Forcing
      them means `pnpm overrides` against versions next pins for itself, one of
      which is a native image library.
      *Decision needed:* override, or wait for the next Next release.

- [ ] **Two public methods exist only as aliases.**
      `compute_source_kpis` and `compute_salesperson_kpis` each consist of one
      call to `compute_for_date`. One cites "test compatibility", the other
      "backwards compatibility" — with one client and no external API consumers
      there is no backwards to be compatible with.
      *Fix:* delete both, point the tests at the real name.

- [ ] **FastAPI dependency wiring lives in `core/`.**
      `core/dependencies.py` holds `get_current_user` and imports `db.deps`,
      which is the sole cause of the one cycle in the module graph
      (`core ⇄ db`, package level only, no runtime effect).
      *Fix:* move it under `api/`. Small, and it makes the graph acyclic.

- [ ] **12 unused imports** in `app/`. `ruff check --fix` clears them.

- [ ] **`_rate` is duplicated** across `daily_kpi_service` and
      `salesperson_kpi_service`. Two copies of division-with-a-zero-guard. Rule
      of three says wait; note it here so the third copy is noticed.

---

## Interface: Davoq portal world

Palette, fonts and the token layer were adopted from the Davoq engine portal on
2026-08-25, applied to the insights screen. What is left is the same move on the
remaining surfaces.

- [ ] **35 hard-coded Tailwind palette colours on the other screens.**
      `dashboards/sales` (20), `dashboards/salespeople` (2), and 35 raw hex
      values inside chart components (`#71717A` ×28, `#2563EB` ×4, `#09090B` ×3).
      None of them respond to the theme: in dark mode a `bg-yellow-100` surface
      under `text-yellow-800` is unreadable, and chart axes stay light grey on a
      dark ground.
      *Fix:* the same substitution done on insights — semantic tokens for meaning
      (`--ok`, `--warn`, `--danger`), `--muted-fg` for chart furniture, `--accent`
      for the series. Recharts takes CSS variables through `stroke` and `fill`.

- [ ] **No theme switch in the analyst.** The tokens carry all three states —
      system, explicit light, explicit dark — and nothing lets a person choose.
      The portal has the control; copy it rather than inventing a second one.

- [ ] **Card radius and shadow are now tokens; other primitives are not.**
      `card.tsx` uses `rounded-card` / `shadow-card`. Buttons, inputs, selects
      and popovers still carry shadcn's `rounded-md`, so controls sit at 6 px
      beside 14 px cards.
      *Fix:* `rounded-control` on the control primitives.

- [ ] **PRODUCT.md and DESIGN.md were never captured.** `impeccable` ran under
      its scoped-refinement path because no product context exists. Every future
      design task will re-derive the same answers.
      *Fix:* `/impeccable init`, then `document` to write DESIGN.md from the
      tokens that now exist.

---

## Coverage gaps, not defects

- [ ] **Frontend has 6 test files against 85 source files.** Covered: the SSE
      parser, the API client's refresh-and-retry path, a few components. Not
      covered: most of the dashboard.

- [ ] **The Playwright spec has never run.** `frontend/tests/e2e/chat.spec.ts`
      exists; Playwright is not in `package.json`, so `pnpm test:e2e` does not
      exist either. Either install it and run the spec, or delete the spec —
      a test file nobody can run reads as coverage that is not there.

- [ ] **No query plans measured.** `EXPLAIN ANALYZE` needs a database with real
      data and the stack was not running. Indexes exist on every tenant-scoped
      table; whether the funnel queries use them at volume is unverified.

- [ ] **Tools that never ran:** `semgrep`, `gitleaks`, `trivy`, `bandit`. Their
      categories — injection patterns, committed secrets, base-image CVEs — were
      covered by hand and by `ruff`'s `S` rules, which is thinner.

---

## Checked and clean

Recorded so nobody re-investigates:

- **No SQL injection.** Ruff flags `S608` twice; both are safe on inspection.
  `get_loss_reasons` takes its column from a static dict that raises `KeyError`
  on an unknown key; `get_leads` takes its table from a ternary over two
  constants. User input goes through bound parameters in both.
- **No secrets in history.** 293 commits, no `.env` ever committed, no
  `sk-ant-…`, `lrd_…`, `ghp_…` or private PEM anywhere.
- **Tenant filtering is explicit** on every Core select, including the ones that
  bypass the automatic loader criteria.
- **Zero `TODO` / `FIXME` / `XXX`** in `backend/app`.
- **Failure model is deliberate**: retries with backoff and jitter, `Retry-After`
  honoured, a fallback insight when Claude is unavailable, engine rebuilt per
  worker process after fork.
- **`anomaly_service.py` at 766 lines should not be split.** Five detection
  rules sharing thresholds, comparison windows and loss formulas. Splitting them
  across files makes them drift on the first threshold change. That length is
  cohesion.
