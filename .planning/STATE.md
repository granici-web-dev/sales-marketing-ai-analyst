# Project State

**Project:** Sales & Marketing AI Analyst
**Initialized:** 2026-05-19
**Current Phase:** Phase 3 — Metrics Engine
**Milestone:** Iteration 1 (MVP1: MEFI-only)

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-19)

**Core value:** Every morning, Sofa Belle gets a clear answer to "where are we losing money?" and 5–7 specific tasks for the day.
**Current focus:** Phase 3 — Metrics Engine

## Phase Progress

| Phase | Name | Status | Plans |
|-------|------|--------|-------|
| 1 | Foundation | ✓ Complete (2026-05-21) | 7/7 |
| 2 | MEFI ETL | ✓ Complete (2026-05-23) | 5/5 |
| 3 | Metrics Engine | ◆ In progress | 3/4 |
| 4 | Anomaly Detection | ○ Pending | — |
| 5 | AI Insights | ○ Pending | — |
| 6 | Backend HTTP API | ○ Pending | — |
| 7 | Frontend Dashboards | ○ Pending | — |
| 8 | AI Chat | ○ Pending | — |
| 9 | Polish & Deploy | ○ Pending | — |

## Blockers

None currently.

## Key Decisions Made

- Single-tenant first (MVP1-3): tenant_id in schema, enforcement seam in Phase 1
- claude-sonnet-4-5 for AI insights and chat (per SPEC.md)
- shadcn/ui chart (Recharts v3) replacing Tremor
- Next.js 16.2, React 19.2, Tailwind v4.3
- celery-redbeat replacing default Beat file scheduler
- Celery chain() for daily pipeline (not 4 independent cron jobs)
- "Ever reached" funnel stage logic (not "currently in")
- AI Chat (Phase 8): FastAPI StreamingResponse + Anthropic async client + Tool Use — documented exception to batch-only Claude rule; reuses Phase 6 metric services as tool backends
- claude-sonnet-4-5 for both batch insights (Phase 5) and interactive chat (Phase 8) — per SPEC.md and docs/CHAT.md
- Phase 1 auth: HttpOnly cookie + interceptor-based refresh + Next.js middleware route protection
- Phase 1 tenancy: hardcoded Sofa Belle UUID at startup (context var), with_loader_criteria seam, Alembic data migration for seed data
- Phase 1 Docker: separate worker + beat + flower containers, depends_on with service_healthy
- Phase 1 frontend: full shell layout with all 8 nav items from SPEC §13.1, next-intl with Romanian strings from day 1

**Last session:** 2026-05-21 — Phase 1 complete ✓. Known issue: KI-01 CSS/Tailwind not loading (fix in Phase 7 or parallel). Advancing to Phase 2 MEFI ETL.

**2026-05-21 session:** Phase 2 context gathered. Key decisions: store all lifecycle states (active/lost/junk) in raw_mefi_leads, two conformed views (v_mefi_leads_active + v_mefi_leads_junk), auto-detect backfill on first sync, auto-upsert salespeople, new Alembic migration 003 for funnel_config JSONB.

**2026-05-23 session:** Phase 2 APPROVED COMPLETE. 1000/1155 leads ingested (KI-02: burst rate limit on initial backfill — remaining 155 will be picked up by nightly syncs over a few days; deferred fix to Phase 9). All success criteria met: UPSERT idempotent, rate-limit detection+retry working, async event loop bug fixed, custom fields extracted. Advancing to Phase 3 — Metrics Engine.

**2026-05-25 session:** Phase 3 context gathered. Key decisions: 7 source categories (funnel_config names + google), time_to_first_touch from mefi_lead_history first status change with business-hours adjustment (Mon–Sun 09:00–19:00 Bucharest), full SPEC.md §7 schema with nullable ad-spend columns, calculate for yesterday with NULL deltas on missing prior data, date-parameterizable task for backfill. Resume file: .planning/phases/03-metrics-engine/03-CONTEXT.md

**2026-05-25 session (continued):** Phase 3 planning complete. 4 plans in 4 waves: Wave 0 (test stubs), Wave 1 (migration 004 + models), Wave 2 (metric services + MetricsRepository), Wave 3 (calculate_daily_kpis Celery task + chain). All 6 METR requirements covered. Status: Ready to execute.

**2026-05-25 session (03-01 executed):** Phase 3 Plan 01 (Wave 0 test stubs) COMPLETE. 9 files created: 8 RED-state test files + metrics factory. All acceptance criteria met.

**2026-05-26 session (03-02 executed):** Phase 3 Plan 02 (schema foundation) COMPLETE. Migration 004 + 3 SQLAlchemy models + metrics package. 24 Wave 0 model/migration tests GREEN.

**2026-05-26 session (03-03 executed):** Phase 3 Plan 03 (service layer) COMPLETE. 6 files: business_hours util, DailyKpiService, SalespersonKpiService, SourceKpiService, MetricsRepository, services/metrics/__init__.py. 40/40 service layer tests GREEN. Advancing to Plan 04 (calculate_daily_kpis Celery task + pipeline chain).
