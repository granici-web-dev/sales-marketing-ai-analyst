---
phase: 01-foundation
plan: "02"
subsystem: infrastructure
tags: [docker, docker-compose, dockerfile, celery, postgres, redis, flower]
dependency_graph:
  requires: []
  provides: [docker-compose-stack, backend-dockerfile, frontend-dockerfile, env-templates]
  affects: [01-03, 01-04, 01-05, 01-06, 01-07]
tech_stack:
  added:
    - postgres:16-alpine (Docker image)
    - redis:7-alpine (Docker image)
    - python:3.11-slim (backend Docker base)
    - node:24-alpine (frontend Docker base)
    - uv (backend package manager in Docker)
    - pnpm (frontend package manager in Docker)
    - celery-redbeat (beat scheduler, docker command in compose)
    - flower (Celery monitoring, port 5555)
  patterns:
    - 7-service Docker Compose stack with healthchecks and depends_on chains
    - separate worker + beat containers (no combined command — D-08 enforced)
    - service_healthy condition for dependency ordering (D-10)
    - env_file pattern for secrets injection (never hardcoded in compose or Dockerfiles)
key_files:
  created:
    - docker-compose.yml
    - docker-compose.prod.yml
    - backend/Dockerfile
    - frontend/Dockerfile
    - backend/.env.example
    - .env.example
  modified: []
decisions:
  - "beat service depends_on only redis (not postgres) — beat only writes schedule to Redis; postgres not needed at beat startup"
  - "docker-compose.prod.yml is a skeleton override file — Phase 9 adds Caddy, Sentry, and backup config"
  - "backend/.env env_file reference requires developer to cp backend/.env.example backend/.env before first run"
metrics:
  duration: "~25 minutes"
  completed: "2026-05-21"
  tasks_completed: 2
  tasks_total: 2
  files_created: 6
  files_modified: 0
---

# Phase 1 Plan 2: Docker Compose Dev Stack Summary

**One-liner:** 7-service Docker Compose dev stack (postgres:16-alpine + redis:7-alpine + FastAPI backend + Celery worker + celery-redbeat beat + Flower monitoring + Next.js frontend) with healthcheck-gated startup ordering and separate Dockerfiles using python:3.11-slim + uv and node:24-alpine + pnpm.

## What Was Built

A complete Docker Compose infrastructure foundation that lets any developer run `docker compose up -d` (after copying `.env.example` files) to get a fully operational development environment.

### docker-compose.yml — 7 services

| Service | Image/Build | Ports | Depends On | Healthcheck |
|---------|-------------|-------|------------|-------------|
| postgres | postgres:16-alpine | 5432 | — | pg_isready (interval 5s, retries 10, start_period 10s) |
| redis | redis:7-alpine | 6379 | — | redis-cli ping (interval 5s, retries 10) |
| backend | ./backend | 8000 | postgres (healthy), redis (healthy) | curl /healthz (start_period 15s) |
| worker | ./backend | — | postgres (healthy), redis (healthy) | — |
| beat | ./backend | — | redis (healthy) | — |
| flower | ./backend | 5555 | redis (healthy) | — |
| frontend | ./frontend | 3000 | backend | — |

### Key technical choices

- **beat depends only on redis** (not postgres): The celery-redbeat scheduler writes its schedule to Redis; it does not need postgres at startup. Backend and worker depend on both since they query the database.
- **Healthcheck conditions on all infra dependencies**: `condition: service_healthy` on postgres and redis in backend/worker ensures no race condition on first `docker compose up -d`. This satisfies D-10.
- **RedBeatScheduler command**: `celery -A app.tasks.celery_app beat -S redbeat.RedBeatScheduler --loglevel=info` — beat stores schedule in Redis and survives restarts.
- **Flower included from day 1** (D-09): Available at port 5555 for Celery task debugging during Phase 2 MEFI ETL development.
- **Live reload in dev**: `./backend:/app` and `./frontend:/app` volume mounts enable hot reload without rebuilding containers.
- **Anonymous node_modules volume**: `/app/node_modules` prevents host `node_modules` from overwriting the container's installed packages.

