# Project State

**Project:** Sales & Marketing AI Analyst
**Initialized:** 2026-05-19
**Current Phase:** Phase 1 — Foundation
**Milestone:** Iteration 1 (MVP1: MEFI-only)

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-19)

**Core value:** Every morning, Sofa Belle gets a clear answer to "where are we losing money?" and 5–7 specific tasks for the day.
**Current focus:** Phase 1 — Foundation

## Phase Progress

| Phase | Name | Status | Plans |
|-------|------|--------|-------|
| 1 | Foundation | ◐ Context | — |
| 2 | MEFI ETL | ○ Pending | — |
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

**Last session:** 2026-05-20 — Phase 1 context gathered (.planning/phases/01-foundation/01-CONTEXT.md)
