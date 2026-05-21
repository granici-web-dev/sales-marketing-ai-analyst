# Phase 2: MEFI ETL - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-21
**Phase:** 02-MEFI ETL
**Areas discussed:** Raw storage scope, Backfill trigger, Salesperson list & showroom, Funnel config migration

---

## Raw Storage Scope

| Option | Description | Selected |
|--------|-------------|----------|
| All 3 lifecycles (active + lost + junk) | Pull everything from MEFI, store in raw, filter in views | ✓ |
| Active + lost only | Exclude junk at API level (filters.lifecycle=["active","lost"]) | |

**User's choice:** All 3 lifecycles
**Notes:** Complete audit history valued over storage savings. If MEFI reclassifies a junk lead to active, the early history is preserved.

---

## Separate junk view

| Option | Description | Selected |
|--------|-------------|----------|
| Separate junk view (v_mefi_leads_junk) | v_mefi_leads_active + v_mefi_leads_junk as separate views | ✓ |
| One active view only | v_mefi_leads_active only; junk% computed from raw table directly | |

**User's choice:** Separate junk view
**Notes:** ANOM-07 (junk% > 20% alert) needs a clean junk view. Two views keep metric logic consistent — never query raw directly.

---

## Backfill Trigger

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-detect on first sync | sync_mefi_leads checks if raw_mefi_leads is empty → enqueues backfill | ✓ |
| Manual task call | Developer runs celery call app.tasks.etl.backfill_mefi_leads explicitly | |

**User's choice:** Auto-detect on first sync
**Notes:** Zero-friction production deploy. No runbook step to forget.

---

## Backfill Chunk Granularity

| Option | Description | Selected |
|--------|-------------|----------|
| Full calendar months, current month separate | 12 complete prior months; partial current month via incremental | ✓ |
| Rolling 365-day window in 30-day chunks | More precise date math; overlap management needed | |

**User's choice:** Full calendar months, current month separate
**Notes:** Simpler date arithmetic; clean boundary between backfill and incremental sync.

---

## Salesperson List & Showroom

| Option | Description | Selected |
|--------|-------------|----------|
| Seed known mapping now | Provide 6 active IDs + showrooms now; seed in migration | |
| Import all 11, mark active/showroom in DB | Auto-upsert all observed IDs; manually set is_active + showroom after first sync | ✓ |
| Defer to Phase 7 | Store assigned_to as-is; Salespeople dashboard handles mapping | |

**User's choice:** Import all 11, mark active/showroom in DB
**Notes:** Flexible — doesn't require knowing the exact 6 now. Post-first-sync manual update is a one-time operation. Phase 3 metrics filter on is_active=true.

---

## Salesperson Auto-Upsert

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-upsert during sync | INSERT ... ON CONFLICT DO NOTHING for each unique assigned_to ID seen | ✓ |
| Separate setup task | ETL task only touches lead data; salesperson table populated separately | |

**User's choice:** Auto-upsert during sync
**Notes:** Self-maintaining — new users in MEFI appear automatically after next sync.

---

## Funnel Config Migration

| Option | Description | Selected |
|--------|-------------|----------|
| New Alembic migration 003 | Phase 2 adds 003_seed_funnel_config.py; 002 untouched | ✓ |
| Amend Phase 1's 002 | Update existing 002_seed_sofabelle.py | |
| Python constants at sync time | Hardcoded dict in ETL task code | |

**User's choice:** New Alembic migration 003
**Notes:** Consistent with D-07 from Phase 1 (all seed data via Alembic). Phase 1 migrations untouched — safe for any already-applied environments.

---

## Funnel Config JSONB Scope

| Option | Description | Selected |
|--------|-------------|----------|
| One JSONB for all mappings | funnel_config stores funnel_stages + source_categories + lifecycle_filter + showroom field | ✓ |
| Separate source_config column | funnel_config for stages only; source_config for source→category | |

**User's choice:** One JSONB for all mappings
**Notes:** Single config home per MEFI-07 spirit. One column to update when onboarding a new MEFI client.

---

## Claude's Discretion

- Exact schema for `raw_mefi_leads`, `mefi_lead_history`, `mefi_salespeople` tables — researcher and planner derive from SPEC.md §7 + API docs
- `MefiClient(BaseIntegration)` method signatures and retry logic — standard patterns per CLAUDE.md + docs/INTEGRATIONS.md
- Conformed view SQL — planner writes based on funnel_config values from enums.md

## Deferred Ideas

- Webhook ingestion for real-time updates — future when MEFI supports it
- Multi-tenant `funnel_config` UI for onboarding new clients — Iteration 4
- Call data (transcripts, sentiment) — future when MEFI API expands
