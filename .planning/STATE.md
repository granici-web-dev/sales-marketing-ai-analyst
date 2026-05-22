# Project State

**Project:** Sales & Marketing AI Analyst
**Initialized:** 2026-05-19
**Current Phase:** Phase 2 — MEFI ETL
**Milestone:** Iteration 1 (MVP1: MEFI-only)

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-19)

**Core value:** Every morning, Sofa Belle gets a clear answer to "where are we losing money?" and 5–7 specific tasks for the day.
**Current focus:** Phase 2 — MEFI ETL

## Phase Progress

| Phase | Name | Status | Plans |
|-------|------|--------|-------|
| 1 | Foundation | ✓ Complete (2026-05-21) | 7/7 |
| 2 | MEFI ETL | ◐ In Progress (4/5 plans) | 4/5 |
| 3 | Metrics Engine | ○ Pending | — |
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
