# Research Summary — Sales & Marketing AI Analyst

**Project:** Sales & Marketing AI Analyst (Sofa Belle pilot)
**Date:** 2026-05-19
**Synthesized from:** STACK.md, FEATURES.md, ARCHITECTURE.md, PITFALLS.md
**Overall confidence:** HIGH on stack, architecture, pitfalls; MEDIUM on AI-insight UX patterns (validate with pilot)

---

## Executive Summary

This is **not a generic BI dashboard** — it is a daily Romanian-language action plan for a non-analyst SMB owner, built on top of a classic medallion (raw → conformed → metrics → AI) data architecture. The pilot client (Sofa Belle) already tracks the exact same KPIs in Excel; the product's job is to mirror that structure 1:1, add anomaly detection, and let Claude Sonnet 4.6 turn the structured findings into 3 prioritised problems with 5–7 RON-quantified action items every morning. The competitive moat is the combination of Romanian-first output, domain-aware prompting (premium furniture, long cycle, mandatory showroom visit), and the discipline of computing every number deterministically before the LLM ever sees the data.

The recommended stack is largely a **refresh** of the existing `docs/STACK.md`: Python 3.12, FastAPI, SQLAlchemy 2.x async, Celery 5.6, PostgreSQL 16, Redis 7 are validated as-is, but several pre-existing decisions are stale and must change before Phase 1 — Next.js 14 → 16.2, React 18 → 19.2, Tailwind 3 → 4.3, and most consequentially **Tremor → shadcn/ui chart (Recharts v3)** because the `@tremor/react` package has been effectively abandoned since January 2025. The Celery Beat default file scheduler must be replaced with `celery-redbeat`, and the async/sync boundary in workers needs a per-forked-worker engine pattern that is currently not documented.

The biggest risks are not technical — they are **domain modelling and timezone**: deriving the Lead → Vizita → Oferta → Contract funnel from MEFI's *current* `status_id` (rather than "ever reached" history) will silently produce wrong conversion rates and trigger fake AI alarms; storing leads in UTC without `AT TIME ZONE 'Europe/Bucharest'` will assign Romanian evening leads to the wrong day, especially around DST. Both must be fixed in Phase 1 alongside the multi-tenancy seam (which is cheap to install now and prohibitively expensive to retrofit).

---

## Stack

**Validated stack (keep as-is):** Python 3.12, FastAPI, SQLAlchemy 2.x async, Celery 5.6, PostgreSQL 16, Redis 7, Pydantic v2, structlog, httpx.

**Critical changes required before Phase 1:**

| Decision | Change | Reason |
|---|---|---|
| `@tremor/react` → `shadcn/ui chart` (Recharts v3) | **CHANGE** | Tremor last shipped v3.18.7 on 2025-01-13 — abandoned. shadcn chart is actively maintained and targets Tailwind v4 |
| Next.js 14 → 16.2.6, React 18 → 19.2, Tailwind 3 → 4.3 | **CHANGE** | Next 14 is security-fix-only; shadcn `new-york-v4` registry requires Tailwind 4 |
| `claude-sonnet-4-5` → `claude-sonnet-4-6` | **CHANGE** | Fixed in PROJECT.md; still wrong in CLAUDE.md and docs/STACK.md |
| Default Beat file scheduler → `celery-redbeat` | **ADD** | File Beat loses schedule on restart, corrupts under concurrent writers |
| `asyncio.run()` per Celery task + per-worker engine init | **ADD** | Celery forks processes; sharing an async engine across fork is unsafe (SQLAlchemy 2.x docs) |

**New dependencies to add:**

| Package | Replaces / Why |
|---|---|
| `tenacity` | Retry logic for external API calls |
| `pyjwt[crypto]` | `python-jose` (last release 2023) |
| `psycopg[binary]` v3 | `psycopg2-binary` (Psycopg 3 is the current driver) |
| `bcrypt` | `passlib` (maintainer abandoned it in 2020) |
| `respx` | httpx test mocking |
| `sentry-sdk[fastapi,celery,sqlalchemy]` | Observability |

---

## Table Stakes

