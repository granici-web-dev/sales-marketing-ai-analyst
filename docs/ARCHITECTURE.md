# Architecture

> Краткий обзор архитектуры системы. Для полной спецификации см. [SPEC.md](../SPEC.md) разделы 4 и 7.

## High-level Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  External Data Sources                                           │
│                                                                  │
│  ┌──────────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  MEFI CRM        │  │ Meta Ads     │  │ Google Ads   │      │
│  │  (leads, deals,  │  │ API          │  │ API          │      │
│  │   calls — with   │  └──────────────┘  └──────────────┘      │
│  │   transcripts    │                                           │
│  │   from DOTRO)    │  ┌──────────────┐  ┌──────────────┐      │
│  └──────────────────┘  │ TikTok Ads   │  │  GA4 API     │      │
│                        │ API          │  │              │      │
│                        └──────────────┘  └──────────────┘      │
│                        ┌──────────────┐                         │
│                        │  Search      │                         │
│                        │  Console API │                         │
│                        └──────────────┘                         │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
                  ┌────────────────────┐
                  │  ETL Service       │
                  │  (Celery workers)  │
                  │  Nightly @ 03:00   │
                  └────────┬───────────┘
                           │
                           ▼
                ┌──────────────────────┐
                │   PostgreSQL         │
                │   ┌────────────────┐ │
                │   │ Raw layer      │ │ ◄── Sync from sources
                │   ├────────────────┤ │
                │   │ Metrics layer  │ │ ◄── Aggregated KPIs
                │   ├────────────────┤ │
                │   │ Insights layer │ │ ◄── AI-generated reports
                │   └────────────────┘ │
                └──────────┬───────────┘
                           │
                           ▼
              ┌─────────────────────────┐
              │  Insights Generator     │
              │  (Celery @ 06:00)       │ ──► Claude Sonnet 4.5
              │  - Anomaly detection    │
              │  - Generate narrative   │
              │  - Build action plan    │
              └──────────┬──────────────┘
                         │
                         ▼
                ┌────────────────────┐
                │   FastAPI Backend  │
                └──────────┬─────────┘
                           │
                           ▼
                ┌────────────────────┐
                │   Next.js Frontend │
                └────────────────────┘
```

## Layers

### 1. ETL Layer (`backend/app/services/integrations/`)

Каждый источник = отдельный класс-наследник `BaseIntegration`:
- `MefiIntegration` — лиды, сделки, звонки, транскрипты (Iteration 1)
- `MetaAdsIntegration` — Facebook + Instagram (Iteration 2)
- `GoogleAdsIntegration` (Iteration 2)
- `TikTokAdsIntegration` (Iteration 2)
- `GA4Integration` (Iteration 3)
- `SearchConsoleIntegration` (Iteration 3)

**Принцип:** все sync только через Celery, никогда синхронно в HTTP-запросе.

### 2. Raw Data Layer (PostgreSQL `raw_*` tables)

Сырые данные из источников, сохранённые "как есть" + `raw_payload JSONB` для отладки.
Изменяется только через sync задачи.

### 3. Metrics Layer (PostgreSQL `*_kpi` tables)

Агрегированные KPI:
- `daily_kpi` — общие метрики дня по тенанту
- `salesperson_daily_kpi` — по продавцам
- `source_daily_kpi` — по источникам лидов / рекламным каналам

Рассчитываются Celery задачей `metrics_calc` после ETL.

### 4. Anomaly Detection Layer

Алгоритмические правила (`backend/app/services/anomaly_detection/rules.py`) ищут проблемы в данных.
Результаты сохраняются в `detected_problems`.
Запускается после расчёта метрик.

### 5. AI Insights Layer

Celery задача `insights_generator`:
1. Берёт `detected_problems` за день + контекст бизнеса
2. Формирует prompt для Claude Sonnet 4.5 (на румынском)
3. Парсит JSON-ответ
4. Сохраняет в `daily_insights`

### 6. API Layer (`backend/app/api/v1/`)

FastAPI routers, **тонкие endpoints**:
- Парсинг запроса (Pydantic)
- Вызов service
- Возврат ответа

Никаких DB-запросов или вычислений в endpoints.

### 7. Frontend Layer (`frontend/`)

Next.js 14 App Router:
- Server Components для статики
- Client Components для интерактивности
- TanStack Query для серверного состояния
- Tremor для дашбордов

## Daily Cycle

Все времена в Europe/Bucharest:

| Время | Задача | Описание |
|---|---|---|
| 03:00 | `etl_sync_all` | Sync со всех источников → `raw_*` таблицы |
| 04:00 | `metrics_calc` | Расчёт KPI → `*_kpi` таблицы |
| 05:00 | `anomaly_detection` | Поиск проблем → `detected_problems` |
| 06:00 | `insights_generator` | Claude API → `daily_insights` |
| 07:00 | `send_email_digest` | Email с резюме (опционально, позже) |

## Multi-tenancy

Каждая запись (кроме `tenants`, `admin_users`) имеет `tenant_id`.

Изоляция обеспечивается:
1. SQLAlchemy event listener — автоматически добавляет `WHERE tenant_id = ?`
2. JWT содержит `tenant_id`, извлекается middleware
3. Тесты на изоляцию обязательны

## Async/Sync boundary

- **Async:** все HTTP endpoints, DB-запросы, внешние API
- **Sync:** только внутри Celery tasks (Celery 5.x не полностью async)
- В Celery tasks использовать `asyncio.run()` для вызова async кода

## Key Design Decisions

### Why PostgreSQL, not MongoDB?
Аналитика, агрегации, time-series, индексы по нескольким полям, JOIN'ы — реляционная БД подходит лучше.

### Why Celery, not asyncio + background tasks?
- Идемпотентные retry с экспоненциальным backoff
- Распределение задач по нескольким воркерам
- Celery Beat для расписаний
- Monitoring через Flower

### Why Next.js, not pure React SPA?
- SSR/SSG для лучшего SEO маркетингового сайта (если будет)
- App Router с Server Components для производительности
- Встроенная маршрутизация и API routes
- Хороший DX

### Why Tremor for dashboards?
- Заточен именно под аналитические дашборды
- Готовые компоненты (KPI cards, line/bar/funnel charts)
- Хорошо работает с Tailwind
- Меньше boilerplate чем чистый Recharts

## See also

- [SPEC.md section 4](../SPEC.md#4-архитектура) — Full architecture details
- [SPEC.md section 6](../SPEC.md#6-структура-проекта) — Project structure
- [SPEC.md section 7](../SPEC.md#7-схема-бд-postgresql) — Database schema
- [docs/STACK.md](./STACK.md) — Technology choices
- [docs/INTEGRATIONS.md](./INTEGRATIONS.md) — External integrations details
