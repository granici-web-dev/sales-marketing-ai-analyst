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

- [x] **PRODUCT.md and DESIGN.md were never captured.** Written, by hand rather
      than by `impeccable` — the tool is not installed here, and most of what it
      would have asked already exists: `SPEC.md` §1 has the product concept and
      `docs/SOFABELLE.md` the pilot client. Restating those would have made a
      third place to keep in sync.

      What was genuinely missing: the product picture *after* the two products
      merged into one cabinet — `SPEC.md` still describes the analyst as
      standalone with its own login — and the design system, which existed only
      as comments scattered across individual components.

- [x] **The base Button is 36 px tall; the 44 px touch target is added by hand.**
      Done, in the primitive. `Button` is `h-11` at every size (`lg` 48,
      `icon` `size-11`), `Input` the same. The size scale now varies weight —
      padding and type size — not the target: a finger is the same size on
      every button, and `sm` is still the compact one.

      Two counts in the old entry were wrong, and the correction is the
      interesting part. Of the 26 manual overrides only **seven** sat on
      `<Button>`; the other 19 are hand-rolled `<button>`, `<Link>` and
      `CollapsibleTrigger` that the primitive cannot reach. But the miss was
      wider than "roughly a third": `size="sm"` is 32 px and 27 of the 44
      buttons use it, so 37 of 44 were under the floor.

      `Input` came along because it had to. It was `h-9` too, and it stands in
      a row with a button (`knowledge.tsx` — the page address and "Add"):
      raising the button alone would have fixed the target and broken the row.
      Four hand-styled `h-9` controls in the portal — two selects, a colour
      swatch, an HTTP-method select — went with them for the same reason, and
      the insights date input moved onto `<Input>`, which is what
      `conversations.tsx` already did with its date fields.

      Proved in both halves, like route protection. The cheap half reads the
      rendered class list — jsdom does not compute Tailwind, so the classes are
      converted to pixels on Tailwind's own scale — and a source sweep fails if
      markup starts writing the floor back on top of `Button` or `Input`, since
      an override in markup means the primitive is not providing it. The
      expensive half measures `boundingBox()` in the built app on `/login`,
      which needs no session and holds both primitives side by side. Seven
      mutations seen red: each of the four sizes lowered, the icon's width,
      `Input` lowered, and an override re-added at a call site — the browser
      half reported `36`, which is exactly the number the class-reading half
      cannot see.

      What is not covered: the 19 hand-rolled controls hold their own 44 px,
      and a *new* one written below the floor would pass. Detecting that from
      source is not reliable — heights under 44 px are legitimate everywhere
      for icons, dividers and skeletons, so a blanket sweep would be noise.
      What can be owned is the primitive, and it is.

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

- [x] **The Playwright spec has never run, and its premise is gone.** Rewritten
      and turned on. It authenticates with a session cookie — `proxy.ts` checks
      only that `aw_session` is present, since the value is opaque and the real
      check runs on the backend at every data request — so no password login is
      involved, which is what made the old spec unrunnable.

      What it earns its keep for: jsdom cannot stream a response body, and the
      bot's answer arrives over SSE in pieces that append into one bubble. Two
      chunks, deliberately, so replacing rather than appending fails. Both
      mutations — replace-instead-of-append, and ignore chunks entirely — kill
      it. The engine and the backend are stubbed: with them this would be a
      full-stack run costing real model calls per push, and it would no longer
      be testing rendering.

      A stub engine had to come with it. The dashboard shell asks the engine
      for entitlements *server-side*, and `page.route` never sees those — they
      leave Next, not the browser. It answers exactly the two paths the shell
      reads and 404s everything else, so a third request cannot slip in unseen.

      In CI after the build, chromium only. `tests/e2e` is no longer excluded
      from `tsconfig`, so the spec is typechecked like everything else.

