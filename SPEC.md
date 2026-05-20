# SPEC.md — Sales & Marketing AI Analyst

> **Версия:** 2.1
> **Дата:** Май 2026
> **Статус:** Утверждено для разработки
>
> **Изменения в v2.1:**
>
> - Добавлен AI Chat — интерактивный диалог с Claude для бизнес-вопросов (раздел 11)
> - Добавлена Phase 8 в roadmap для разработки чата
> - Обновлена ценностная пропозиция: продукт теперь "AI-консультант с дашбордами", а не "дашборды + отчёт"

---

## 1. Концепция продукта

**Название (рабочее):** Sales & Marketing AI Analyst для румынского малого/среднего бизнеса.

**Что строим:** SaaS-платформа, которая собирает данные из CRM (MEFI), рекламных систем (Meta Ads, Google Ads, TikTok Ads) и веб-аналитики (GA4, Google Search Console), строит дашборды по ключевым метрикам маркетинга и продаж, **раз в день генерирует AI-инсайты** через Claude Sonnet 4.5 — с конкретным планом действий на румынском языке, и предоставляет **интерактивный AI-чат** где владельцы бизнеса и менеджеры могут задавать вопросы о своих данных на естественном языке.

**Что НЕ строим:**

- ❌ Транскрипцию звонков (это делает DOTRO MonitorAI или 3CX ENT/AI на стороне клиента)
- ❌ Дашборды-двойники MEFI BI (у MEFI уже есть свой BI с сырыми цифрами)
- ❌ Собственную телефонию или CRM

**Ценностное предложение:**

> "Вы платите за CRM, рекламу и веб-аналитику. В системах куча данных, но вы не знаете что с ними делать. Мы каждое утро даём вам отчёт на человеческом языке: что идёт хорошо, что плохо, и 5-7 конкретных задач на день/неделю. А если возникают вопросы — спросите наш AI-чат на румынском: 'почему упали продажи?', 'кто из продавцов лучший?', 'что делать чтобы увеличить выручку?'. Как личный бизнес-аналитик доступный 24/7, но в 10 раз дешевле."

