# AGENTS.md — Instructions for Codex

> Этот файл — главная точка входа для Codex в этом проекте.
> Прочитай его полностью перед началом работы.

## Project Overview

**Sales & Marketing AI Analyst** — SaaS-платформа для румынского SMB, которая:

1. Собирает данные из MEFI CRM + Meta/Google/TikTok Ads + GA4 + Search Console
2. Считает метрики маркетинга и продаж
3. Раз в день генерирует AI-инсайты через Codex Sonnet 4.5 с планом действий на румынском

**Пилот:** Sofa Belle (премиум-мебель, Румыния, 6 продавцов, 3 шоурума)

📖 **Полная спецификация:** [SPEC.md](./SPEC.md) — обязательно прочитай перед любой работой.
📖 **Архитектура:** [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md)
📖 **Стек:** [docs/STACK.md](./docs/STACK.md)
📖 **Конвенции кода:** [docs/CONVENTIONS.md](./docs/CONVENTIONS.md)
📖 **Контекст клиента:** [docs/SOFABELLE.md](./docs/SOFABELLE.md)
📖 **Интеграции:** [docs/INTEGRATIONS.md](./docs/INTEGRATIONS.md)
📖 **MEFI API reference:** [docs/api-references/mefi/](./docs/api-references/mefi/) — official MEFI API documentation (start with README.md)

---

## Tech Stack Quick Reference

| Layer    | Technology                                                        |
| -------- | ----------------------------------------------------------------- |
| Backend  | Python 3.11+, FastAPI, SQLAlchemy 2.x, Pydantic v2                |
| Database | PostgreSQL 16, Redis 7                                            |
| Queue    | Celery + Celery Beat                                              |
| ETL      | httpx (async), официальные SDK провайдеров                        |
| AI       | Anthropic Codex Sonnet 4.5 (`Codex-sonnet-4-5`)                 |
| Frontend | Next.js 14 App Router, TypeScript, TailwindCSS, shadcn/ui, Tremor |
| Infra    | Docker Compose (dev), Hetzner/Unihost (prod), Caddy               |

---

## Core Principles (НЕ нарушать)

### 1. Async-first

- Все I/O операции через `async/await`
- HTTP клиенты — `httpx.AsyncClient`
- БД — `asyncpg` через SQLAlchemy 2.x async
- НЕ смешивать sync и async код без явной причины

### 2. Type hints везде

- Python 3.11+ syntax (`list[str]`, `int | None`)
- Pydantic v2 для всех моделей данных
- `from __future__ import annotations` в каждом файле
- mypy strict mode

### 3. Multi-tenancy isolation

- **КАЖДЫЙ** запрос к БД должен фильтроваться по `tenant_id`
- Никогда не делать запрос без `WHERE tenant_id = ?`
- На уровне SQLAlchemy — global filter через event listener
- Если видишь модель без `tenant_id` — это БАГ (кроме `tenants`, `admin_users`)

### 4. Никаких секретов в коде

- ВСЁ через переменные окружения (`.env`)
- Pydantic Settings для типизированной конфигурации
- API credentials в БД — шифровать через Fernet
- Pre-commit hook `gitleaks` обязателен

### 5. Backend никогда не дёргает третьи API синхронно

- Все вызовы к MEFI/Meta/Google/TikTok/GA4/GSC — ТОЛЬКО через Celery tasks
- Никогда не блокировать HTTP-запрос пользователя на запрос к внешнему API
- БД как буфер между внешними API и UI

### 6. Логирование без PII

- `structlog` с JSON-форматом
- Никогда не логировать: телефоны клиентов, email клиентов, имена клиентов, содержимое транскриптов
- OK логировать: `tenant_id`, `call_id`, статусы, ошибки, latency

### 7. Миграции только через Alembic

- Никаких ручных правок схемы
- Каждое изменение модели → Alembic migration
- Migrations review обязателен перед merge

---

## Critical Rules

### ❌ DO NOT

- ❌ Не использовать MongoDB (мы на PostgreSQL)
- ❌ Не делать собственную транскрипцию звонков (это делает DOTRO MonitorAI)
- ❌ Не использовать Whisper / pyannote / faster-whisper (не нужно для этого проекта)
- ❌ Не вызывать Codex API из HTTP-handler'ов (только из Celery tasks)
- ❌ Не использовать sync-функции в async-коде
- ❌ Не делать `SELECT *` — указывать конкретные поля
- ❌ Не использовать raw SQL без причины — SQLAlchemy ORM
- ❌ Не коммитить `.env`, `.env.local`, `*.key`, `*.pem`
- ❌ Не использовать `print()` для логирования — только `structlog`
- ❌ Не игнорировать `tenant_id` при запросах к БД

