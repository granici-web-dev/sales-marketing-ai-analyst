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

- [x] **Route protection is proved, in both halves.** The cheap half:
      `src/__tests__/proxy-location.test.ts` asserts `proxy.ts` sits beside
      `app/` and nowhere else, in a file that imports nothing from the app so
      the check does not depend on loading the thing it checks.
      `src/__tests__/route-protection.test.ts` enumerates every page under
      `(dashboard)` from the filesystem — a new protected page is covered
      without anyone remembering to add it — and drives `proxy()` directly.
      `PUBLIC_PATHS` is exported and its contents asserted, because widening
      that list is the one way to disable protection without touching a line
      of logic.
      The expensive half: `pnpm test:routes` (`scripts/route-protection.mjs`)
      boots the built app on a free port and asks it, 24 requests. This is the
      half that catches what the other cannot — the original bug was a
      perfectly correct function in a file Next never loaded.
      Both halves were seen red before being trusted: `proxy.ts` moved to the
      project root (11 protected paths answered 200, and `Proxy (Middleware)`
      vanished from the build output), the cookie check deleted, the matcher
      narrowed, `/marketing` added to `PUBLIC_PATHS`, and `/login` rewritten to
      a locale that does not exist — the last reproducing the next-intl bug and
      caught only by the request half.

