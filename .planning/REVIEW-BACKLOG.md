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

- [x] **Dashboard date ranges are unbounded and unordered.** Both checks now sit
      in one `date_range` dependency in `app/api/deps.py`, shared by the three
      endpoints. Ceiling is 731 days — the widest button in the interface asks
      for 366, and two years leaves room for a year-on-year comparison through
      the API. Reversed dates were the worse half: they returned an empty chart
      rather than an error, so the reader saw "no data" where data exists.
      Three tests, each branch mutation-tested.

- [x] **MEFI request interval is roughly three times too fast.** Raised to 1.2 s.
      The docstring was wrong too, and that is why the value survived: it claimed
      the ceiling was 100 req/10 s, so 0.35 s looked like ample headroom instead
      of triple the real rate. Both corrected together.

- [x] **Eight transitive advisories remain**, all through `next` itself. Closed
      by waiting rather than overriding, which was the right half of the choice:
      `next` 16.2.11 → 16.3.1 stopped pinning `postcss@8.4.31` and `sharp@0.34.5`
      for itself. Production tree is now `postcss@8.5.23`, `nanoid@3.3.18`,
      `sharp@0.35.3` — trivy reports zero HIGH/CRITICAL. One LOW remains in
      `@babel/core`, below the gate.

- [x] **Two public methods exist only as aliases.** Deleted; the five test call
      sites use `compute_for_date`. Three of them carried
      `# type: ignore[attr-defined]` — the alias was invisible to mypy, so the
      compatibility it provided was never typed either.

- [x] **FastAPI dependency wiring lives in `core/`.** Moved to `app/api/deps.py`.
      Nothing under `app/core/` imports `app/db/` any more, so the `core ⇄ db`
      pair is gone. The new module also hosts `date_range`, which is where the
      range guard above belongs: both are request wiring.

- [x] **12 unused imports** in `app/`. Gone with the linter pass; `ruff check --select F401` is clean.

- [ ] **`_rate` is duplicated** across `daily_kpi_service` and
      `salesperson_kpi_service`. Two copies of division-with-a-zero-guard. Rule
      of three says wait; note it here so the third copy is noticed.

---

## Interface: Davoq portal world

Palette, fonts and the token layer were adopted from the Davoq engine portal on
2026-08-25, applied to the insights screen. What is left is the same move on the
remaining surfaces.

- [x] **Hard-coded colours on the other screens.** The count was low: 159
      theme-blind values across 35 files, not 35 colours. The bulk was not the
      Tailwind palette but the old shadcn zinc/blue set written as literal
      `hsl()` — 89 of them, largely in `ui/` primitives that every screen
      inherits, so fixing the dashboards alone would have left the theme broken
      in the same views. Substituted wholesale; `--chart-1…6` added because a
      six-series chart cannot be drawn from one accent. `src/__tests__/theme-tokens.test.ts`
      fails if any of it comes back — mutation-tested on both the palette and
      the bare-`hsl()` case, which the first version of the sweep missed.

      One claim in the old entry was wrong and worth recording: `badge.tsx` was
      already on tokens; its `bg-yellow-100` sits inside the comment explaining
      why the palette was not used.

- [x] **Card radius and shadow are now tokens; other primitives are not.** Done
      for `button.tsx` in the same pass — `rounded-control` on every size, and
      `shadow-card` instead of raw `shadow`. Inputs, selects and popovers still
      carry `rounded-md`; they read as controls either way, so this is no longer
      the mismatch it was.

- [ ] **PRODUCT.md and DESIGN.md were never captured.** `impeccable` ran under
      its scoped-refinement path because no product context exists. Every future
      design task will re-derive the same answers.
      *Fix:* `/impeccable init`, then `document` to write DESIGN.md from the
      tokens that now exist.

---

## Coverage gaps, not defects