### ✅ DO

- ✅ Читать SPEC.md перед началом нового этапа
- ✅ Писать тесты для бизнес-логики (pytest, минимум 70% coverage)
- ✅ Использовать `from __future__ import annotations`
- ✅ Использовать Pydantic v2 models для всех DTO
- ✅ Структурировать код по принципам Clean Architecture (api → services → repositories → models)
- ✅ Каждая внешняя интеграция — отдельный класс наследующий `BaseIntegration`
- ✅ Каждая Celery задача — идемпотентна (можно перезапустить без побочных эффектов)
- ✅ Conventional Commits (feat:, fix:, chore:, docs:, refactor:, test:)
- ✅ Обновлять `STATE.md` после завершения значимой работы

---

## Commands

### Development

```bash
# Запустить весь стек локально
docker compose up -d

# Backend (без Docker, для разработки)
cd backend
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
pnpm install
pnpm dev

# Celery worker
cd backend
celery -A app.tasks.celery_app worker --loglevel=info

# Celery beat (scheduler)
celery -A app.tasks.celery_app beat --loglevel=info
```

### Database

```bash
# Создать новую миграцию
cd backend
alembic revision --autogenerate -m "описание изменений"

# Применить миграции
alembic upgrade head

# Откатить последнюю миграцию
alembic downgrade -1

# Посмотреть текущую версию
alembic current
```

### Testing

```bash
# Backend tests
cd backend
pytest                              # все тесты
pytest --cov=app --cov-report=html  # с покрытием
pytest tests/unit                   # только unit
pytest tests/integration            # только integration
pytest -k "test_mefi"               # по pattern

# Frontend tests
cd frontend
pnpm test
pnpm test:e2e                       # Playwright

# Линт
cd backend
ruff check .
ruff format .
mypy app

cd frontend
pnpm lint
pnpm typecheck
```

### Production

```bash
# Деплой через Docker Compose
docker compose -f docker-compose.prod.yml up -d --build

# Логи
docker compose logs -f backend
docker compose logs -f worker
```

---

## Code Style

### Python

- **Formatter:** ruff format (line length 100)
- **Linter:** ruff (with strict settings)
- **Type checker:** mypy strict
- **Imports:** isort через ruff
- **Docstrings:** Google style для публичных функций
- **Naming:**
  - `snake_case` для функций и переменных
  - `PascalCase` для классов
  - `UPPER_CASE` для констант
  - Префикс `_` для private

### TypeScript

- **Formatter:** Prettier (default config)
- **Linter:** ESLint with Next.js config
- **Naming:**
  - `camelCase` для функций и переменных
  - `PascalCase` для типов, интерфейсов, компонентов
  - `kebab-case` для имён файлов компонентов
- **Components:** функциональные с Hooks, не классовые

### Commits (Conventional Commits)

```
feat: add MEFI leads sync task
fix: handle timeout in google ads client
chore: bump faster-whisper to 1.0.3
docs: update integrations.md with TikTok flow
refactor: extract anomaly rules to separate module
test: add fixtures for daily_kpi calculation
```

---

## File Organization

### Backend

```
backend/app/
├── api/v1/              # FastAPI routers (только thin endpoints)
├── core/                # Cross-cutting: security, tenancy, exceptions
├── db/                  # DB session, base
├── models/              # SQLAlchemy models (raw/, metrics/, insights/)
├── schemas/             # Pydantic DTOs (отдельно от models!)
├── services/            # Бизнес-логика
│   ├── integrations/    # Внешние API клиенты
│   ├── metrics/         # Расчёт KPI
│   ├── anomaly_detection/
│   └── insights/        # Codex prompt + parsing
└── tasks/               # Celery tasks
```

**Принцип разделения:** `api/` → `services/` → `db/` (или `services/integrations/`)

- API layer: только парсинг запроса, валидация, вызов service
- Service layer: бизнес-логика
- DB layer: запросы к БД через SQLAlchemy

**Никогда:** API endpoint не должен напрямую делать SQL-запросы или вызывать httpx.

### Frontend

```
frontend/app/
├── (auth)/             # Public routes
├── (dashboard)/        # Protected routes
└── api/                # Next.js API routes (если нужно)

frontend/components/
├── ui/                 # shadcn primitives
├── dashboards/         # Strona-specific
├── charts/             # Tremor wrappers
└── insights/           # Insights page components
```

---

## How to Work on This Project

### When starting a new task