- [x] **Query plans measured.** Full write-up in `docs/QUERY-PLANS.md`;
      reproducible from `backend/scripts/load-fixture.sql` and
      `backend/scripts/query-plans.py`. Measured on synthetic volume — 51
      tenants, 640k leads, 1.9M history rows — because the pilot has ~1 200
      leads and Postgres correctly prefers a sequential scan below a few
      thousand rows, so "the index is not used" on a test database means
      nothing.

      The question was not "is it fast for the pilot" — it is. This is a
      multi-tenant product, so the question was whether one tenant's dashboard
      reads the other tenants' rows. **It does not.** `v_mefi_leads_active`
      contains a subquery over the whole history table with no WHERE at all,
      which reads as if every dashboard folds 1.9M rows; the planner pushes
      `tenant_id = $1` inside the GROUP BY (it may — tenant_id is a grouping
      key) and touches 120k. Recorded in *Checked and clean* below so nobody
      investigates it twice.

      What the measurement did turn up is where the time actually goes: **the
      sales dashboard spends 115 ms in the database and 112 of them on one
      query** — stuck offers, 97%. It reads `mefi_lead_history` twice, once
      inside the view and once as an outer join for `MAX(changed_at)`: the
      same 120k rows, 2 410 pages each, 83% of the query's buffers.

      Two changes follow, with numbers rather than opinions. Neither is
      applied — the item was to measure, and both are their own decision.

- [x] **Stuck offers: read the history once, not twice.** Done, but not the
      way it was measured. Folding the aggregate into a CTE inside the service
      would have needed no migration — and would have carried `IN (3, 1)` out
      of the view and into the service. That definition of "reached the offer"
      lives in the view and only there, and the funnel is per-tenant config
      (`tenants.funnel_config`); a second home for the same constant costs more
      than one migration.

      So `MAX(changed_at)` is computed where the `BOOL_OR`s already are — the
      history is folded there anyway, and one more aggregate in that fold is
      free — and arrives as `last_history_change_at` (migration 012). The
      service query then needs no second join to the history, no outer
      `GROUP BY`, and no `::text` casts.

      Measured on the same stand after migrating: inside the sales dashboard
      112 ms → 68–80, standalone 88–101 → 49.5–51.3, buffers 5 794 → 3 399.
      Equivalence re-asked on the new view: 32 179 rows both sides, `EXCEPT ALL`
      zero in both directions. In the plan the history is one `HashAggregate`,
      and the salespeople join is now a nested loop with `Memoize` on
      `assigned_to_id` — precisely what the casts had been preventing.

      Two things fell out. `AND v.lifecycle NOT IN ('junk')` was a tautology —
      the view emits only `'active'` and `'lost'` — and survived because nothing
      checked it. And `ORDER BY days_stuck DESC` had no tiebreaker, so which
      fifty offers a person saw was undefined among equal values; `,
      v.external_id` added in the same pass.

      The SQL had no test at all: the one test on `get_stuck_offers` mocked
      `session.execute` and knew nothing about the query. Now
      `tests/integration/test_stuck_offers.py` seeds one lead per branch —
      offer by status, by flag, by history only, no history at all, lost,
      recent, never reached, junk, another tenant — against a real database.
      Written against the OLD query and seen green on it first, because a test
      written after the change describes the intention rather than the
      behaviour. Seven mutations killed on both versions.

      Row estimates are still 3–4× low (9 179 planned, 32 179 actual). Benign
      today — the hash joins chosen are right — and exactly the kind of
      underestimate that flips a planner into a nested loop. Left as is,
      noted here.

- [ ] **`raw_mefi_leads` has no index on the date it is filtered by.** Both
      marketing queries filter `(tenant_id, created_at_source)` and only
      `tenant_id` is indexed, so the planner reads all 40 000 of the tenant's
      leads and discards 31 704 after the fact. With the composite index:
      1.27–1.43 ms against 2.72–3.08 ms, six runs each, 6.6 MB for 640k rows.
      A millisecond and a half is not a reason to add an index — writes pay for
      it. The shape is: without it the work is proportional to *all* of the
      tenant's leads ever, with it only to the window. At the pilot's 1 200
      leads there is no difference at all; at 400 000 it is 29 ms against 2.

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

