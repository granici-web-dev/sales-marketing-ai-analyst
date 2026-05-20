# Tech Stack

> Полное описание выбора технологий. Для контекста см. [SPEC.md раздел 3](../SPEC.md#3-технологический-стек).

## Backend

### Core
| Tool | Version | Why |
|---|---|---|
| Python | 3.11+ | Modern syntax, async improvements, type system maturity |
| FastAPI | latest | Async, auto OpenAPI, Pydantic integration |
| Pydantic | v2 | Validation, serialization, settings management |
| SQLAlchemy | 2.x | Best Python ORM, full async support, mature |
| Alembic | latest | Standard migration tool for SQLAlchemy |
| asyncpg | latest | Fastest async PostgreSQL driver |
| httpx | latest | Async HTTP client, replaces requests |
| structlog | latest | Structured logging with JSON output |

### Task Queue
| Tool | Version | Why |
|---|---|---|
| Celery | 5.x | Mature, well-documented, distributed task queue |
| Celery Beat | bundled | Cron-like scheduling |
| Redis | 7 | Celery broker + cache |
| Flower | latest | Celery monitoring UI |

### AI
| Tool | Version | Why |
|---|---|---|
| anthropic | latest | Official Anthropic SDK for Python |
| Model | `claude-sonnet-4-5` | Best quality for Romanian/Russian business analysis at reasonable cost |

### Testing
| Tool | Version | Why |
|---|---|---|
| pytest | latest | Standard Python testing framework |
| pytest-asyncio | latest | Async test support |
| pytest-cov | latest | Coverage reporting |
| httpx | latest | Test client for FastAPI |
| factory_boy | latest | Test data fixtures |
| freezegun | latest | Time mocking for time-sensitive tests |

### Code Quality
| Tool | Why |
|---|---|
| ruff | Linter + formatter (replaces black, isort, flake8) |
| mypy | Static type checker, strict mode |
| pre-commit | Git hooks for lint/format/secrets check |
| gitleaks | Prevent committing secrets |

## Frontend

### Core
| Tool | Version | Why |
|---|---|---|
| Next.js | 14 (App Router) | SSR, SSG, file-based routing, mature ecosystem |
| TypeScript | 5.x | Type safety |
| React | 18 | Required by Next.js |
| TailwindCSS | 3.x | Utility-first CSS, fast development |
| shadcn/ui | latest | Copy-paste components, owns the code, accessible |

### Data & State
| Tool | Why |
|---|---|
| TanStack Query | Server state, caching, refetching |
| Zustand | Client state (lightweight alternative to Redux) |
| next-intl | i18n for ro/en/ru |

### Dashboards & Charts
| Tool | Why |
|---|---|
| Tremor | Built for analytics dashboards, beautiful by default |
| Recharts | Underneath Tremor; can use directly for custom charts |
| date-fns | Date manipulation |

### Forms
| Tool | Why |
|---|---|
| react-hook-form | Best form library for React |
| zod | Schema validation, integrates with react-hook-form |

### Testing
| Tool | Why |
|---|---|
| Vitest | Fast unit test runner |
| Testing Library | Component testing |
| Playwright | E2E testing |

### Code Quality
| Tool | Why |
|---|---|
| ESLint | Linter with Next.js config |
| Prettier | Formatter |
| TypeScript strict mode | Maximum type safety |

## Database

| Tool | Version | Why |
|---|---|---|
| PostgreSQL | 16 | Mature, JSONB support, great for analytics |
| TimescaleDB | latest (optional) | If we need time-series at scale (later) |
| Redis | 7 | Cache + Celery broker |

## Infrastructure

### Development
| Tool | Why |
|---|---|
| Docker | Containerization |
| Docker Compose | Multi-service local dev |
| uv | Fast Python package manager (replaces pip + venv) |
| pnpm | Fast Node.js package manager |

### Production
| Tool | Why |
|---|---|
| Hetzner (Germany) | EU hosting, good price/performance |
| Caddy | Reverse proxy, automatic SSL |
| Docker Compose | Production orchestration (simpler than K8s for our scale) |
| Sentry | Error tracking |
| Grafana + Prometheus | Monitoring (optional for MVP) |

### CI/CD
| Tool | Why |
|---|---|
| GitHub Actions | Standard, free for open source, good for our scale |
| GitHub Container Registry | Docker images |

## Why NOT certain technologies

### ❌ MongoDB
We started thinking we needed it for call transcripts, but pivoted: now we just read transcripts from MEFI API, no need for document store. PostgreSQL with JSONB is sufficient.

### ❌ Whisper / pyannote / faster-whisper
Original plan was to transcribe calls ourselves. DOTRO MonitorAI does this better and is already integrated with MEFI. We just consume the data.

### ❌ Kubernetes
Premature optimization. Docker Compose is enough for our scale (10s of clients). Move to K8s when we have 100+ clients and need autoscaling.

### ❌ Microservices
Same reason. Monolith with clear module separation is faster to develop and deploy.

### ❌ GraphQL
REST + OpenAPI is simpler, well-supported by FastAPI, and our dashboard queries are well-defined.

### ❌ MongoDB / Cassandra / DynamoDB
PostgreSQL is more than enough for our analytical workload. Don't add complexity prematurely.

### ❌ Kafka / RabbitMQ
Redis + Celery is sufficient. No need for high-throughput streaming.

## Stack Compatibility Matrix

| Library | Min Python | Notes |
|---|---|---|
| FastAPI | 3.8+ | We use 3.11+ for latest type features |
| SQLAlchemy 2.x | 3.7+ | Async requires asyncpg |
| Pydantic 2.x | 3.8+ | Much faster than v1 |
| Celery 5.x | 3.8+ | Native Python 3.11 support |
| anthropic | 3.8+ | Async client available |

## Version Pinning Strategy

- **Direct dependencies:** pinned to specific minor versions in `pyproject.toml`
- **Transitive dependencies:** locked in `uv.lock` / `pnpm-lock.yaml`
- **Major version bumps:** require dedicated branch and testing
- **Security updates:** applied within 7 days via Dependabot