1. Прочитай SPEC.md если ещё не читал
2. Прочитай соответствующий раздел `docs/`
3. Проверь `STATE.md` (создаётся GSD) — где сейчас находится проект
4. Если задача из конкретной фазы — открой `.planning/phases/N/PLAN.md`

### When implementing a feature

1. Создай миграцию (если меняется схема)
2. Создай/обнови модель в `app/models/`
3. Создай/обнови Pydantic схему в `app/schemas/`
4. Создай/обнови service в `app/services/`
5. Создай/обнови API endpoint в `app/api/v1/`
6. Напиши тесты (unit + integration)
7. Если есть UI часть — создай компоненты в `frontend/`
8. Обнови документацию если изменилось поведение

### When working with external APIs

For MEFI integration specifically, ALWAYS read these files first:

- `docs/api-references/mefi/README.md` — overview, auth, limits
- `docs/api-references/mefi/leads-read.md` — read endpoints (primary)
- `docs/api-references/mefi/enums.md` — status/source/user ID mappings for Sofa Belle
- `docs/api-references/mefi/custom-fields.md` — custom field structure

Note: MEFI API currently exposes ONLY lead endpoints. Deals/offers/calls/visits
must be derived from lead statuses and custom fields. See enums.md for funnel mapping.

1. Создай клиент в `app/services/integrations/{source}.py`, унаследуй `BaseIntegration`
2. Реализуй методы: `authenticate()`, `sync()`, `health_check()`
3. Все вызовы внешних API — через Celery task в `app/tasks/etl/sync_{source}.py`
4. Используй retry logic (Celery autoretry)
5. Логируй каждый sync с метриками (длительность, кол-во записей, ошибки)

### When something breaks

1. Не паникуй
2. Прочитай логи (`docker compose logs -f backend`)
3. Проверь Sentry если настроен
4. Воспроизведи в тесте
5. Исправь
6. Покрой тестом

---

## Pre-commit Checks

Перед коммитом автоматически запускается:

- `ruff check` — линт Python
- `ruff format --check` — форматирование Python
- `mypy` — type checking
- `gitleaks` — поиск утечек секретов
- `prettier --check` — форматирование TS/JS
- `eslint` — линт TS/JS

Если какая-то проверка падает — НЕ обходить через `--no-verify`, исправлять.

---

## When in doubt

**Алгоритм действий когда непонятно как делать:**

1. Прочитай SPEC.md ещё раз
2. Прочитай соответствующий раздел `docs/`
3. Посмотри как сделано в похожих местах кодовой базы
4. Если всё равно непонятно — задай вопрос пользователю (не угадывай)
5. Никогда не делай "magic" без явного указания

**Хорошие вопросы пользователю:**

- "В SPEC.md воронка описана как Lead → Vizita → Oferta → Contract. Сейчас у нас в данных MEFI отсутствует таблица visits. Создавать её или собирать визиты из другой сущности?"
- "Для Meta Ads API нужен Business Manager доступ. У тебя уже есть credentials или нужно подключаться через OAuth?"

**Плохие действия:**

- Угадать что подразумевалось
- Использовать другой stack чем указано
- Пропустить тесты "потому что просто прототип"
- Захардкодить tenant_id для упрощения

---

## Resources

- [Anthropic API docs](https://docs.anthropic.com)
- [Codex Sonnet 4.5 model card](https://docs.Codex.com/en/docs/about-Codex/models)
- [FastAPI docs](https://fastapi.tiangolo.com)
- [SQLAlchemy 2.x docs](https://docs.sqlalchemy.org/en/20/)
- [Celery docs](https://docs.celeryq.dev)
- [Next.js docs](https://nextjs.org/docs)
- [Tremor docs](https://www.tremor.so/docs)
- [shadcn/ui](https://ui.shadcn.com)
- [MEFI CRM](https://mefi.ro) — основная CRM пилотного клиента
- [DOTRO Telecom](https://dotro.ro) — рекомендованная телефония

---

## Project Status

Проект на этапе **Иніциализации**. Следующие шаги:

1. ✅ Получить документацию MEFI API (отправить email — шаблон в SPEC.md, Приложение A)
2. ⛔ Получить тестовый доступ к MEFI от Sofa Belle
3. ✅ Получить Anthropic API key
4. 🟡 Подать заявку на Google Ads Developer Token (займёт 1-3 недели)
5. ⏳ Запустить `/gsd-new-project` для инициализации GSD планирования

**Текущая фаза:** Pre-development (preparation)

После получения MEFI API доступа → Этап 0 из SPEC.md раздел 18.