Must-have features for MVP1, grounded in Sofa Belle's existing Excel structure:

1. **Funnel visualization**: Lead → Vizita → Oferta → Contract with stage-by-stage conversion rates (the product's core view)
2. **Lead source breakdown**: 6 categories matching MEFI `source_id` exactly (Mail/FB/IG, Telefon, WhatsApp, Site, Designer, Alte)
3. **Salesperson leaderboard**: 6 reps with leads/visits/offers/contracts/revenue/win-rate
4. **Time-to-first-touch** with `< 4h` target indicator — the #1 owner pain point from SOFABELLE.md
5. **Daily AI Insights page**: top-3 problems + 5–7 action items in Romanian with RON-quantified impact
6. **Romanian-first UI**: `1.234,56 RON`, `DD.MM.YYYY`, locale `ro-RO`
7. **Date range picker** with YoY toggle; WoW/MoM/YoY delta indicators on every KPI card
8. **Stuck-offers widget**: offers with no activity > 14 days
9. **Data freshness banner**: stale-data warning + manual "Sync now" trigger
10. Loading/empty/error states on every chart and table

---

## Differentiators

What makes this worth paying for vs MEFI BI / Looker Studio:

- **Romanian-language AI insights with RON-quantified impact** — nobody else does this for Romanian SMB
- **Action-plan framing**: owner gets a to-do list with checkboxes, not a dashboard
- **Sofa Belle's Excel structure mirrored 1:1** → instant familiarity, zero learning curve
- **Domain-aware prompt**: premium furniture, long cycle, showroom-mandatory model baked into system prompt
- **Anomaly detection runs before LLM**: Claude gets pre-computed structured problems, never raw data → cheap, reproducible, no hallucinated numbers
- **Estimated loss in RON per problem**: SMB owners think in money, not percentages

**Explicit anti-features (do NOT build):** custom report builder, free-form AI chat, real-time dashboards, our own call transcription, lead-scoring ML, duplicating MEFI BI, editing CRM from our UI, per-salesperson logins in MVP1, PDF export in MVP1, configurable funnel stages until client #2.

---

## Watch Out For

**Top 6 critical pitfalls — all must be addressed in Phase 1:**

1. **Funnel from current `status_id`, not history** — a lead at Oferta no longer counts toward Vizita; L→V collapses → fake showroom-crisis AI alarms. Fix: "ever reached" semantics from status_id sets + best-effort `mefi_lead_history` from sync diffs.

2. **Redis visibility timeout < task runtime** — default 1h; MEFI initial sync runs 1–3h → duplicate worker execution. Fix: `visibility_timeout` ≥ 2× longest task, Redis `SET NX EX` application lock, `acks_late=True`.

3. **Timezone: MEFI UTC vs Europe/Bucharest** — Romanian evening leads land in wrong day; DST edge cases (last Sundays March/October). Fix: `TIMESTAMPTZ` everywhere, `AT TIME ZONE 'Europe/Bucharest'` in every group-by-day query, Celery Beat `timezone='Europe/Bucharest'` + `enable_utc=True`.

4. **`tenant_id` enforcement deferred → guaranteed Iteration 4 leak** — PROJECT.md says defer; CLAUDE.md mandates filtering. Fix: install `with_loader_criteria` event-listener seam in Phase 1 with hardcoded constant; Iteration 4 = one-line change. CI lint blocks raw `text()` SQL without tenant filter.

5. **Claude hallucinating numbers in narrative** — writes "scăzut cu 23%" when actual was 17%. Trust-killer. Fix: `client.messages.parse(output_format=DailyInsightResponse)`, every numeric claim is a typed Pydantic field computed by us, post-validation regex cross-check ±2%, regenerate on mismatch.

6. **Google Ads Developer Token 1–3 week review** — submit during Phase 1 even though integration is Iteration 2.

**Plus High:** tenant-specific MEFI enum IDs hardcoded → use `tenants.funnel_config JSONB`; `lifecycle="junk"` inflating leads → `v_leads_clean` view; Meta token expiry at 60 days; chart `"use client"` boundary mistakes; next-intl server/client timezone divergence.

---

## Build Order

Dependency-driven 8-phase sequence:

| Phase | Name | Why this order | Key deliverable |
|---|---|---|---|
| **A** | **Foundation** | All architectural decisions cost 10× to retrofit | Docker, FastAPI async, Celery+RedBeat, Next 16+shadcn, auth, i18n, `with_loader_criteria` seam |
| **B** | **MEFI ETL** | Highest-risk integration; everything depends on data | MEFI client, raw tables, **conformed views**, best-effort lead history, "ever reached" funnel logic |
| **C** | **Metrics engine** | Depends on B | `daily_kpi`, salesperson/source KPIs, Decimal-precise RON, junk-filtered totals |
| **D** | **Anomaly detection** | LLM input prerequisite | Rules engine, `detected_problems` rows, `estimated_loss_ron` |
| **E** | **AI insights** | Consumes `detected_problems` | `DailyInsightResponse` Pydantic schema, Romanian prompt, `messages.parse()`, post-validation, prompt caching |
| **F** | **Backend HTTP API** | Thin endpoints after B/C/D/E | `/dashboards/*`, `/insights/*`, `/healthz` |
| **G** | **Frontend dashboards** | Insights page LAST — highest design stakes | Overview → Sales → Salespeople → Marketing → **Insights** |
| **H** | **Polish & deploy** | Ship to Sofa Belle | Playwright E2E, Sentry, healthcheck task, Hetzner+Caddy |

---

## Key Decisions to Lock In Before Phase A

1. `with_loader_criteria` tenant seam installed in Phase A with hardcoded constant (not deferred to Iteration 4)
2. Single Celery `chain()` pipeline at 04:00 EEST — not 4 independent cron jobs
3. SQL conformed views (`v_leads`, `v_deals`, …) between raw tables and metrics — never query `mefi_*` from metrics or API code
4. TanStack Query `HydrationBoundary` server-prefetch + client-render pattern locked in on first dashboard PR
5. Funnel as "ever reached" from `tenants.funnel_config JSONB` — not "currently in"
6. shadcn `new-york-v4` registry; CI PR check blocks `@tremor/react` imports
7. `messages.parse(output_format=DailyInsightResponse)` for Claude — not hand-rolled JSON parsing
8. Per-worker async SQLAlchemy engine via `worker_process_init` signal — not module-level engine
9. `celery-redbeat` Beat scheduler
10. `tenant_id NOT NULL` on every table (enables future PostgreSQL Row-Level Security)

---

## Documentation Cleanup Required (Phase A)

- `CLAUDE.md` and `docs/STACK.md`: `claude-sonnet-4-5` → `claude-sonnet-4-6`
- `docs/STACK.md`: Tremor → shadcn/ui chart; Next 14/React 18/Tailwind 3 → Next 16/React 19/Tailwind 4
- `docs/ARCHITECTURE.md`: 4 independent cron jobs → single Celery `chain()` at 04:00 EEST
- `docs/ARCHITECTURE.md`: add per-worker async engine fork-safety pattern
- `CLAUDE.md`: note that `tenant_id` enforcement uses `with_loader_criteria` seam (not yet enforced, seam installed in Phase A)

---

## Open Questions for Phase Planning

1. Does MEFI plan to expose status-transition history (`/leads/{id}/history`)? If yes, request it now — eliminates best-effort approximation.
2. Does MEFI support webhooks? Would remove Redis visibility-timeout problem entirely.
3. Sofa Belle TikTok: `enums.md` warns TikTok leads land under `source_id=2 (Meta ADS)` — confirm with client before building TikTok integration.
4. Is `loss_reason` clean enough in MEFI today to power loss-reasons chart? If not, defer chart.
5. Funnel chart library choice: Recharts has no native funnel — `@nivo/funnel` vs custom SVG vs horizontal stacked bar?
6. Insight cadence preference: daily digest or weekly summary? Validate with owner week 1.
7. Owner comfort with AI naming specific salespeople in insights? Validate pilot week 1.
8. Action-completion tracking (persistent checkboxes on insight items) — schema implications; validate before designing.

---

*Research completed: 2026-05-19*