- [x] **The control set is in CI** — nightly and on a button, not on every
      commit. `.github/workflows/control-set.yml` in the engine repo.

      A separate workflow rather than a step in `ci.yml`, because a model's
      answer is not deterministic: the same question twice gives different
      words, and the set checks meaning, not a string. A gate that sometimes
      goes red through no fault of the commit stops being read — the same
      reasoning already written in `ci.yml` about arriving red. A fork's pull
      request cannot reach the secrets either, so such a step would fail on
      every fork. Hence two triggers: nightly, which catches drift on the
      model's side that no commit of ours caused, and manual before a deploy,
      where `--only` can take a subset.

      The stand is the one from `docker-compose`: `pgvector/pgvector:pg17` and
      redis. Two database roles, not one — the owner `app` for migrations and
      `assistwidget_app` for everything else. RLS does not apply to the owner,
      so a run under it would be testing a configuration that exists nowhere.
      `.env.example` points both at the owner; that is a development
      convenience and there was no reason to carry it into CI.

      Rehearsed rather than sketched: the whole sequence ran on a throwaway
      database from empty — migrations, corpus (3 documents, 20 chunks),
      engine under tsx, the set. 15/15, exit 0, and the working database with
      the pilot's material was not touched. Measured cost per run: fifteen
      Haiku calls plus three embeddings, a few cents.

      Two things the rehearsal turned up. `--env-file=.env` fails on a missing
      file, and CI has no `.env` — both control scripts moved to
      `--env-file-if-exists`, which is how `env.ts` already treats it and what
      two other scripts already did. And the first draft interpolated
      `${{ inputs.only }}` straight into the shell command; the repo's own
      semgrep caught it as `run-shell-injection`. Checked both ways: one
      finding with the interpolation, zero when the value goes through the
      environment.

      Still needed from the owner: `AWS_ACCESS_KEY_ID` and
      `AWS_SECRET_ACCESS_KEY` as repository secrets, scoped to
      `infra/bedrock-policy.json`. Without them the run fails on the first
      step with that sentence rather than after three minutes of install.

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

- [x] **The insights page never shows a failed refresh.** Done. The timeout is
      its own error type rather than a string to match on, so the page can say
      "generation did not finish, the text below is the previous one" — which is
      the part that matters: the old narrative stays on screen either way, and
      without a word it reads as fresh. Other failures get a different sentence;
      neither shows the English message from our own code.

      Three neighbouring strings were hardcoded Romanian in the same block
      ("Astăzi", the load-error text and its retry button) — translated in the
      same pass, since an English-locale reader was getting Romanian there.

- [x] **A missing translation in one locale was not caught by anything.** The
      ICU test iterates each dictionary on its own, so deleting a key from
      `en.json` simply produced one test fewer and a green run. On screen that
      is the key path rendered instead of the sentence — next-intl reports to
      `onError` and returns the path rather than throwing. Two parity checks
      added, both mutation-tested in each direction.

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
- **Tenant isolation holds at volume, including through the view.** The
  unfiltered `GROUP BY` subquery inside `v_mefi_leads_active` does not fold
  other tenants' history: the planner pushes the tenant predicate inside it.
  Verified by `EXPLAIN ANALYZE` at 1.9M history rows across 51 tenants —
  120 000 rows touched, not 1 920 000. See `docs/QUERY-PLANS.md`.
- **`anomaly_service.py` at 766 lines should not be split.** Five detection
  rules sharing thresholds, comparison windows and loss formulas. Splitting them
  across files makes them drift on the first threshold change. That length is
  cohesion.
