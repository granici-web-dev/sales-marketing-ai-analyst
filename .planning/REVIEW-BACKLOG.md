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

---

## Before the next deploy

- [ ] **Access token is readable by any script, and travels over plain HTTP.**
      `frontend/src/lib/api-client.ts`, `src/app/(auth)/login/page.tsx`.
      Set by client JS as `access_token=…; path=/; SameSite=Lax` — no `HttpOnly`,
      no `Secure`. One XSS anywhere on the page, including through a dependency,
      takes the whole token. Also diverges from the Phase 1 decision on record
      ("HttpOnly cookie + interceptor-based refresh"): the interceptor exists,
      the HttpOnly does not.
      *Fix:* access token in memory, refresh token in an `HttpOnly; Secure;
      SameSite=Strict` cookie set by the backend. If the cookie must stay, add
      `Secure` at minimum. Half a day, touches login and the API client.

- [ ] **The daily schedule can fail to register and say nothing.**
      `backend/app/tasks/celery_app.py:118`. The only registration site, wrapped
      in `except Exception: pass` with no log line. The comment promises the beat
      container registers it authoritatively — this *is* the code that runs
      there. Compose gates Redis health so the common start is covered, but a bad
      crontab, a redbeat incompatibility or a serialization failure disappears
      silently, and the product is the 04:00 run.
      *Fix:* `logger.exception("beat.schedule_registration_failed")` instead of
      `pass`. One line. This is also the only place in the codebase that breaks
      its own rule — the other 28 broad catches all log.

- [ ] **Two sources of truth for the tenant.** Eight endpoints in
      `dashboards.py`, `insights.py`, `health.py`, `sync.py` read
      `settings.sofa_belle_tenant_id`; the six in `chat.py` read the context var
      via `require_tenant_id()`. Every Celery task does it correctly.
      Harmless today (one tenant, both values equal) and a silent cross-tenant
      leak the moment Iteration 4 sets the context var from the JWT: chat will
      serve the right tenant, those eight will keep serving Sofa Belle. Same 200,
      wrong data.
      *Fix:* replace the eight with `require_tenant_id()`, then add a source scan
      that fails if `sofa_belle_tenant_id` appears under `app/api/`, the way the
      PII-in-logs check works. Mechanical, no behaviour change today. **Do it
      before the multi-tenancy work, not inside it** — inside, nobody will see it.

- [ ] **Python dependencies have never been checked.** `pip-audit` is not
      installed, so the backend got no dependency audit at all. The frontend had
      17 production advisories; the backend number is unknown.
      *Fix:* add `pip-audit` to the dev extras and run it. Minutes.

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