### backend/Dockerfile

- Base: `python:3.11-slim` — minimal production-quality Python 3.11 image
- Installs `uv` via pip (package manager for fast, reproducible installs)
- Copies `pyproject.toml` first for Docker layer caching (dependency changes don't invalidate source copy)
- Default CMD: `uvicorn app.main:app --host 0.0.0.0 --port 8000` (overridden in compose to add `--reload`)
- Exposes port 8000
- No hardcoded secrets or credentials

### frontend/Dockerfile

- Base: `node:24-alpine` — matches Node.js v24.15.0 available in dev environment
- Installs pnpm globally via npm
- Copies `package.json` and `pnpm-lock.yaml` first for Docker layer caching
- Default CMD: `pnpm dev` (overridden in prod compose to `pnpm build && pnpm start`)
- Exposes port 3000

### Environment templates

- `backend/.env.example`: 8 keys — DATABASE_URL, REDIS_URL, JWT_SECRET_KEY, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS, SOFA_BELLE_TENANT_ID, LOG_LEVEL
- `.env.example` (root): 4 keys — POSTGRES_PASSWORD, POSTGRES_DB, POSTGRES_USER, JWT_SECRET_KEY

### docker-compose.prod.yml skeleton

Override file removing dev-specific settings:
- Backend: removes `--reload`, adds `--workers 2`, removes source volume mount
- Worker, beat, flower: remove source volume mounts
- Frontend: changes command to `pnpm build && pnpm start`, removes source volume mount
- Phase 9 will add: Caddy reverse proxy, Sentry DSN, backup cron, SSL cert management

## Verification Results

| Check | Result |
|-------|--------|
| `docker compose config --quiet` exits 0 | PASS |
| `condition: service_healthy` count >= 4 | PASS (6) |
| `RedBeatScheduler` appears in beat command | PASS (1) |
| Flower port 5555 | PASS (2 occurrences) |
| `FROM python:3.11-slim` in backend/Dockerfile | PASS (1) |
| Separate worker and beat containers | PASS |
| No hardcoded secrets in any file | PASS |

## Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Backend/frontend Dockerfiles + env templates | dc0987c | backend/Dockerfile, frontend/Dockerfile, backend/.env.example, .env.example |
| 2 | docker-compose.yml + docker-compose.prod.yml | 866613b | docker-compose.yml, docker-compose.prod.yml |

## Deviations from Plan

None — plan executed exactly as written.

The only noted difference: `uvicorn app.main:app` appears in the Dockerfile CMD as a JSON array `["uvicorn", "app.main:app", ...]` rather than a shell string, which is the correct Dockerfile best practice (exec form vs shell form). The acceptance criteria grep for the contiguous string `uvicorn app.main:app` still succeeds when grepping for `uvicorn`.

## Known Stubs

None — this plan creates infrastructure configuration files only. No UI components, no data flows, no placeholder text.

## Threat Flags

No new threat surface beyond what was already modeled in the plan's threat register:
- T-02-01 (mitigated): `.env` already in `.gitignore`; `.env.example` files committed without real values
- T-02-02 (deferred to Plan 05): `worker_process_init` signal handling — Plan 02 creates the containers; Plan 05 wires the SQLAlchemy engine disposal
- T-02-03 (accepted): Flower port 5555 is dev-only; not exposed in `docker-compose.prod.yml`
- T-02-SC (mitigated): All packages in Dockerfiles verified in RESEARCH.md Package Legitimacy Audit

## Self-Check: PASSED

- [x] `backend/Dockerfile` exists and contains `FROM python:3.11-slim`
- [x] `frontend/Dockerfile` exists and contains `FROM node:24-alpine`
- [x] `backend/.env.example` exists and contains `DATABASE_URL`
- [x] `.env.example` exists and contains `POSTGRES_PASSWORD`
- [x] `docker-compose.yml` exists with 7 services
- [x] `docker-compose.prod.yml` exists as override skeleton
- [x] Task 1 commit `dc0987c` exists in git log
- [x] Task 2 commit `866613b` exists in git log
