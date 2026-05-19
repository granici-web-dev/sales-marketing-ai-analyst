# Sales & Marketing AI Analyst

## What This Is

A SaaS platform for Romanian SMB businesses that collects data from MEFI CRM,
Meta/Google/TikTok Ads, GA4, and Google Search Console — then every morning
generates an AI-powered insight report in Romanian with a concrete action plan.

Pilot client: **Sofa Belle** — premium furniture manufacturer, 3 showrooms, 6 salespeople, average deal 20,000+ RON.
Target market: Romanian SMBs using MEFI CRM (10-100 employees).

## Core Value

Every morning, Sofa Belle gets a clear answer to "where are we losing money?" and
a 5-7 specific tasks for the day — not raw charts, but decisions ready to act on.

## Requirements

### Validated

(None yet — ship to validate)

### Active

#### Infrastructure & Foundation
- [ ] Docker Compose dev stack (PostgreSQL, Redis, FastAPI, Celery, Next.js)
- [ ] FastAPI backend with async SQLAlchemy, Pydantic v2, structlog
- [ ] Next.js 14 frontend with TailwindCSS, shadcn/ui, Tremor
- [ ] PostgreSQL schema with tenant_id on every table (enforcement deferred to Iteration 4)
- [ ] Celery + Celery Beat for scheduled tasks

#### Authentication
- [ ] Basic JWT authentication (single-tenant, hard-coded Sofa Belle seed data)
- [ ] Protected dashboard routes in Next.js

#### MEFI Integration (ETL)
- [ ] MEFI /leads API client (API key: lrd_* in .env)
- [ ] Nightly sync at 03:00 Romania time → raw_leads table
- [ ] Sales funnel derivation from lead statuses + custom fields (Vizita → Oferta → Contract)
- [ ] Celery task with idempotent retry logic

#### Metrics Calculation
- [ ] Daily KPI calculation from raw leads (daily_kpi, salesperson_daily_kpi, source_daily_kpi)
- [ ] Funnel conversion rates: L→V, V→O, L→O, O→C, L→C
- [ ] Cost per lead, CAC, ROAS (ad spend data deferred to Iteration 2)
- [ ] Anomaly detection rules for stuck leads, missed calls, slow response time

#### Sales Dashboard
- [ ] Funnel visualization (Lead → Vizita → Oferta → Contract)
- [ ] Conversion rates with WoW/MoM comparison
- [ ] Lead source breakdown (Mail/FB/IG, Telefon, WhatsApp, Site, Designer, Alte)
- [ ] Revenue tracking (Încasări, Cec mediu)

#### Salespeople Dashboard
- [ ] Per-salesperson KPIs: leads handled, visits scheduled, offers sent, contracts closed
- [ ] Time-to-first-touch metric (< 4h target)
- [ ] Performance comparison across 6 salespeople

#### Marketing Dashboard (MVP1 without ad spend)
- [ ] Lead volume by source over time
- [ ] Site conversion rate (leads / sessions — sessions from MEFI approximation)
- [ ] Placeholder structure ready for ad spend data (Iteration 2)

#### AI Insights
- [ ] Daily insights generator Celery task at 06:00
- [ ] Claude Sonnet 4.6 integration with structured prompt (anomalies + business context)
- [ ] JSON-parsed response: top-3 problems + 5-7 action items in Romanian
- [ ] Insights page in frontend with daily report + action plan

#### UI/UX
- [ ] Romanian primary language, English secondary
- [ ] Responsive design for desktop and tablet
- [ ] Dark/light mode (optional)

### Out of Scope

- Meta/Google/TikTok Ads API integration — Iteration 2
- GA4 / Google Search Console integration — Iteration 3
- Multi-tenancy enforcement (SQLAlchemy event listeners, JWT tenant claim, isolation tests) — Iteration 4
- Tenant onboarding flow and Stripe billing — Iteration 4
- Email digest / push notifications — future iteration
- Call transcription — handled by DOTRO MonitorAI (not our responsibility)
- Showroom-level analytics (requires IP telephony not yet deployed)
- Benchmarks between clients — after 5+ clients
- Mobile app, Telegram/WhatsApp bot, forecasting — backlog

## Context

**MEFI API status:** API key `lrd_*` is in `.env` as `MEFI_API_KEY`. Full API docs are at
`docs/api-references/mefi/`. MEFI currently only exposes `/leads` — the sales funnel
(Vizita → Oferta → Contract) must be derived from lead statuses and custom fields.
See `docs/api-references/mefi/enums.md` for the complete mapping.

**Existing documentation:** The project has a 70KB SPEC.md, ARCHITECTURE.md, STACK.md,
CONVENTIONS.md, INTEGRATIONS.md, and SOFABELLE.md. All planning agents should read
these before making architectural decisions.

**Client's existing data:** Sofa Belle has an Excel spreadsheet with 12+ months of
metrics (May 2025 → May 2026). Use it as ground truth for which KPIs matter.
Exact columns documented in `docs/SOFABELLE.md`.

**Claude model decision:** Spec originally wrote `claude-sonnet-4-5`. After review,
we are using `claude-sonnet-4-6` (current generation) for the AI insights generator.

**Sales cycle characteristics:** Premium furniture, long cycle (2 weeks – 2 months),
high ticket (20,000+ RON). Visit to showroom is mandatory before any deal closes.
AI insights must account for these domain specifics, not apply generic e-commerce logic.

## Constraints

- **Tech stack**: Python 3.11+, FastAPI, SQLAlchemy 2.x async, Pydantic v2, Next.js 14, PostgreSQL 16, Redis 7, Celery — non-negotiable, defined in CLAUDE.md
- **Async-first**: All I/O must be async/await; no sync code in HTTP handlers
- **Security**: No PII in logs (structlog JSON), Fernet encryption for API credentials in DB, gitleaks pre-commit hook
- **AI API**: Claude calls only from Celery tasks, never from HTTP handlers
- **Multi-tenancy scope**: Schema has tenant_id but enforcement is deferred — code does NOT filter by tenant_id in MVP1-3
- **No hard deadline**: Quality over speed; ship when it's solid
- **Language**: UI primary in Romanian, fallback English; AI insights always in Romanian

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Single-tenant first (MVP1-3) | Pilot is one client; full multi-tenancy would add ~30% dev time with zero value now | — Pending |
| Schema has tenant_id everywhere | Avoids DB migrations when we add full tenancy in Iteration 4 | — Pending |
| claude-sonnet-4-6 (upgraded from spec's 4.5) | Current generation, better reasoning for Romanian business insights | — Pending |
| MEFI /leads is the only endpoint | Sales funnel derived from statuses + custom fields, not dedicated endpoints | — Pending |
| Build it right (no MVP shortcuts on architecture) | No hard deadline; foundation quality saves time in later iterations | — Pending |
| Celery tasks for all ETL + AI calls | Never block HTTP handlers; idempotent retry; Celery Beat scheduling | — Pending |

---

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-19 after initialization*