- [ ] **Frontend coverage: 15.7% of lines, 89 of 109 files at zero.** Measured,
      not counted — `pnpm test:coverage`. The old entry said "6 test files
      against 85 source files"; the file ratio was never the number that
      mattered, and it was stale twice over.

      One pass has been made, aimed at consequence rather than percentage:
      `lib/engine-client.ts` and `hooks/useUrlDateRange.ts` are at 100%, and
      writing those tests turned up a live defect (see below). The percentage
      moved 13.4 → 15.7, which is the honest size of the change.

      Three passes done, 13.4 → 24.7. Each one turned up a live defect, which
      is the argument for aiming at consequence rather than percentage:
      `engine-client` 100%, `useUrlDateRange` 100%, `useSyncTrigger` 95%,
      `date-range-picker` 78%, `useConversations` 92%, `useInsights` 100%.

      The behavioural layer is now covered. What remains uncovered in
      `hooks/` and `lib/` is seven files of five to nine lines each — thin
      query wrappers with no branching worth pinning.

      What is left elsewhere is presentational: chart wrappers, insight cards,
      dashboard pages. Render tests there pin markup and break on every
      restyle — the theme pass would have broken a dozen of them.

      No coverage gate in CI: a threshold at 15% protects nothing, and a
      threshold that stops the build is a promise to keep raising it.

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

- [x] **Expired session showed clients an English error and left the screen
      dead.** Found while covering `engine-client.ts`. Eight action handlers
      across the portal — save, upload, verify, approve, sync, checkout — had
      no 401 branch at all, and three screens had none anywhere: they rendered
      `err.message`, which for `EngineUnauthorized` is our own string "engine
      session expired". A Romanian director got an English sentence out of our
      source and a screen that would never load. Actions are where this bites
      hardest: you open the screen, and press Save an hour later.

      All of it now goes through one `reportEngineError`, which is unit-tested
      properly; a source sweep keeps the next screen from being written without
      it. `unlock-panel` keeps its own answer — reloading mid-entry would carry
      away what the person was typing — and that exception is named in the test.

- [x] **The refresh button locked itself out permanently.** A 429 from
      `/sync/trigger` put the hook in `rate-limited`, and the button is disabled
      in that state — but nothing ever cleared it. `success` and `error` both
      auto-reset; this one was forgotten. The whole point of `Retry-After` is
      that the wait ends, so until the page was reloaded the client could not
      refresh data at all. Now it returns to idle after the header's seconds,
      and a non-numeric `Retry-After` (RFC allows a date) falls back to 60
      instead of rendering "NaNs".

- [x] **Dates shifted a day west of the meridian.** `new Date("2026-03-01")` is
      midnight *UTC*; formatted back through a local formatter it becomes
      `2026-02-28` anywhere west of Greenwich. Three places did it: `formatDate`
      (the label under the period button — what the client actually reads),
      the range picker's calendar state, and the revenue chart's axis labels.
      All now use `parseISO`. Invisible from Bucharest, which is why it lived;
      the suite now runs clean in both `Europe/Bucharest` and
      `America/New_York`, and the old code fails the existing `formatDate` test
      under the latter.

      Pinned by test: `formatDate`. Not pinned: the picker's calendar state and
      the chart labels — the calendar opens on the current month and marks
      nothing `aria-selected`, so the selection cannot be asserted, and the
      chart needs recharts in jsdom. Fixed by inspection, stated here rather
      than claimed as covered.

- [x] **Insight refresh waited ten seconds by the clock.** `useInsightsRefresh`
      slept a fixed 10s on the reasoning that "Claude generation typically takes
      6–8s", then invalidated the query. When it took longer, the page refetched
      the *previous* narrative and presented it as the new one — no error, no
      spinner, just yesterday's text under today's date. The engine already
      learned this on Drive sync, where the comment calls waiting by the clock
      the most common pilot failure.

      The refresh endpoint returns `pipeline_run_id` and `/api/v1/sync/status`
      takes any Celery task id, so it now polls for the task to actually finish
      — the same shape as the refresh button, which is already tested. On
      timeout it throws rather than claiming success.

- [ ] **The insights page never shows a failed refresh.** It reads `isPending`
      and the rate-limit payload and nothing else, so a thrown error just stops
      the spinner with no message. That was survivable while the mutation could
      not fail in practice; now that a timeout throws, it is a visible gap.
      Small: one `isError` branch beside the existing spinner.

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