- [x] **Linking a client is a command, not a comment.** `python -m app.cli
      tenants list | link <slug> <uuid> [--force] | unlink <slug>`. The step
      used to be a `UPDATE tenants SET engine_tenant_id = …` written in a
      docstring, and a comment cannot refuse anything. The command refuses to
      point one engine tenant at two clients (that would let one client's login
      land in another's data) and refuses to move an existing link without
      `--force`. It is idempotent: re-linking to the same value says so and
      changes nothing.
      Every query against `tenants` — the login lookup, the startup count, the
      command — now lives in `services/tenants/directory.py`, so the one place
      that must bypass the ORM isolation gate is documented once instead of
      three times.
      On startup the backend logs how many tenants are unlinked, with the
      command to fix them; a database that is down is logged, not swallowed,
      and does not stop the app. Five mutations seen red: a taken engine tenant
      allowed, a link replaced without `--force`, `count_unlinked` counting
      everything, the warning without its command, and the failure path made
      silent. 589 tests with a database, up from 572.
      The README's `# Create first admin user (script will be added later)`
      went with it — that module was never written and never will be, because
      password login is gone.

- [x] **Theme switch.** Three states, not two: "as the system does" is a choice
      too, and it is the default. Remembered in the browser, not the database —
      it is a property of the desk, not the account. Applied before first paint
      by an inline script, or a dark-theme user gets a flash of light on every
      navigation. It came across from the engine panel, which had it; deleting
      the panel without it would have taken a working thing away.

- [x] **CI exists.** `.github/workflows/ci.yml`, two jobs. Backend: ruff,
      `ruff format --check`, mypy, `alembic upgrade head`, pytest against a
      postgres and a redis service. Frontend: eslint, tsc, vitest, `next build`,
      with `--frozen-lockfile`. It was made green before it was switched on:
      a gate that arrives red teaches people to stop reading it.

- [x] **54 `noqa` markers suppressed rules that were not enabled.** `BLE` is on,
      so its 28 markers now mean something. `PLC0415` is off *by name*: deferred
      imports are the design here (INFRA-05, fork safety), 442 of them are
      deliberate, and the rule asks for the opposite — its 97 markers became
      plain comments. `RUF100` is on, which is the systemic fix: a marker that
      outlives its rule is now itself an error.

- [x] **Linter output was 1 033 lines; it is 0.** 589 of them were `E402` caused
      by `from __future__ import annotations` sitting *above* the module
      docstring in 130 of 200 files — which meant those modules had no docstring
      at all, only an inert string expression. Real docstrings went 22 → 151.
      `B008` is ignored with a note (it is `Depends()`); `E501` is ignored
      because `ruff format` owns line length for code and what remains is
      Romanian prompt text and SQL. The formatter ran once over 102 files;
      that revision is in `.git-blame-ignore-revs`.

- [x] **`mypy` was declared `strict` and not installed.** 212 errors on first
      run, now 0. The clusters: `Tool` declared its handler as taking any
      `BaseModel` (callable parameters are contravariant — it claimed one tool's
      handler could be called with another's input); eight signatures said
      `object` where a real type existed; `Result.rowcount` where DML returns a
      `CursorResult`; plain dicts where the Anthropic SDK has parameter types.
      One relaxation kept and named: `disallow_any_generics` off, 138 bare
      `dict`/`list` annotations, a breadth debt rather than a defect.

- [x] **39 integration tests had never run; 24 of them failed.** Found by
      standing up the database for CI. A module-scoped async engine against
      function-scoped event loops; a `get_current_user` override that identified
      the user but never set the tenant; raw SQL against three columns that never
      existed; an async test calling a Celery task that does `asyncio.run()`
      internally. Two tests asserted things the code contradicts on purpose,
      and the code was right both times. With a database: 572 pass, 3 skip.

- [x] **`pnpm-lock.yaml` had drifted.** It still listed `jose`, removed from
      `package.json` when the token went. `--frozen-lockfile` caught it on the
      first run — before the workflow was ever pushed.

---

## Before the next deploy

Empty. Both items are in *Done* above.

---

---

## Before CI can be trusted

Done. All four, plus what the work uncovered — see *Done* above for the detail.

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

- [x] **Eight transitive advisories remain**, all through `next` itself. Closed
      by waiting rather than overriding, which was the right half of the choice:
      `next` 16.2.11 → 16.3.1 stopped pinning `postcss@8.4.31` and `sharp@0.34.5`
      for itself. Production tree is now `postcss@8.5.23`, `nanoid@3.3.18`,
      `sharp@0.35.3` — trivy reports zero HIGH/CRITICAL. One LOW remains in
      `@babel/core`, below the gate.

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

- [x] **12 unused imports** in `app/`. Gone with the linter pass; `ruff check --select F401` is clean.

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

- [ ] **The Playwright spec has never run, and its premise is gone.**
      `frontend/tests/e2e/chat.spec.ts` exists; Playwright is not in
      `package.json`, so `pnpm test:e2e` does not exist either. Its own header
      says plan 08-06 would install it; 08-06 shipped and it never did. Worse,
      the contract it documents starts "user logs in with seeded test
      credentials" — password login was removed, identity comes from the engine
      now, so the spec could not pass even with Playwright installed.
      *Fix:* rewrite it around an engine session cookie and install Playwright,
      or delete it. A test file nobody can run reads as coverage that is not
      there, and this one also documents a login that no longer exists.
      Note the route-protection half of what e2e was for is now covered by
      `pnpm test:routes`, which needs no browser.

- [ ] **No query plans measured.** `EXPLAIN ANALYZE` needs a database with real
      data and the stack was not running. Indexes exist on every tenant-scoped
      table; whether the funnel queries use them at volume is unverified.

- [x] **Tools that never ran:** `semgrep`, `gitleaks`, `trivy`, `bandit`. Now in
      `.github/workflows/security.yml`, three jobs, weekly schedule. What they
      found on the first run: ten HIGH dependency CVEs (fixed), both Dockerfiles
      running as root (fixed), a `.dockerignore` that kept the lockfile out of
      the image (fixed), five unpinned action tags (pinned), and the seeded admin
      password (migration 011). The two `S608` spots below were confirmed safe
      by two scanners independently and are now suppressed with the reason
      inline.

- [x] **pnpm 9 → 10.** Done: `10.34.5`, pinned once in `packageManager` and read
      from there by CI, the image and corepack. All three hardening settings are
      live in `frontend/pnpm-workspace.yaml` and each was mutation-tested. The
      cooldown bites immediately and correctly: `next` sits on `16.3.1` rather
      than `16.3.3`, because 16.3.3 was published a day earlier than the install
      — the CVE that prompted the bump is fixed in both.

- [ ] **The control set still needs Bedrock keys**, so it is not in CI. Its
      corpus is reproducible now (`npm run seed:control` in the engine repo)
      and it runs on any machine rather than the one holding the pilot's
      materials — but fifteen model calls per push is a real bill.

---

## Checked and clean

Recorded so nobody re-investigates:

- **No SQL injection.** Ruff flags `S608` twice; both are safe on inspection.
  `get_loss_reasons` takes its column from a static dict that raises `KeyError`
  on an unknown key; `get_leads` takes its table from a ternary over two
  constants. User input goes through bound parameters in both.
- **No secrets in history.** 293 commits by hand; since confirmed by gitleaks
  over all 333 commits — zero findings. The engine repo has one, a public widget
  key, allow-listed with the reason in `.gitleaksignore` there.
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
