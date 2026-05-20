# External Integrations

> Детальная информация по каждой интеграции. Используется при разработке ETL.

## Overview

| Source | Iteration | Status | Auth | Sync frequency |
|---|---|---|---|---|
| MEFI CRM | 1 (critical) | ⛔ Need docs | TBD (API key or OAuth) | Daily 03:00 |
| Meta Marketing API | 2 | ⏳ Not started | OAuth 2.0 | Daily 03:00 |
| Google Ads API | 2 | ⏳ Not started | OAuth 2.0 + Developer Token | Daily 03:00 |
| TikTok Marketing API | 2 | ⏳ Not started | OAuth 2.0 | Daily 03:00 |
| GA4 Data API | 3 | ⏳ Not started | OAuth 2.0 or Service Account | Daily 03:00 |
| Search Console API | 3 | ⏳ Not started | OAuth 2.0 | Daily 03:00 |

---

## 1. MEFI CRM (Iteration 1, critical)

### Status
**⛔ BLOCKER:** Documentation not yet received. Email sent to MEFI support (template in [SPEC.md Appendix A](../SPEC.md#приложение-a-шаблон-email-в-mefi-support-на-румынском)).

### What we need from MEFI

- [ ] API documentation (endpoints, schemas, examples)
- [ ] Authentication method (API key, OAuth 2.0, JWT)
- [ ] Rate limits
- [ ] Webhook support (real-time event push)
- [ ] Sandbox/test environment
- [ ] Test account for Sofa Belle

### Data we'll sync

#### Entities
- **Leads (`clienți potențiali`):**
  - id, created_at, source, category, utm_*, status, salesperson, customer_phone/email/name
  - Status history (when status changed, from→to)
- **Visits (`vizite`):**
  - lead_id, salesperson_id, visited_at, showroom, outcome
- **Offers (`oferte`):**
  - lead_id, visit_id, salesperson_id, amount, status, sent_at
- **Deals/Contracts (`contracte`):**
  - lead_id, offer_id, salesperson_id, amount, status, loss_reason, items_count, closed_at
- **Calls (`apeluri`):**
  - lead_id, salesperson_id, direction, status, duration, started_at
  - **+ enriched by DOTRO MonitorAI / 3CX AI:**
    - transcript_summary, sentiment_score, sentiment_label, topics
- **Salespeople (`utilizatori`):**
  - id, full_name, email, showroom, active
- **Funnel stages (`etape pâlnie`):**
  - Tenant-specific stage configuration

### Sync strategy

#### Initial sync
- Pull last 12 months of data
- Run on first integration setup, expected to take 1-3 hours
- Use pagination if API supports it
- Mark records with `synced_at` timestamp

#### Incremental sync
- Run daily at 03:00 Europe/Bucharest
- Pull records changed since `last_sync_at`
- Update existing records (UPSERT by `external_id`)
- Insert new records

#### Error handling
- Retry transient failures (5xx, timeouts) with exponential backoff (Celery autoretry)
- Permanent failures (4xx) — log and continue with next entity
- After 3 consecutive failures: mark integration as `failed`, notify user

### Implementation file
```
backend/app/services/integrations/mefi.py
backend/app/tasks/etl/sync_mefi.py
```

### Mocking for development
Until we have real MEFI API access, create a mock client:
```
backend/app/services/integrations/mefi_mock.py
```
That returns fixture data resembling expected MEFI structure.

---

## 2. Meta Marketing API (Iteration 2)

### Setup
1. Create app at https://developers.facebook.com/apps/
2. Add **Marketing API** product
3. Configure OAuth redirect URI
4. Submit for review if needed (Business Asset User Profile access)

### Authentication
- **Type:** OAuth 2.0
- **Flow:** Facebook Business Login
- **Required permissions (scopes):**
  - `ads_read` — read campaign data
  - `business_management` — access to Business Manager
- **Token lifetime:** Long-lived tokens valid ~60 days, refresh via Graph API

### What we'll sync

#### Entities
- **Ad Accounts:** id, name, currency, account_status
- **Campaigns:** id, name, objective, status, start_time, stop_time
- **Ad Sets:** targeting, budget, schedule
- **Ads:** creative, status
- **Insights (daily):**
  - spend, impressions, clicks, ctr, cpc, cpm, reach, frequency
  - actions: `lead`, `purchase`, `landing_page_view`, etc.

### API specifics
- **Endpoint:** `https://graph.facebook.com/v20.0/`
- **Rate limit:** dynamic, calculated per app
- **Batch requests:** supported, can batch up to 50 requests
- **Insights API:** async для больших данных (request → wait → fetch results)

### SDK
```python
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount

FacebookAdsApi.init(access_token=token)
account = AdAccount('act_<account_id>')

insights = account.get_insights(
    params={
        'level': 'campaign',
        'fields': ['campaign_id', 'spend', 'impressions', 'clicks', 'ctr'],
        'time_range': {'since': '2026-05-01', 'until': '2026-05-17'},
        'time_increment': 1,  # daily breakdown
    }
)
```

### Implementation file
```
backend/app/services/integrations/meta_ads.py
backend/app/tasks/etl/sync_meta.py
```

---

## 3. Google Ads API (Iteration 2)

### Setup
1. Create project in Google Cloud Console
2. Enable Google Ads API
3. **Apply for Developer Token** at https://ads.google.com/aw/apicenter (takes 1-3 weeks!)
4. Create OAuth client credentials

### ⚠️ Important
**Developer Token approval takes 1-3 weeks** — apply EARLY, even before starting development. Test token works in test mode but rate limited.

### Authentication
- **Type:** OAuth 2.0 + Developer Token
- **Scopes:** `https://www.googleapis.com/auth/adwords`
- **For MCC (manager accounts):** specify `login_customer_id`

### What we'll sync

#### Entities
- **Customers (accounts):** customer_id, descriptive_name, currency_code
- **Campaigns:** id, name, status, advertising_channel_type, bidding_strategy_type
- **Ad Groups:** id, name, status
- **Ads:** id, status, type
- **Keywords:** match_type, text, quality_score (для Search)
- **Metrics (daily):**
  - cost_micros, impressions, clicks, conversions, conversions_value
  - ctr, average_cpc, average_cpm

### API specifics
- **GAQL (Google Ads Query Language):** SQL-like syntax
- **Currencies:** in micros (multiply by 1,000,000)
- **Time zone:** account-specific

### SDK
```python
from google.ads.googleads.client import GoogleAdsClient

client = GoogleAdsClient.load_from_dict({
    "developer_token": DEVELOPER_TOKEN,
    "refresh_token": refresh_token,
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "use_proto_plus": True,
})

ga_service = client.get_service("GoogleAdsService")
query = """
    SELECT
        campaign.id,
        campaign.name,
        metrics.cost_micros,
        metrics.impressions,
        metrics.clicks
    FROM campaign
    WHERE segments.date BETWEEN '2026-05-01' AND '2026-05-17'
"""
response = ga_service.search(customer_id="1234567890", query=query)
```

### Implementation file
```
backend/app/services/integrations/google_ads.py
backend/app/tasks/etl/sync_google_ads.py
```

---

## 4. TikTok Marketing API (Iteration 2)

### Setup
1. Register at https://business-api.tiktok.com
2. Create developer app
3. Configure OAuth redirect URI
4. Submit for review

### Authentication
- **Type:** OAuth 2.0
- **Flow:** TikTok for Business
- **Access token lifetime:** ~1 year

### What we'll sync

#### Entities
- **Advertisers (ad accounts):** id, name, currency, status
- **Campaigns:** campaign_id, campaign_name, objective_type, status
- **Ad Groups:** adgroup_id, adgroup_name, budget, schedule
- **Ads:** ad_id, ad_name, status, creative
- **Reports (daily):**
  - spend, impressions, clicks, ctr, cpc, conversions
  - video views (для video campaigns)

### API specifics
- **Endpoint:** `https://business-api.tiktok.com/open_api/v1.3/`
- **Rate limit:** 10 req/sec per app, can request increase
- **Reports endpoint:** synchronous or async

### SDK
Официального Python SDK нет (на момент написания). Используем httpx + ручные запросы:

```python
import httpx

async with httpx.AsyncClient() as client:
    response = await client.get(
        "https://business-api.tiktok.com/open_api/v1.3/report/integrated/get/",
        headers={"Access-Token": access_token},
        params={
            "advertiser_id": advertiser_id,
            "report_type": "BASIC",
            "dimensions": '["campaign_id", "stat_time_day"]',
            "metrics": '["spend", "impressions", "clicks", "ctr"]',
            "start_date": "2026-05-01",
            "end_date": "2026-05-17",
        },
    )
```

### Implementation file
```
backend/app/services/integrations/tiktok_ads.py
backend/app/tasks/etl/sync_tiktok.py
```

---

## 5. Google Analytics 4 Data API (Iteration 3)

### Setup
1. Use same Google Cloud project as Google Ads
2. Enable **Google Analytics Data API**
3. For service account: create + add to GA4 property as viewer
4. For OAuth: scope `https://www.googleapis.com/auth/analytics.readonly`

### Authentication
**Two options:**
- **Service Account (preferred for our use case):** Long-lived, no user interaction
- **OAuth 2.0:** If user-driven setup needed

### What we'll sync

#### Reports (daily)
- **Sessions, users, engagement:** by date, by source/medium, by campaign
- **Conversions:** lead form submits, phone clicks, "add to cart" events
- **Geography:** by country/city (для понимания откуда приходят клиенты)
- **Devices:** desktop / mobile / tablet
- **Traffic sources:** Default Channel Grouping (Organic Search, Paid Search, Social, Direct, Referral)

### API specifics
- **Endpoint:** `https://analyticsdata.googleapis.com/v1beta/`
- **Property ID** (not Tracking ID!) — different format than Universal Analytics
- **Dimensions + metrics** in single request
- **Date range:** in 'YYYY-MM-DD' format

### SDK
```python
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
)

client = BetaAnalyticsDataClient()

request = RunReportRequest(
    property=f"properties/{property_id}",
    dimensions=[
        Dimension(name="date"),
        Dimension(name="sessionSource"),
        Dimension(name="sessionMedium"),
    ],
    metrics=[
        Metric(name="sessions"),
        Metric(name="conversions"),
        Metric(name="totalUsers"),
    ],
    date_ranges=[DateRange(start_date="2026-05-01", end_date="2026-05-17")],
)

response = client.run_report(request)
```

### Implementation file
```
backend/app/services/integrations/ga4.py
backend/app/tasks/etl/sync_ga4.py
```

---

## 6. Google Search Console API (Iteration 3)

### Setup
1. Use same Google Cloud project
2. Enable **Search Console API**
3. Add property if not added: https://search.google.com/search-console
4. Grant access to OAuth user / service account

### Authentication
- **Type:** OAuth 2.0
- **Scopes:** `https://www.googleapis.com/auth/webmasters.readonly`

### What we'll sync

#### Queries report (daily)
- query (search term)
- page (landing URL)
- clicks, impressions, ctr, position
- country, device

### API specifics
- **Endpoint:** `https://www.googleapis.com/webmasters/v3/sites/{siteUrl}/searchAnalytics/query`
- **Data delay:** 2-3 days (Google's delay, not API issue)
- **Max rows per request:** 25,000
- **History:** 16 months max

### SDK
```python
from googleapiclient.discovery import build

service = build("searchconsole", "v1", credentials=credentials)

response = service.searchanalytics().query(
    siteUrl="https://sofabelle.ro",
    body={
        "startDate": "2026-05-01",
        "endDate": "2026-05-17",
        "dimensions": ["query", "page", "date"],
        "rowLimit": 25000,
    }
).execute()
```

### Implementation file
```
backend/app/services/integrations/search_console.py
backend/app/tasks/etl/sync_gsc.py
```

---

## Common patterns

### Base integration class

```python
# backend/app/services/integrations/base.py

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SyncResult(BaseModel):
    source: str
    started_at: datetime
    finished_at: datetime
    records_synced: int
    errors: list[str]
    status: str  # 'success' | 'partial' | 'failed'


class BaseIntegration(ABC):
    """Base class for all external integrations."""
    
    source_name: str
    
    @abstractmethod
    async def authenticate(self, credentials: dict) -> bool:
        """Verify credentials are valid."""
        ...
    
    @abstractmethod
    async def sync(
        self,
        tenant_id: UUID,
        since: datetime | None = None,
    ) -> SyncResult:
        """Sync data from source. If since is None — full sync."""
        ...
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Quick check that integration is working."""
        ...
```

### Celery task pattern

```python
# backend/app/tasks/etl/sync_mefi.py

from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(httpx.HTTPError, ConnectionError),
    retry_kwargs={"max_retries": 3, "countdown": 60},
    retry_backoff=True,
    retry_backoff_max=600,
)
def sync_mefi_for_tenant(self, tenant_id: str) -> dict:
    """Sync MEFI data for a single tenant.
    
    This task is IDEMPOTENT — can be safely retried.
    """
    import asyncio
    from app.services.integrations.mefi import MefiIntegration
    
    integration = MefiIntegration()
    result = asyncio.run(integration.sync(UUID(tenant_id)))
    
    logger.info(
        "mefi.sync.completed",
        extra={
            "tenant_id": tenant_id,
            "records_synced": result.records_synced,
            "status": result.status,
        },
    )
    
    return result.model_dump(mode="json")
```

### OAuth flow pattern

```python
# backend/app/api/v1/integrations.py

@router.get("/{source}/connect")
async def start_oauth(
    source: IntegrationSource,
    tenant: Tenant = Depends(get_current_tenant),
) -> RedirectResponse:
    """Start OAuth flow for given source."""
    
    state = generate_oauth_state(tenant.id)  # CSRF protection
    auth_url = build_oauth_url(source, state)
    
    return RedirectResponse(auth_url)


@router.get("/{source}/callback")
async def oauth_callback(
    source: IntegrationSource,
    code: str,
    state: str,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Handle OAuth callback, save credentials."""
    
    tenant_id = verify_oauth_state(state)
    tokens = await exchange_code_for_tokens(source, code)
    
    integration = Integration(
        tenant_id=tenant_id,
        source=source.value,
        credentials=encrypt_credentials(tokens),
        status="active",
    )
    db.add(integration)
    await db.commit()
    
    return {"status": "connected"}
```

### Credentials encryption

```python
# backend/app/core/security.py

from cryptography.fernet import Fernet

fernet = Fernet(settings.FERNET_KEY.encode())


def encrypt_credentials(data: dict) -> dict:
    """Encrypt sensitive credential fields."""
    encrypted = {}
    for key, value in data.items():
        if key in ("access_token", "refresh_token", "api_key", "secret"):
            encrypted[key] = fernet.encrypt(value.encode()).decode()
        else:
            encrypted[key] = value
    return encrypted


def decrypt_credentials(data: dict) -> dict:
    """Decrypt credential fields."""
    decrypted = {}
    for key, value in data.items():
        if key in ("access_token", "refresh_token", "api_key", "secret"):
            decrypted[key] = fernet.decrypt(value.encode()).decode()
        else:
            decrypted[key] = value
    return decrypted
```

## Token refresh strategy

For OAuth-based integrations:
- Check token expiry before each API call
- If expired or expires within 5 minutes: refresh
- Update encrypted credentials in DB
- If refresh fails: mark integration as `requires_reauth`, notify user

## Rate limiting

Each integration may have different rate limits. We handle this:
- Implement per-source semaphore in Celery tasks
- Honor `Retry-After` headers
- Use exponential backoff on 429 responses

## Testing integrations

Each integration must have:
- **Unit tests** with mocked HTTP responses (using `respx` for httpx)
- **Integration tests** with VCR.py cassettes (recorded once, replayed in CI)
- **Smoke tests** against sandbox/test environments (manual, before deploys)

## Future integrations (not in MVP)

- WhatsApp Business API (для отслеживания WhatsApp лидов)
- LinkedIn Ads (если клиенты будут B2B)
- Stripe (для биллинга, когда подключим подписки)
- Sentry (для error tracking — это не data source, но интеграция)