**Пилотный клиент:** [Sofa Belle](https://sofabelle.ro) — румынский производитель премиум-мебели (диваны, кресла, мебель на заказ). 3 шоурума: Brașov, București, Cluj-Napoca. 6 продавцов. Средний чек 20.000+ lei.

**Главная боль клиента:** Хочет понимать, **где теряются деньги в маркетинге и продажах**, и получать конкретный план действий по их возврату.

**Целевой рынок:** Румынские SMB (10-100 сотрудников), использующие MEFI CRM.

**Конкуренты и дифференциация:**

| Конкурент                           | Что делает                   | Чем мы отличаемся                                                                |
| ----------------------------------- | ---------------------------- | -------------------------------------------------------------------------------- |
| **MEFI BI**                         | Дашборды по данным CRM       | Объединяем CRM + 4 рекламных/аналитических источника, добавляем AI-интерпретацию |
| **Gong.io / Chorus.ai**             | Анализ звонков               | Мы про всю воронку маркетинга и продаж, не только звонки. И мы дешевле           |
| **Google Looker Studio / Power BI** | Универсальные BI-инструменты | Заточены под румынский SMB на MEFI, готовые шаблоны без настройки                |
| **Локальные конкуренты в Румынии**  | —                            | На данный момент таких нет                                                       |

**Ключевые отличия:**

1. **Объединение данных из 6+ источников** в одну картину (MEFI + Meta + Google + TikTok + GA4 + GSC)
2. **AI-интерпретация на румынском языке** с конкретным планом действий, а не сырые цифры
3. **Не дашборд, а консультант** — клиент получает ответы, а не графики
4. **Интерактивный AI-чат** — пользователь может задавать вопросы о своих данных голосом или текстом (24/7)
5. **Заточен под румынский SMB на MEFI** — готовые интеграции, румынский язык, локальные бенчмарки в будущем

---

## 2. Roadmap по итерациям

Разработка идёт **итерационно**, каждая итерация — самостоятельный продукт, который можно показать клиенту.

### Итерация 1 (MVP1): MEFI only

**Длительность:** 4-5 недель.

**Что входит:**

- ETL из MEFI API (лиды, визиты в шоурум, оферты, контракты, продавцы, звонки)
- Sales Dashboard (полноценный)
- Marketing Dashboard (структура лидов по категориям, без рекламных расходов — пока нет данных Ads)
- Salespeople Dashboard
- Insights Page с AI-выводами через Claude Sonnet 4.5 (батч, раз в день)
- **AI Chat** ⭐ — интерактивный диалог с Claude через function calling
- UI на румынском + английском
- Базовая аутентификация, single-tenant архитектура (multi-tenancy заложена в схеме, но не реализована)

**Результат:** Клиент видит свою воронку продаж, работу продавцов, получает ежедневный AI-отчёт.

### Итерация 2: + Реклама (Meta + Google + TikTok)

**Длительность:** +3 недели.

**Что добавляется:**

- Интеграция с Meta Marketing API (Facebook + Instagram)
- Интеграция с Google Ads API
- Интеграция с TikTok Marketing API
- Полноценный Marketing Dashboard: CPL, CAC, ROAS, по каналам
- AI-выводы обогащаются маркетинговой экономикой

**Результат:** Появляется полноценная картина "сколько потратили → сколько лидов → сколько денег заработали" по всем каналам.

### Итерация 3: + Web Analytics (GA4 + GSC)

**Длительность:** +2 недели.

**Что добавляется:**

- Интеграция с GA4 API
- Интеграция с Google Search Console API
- Контент-метрики: трафик, конверсии на сайте, SEO-запросы и позиции
- AI-выводы по веб-каналам

**Результат:** Полная картина digital-маркетинга — от показа рекламы до закрытой сделки.

### Итерация 4: Production multi-tenant

**Длительность:** +2-3 недели.

- Реальная мульти-тенантность с изоляцией
- Onboarding flow для новых клиентов
- Биллинг (Stripe)
- Production deployment в Румынии (Hetzner/Unihost)
- DPA-шаблон, GDPR audit log

### Отложено на будущие итерации

- **3 шоурума как отдельное измерение аналитики** — добавляется когда Sofa Belle подключит IP-телефонию и в данных появится привязка звонка к шоуруму
- **Бенчмарки между клиентами** (анонимизированные) — после 5+ клиентов
- **Telegram/WhatsApp бот** с push-уведомлениями
- **Прогнозирование** (forecast revenue, deal probability)
- **Mobile-friendly PWA или native app**

---

## 3. Технологический стек

### Backend

- **Python 3.11+**
- **FastAPI** — REST API
- **SQLAlchemy 2.x + Alembic** — ORM + миграции
- **Pydantic v2** — валидация моделей
- **Celery + Celery Beat + Redis** — фоновые задачи (ETL, расчёт метрик, AI-генерация)
- **httpx** — async HTTP клиент для интеграций

### База данных

- **PostgreSQL 16** — основная БД для аналитики
- **TimescaleDB extension** (опционально) — для time-series метрик при росте объёма
- **Redis 7** — кэш + Celery broker

### Интеграции (по итерациям)

- **MEFI API** (Итерация 1) — формат уточнить у поддержки
- **Meta Marketing API** (Итерация 2) — `facebook-business` SDK
- **Google Ads API** (Итерация 2) — `google-ads` Python library
- **TikTok Marketing API** (Итерация 2) — официальный TikTok for Business SDK
- **GA4 Data API** (Итерация 3) — `google-analytics-data` library
- **Google Search Console API** (Итерация 3) — `google-api-python-client`
- **Anthropic API** — `anthropic` SDK для AI-инсайтов, модель `claude-sonnet-4-5`

### Frontend

- **Next.js 14 (App Router)** + TypeScript
- **TailwindCSS + shadcn/ui** — UI компоненты
- **Tremor** — графики и дашборды (заточен под аналитику)
- **TanStack Query** — серверное состояние и кеширование
- **next-intl** — i18n: румынский (основной для клиента) + английский (для разработки) + русский (для тебя)

### Инфраструктура

- **Docker + Docker Compose** для разработки
- **GitHub Actions** — CI/CD
- **Hetzner Germany / Unihost Romania** — production хостинг (EU-резидентность для GDPR)
- **Caddy** — reverse proxy + автоматический SSL
- **Sentry** — error tracking
- **Grafana + Prometheus** — мониторинг (опционально на старте)

### Чего НЕ нужно

- ~~GPU-сервер~~ — транскрипцию делает DOTRO MonitorAI
- ~~Whisper / pyannote / faster-whisper~~ — не нужны
- ~~MongoDB~~ — используем PostgreSQL для аналитики
- ~~MinIO~~ — аудио мы не храним

---

## 4. Архитектура

```
┌──────────────────────────────────────────────────────────────────┐
│  Внешние источники данных                                         │
│                                                                   │
│  ┌──────────────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │  MEFI CRM            │  │ Meta Ads API │  │ Google Ads   │   │
│  │  - Лиды/сделки       │  │              │  │ API          │   │
│  │  - Визиты в шоурум   │  └──────────────┘  └──────────────┘   │
│  │  - Звонки (DOTRO     │                                        │
│  │    кладёт сюда       │  ┌──────────────┐  ┌──────────────┐   │
│  │    transcript+       │  │ TikTok Ads   │  │  GA4 API     │   │
│  │    sentiment+        │  │ API          │  │              │   │
│  │    summary)          │  └──────────────┘  └──────────────┘   │
│  └──────────────────────┘                                        │
│                            ┌──────────────┐                       │
│                            │  Search      │                       │
│                            │  Console API │                       │
│                            └──────────────┘                       │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
                ┌────────────────────┐
                │  ETL Service       │
                │  (Celery workers)  │
                │  Nightly 03:00     │
                └────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │   PostgreSQL         │
              │   ┌────────────────┐ │
              │   │ Raw layer      │ │ ◄── сырые данные источников
              │   ├────────────────┤ │
              │   │ Metrics layer  │ │ ◄── рассчитанные KPI
              │   ├────────────────┤ │
              │   │ Insights layer │ │ ◄── AI-выводы
              │   └────────────────┘ │
              └──────────┬───────────┘
                         │
                         ▼
             ┌────────────────────────┐
             │ Insights Generator     │
             │ (Celery, 06:00)        │ ◄─── Claude Sonnet 4.5 API
             │ - Anomaly detection    │
             │ - Generate narrative   │
             │ - Build action plan    │
             └──────────┬─────────────┘
                        │
                        ▼
              ┌──────────────────────┐
              │   FastAPI Backend    │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │   Next.js Frontend   │
              │   ┌────────────────┐ │
              │   │ Overview       │ │
              │   │ Marketing Dash │ │
              │   │ Sales Dash     │ │
              │   │ Salespeople    │ │
              │   │ Insights ⭐    │ │
              │   │ Integrations   │ │
              │   └────────────────┘ │
              └──────────────────────┘
```

### Ночной цикл (Europe/Bucharest)

| Время     | Что происходит                                                                       |
| --------- | ------------------------------------------------------------------------------------ |
| **03:00** | ETL: sync со всеми источниками. Сырые данные → `raw_*` таблицы                       |
| **04:00** | Metrics: расчёт `daily_kpi`, `salesperson_daily_kpi`, `source_daily_kpi`             |
| **05:00** | Anomaly Detection: алгоритмическое выявление проблем по правилам                     |
| **06:00** | AI Insights: вызов Claude API с найденными аномалиями, сохранение в `daily_insights` |
| **07:00** | Email-уведомления (опционально, позже)                                               |

### Дневной цикл

- Клиент открывает UI, видит свежий отчёт за сегодня
- Может листать предыдущие отчёты
- Может нажать "Refresh insights" → пересчёт AI-инсайтов на актуальные данные (с rate limit)

**Архитектурный принцип:** backend никогда не вызывает третьи API синхронно во время HTTP-запроса пользователя. Только через Celery + БД как буфер.

---

## 5. Источники данных и интеграции

### 5.1 MEFI API (Итерация 1, критично)

**Что синхронизируем:**

- **Лиды (clienți potențiali):** id, дата, источник, категория (Mail/FB/IG, Telefon, WhatsApp, Site, Designer, Alte), статус, UTM-метки, продавец, история движения по этапам
- **Визиты в шоурум (vizite):** связь с лидом, дата, продавец, шоурум
- **Оферты (oferte):** связь с лидом/визитом, продавец, сумма, дата, статус
- **Сделки/контракты (contracte):** связь с лидом/офертой, продавец, сумма, дата, статус (won/lost), причина потери, количество позиций
- **Звонки (apeluri):** связь с лидом, продавец, направление, статус, длительность, дата
  - **+ обогащённые поля:** `transcript_summary`, `sentiment_score`, `topics` — кладёт DOTRO MonitorAI (или 3CX AI), мы их просто читаем
- **Продавцы (utilizatori):** имя, email, шоурум, активность
- **Этапы воронки (etape pâlnie):** настройки конкретного клиента

**Стратегия sync:**

- Первый sync: полный (за последние 6-12 месяцев)
- Инкрементальный: каждую ночь, только изменённые с момента `last_sync_at`

**⚠️ Главный блокер:** документация MEFI API. До старта разработки нужно:

1. Написать в support MEFI (шаблон email — в Приложении A)
2. Получить документацию API endpoints, аутентификации, форматов
3. Если публичного API нет — обсудить варианты (partnership, экспорт, scraping)

### 5.2 Meta Marketing API (Итерация 2)

**Что синхронизируем:**

- Аккаунты Business Manager
- Кампании, ad sets, ads
- Daily insights: spend, impressions, clicks, CTR, CPM, CPC, reach
- Действия (lead form submits, purchases) с привязкой к кампаниям

**Аутентификация:** OAuth через Facebook Business Login.

**Связка с MEFI лидами:** через UTM-метки или Facebook Lead Ads → MEFI.

### 5.3 Google Ads API (Итерация 2)

**Что синхронизируем:**

- Аккаунты (включая sub-accounts через MCC)
- Кампании, ad groups, ads, keywords
- Daily metrics: cost, impressions, clicks, CTR, conversions

**Аутентификация:** OAuth + Developer Token (нужно подать заявку Google, занимает 1-3 недели — **подать заранее**).

### 5.4 TikTok Marketing API (Итерация 2)

**Что синхронизируем:**

- Рекламные аккаунты
- Кампании, ad groups, ads
- Daily insights: spend, impressions, clicks, conversions, CTR, CPC

**Аутентификация:** OAuth через TikTok for Business.

### 5.5 Google Analytics 4 API (Итерация 3)

**Что синхронизируем:**

- Sessions, users, page views, bounce rate
- Conversions (lead form submits, phone clicks)
- Traffic sources (default channel grouping + UTM)
- Demographics (если доступны)

**Аутентификация:** Service Account или OAuth.

### 5.6 Google Search Console API (Итерация 3)

**Что синхронизируем:**

- Search queries (с кликами, impressions, position, CTR)
- Pages performance
- Изменения позиций в выдаче

**Аутентификация:** OAuth.

### 5.7 Принцип: MEFI-агностичность для телефонии

**Какая бы IP-телефония ни стояла у клиента (DOTRO SmartPBX, 3CX, другая) — нам всё равно.**

Все данные о звонках (включая транскрипт, sentiment, summary от MonitorAI/3CX AI) попадают в MEFI через их официальные интеграции. Мы читаем готовые данные через MEFI API.

**Преимущества:**

- Клиент не привязан к одному вендору
- Если в будущем сменит DOTRO на 3CX или наоборот — наш продукт продолжит работать
- Когда мы пойдём к другим клиентам на MEFI — подключение единообразное

---

## 6. Структура проекта

```
sales-marketing-ai-analyst/
├── docker-compose.yml
├── docker-compose.prod.yml
├── .env.example
├── README.md
├── SPEC.md
│
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── auth.py
│   │   │       ├── tenants.py
│   │   │       ├── integrations.py     # OAuth flows для каждого источника
│   │   │       ├── dashboards.py       # marketing + sales endpoints
│   │   │       ├── insights.py         # AI-инсайты
│   │   │       └── metrics.py          # raw metrics для drill-down
│   │   ├── core/
│   │   │   ├── security.py
│   │   │   ├── tenancy.py
│   │   │   └── exceptions.py
│   │   ├── db/
│   │   │   ├── session.py
│   │   │   └── base.py
│   │   ├── models/                     # SQLAlchemy модели
│   │   │   ├── tenant.py
│   │   │   ├── user.py
│   │   │   ├── integration.py
│   │   │   ├── raw/                    # сырые данные из источников
│   │   │   │   ├── mefi_lead.py
│   │   │   │   ├── mefi_visit.py
│   │   │   │   ├── mefi_offer.py
│   │   │   │   ├── mefi_deal.py
│   │   │   │   ├── mefi_call.py
│   │   │   │   ├── mefi_salesperson.py
│   │   │   │   ├── meta_campaign.py
│   │   │   │   ├── google_ads_campaign.py
│   │   │   │   ├── tiktok_campaign.py
│   │   │   │   ├── ga4_session.py
│   │   │   │   └── gsc_query.py
│   │   │   ├── metrics/                # агрегированные метрики
│   │   │   │   ├── daily_kpi.py
│   │   │   │   ├── salesperson_kpi.py
│   │   │   │   └── source_kpi.py
│   │   │   └── insights/
│   │   │       ├── daily_insight.py
│   │   │       └── detected_problem.py
│   │   ├── schemas/                    # Pydantic схемы для API
│   │   ├── services/
│   │   │   ├── integrations/           # клиенты для каждого источника
│   │   │   │   ├── base.py
│   │   │   │   ├── mefi.py
│   │   │   │   ├── meta_ads.py
│   │   │   │   ├── google_ads.py
│   │   │   │   ├── tiktok_ads.py
│   │   │   │   ├── ga4.py
│   │   │   │   └── search_console.py
│   │   │   ├── metrics/                # расчёт KPI
│   │   │   │   ├── marketing.py
│   │   │   │   ├── sales.py
│   │   │   │   └── salesperson.py
│   │   │   ├── anomaly_detection/      # детекция проблем
│   │   │   │   ├── rules.py
│   │   │   │   └── detector.py
│   │   │   └── insights/
│   │   │       ├── prompt_builder.py
│   │   │       ├── claude_client.py
│   │   │       └── parser.py
│   │   └── tasks/                      # Celery tasks
│   │       ├── celery_app.py
│   │       ├── etl/
│   │       │   ├── sync_mefi.py
│   │       │   ├── sync_meta.py
│   │       │   ├── sync_google_ads.py
│   │       │   ├── sync_tiktok.py
│   │       │   ├── sync_ga4.py
│   │       │   └── sync_gsc.py
│   │       ├── metrics_calc.py
│   │       └── insights_generator.py
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── next.config.js
│   ├── app/
│   │   ├── (auth)/login/
│   │   ├── (dashboard)/
│   │   │   ├── layout.tsx
│   │   │   ├── overview/page.tsx
│   │   │   ├── marketing/page.tsx
│   │   │   ├── sales/page.tsx
│   │   │   ├── salespeople/
│   │   │   │   ├── page.tsx
│   │   │   │   └── [id]/page.tsx
│   │   │   ├── insights/
│   │   │   │   ├── page.tsx
│   │   │   │   └── [date]/page.tsx
│   │   │   └── integrations/page.tsx
│   │   └── layout.tsx
│   ├── components/
│   │   ├── charts/
│   │   ├── insights/
│   │   ├── dashboards/
│   │   └── ui/
│   ├── lib/
│   │   ├── api.ts
│   │   ├── auth.ts
│   │   └── i18n/                       # ro/en/ru
│
├── infra/
│   ├── caddy/Caddyfile
│   └── scripts/
│       └── init_db.sql
│
└── tests/
    ├── backend/
    │   ├── unit/
    │   └── integration/
    └── e2e/
```

---

## 7. Схема БД (PostgreSQL)

### Слой 1: Tenants, Users, Integrations

```sql
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    industry TEXT,                       -- "furniture", "real_estate", etc.
    locale TEXT DEFAULT 'ro',
    timezone TEXT DEFAULT 'Europe/Bucharest',
    funnel_config JSONB,                 -- этапы воронки клиента (для Sofa Belle: Lead→Vizita→Oferta→Contract)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    active BOOLEAN DEFAULT TRUE
);

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT,
    role TEXT CHECK (role IN ('owner', 'analyst', 'admin')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_login TIMESTAMPTZ
);

CREATE TABLE integrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    source TEXT CHECK (source IN ('mefi', 'meta_ads', 'google_ads', 'tiktok_ads', 'ga4', 'search_console')),
    credentials JSONB NOT NULL,          -- зашифрованные через Fernet
    config JSONB,                        -- account_id, property_id, etc.
    status TEXT DEFAULT 'active',
    last_sync_at TIMESTAMPTZ,
    last_sync_status TEXT,
    last_sync_error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, source)
);
```

### Слой 2: Raw data (MEFI)

```sql
CREATE TABLE mefi_leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    external_id TEXT NOT NULL,
    created_at_source TIMESTAMPTZ,
    source TEXT,                         -- "Facebook", "Google", "Website", "Showroom"
    category TEXT,                       -- 'mail_fb_ig', 'telefon', 'whatsapp', 'site', 'designer', 'alte'
    utm_source TEXT,
    utm_medium TEXT,
    utm_campaign TEXT,
    status TEXT,
    salesperson_id TEXT,
    customer_phone TEXT,
    customer_name TEXT,
    raw_payload JSONB,
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, external_id)
);
CREATE INDEX ON mefi_leads (tenant_id, created_at_source DESC);
CREATE INDEX ON mefi_leads (tenant_id, source);
CREATE INDEX ON mefi_leads (tenant_id, category);
CREATE INDEX ON mefi_leads (tenant_id, salesperson_id);

CREATE TABLE mefi_lead_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    lead_external_id TEXT,
    changed_at TIMESTAMPTZ,
    from_status TEXT,
    to_status TEXT,
    changed_by TEXT
);
CREATE INDEX ON mefi_lead_history (tenant_id, lead_external_id);

CREATE TABLE mefi_visits (               -- визиты в шоурум (специфика премиум-мебели)
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    external_id TEXT NOT NULL,
    lead_external_id TEXT,
    salesperson_id TEXT,
    visited_at_source TIMESTAMPTZ,
    showroom TEXT,                       -- 'Brașov', 'București', 'Cluj'
    duration_minutes INT,
    outcome TEXT,                        -- 'offer_sent', 'no_interest', 'follow_up'
    raw_payload JSONB,
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, external_id)
);
CREATE INDEX ON mefi_visits (tenant_id, visited_at_source DESC);
CREATE INDEX ON mefi_visits (tenant_id, salesperson_id);
CREATE INDEX ON mefi_visits (tenant_id, showroom);

CREATE TABLE mefi_offers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    external_id TEXT NOT NULL,
    lead_external_id TEXT,
    visit_external_id TEXT,
    salesperson_id TEXT,
    amount NUMERIC(12,2),
    status TEXT,                         -- 'sent', 'accepted', 'rejected', 'expired'
    sent_at_source TIMESTAMPTZ,
    raw_payload JSONB,
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, external_id)
);
CREATE INDEX ON mefi_offers (tenant_id, sent_at_source DESC);

CREATE TABLE mefi_deals (                -- контракты
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    external_id TEXT NOT NULL,
    lead_external_id TEXT,
    offer_external_id TEXT,
    salesperson_id TEXT,
    amount NUMERIC(12,2),
    currency TEXT DEFAULT 'RON',
    status TEXT,                         -- 'won', 'lost', 'pending'
    loss_reason TEXT,
    items_count INT,
    created_at_source TIMESTAMPTZ,
    closed_at_source TIMESTAMPTZ,
    raw_payload JSONB,
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, external_id)
);
CREATE INDEX ON mefi_deals (tenant_id, created_at_source DESC);
CREATE INDEX ON mefi_deals (tenant_id, salesperson_id);
CREATE INDEX ON mefi_deals (tenant_id, status);

CREATE TABLE mefi_calls (                -- звонки (обогащённые DOTRO/3CX через MEFI)
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    external_id TEXT NOT NULL,
    salesperson_id TEXT,
    customer_phone TEXT,
    lead_external_id TEXT,
    direction TEXT,                      -- 'inbound' | 'outbound'
    status TEXT,                         -- 'answered' | 'missed' | 'busy' | 'no_answer'
    duration_seconds INT,
    started_at_source TIMESTAMPTZ,
    -- данные от MonitorAI/3CX AI, читаем как есть:
    transcript_summary TEXT,
    sentiment_score NUMERIC(3,2),
    sentiment_label TEXT,                -- 'positive', 'neutral', 'negative'
    topics TEXT[],
    raw_payload JSONB,
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, external_id)
);
CREATE INDEX ON mefi_calls (tenant_id, started_at_source DESC);
CREATE INDEX ON mefi_calls (tenant_id, salesperson_id);

CREATE TABLE mefi_salespeople (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    external_id TEXT NOT NULL,
    full_name TEXT,
    email TEXT,
    showroom TEXT,
    active BOOLEAN DEFAULT TRUE,
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, external_id)
);
```

### Слой 2: Raw data (рекламные системы)

```sql
CREATE TABLE meta_ad_campaigns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    external_id TEXT NOT NULL,
    name TEXT,
    objective TEXT,
    status TEXT,
    raw_payload JSONB,
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, external_id)
);

CREATE TABLE meta_ad_insights_daily (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    campaign_external_id TEXT,
    date DATE,
    spend NUMERIC(10,2),
    impressions BIGINT,
    clicks BIGINT,
    ctr NUMERIC(5,4),
    cpc NUMERIC(8,2),
    cpm NUMERIC(8,2),
    reach BIGINT,
    actions JSONB,
    raw_payload JSONB,
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, campaign_external_id, date)
);
CREATE INDEX ON meta_ad_insights_daily (tenant_id, date DESC);

-- Аналогичные таблицы для Google Ads и TikTok Ads:
-- google_ads_campaigns, google_ads_insights_daily
-- tiktok_ad_campaigns, tiktok_ad_insights_daily
```

### Слой 2: Raw data (веб-аналитика, Итерация 3)

```sql
CREATE TABLE ga4_sessions_daily (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    date DATE,
    source TEXT,                         -- 'google', 'facebook', 'direct', 'organic'
    medium TEXT,                         -- 'cpc', 'organic', 'social', 'referral'
    campaign TEXT,
    sessions BIGINT,
    users BIGINT,
    page_views BIGINT,
    bounce_rate NUMERIC(5,4),
    avg_session_duration NUMERIC(8,2),
    conversions BIGINT,
    raw_payload JSONB,
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, date, source, medium, campaign)
);

CREATE TABLE gsc_queries_daily (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    date DATE,
    query TEXT,
    page TEXT,
    clicks INT,
    impressions INT,
    ctr NUMERIC(5,4),
    position NUMERIC(5,2),
    raw_payload JSONB,
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, date, query, page)
);
```

### Слой 3: Aggregated metrics

```sql
CREATE TABLE daily_kpi (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    date DATE,

    -- Marketing: бюджеты
    spend_meta NUMERIC(10,2),
    spend_google NUMERIC(10,2),
    spend_tiktok NUMERIC(10,2),
    spend_digital_total NUMERIC(10,2),

    -- Marketing: трафик
    web_sessions INT,                    -- из GA4
    web_conversion_rate NUMERIC(5,4),

    -- Marketing: лиды по категориям (как у Sofa Belle)
    leads_mail_fb_ig INT,
    leads_telefon INT,
    leads_whatsapp INT,
    leads_site INT,
    leads_designer INT,
    leads_alte INT,
    leads_total INT,

    -- Marketing: экономика
    cpl_overall NUMERIC(8,2),
    cpl_by_channel JSONB,                -- {"meta": 105, "google": 80, "tiktok": 60}

    -- Sales: воронка (Lead → Visit → Offer → Contract)
    visits_count INT,
    offers_count INT,
    contracts_count INT,

    -- Sales: конверсии воронки
    conversion_l_to_v NUMERIC(5,4),      -- Lead → Visit
    conversion_v_to_o NUMERIC(5,4),      -- Visit → Offer
    conversion_l_to_o NUMERIC(5,4),      -- Lead → Offer
    conversion_o_to_c NUMERIC(5,4),      -- Offer → Contract
    conversion_l_to_c NUMERIC(5,4),      -- Lead → Contract (общая)

    -- Sales: финансы
    revenue NUMERIC(12,2),               -- Încasări
    avg_deal_size NUMERIC(10,2),         -- Cec mediu
    avg_deal_size_per_day NUMERIC(10,2), -- Cec mediu / zi
    cost_acquisition_contract NUMERIC(10,2),

    -- Compound
    cac NUMERIC(10,2),
    roas NUMERIC(8,2),

    -- Звонки (если данные доступны)
    calls_total INT,
    calls_answered INT,
    calls_missed INT,
    avg_call_duration_seconds INT,
    avg_sentiment_score NUMERIC(3,2),

    calculated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, date)
);
CREATE INDEX ON daily_kpi (tenant_id, date DESC);

CREATE TABLE salesperson_daily_kpi (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    salesperson_external_id TEXT,
    date DATE,

    leads_assigned INT,
    leads_contacted INT,
    avg_time_to_first_touch_minutes INT,

    visits_conducted INT,
    offers_sent INT,
    deals_won INT,
    deals_lost INT,
    revenue NUMERIC(12,2),

    conversion_l_to_v NUMERIC(5,4),
    conversion_v_to_o NUMERIC(5,4),
    conversion_o_to_c NUMERIC(5,4),
    conversion_l_to_c NUMERIC(5,4),
    avg_deal_size NUMERIC(10,2),

    calls_made INT,
    calls_answered INT,
    avg_call_duration_seconds INT,
    avg_sentiment_score NUMERIC(3,2),

    calculated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, salesperson_external_id, date)
);
CREATE INDEX ON salesperson_daily_kpi (tenant_id, date DESC, salesperson_external_id);

CREATE TABLE source_daily_kpi (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    source TEXT,                         -- 'meta', 'google', 'tiktok', 'organic', 'direct', 'showroom'
    date DATE,

    leads INT,
    ad_spend NUMERIC(10,2),
    cpl NUMERIC(8,2),
    visits INT,
    offers INT,
    deals_won INT,
    revenue NUMERIC(12,2),
    cac NUMERIC(10,2),
    roas NUMERIC(8,2),
    conversion_rate NUMERIC(5,4),

    calculated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, source, date)
);
```

### Слой 4: AI Insights

```sql
CREATE TABLE detected_problems (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    date DATE,
    rule_id TEXT,
    severity TEXT,                       -- 'high', 'medium', 'low', 'positive'
    category TEXT,                       -- 'marketing', 'sales', 'team', 'funnel'
    metric_name TEXT,
    current_value NUMERIC,
    expected_value NUMERIC,
    delta_percent NUMERIC,
    context JSONB,
    estimated_impact_revenue NUMERIC,
    detected_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX ON detected_problems (tenant_id, date DESC, severity);

CREATE TABLE daily_insights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    date DATE,

    summary TEXT,
    problems JSONB,
    positives JSONB,
    warnings JSONB,
    weekly_action_plan JSONB,

    raw_llm_response TEXT,
    llm_model TEXT,
    tokens_used INT,
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, date)
);
CREATE INDEX ON daily_insights (tenant_id, date DESC);
```

### Слой 5: AI Chat ⭐ NEW

```sql
CREATE TABLE chat_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    user_id UUID REFERENCES users(id),
    title TEXT,                          -- автогенерится из первого вопроса или AI-summary
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_message_at TIMESTAMPTZ DEFAULT NOW(),
    archived BOOLEAN DEFAULT FALSE
);
CREATE INDEX ON chat_conversations (tenant_id, user_id, last_message_at DESC);

CREATE TABLE chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES chat_conversations(id) ON DELETE CASCADE,
    tenant_id UUID REFERENCES tenants(id),
    role TEXT CHECK (role IN ('user', 'assistant', 'tool_use', 'tool_result')),
    content TEXT,                        -- текст сообщения (для user/assistant)
    tool_calls JSONB,                    -- [{name, input}] если Claude вызывает tools
    tool_results JSONB,                  -- результаты вызовов tools
    tokens_used INT,                     -- для биллинга и аналитики
    duration_ms INT,                     -- сколько занял этот шаг
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX ON chat_messages (conversation_id, created_at);

CREATE TABLE chat_tool_calls (           -- audit лог вызовов tools (для отладки и мониторинга)
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    message_id UUID REFERENCES chat_messages(id) ON DELETE CASCADE,
    tool_name TEXT,
    input_args JSONB,
    output_data JSONB,
    duration_ms INT,
    error TEXT,                          -- если tool упал
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX ON chat_tool_calls (tenant_id, tool_name, created_at DESC);
```

**Зачем три таблицы вместо одной:**

- `chat_conversations` — метаданные беседы (для списка слева в UI)
- `chat_messages` — каждое сообщение в беседе (для рендера диалога)
- `chat_tool_calls` — отдельный audit log вызовов tools для мониторинга качества AI (помогает анализировать какие tools Claude вызывает чаще и не возвращают ли они мусор)

````

---

## 8. Метрики и формулы

### Marketing Metrics

| Метрика | Формула | Источник | Заметка |
|---|---|---|---|
| **Buget META** | SUM(spend) | Meta Ads API | Helă бюджет META по дням/месяцам |
| **Buget Google** | SUM(cost) | Google Ads API | |
| **Buget TikTok** | SUM(spend) | TikTok API | |
| **Buget Digital Total** | sum всех каналов | Meta+Google+TikTok | |
| **Trafic (sesiuni)** | sum(sessions) | GA4 | Итерация 3 |
| **Leads Mail/FB/IG** | COUNT WHERE category='mail_fb_ig' | MEFI | |
| **Leads Telefon** | COUNT WHERE category='telefon' | MEFI | |
| **Leads WhatsApp** | COUNT WHERE category='whatsapp' | MEFI | |
| **Leads Site** | COUNT WHERE category='site' | MEFI | |
| **Leads Designer** | COUNT WHERE category='designer' | MEFI | |
| **Leads Alte** | COUNT WHERE category='alte' | MEFI | |
| **Leads Total** | COUNT всех лидов | MEFI | |
| **Cost per Lead** | ad_spend / leads | Ads + MEFI | По каналам и общий |
| **Conversie site** | leads / sessions | MEFI + GA4 | % |
| **CTR** | clicks / impressions | Ads | |
| **CPC** | spend / clicks | Ads | |
| **CPM** | (spend / impressions) × 1000 | Ads | |
| **CAC** | total_marketing_cost / won_deals | All | Cost Aquisition Contract |
| **ROAS** | revenue / ad_spend | All | |
| **YoY** | (current - last_year) / last_year × 100 | All | Стандартный режим сравнения |

### Sales Metrics (воронка Sofa Belle: Lead → Vizita → Oferta → Contract)

| Метрика | Формула | Источник |
|---|---|---|
| **Vizita** | COUNT визитов в шоурум | MEFI |
| **Oferta** | COUNT отправленных оферт | MEFI |
| **Contract** | COUNT закрытых контрактов | MEFI |
| **Conversie L→V** | visits / leads | MEFI |
| **Conversie V→O** | offers / visits | MEFI |
| **Conversie L→O** | offers / leads | MEFI |
| **Conversie O→C** | contracts / offers | MEFI |
| **Conversie L→C** | contracts / leads | MEFI (общая) |
| **Cec mediu** | revenue / contracts | MEFI (средний чек) |
| **Cec mediu / zi** | revenue_per_day / contracts_per_day | MEFI |
| **Cost Acquisition Contract** | total_marketing_cost / contracts | All |
| **Încasări** | SUM(amount) WHERE status='won' | MEFI |
| **Items per Deal** | AVG(items_count) | MEFI |
| **Time to First Touch** | first_call_at - lead_created_at | MEFI |
| **Sales Cycle Days** | contract_date - lead_date | MEFI |
| **Win Rate** | won / (won + lost) | MEFI |
| **YoY Revenue** | current_revenue / last_year_revenue × 100 | MEFI |

### Per-salesperson Metrics
Все sales-метрики дублируются на уровне продавца. Плюс:

| Метрика | Формула | Источник |
|---|---|---|
| **Calls Made** | COUNT звонков | MEFI |
| **Answered Rate** | answered / total_calls | MEFI |
| **Avg Call Duration** | AVG(duration) | MEFI |
| **Avg Sentiment** | AVG(sentiment_score) | MEFI (через MonitorAI) |

### Временные окна
Все метрики считаются для:
- Сегодня
- 7 дней
- 30 дней
- 90 дней (важно для длинного цикла Sofa Belle)
- Custom range
- **YoY toggle:** сравнение с тем же периодом год назад (стандартный режим)

---

## 9. Anomaly Detection (правила детекции проблем)

Перед вызовом LLM алгоритмически детектируем проблемы по правилам. LLM получает структурированный список и формирует человеческий отчёт с планом действий.

### Marketing rules

```yaml
rule_id: source_drop
trigger: leads_from_source_7d < leads_from_source_previous_7d × 0.7
severity: high if main_source else medium
category: marketing
description: "Источник лидов теряет эффективность"

rule_id: cpl_increase
trigger: cpl_7d > cpl_previous_30d × 1.3
severity: high if main_source else medium
category: marketing
description: "Стоимость лида растёт"

rule_id: roas_drop
trigger: roas_7d < roas_previous_30d × 0.7
severity: high
category: marketing
description: "Окупаемость рекламы падает"

rule_id: budget_overrun
trigger: spend_month_to_date > planned_budget × 1.1
severity: medium
category: marketing
description: "Превышение запланированного бюджета"
````

### Sales rules

```yaml
rule_id: slow_first_touch
trigger: avg_time_to_first_touch > 4_hours (в рабочее время)
severity: high if > 24h else medium
category: sales
description: "Медленная реакция на лид"

rule_id: bottleneck_l_to_v
trigger: conversion_l_to_v_7d < conversion_l_to_v_baseline × 0.8
severity: high
category: funnel
description: "Узкое горлышко: лиды не доходят до визита"

rule_id: bottleneck_v_to_o
trigger: conversion_v_to_o_7d < conversion_v_to_o_baseline × 0.8
severity: high
category: funnel
description: "Узкое горлышко: визиты не конвертируются в оферту"

rule_id: bottleneck_o_to_c
trigger: conversion_o_to_c_7d < conversion_o_to_c_baseline × 0.8
severity: high
category: funnel
description: "Узкое горлышко: оферты не закрываются в контракт"

rule_id: stuck_offers
trigger: count(offers WHERE status='sent' AND last_activity > 14d) > 0
severity: medium
category: sales
description: "Зависшие оферты без активности"

rule_id: avg_deal_drop
trigger: avg_deal_size_30d < avg_deal_size_previous_90d × 0.85
severity: medium
category: sales
description: "Падение среднего чека"
```

### Team rules

```yaml
rule_id: salesperson_drop
trigger: salesperson_conversion_7d < salesperson_conversion_30d × 0.7
severity: medium
category: team
description: "Падение производительности конкретного продавца"

rule_id: missed_calls_high
trigger: missed_calls_rate_7d > 0.2
severity: high
category: team
description: "Слишком много пропущенных входящих звонков"

rule_id: negative_sentiment
trigger: avg_sentiment_score_7d < -0.2
severity: high
category: team
description: "Негативный sentiment в звонках"
```

### Положительные сигналы

```yaml
rule_id: salesperson_outperform
trigger: salesperson_conversion_7d > team_avg × 1.3
severity: positive
category: team

rule_id: source_improve
trigger: cpl_decrease AND leads_increase
severity: positive
category: marketing

rule_id: revenue_growth
trigger: revenue_30d > revenue_previous_30d × 1.2
severity: positive
category: business
```

**Список правил расширяется итеративно** на основе обратной связи от Sofa Belle и других клиентов. Стартовый набор согласовывается с собственником.

---

## 10. AI Insights (Claude Sonnet 4.5)

### System Prompt (черновик на румынском)

```
Ești un consultant experimentat de marketing și vânzări pentru companii mici
și mijlocii din România. Vorbești în limba română, direct și la obiect, fără
apă. Sarcina ta este, pe baza datelor companiei, să formulezi un plan practic
de acțiune pe care proprietarul îl poate executa într-o săptămână.

Principii:
- Fiecare problemă trebuie să aibă o estimare a impactului în RON.
- Fiecare plan de acțiune — pași concreți cu responsabil și termen.
- Maximum 3 probleme de prioritate înaltă (focus mai important decât completitudine).
- Stil: concis, business-tone, fără jargon.
- Niciun fapt inventat — folosește doar datele din input.

Format de răspuns: JSON conform schemei specificate.
```

### Input structure

```json
{
  "tenant": {
    "name": "Sofa Belle",
    "industry": "furniture_premium",
    "size": "small (6 salespeople, 3 showrooms)",
    "specifics": "Long sales cycle (2 weeks - 2 months), high-ticket (20.000+ RON)"
  },
  "period": {
    "from": "2026-05-11",
    "to": "2026-05-17",
    "comparison_period": "2026-05-04 to 2026-05-10"
  },
  "metrics": { ... все KPI за период },
  "yoy": { ... те же метрики год назад },
  "detected_problems": [ ... список найденных аномалий ]
}
```

### Output JSON Schema

```json
{
  "summary": "Un paragraf de prezentare generală a perioadei.",
  "problems": [
    {
      "id": "slug",
      "severity": "high" | "medium" | "low",
      "category": "marketing" | "sales" | "team" | "funnel",
      "title": "Titlu scurt al problemei",
      "description": "2-3 propoziții cu cifre",
      "estimated_loss_ron": 30000,
      "actions": [
        {
          "order": 1,
          "description": "Acțiune concretă",
          "owner": "Nume vânzător sau rol",
          "deadline": "2026-05-22",
          "expected_outcome": "Metrică și valoare așteptată"
        }
      ]
    }
  ],
  "positives": [
    {
      "title": "Ce merge bine",
      "description": "...",
      "recommendation": "Ce să reproducem"
    }
  ],
  "warnings": [
    {
      "title": "Semnal slab",
      "description": "..."
    }
  ],
  "weekly_action_plan": [
    "Acțiune 1 (prioritate 1)",
    "Acțiune 2 (prioritate 2)"
  ]
}
```

### Стоимость LLM

- Claude Sonnet 4.5: $3 / 1M input tokens, $15 / 1M output tokens
- Средний запрос: ~3000 input + ~2500 output = $0.009 + $0.0375 = **~$0.05 за инсайт**
- Для Sofa Belle: 1 инсайт/день × 30 = **~$1.50/месяц**
- На 100 клиентов: ~$150/мес

### Частота генерации

- **06:00 каждый день** — автоматическая генерация после ETL и metrics calc
- **Кнопка "Refresh insights"** в UI — пересчёт по требованию (rate limit: не чаще 1 раза в час)

---

## 11. AI Chat (интерактивный)

> **Полная спецификация:** [docs/CHAT.md](./docs/CHAT.md)

### Концепция

Помимо ежедневных batch-инсайтов (раздел 10), у пользователя есть **интерактивный AI-чат**, где можно задавать вопросы о своих данных на естественном румынском языке.

**Зачем:** batch-инсайт — это монолог раз в день. Чат — это диалог в любой момент. Owner или manager заходит и спрашивает:

- "Cum stăm comparativ cu săptămâna trecută?" (Как у нас дела по сравнению с прошлой неделей?)
- "Care este cel mai bun vânzător luna asta?" (Кто лучший продавец в этом месяце?)
- "De ce a scăzut conversia la oferte?" (Почему упала конверсия в оферты?)
- "Ce ar trebui să fac pentru a crește vânzările?" (Что делать чтобы увеличить продажи?)
- "Care e CAC pentru Meta Ads anul acesta vs anul trecut?" (CAC по Meta в этом году vs прошлом?)
- "Arată-mi lead-urile blocate de mai mult de 14 zile" (Покажи лиды зависшие >14 дней)

**Это качественно меняет позиционирование продукта** с "BI-дашборд с отчётом" на "AI-консультант с цифрами на бэкенде".

### Технический подход: Tool Use (Function Calling)

Используем **function calling** Claude Sonnet 4.5. Claude получает доступ к **набору функций** для запроса БД и сам решает какие вызвать:

```
User: "Кто лучший продавец в мае?"
  ↓
Claude думает: "Нужно вызвать get_salesperson_performance"
  ↓
Claude вызывает: get_salesperson_performance(date_range="2026-05-01..2026-05-31", metric="revenue")
  ↓
Backend выполняет SQL запрос, возвращает: {"top": "Maria Ionescu", "revenue": 245000, ...}
  ↓
Claude формулирует ответ на румынском с цифрами + контекстом
```

**Почему function calling, а не embedding всех данных в prompt:**

- Точность — Claude не выдумывает цифры, он получает их из БД
- Эффективность — не грузим всё в контекст (10x экономия токенов)
- Масштабируемость — работает на любом объёме данных
- Свежесть — всегда актуальные цифры

### Доступные tools для Claude

Минимальный набор для MVP1:

| Tool                                                       | Назначение                                       |
| ---------------------------------------------------------- | ------------------------------------------------ |
| `get_kpi(date_range, metric_name)`                         | Конкретный KPI за период                         |
| `get_funnel_data(date_range)`                              | Воронка L→V→O→C с конверсиями                    |
| `get_salesperson_performance(salesperson_id?, date_range)` | Метрики продавца(ов)                             |
| `get_leads(filters)`                                       | Список/фильтр лидов                              |
| `compare_periods(period_a, period_b)`                      | Сравнение двух периодов                          |
| `get_loss_reasons(date_range)`                             | Распределение причин потерь                      |
| `get_lead_categories_breakdown(date_range)`                | Лиды по категориям (Mail/FB/IG, Telefon, и т.д.) |
| `get_showroom_performance(showroom?, date_range)`          | Метрики по шоуруму                               |
| `get_recent_insight(date)`                                 | Последний AI-инсайт за день                      |
| `explain_metric(metric_name)`                              | Объяснить что такое метрика                      |

В Итерации 2 добавляются tools для рекламных систем (Meta/Google/TikTok), в Итерации 3 — для GA4 и GSC.

### Защита от галлюцинаций

Главный риск AI-чата — Claude может **выдумать цифру**. Защита:

1. **Cross-check регексом:** все числа в ответе Claude проверяются против БД. Если Claude написал "продажи 245.000 lei", а в результатах tool было 235.000 lei — отбраковываем ответ
2. **Whitelisted сущности:** имена продавцов, шоурумов, кампаний — только из реальной БД, не выдуманные
3. **Honesty prompt:** в системном промпте Claude явно проинструктирован "если данных нет — сказать честно, не выдумывать"
4. **Tool-only data:** Claude **не имеет права** называть конкретные цифры без предварительного вызова tool

### UI

Новая страница `Chat` в навигации:

- Список бесед (как в ChatGPT) слева
- Текущая беседа справа
- Над инпутом — пресеты типовых вопросов (на румынском)
- В ответах Claude — inline ссылки на дашборды (например: "[→ Sales Dashboard]")
- Индикатор "thinking..." когда Claude вызывает tools
- История сохраняется в БД per user

### Стоимость

Claude Sonnet 4.5:

- Один диалог (5-10 вопросов): ~22.500 tokens = ~$0.07
- Активный клиент (2-3 диалога в неделю на 2-х пользователей): ~24 диалогов/мес = ~$1.70/мес
- В сумме с batch инсайтами: **~$3-5/мес на клиента**

Закладываем в pricing.

### Метрики успеха Phase 8 (MVP1)

- ✅ Пользователь задаёт вопрос на румынском → получает осмысленный ответ за <5 секунд
- ✅ Все числа в ответах верифицированы (regex cross-check) против БД — zero hallucinated KPI values
- ✅ Имена продавцов / шоурумов / кампаний — только реальные из БД
- ✅ Когда данных нет (например, спрашивают про deals API которого нет) — Claude честно говорит, не выдумывает
- ✅ История бесед сохраняется и доступна между сессиями
- ✅ Inline-ссылки на дашборды работают
- ✅ Минимум 10 tools реализованы и протестированы
- ✅ Sofa Belle подтверждает что чат полезен (NPS ≥ 8/10 по этой фиче)

---

## 12. API Endpoints

### Auth

- `POST /api/v1/auth/login` — email + password → JWT
- `GET /api/v1/auth/me`
- `POST /api/v1/auth/refresh`

### Tenants (admin only)

- `POST /api/v1/admin/tenants`
- `GET /api/v1/admin/tenants`
- `PATCH /api/v1/admin/tenants/{id}`

### Integrations

- `GET /api/v1/integrations` — список интеграций тенанта со статусом
- `POST /api/v1/integrations/{source}/connect` — старт OAuth flow
- `GET /api/v1/integrations/{source}/callback` — OAuth callback
- `DELETE /api/v1/integrations/{source}` — отключить
- `POST /api/v1/integrations/{source}/sync` — manual trigger sync

### Dashboards

- `GET /api/v1/dashboards/overview?from=&to=&compare=yoy|prev_period`
- `GET /api/v1/dashboards/marketing?from=&to=&compare=&channel=`
- `GET /api/v1/dashboards/sales?from=&to=&compare=`
- `GET /api/v1/dashboards/salespeople?from=&to=` — список продавцов с метриками
- `GET /api/v1/dashboards/salespeople/{id}?from=&to=` — детали

### Insights

- `GET /api/v1/insights/today`
- `GET /api/v1/insights/by-date/{date}`
- `GET /api/v1/insights?from=&to=` — архив
- `POST /api/v1/insights/refresh` — manual regenerate (rate-limited)

### Chat ⭐ (Phase 8)

- `POST /api/v1/chat/conversations` — создать новую беседу
- `GET /api/v1/chat/conversations` — список бесед пользователя
- `GET /api/v1/chat/conversations/{id}` — история конкретной беседы
- `DELETE /api/v1/chat/conversations/{id}` — удалить беседу
- `POST /api/v1/chat/conversations/{id}/messages` — отправить сообщение (с streaming response)
- `GET /api/v1/chat/suggested-questions` — пресет вопросов на текущий момент (контекстуально)

### Metrics (drill-down для аналитика)

- `GET /api/v1/metrics/leads?...` — список лидов с фильтрами
- `GET /api/v1/metrics/deals?...`
- `GET /api/v1/metrics/calls?...`

---

## 13. UI / Frontend

### 13.1 Главное меню (sidebar)

- 🏠 **Overview** — общий обзор
- 📈 **Marketing** — Marketing Dashboard
- 💼 **Sales** — Sales Dashboard
- 👥 **Salespeople** — Список продавцов
- 💡 **Insights** ⭐ (с бейджем "Today's report ready")
- 💬 **Chat** ⭐ NEW — задать вопрос Claude
- ⚙️ **Integrations**
- 👤 Profile / Settings

### 13.2 Overview Page

- Date range picker + YoY toggle
- 6 главных KPI карточек: Revenue, Contracts, New Leads, Cec mediu, CAC, ROAS
- Краткий блок "Today's Top Insight" → клик ведёт на Insights
- График Revenue по дням
- Воронка Lead → Vizita → Oferta → Contract (упрощённая)

### 13.3 Marketing Dashboard

**Структура повторяет логику Excel-таблицы Sofa Belle** (клиент сразу узнает свои метрики).

- **Header:** date range + YoY toggle
- **Бюджеты:** карточки Buget META, Buget Google, Buget TikTok, Buget Digital Total
- **Trafic:** sessions, conversie site
- **Лиды по категориям:** Mail/FB/IG, Telefon, WhatsApp, Site, Designer, Alte, Total — в таблице с YoY
- **Cost per Lead:** общий и по каналам
- **Таблица по каналам:**
  - Канал | Бюджет | Лиды | CPL | CAC | Контракты | Выручка | ROAS
- **SEO блок (Итерация 3):** top queries, traffic trend, средняя позиция
- **Web behavior (Итерация 3):** конверсия по landing pages

### 13.4 Sales Dashboard

- **Header:** date range + YoY toggle
- **Воронка Lead → Vizita → Oferta → Contract** с конверсиями между этапами (L/V, V/O, O/C)
- **Карточки:** Încasări, Contracts, Cec mediu, Cec mediu/zi, Conversie totală L→C, Sales Cycle Days
- **По этапам:** сколько активных на каждом этапе, среднее время на этапе
- **Stuck offers widget:** список оферт без активности > 14 дней
- **Loss reasons:** pie chart причин потерь
- **Calls overview (если данные есть):** total, answered rate, avg duration, avg sentiment

### 13.5 Salespeople Page

- **Leaderboard:** таблица всех продавцов
  - Имя | Шоурум | Лиды | Визиты | Оферты | Контракты | Выручка | Конверсия L→C | Cec mediu | Avg Sentiment
- Сортировка по любому столбцу
- Клик → детальная страница

### 13.6 Salesperson Detail Page

- Карточка с резюме: имя, шоурум
- Метрики vs команда (radar chart)
- Activity timeline (звонки, визиты, оферты, контракты)
- Список последних звонков (с привязкой к транскриптам в MEFI)
- Trends: динамика по неделям с YoY

### 13.7 Insights Page ⭐

- Дата отчёта (по умолчанию сегодня) + archive picker
- **Summary block:** 1-2 параграфа общего обзора (Claude)
- **Top Problems:**
  - Карточка для каждой проблемы (severity color-coded)
  - Заголовок, описание, оценка потерь в RON
  - Развёрнутый план действий с чекбоксами (можно отмечать выполненные)
- **What's Going Well:** позитивные блоки
- **Warnings:** оранжевые блоки слабых сигналов
- **Weekly Action Plan:** консолидированный чек-лист
- Кнопки: Print, Export PDF, Share via Email, Refresh

### 13.8 Chat Page ⭐ NEW (Phase 8)

**Layout (split panel):**

- **Left sidebar** (260px): Список всех бесед пользователя
  - Кнопка "Новая беседа" (New conversation)
  - Каждая беседа: заголовок (первый вопрос или AI-summary), дата, индикатор unread
  - Поиск по беседам
- **Right pane** (flex): Текущая беседа
  - Сообщения чередуются: пользователь (справа), Claude (слева)
  - У сообщений Claude — inline ссылки на дашборды
  - Под последним сообщением (если Claude думает) — индикатор "Caut datele..." (Ищу данные...)
  - Когда Claude вызывает tool — показывается какой именно (transparently): "🔍 get_funnel_data(...)"
- **Bottom input bar:**
  - Textarea с placeholder "Întreabă orice despre datele tale..." (Спроси что угодно о своих данных...)
  - Кнопка отправки (Enter)
  - **Над инпутом — chip-suggestions** с пресет-вопросами (контекстуальные, обновляются от страницы):
    - "Cum a fost săptămâna asta?"
    - "Care e cel mai bun vânzător?"
    - "Care lead-uri au nevoie de atenție?"
  - При клике на chip — текст вопроса вставляется в инпут (но не отправляется автоматически — даёт возможность отредактировать)

**Опционально (post-MVP):** микрофонная кнопка для голосового ввода через Web Speech API.

### 13.9 Integrations Page

- Список всех интеграций с статусом (✅ Connected / ❌ Not connected / ⚠️ Error)
- Карточка: source name, last sync time, "Sync now", "Disconnect"
- Wizard для подключения новой (OAuth flow)

### 13.10 i18n

Все user-facing строки через `next-intl`:

- **ro** (румынский) — основной для клиента
- **en** (английский) — для разработки и международного использования
- **ru** (русский) — для тебя как разработчика

---

## 14. Безопасность и GDPR

### Storage

- API credentials в БД зашифрованы (Fernet, key из env)
- БД на encrypted volume (LUKS на production)
- HTTPS обязателен (Caddy + Let's Encrypt)

### Multi-tenancy isolation

- Каждый запрос идёт с `tenant_id` из JWT
- На уровне SQLAlchemy — global filter по `tenant_id` через event listener
- Обязательные тесты на изоляцию

### GDPR

- **Sofa Belle = Data Controller, мы = Data Processor** → нужен DPA
- Данные клиентов Sofa Belle (телефоны, имена) обрабатываем по их инструкциям
- **Retention:** данные хранятся пока активна подписка + 90 дней. Затем hard delete.
- **Право на забвение:** `DELETE /api/v1/tenants/{id}/customer-data?phone=...`
- **Audit log:** кто, когда, какие данные смотрел
- Серверы в ЕС (Hetzner Germany или Unihost Romania)

### Доступ к третьим API

- OAuth-токены хранятся per tenant, зашифрованы
- Refresh tokens регулярно ротируем
- При auth error — уведомление клиенту "переподключите аккаунт"

---

## 15. Конфигурация (`.env.example`)

```bash
# Database
POSTGRES_USER=postgres
POSTGRES_PASSWORD=
POSTGRES_DB=analyst
DATABASE_URL=postgresql+asyncpg://postgres:${POSTGRES_PASSWORD}@postgres:5432/analyst

# Redis
REDIS_URL=redis://redis:6379/0

# JWT
JWT_SECRET=                              # openssl rand -hex 32
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440

# Encryption (для credentials)
FERNET_KEY=                              # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Anthropic
ANTHROPIC_API_KEY=
CLAUDE_MODEL=claude-sonnet-4-5

# MEFI
MEFI_API_BASE_URL=                       # уточнить после получения документации
MEFI_CLIENT_ID=
MEFI_CLIENT_SECRET=

# Meta (Итерация 2)
META_APP_ID=
META_APP_SECRET=
META_REDIRECT_URI=https://app.example.com/api/v1/integrations/meta_ads/callback

# Google (Итерации 2-3)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_ADS_DEVELOPER_TOKEN=
GOOGLE_REDIRECT_URI=https://app.example.com/api/v1/integrations/google/callback

# TikTok (Итерация 2)
TIKTOK_APP_ID=
TIKTOK_APP_SECRET=
TIKTOK_REDIRECT_URI=https://app.example.com/api/v1/integrations/tiktok/callback

# Application
APP_BASE_URL=https://app.example.com
ENVIRONMENT=development                  # development | staging | production
LOG_LEVEL=INFO
SENTRY_DSN=

# Hosting
DEFAULT_TIMEZONE=Europe/Bucharest
```

---

## 16. Принципы разработки

- **Type hints везде.** Python 3.11+, Pydantic v2.
- **Async-first.** FastAPI async endpoints, httpx, asyncpg.
- **Тесты:** pytest, минимум 70% coverage для бизнес-логики, обязательны integration-тесты для интеграций.
- **Логирование:** structlog, JSON-логи, **без PII**.
- **Миграции:** только через Alembic.
- **Секреты:** только через env, никогда в коде.
- **i18n:** все user-facing строки через `next-intl` (frontend) и gettext (backend для email).
- **Commit messages:** Conventional Commits (feat:, fix:, chore:, docs:, refactor:).
- **Линт:** ruff + mypy (Python), ESLint + Prettier (TS).
- **Pre-commit:** ruff, mypy, gitleaks, prettier.
- **CI:** GitHub Actions — lint + test на каждый PR, auto-deploy на main.
- **Архитектурный принцип:** backend никогда не вызывает третьи API синхронно во время HTTP-запроса. Только через Celery + БД как буфер.

---

## 17. Что нужно перед стартом

### Критичные блокеры (без этого не стартуем):

1. ⛔ **MEFI API документация.** Email шаблон — в Приложении A.
2. ⛔ **Тестовый MEFI-аккаунт от Sofa Belle.** Read-only доступ для разработки + согласие.
3. ✅ **Anthropic API key** (console.anthropic.com).

### Нужно до Итерации 2:

4. **Meta Business Manager** доступ к рекламному аккаунту Sofa Belle.
5. **Google Ads API Developer Token** — подать заявку заранее (1-3 недели).
6. **Google Cloud Project** для OAuth (Google Ads, GA4, GSC).
7. **TikTok for Business Developer App** регистрация.

### Нужно до Итерации 3:

8. **GA4 Property ID** Sofa Belle + service account.
9. **Search Console** доступ для sofabelle.ro.

### Бизнес:

10. **DPA-шаблон.** Юрист в Румынии может составить (типовой Data Processor Agreement).
11. **Согласование anomaly rules** с собственником Sofa Belle (что для него критично).
12. **Категоризация лидов в MEFI у Sofa Belle:** убедиться что они уже размечают лиды по категориям Mail/FB/IG, Telefon, WhatsApp, Site, Designer, Alte.

---

## 18. Метрики успеха MVP1 (Итерация 1)

- ✅ **ETL стабильно работает 7 дней подряд** без ошибок, ночной sync завершается за <30 минут
- ✅ **Sales Dashboard показывает корректные цифры** — сверка с MEFI BI: 100% совпадение
- ✅ **AI Insight генерируется каждое утро к 7:00** без сбоев
- ✅ **Качество вывода Claude (Insights):** собственник Sofa Belle подтверждает что 70%+ рекомендаций действительно полезны
- ✅ **AI Chat работает:** пользователь задаёт вопрос → получает осмысленный ответ за <5 секунд
- ✅ **Zero hallucinated numbers в Chat:** все числа верифицированы regex против БД
- ✅ **Chat coverage:** реализовано минимум 10 базовых tools (KPI, funnel, salesperson, etc.)
- ✅ **Sofa Belle через 2-3 недели пилота:** "Да, я бы платил за это X RON/мес" — цифра X = основа для pricing
- ✅ **Time to first 'aha-moment':** новый пользователь видит ценность за ≤ 5 минут от первого логина

---

## 19. Подробный Roadmap для Claude Code (Итерация 1)

### Этап 0: Подготовка (1-2 дня)

- Создать GitHub репо
- Docker Compose: PostgreSQL + Redis + backend + frontend (заглушки)
- Alembic initial migration
- README с инструкцией запуска
- **Подать заявку Google Ads Developer Token** (для будущей итерации, она долгая)

### Этап 1: Каркас backend (2-3 дня)

- FastAPI + SQLAlchemy + Alembic + Pydantic
- Модели: `tenants`, `users`, `integrations`
- Auth endpoints (JWT)
- Tenancy middleware
- Базовые тесты

### Этап 2: MEFI Integration (5-7 дней) ⚠️ КРИТИЧНО

- **Сначала получить документацию от MEFI.** Без этого этап не начать.
- Базовый MEFI client (httpx)
- Sync задачи (Celery): leads, visits, offers, deals, calls, salespeople
- Raw layer таблицы
- E2E тест: запустил sync → данные в БД

### Этап 3: Metrics Engine (3-4 дня)

- Расчёт `daily_kpi`, `salesperson_daily_kpi`, `source_daily_kpi`
- Celery задача после sync
- Тесты на корректность формул (особенно конверсий L/V/V/O/L/O/O/C)

### Этап 4: Anomaly Detection (2-3 дня)

- Реализация rules engine
- 10-12 стартовых правил
- Celery задача после metrics calc

### Этап 5: AI Insights Generator (3-4 дня)

- Prompt builder (на румынском)
- Claude API клиент
- Парсер JSON-ответа с валидацией
- Сохранение в `daily_insights`
- Celery задача после anomaly detection
- Тестирование на реальных данных Sofa Belle

### Этап 6: Backend API для UI (3 дня)

- Endpoints для dashboards
- Endpoints для insights
- OpenAPI документация авто-генерируется

### Этап 7: Frontend MVP1 (5-7 дней)

- Next.js setup, auth flow
- Layout с sidebar
- Pages: Overview, Marketing (базовый), Sales, Salespeople, Salesperson detail, Insights
- Tremor компоненты для графиков
- i18n: румынский + английский

### Этап 8: AI Chat (5-7 дней) ⭐ NEW

- **Backend (3-4 дня):**
  - Модели БД: `chat_conversations`, `chat_messages` (см. раздел 7)
  - Tool registry: реализовать 10 базовых tools (`get_kpi`, `get_funnel_data`, и т.д.)
  - Chat orchestrator: handle conversation flow, call tools, accumulate context
  - Hallucination guard: regex для cross-check чисел, whitelist имён сущностей
  - System prompt (на румынском) с контекстом бизнеса
  - API endpoints: `POST /chat/conversations/{id}/messages` со streaming
- **Frontend (2-3 дня):**
  - Страница `/chat` с split-layout (sidebar + main pane)
  - Streaming рендеринг ответов
  - Suggested questions chips (контекстуальные)
  - Inline ссылки на dashboards в ответах
  - История бесед
- **Тестирование:**
  - Чек-лист из 30+ типовых вопросов, проверка ответов
  - Adversarial testing: вопросы которые провоцируют галлюцинации
  - Performance: ответ <5 секунд для типовых запросов

### Этап 9: Testing & Polish (3-5 дней)

- E2E тесты (Playwright)
- Bug fixing с реальными данными Sofa Belle
- Performance: индексы в БД, query optimization
- Sentry интеграция

### Этап 10: Demo для Sofa Belle (1 неделя)

- Деплой на временный VPS или твоей машине + ngrok
- Демонстрация собственнику и аналитику
- Сбор обратной связи
- Быстрые правки

### → Итерация 2 (Meta + Google + TikTok Ads)

### → Итерация 3 (GA4 + Search Console)

### → Итерация 4 (Production multi-tenant)

---

## 20. Pricing (предварительно, не для MVP)

**Tier 1: Starter** — €49/мес

- 1 источник (MEFI only)
- Sales Dashboard + базовый Marketing
- Daily insights

**Tier 2: Growth** — €149/мес

- MEFI + Meta + Google + TikTok Ads
- Полноценный Marketing + Sales Dashboards
- Full AI insights
- До 10 пользователей

**Tier 3: Pro** — €299/мес

- - GA4 + Search Console
- Кастомные правила детекции
- API доступ
- Безлимит пользователей
- Приоритет поддержки

**Add-ons:**

- Onboarding / setup: разовый €500
- Кастомизация под индустрию: от €1000
- Бенчмарки между клиентами: +€50/мес (когда будут)

---

## 21. Приложения

### Приложение A: Шаблон email в MEFI Support (на румынском)

> **Subject:** Solicitare acces API pentru integrare cu MEFI CRM
>
> Bună ziua,
>
> Mă numesc [Имя] și dezvolt o platformă de analiză automatizată de marketing și vânzări pentru companii românești. Unul dintre clienții noștri pilot, **Sofa Belle (S.C. BELLE SOFA S.R.L.)**, folosește MEFI CRM și ne-a solicitat să integrăm platforma noastră cu datele lor din MEFI.
>
> Vă rog să ne furnizați informații despre:
>
> 1. **Disponibilitatea unui API public MEFI:** există documentație pentru dezvoltatori?
> 2. **Endpoint-uri relevante:** putem accesa programatic următoarele entități?
>    - Clienți potențiali (leads) cu istoricul modificărilor de statut
>    - Vizite în showroom
>    - Oferte
>    - Contracte / vânzări
>    - Apeluri (din integrarea cu telefonia)
>    - Utilizatori (agenți de vânzări)
>    - Configurarea pâlniei de vânzări
> 3. **Autentificare:** API key, OAuth 2.0, sau alt mecanism?
> 4. **Webhooks:** suportați notificări în timp real pentru evenimente (lead nou, contract semnat, vizită finalizată, etc.)?
> 5. **Rate limits:** există limite de cereri pe minut/oră/zi?
> 6. **Date sincronizate din telefonie:** apelurile primite din integrările cu DOTRO sau 3CX conțin transcript, sumarizare AI și scor sentiment (de la MonitorAI / 3CX AI)? Acestea sunt accesibile prin API?
> 7. **Date din module BI:** sunt accesibile programatic agregările precalculate?
>
> Suntem deschiși și pentru un parteneriat tehnic — dacă MEFI explorează colaborări cu produse complementare de analiză și AI, am fi interesați să discutăm.
>
> Mulțumesc!
>
> Cu stimă,
> [Имя]
> [Контакты]

### Приложение B: Открытые вопросы и отложенные решения

| Тема                                | Описание                                                                                                                               | Когда решать                                                          |
| ----------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| **Showroom-level аналитика**        | Разрез всех метрик по 3 шоурумам (Brașov, București, Cluj). Добавить поля `inbound_number` / `showroom` в звонки и связанные сущности. | После того как Sofa Belle подключит IP-телефонию с 3 разными номерами |
| **Геотаргетинг рекламы по городам** | Связь между городом таргетинга кампании и шоурумом. Расчёт CPL по шоуруму.                                                             | Итерация 2 или 3                                                      |
| **Точная цена MonitorAI у DOTRO**   | Сколько стоит транскрипция на объём Sofa Belle                                                                                         | После того как клиент подключит DOTRO                                 |
| **Бенчмарки между клиентами**       | Анонимизированные средние по индустрии                                                                                                 | После 5+ клиентов в системе                                           |
| **Telegram/WhatsApp бот**           | Push-уведомления о важных событиях                                                                                                     | Future                                                                |
| **Mobile/PWA версия**               | Просмотр инсайтов с телефона                                                                                                           | Future                                                                |
| **Forecasting**                     | Прогноз revenue, вероятность закрытия сделок                                                                                           | Future                                                                |
| **DPA-шаблон**                      | Юридический документ Data Processing Agreement                                                                                         | До production deployment                                              |
| **Имя продукта и брендинг**         | Финальное название, логотип, дизайн-система                                                                                            | До production launch                                                  |
| **Юрлицо**                          | Регистрация SRL в Румынии для подписки клиентов                                                                                        | До первого платного клиента                                           |

### Приложение C: Глоссарий метрик

**Marketing:**

- **CPL** — Cost per Lead, стоимость лида = ad_spend / leads
- **CAC** — Customer Acquisition Cost = total_marketing_cost / won_deals
- **ROAS** — Return on Ad Spend = revenue / ad_spend
- **CTR** — Click-Through Rate = clicks / impressions
- **CPC** — Cost per Click = spend / clicks
- **CPM** — Cost per 1000 impressions = (spend / impressions) × 1000
- **YoY** — Year-over-Year, сравнение с тем же периодом год назад

**Sales (воронка Sofa Belle):**

- **Lead** — лид, потенциальный клиент
- **Vizita** — визит в шоурум
- **Oferta** — отправленная оферта
- **Contract** — закрытая сделка
- **L→V** — конверсия Lead → Vizita
- **V→O** — конверсия Vizita → Oferta
- **L→O** — конверсия Lead → Oferta
- **O→C** — конверсия Oferta → Contract
- **L→C** — общая конверсия Lead → Contract
- **Cec mediu** — средний чек = revenue / contracts
- **Cec mediu / zi** — средний чек по дням
- **Încasări** — выручка
- **Cost Aquisition Contract** — CAC по сделке

**Категории лидов (Sofa Belle):**

- **Mail/FB/IG** — заявки из Facebook/Instagram Lead Ads и email
- **Telefon** — входящие звонки
- **WhatsApp** — заявки через WhatsApp
- **Site** — формы на сайте
- **Designer** — заявки на услугу дизайнера
- **Alte** — другие источники

---

**Конец SPEC.md**
