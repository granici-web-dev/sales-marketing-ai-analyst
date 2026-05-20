# MEFI CRM API Reference

> Official MEFI CRM API documentation for BELLE SOFA S.R.L. (Sofa Belle).
> Source: PDF documentation provided by MEFI on 2026-05-18.

## Base URL

```
https://bellesofa.meficrm.com/api/v1
```

## Authentication

All endpoints require Bearer token authentication:

```
Authorization: Bearer <api_key>
```

### Available scopes

| Scope | Permission | Status |
|---|---|---|
| `leads:create` | Create leads via `POST /api/v1/leads` | ✅ Available |
| `leads:read` | Read leads (search, profile, contacts) | ✅ Available |
| `leads:read:notes` | Read lead notes | 🕓 Coming soon |

### Key types

- **Write keys** (`lapi_*`) — for creating leads (used by website forms, Make.com, etc.)
- **Read keys** (`lrd_*`) — for reading data (used by our analytics platform)

**Keys are managed in MEFI:** `Panou de control → API`

Our project uses only **read keys**. Write keys are managed separately by Sofa Belle's marketing team.

## Endpoints overview

| Endpoint | Method | Purpose | Scope | Doc |
|---|---|---|---|---|
| `/leads` | POST | Create lead | `leads:create` | [leads-create.md](./leads-create.md) |
| `/leads/search` | POST | Search/list leads with filters | `leads:read` | [leads-read.md](./leads-read.md) |
| `/leads/{id}` | GET | Full lead profile | `leads:read` | [leads-read.md](./leads-read.md) |
| `/leads/{id}/contacts` | GET | Lead's contacts | `leads:read` | [leads-read.md](./leads-read.md) |

## Rate limits

| Type | Per minute | Burst (10s) |
|---|---|---|
| Per IP (global, excl. /health) | 60 | 10 |
| Per `leads:read` token | **600** | **100** |

Response headers track current limits:
- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`
- `X-RateLimit-Reset`

On limit exceeded → `429 Too Many Requests` with `Retry-After` header.

## Response codes

| Code | Meaning |
|---|---|
| 200 | Success |
| 201 | Created (POST /leads) |
| 400 | Invalid JSON or parameters |
| 401 | Token missing/invalid/revoked |
| 403 | Token lacks required permission |
| 404 | Resource not found |
| 422 | Validation error (see `errors` in body) |
| 429 | Rate limit exceeded |
| 500 | Server error |

## Reference files in this directory

- [leads-create.md](./leads-create.md) — Create lead endpoint (write API)
- [leads-read.md](./leads-read.md) — Read lead endpoints (search, profile, contacts)
- [enums.md](./enums.md) — Status IDs, source IDs, salesperson IDs for Sofa Belle
- [custom-fields.md](./custom-fields.md) — Sofa Belle's custom fields configuration

## ⚠️ Critical limitations (as of 2026-05-18)

**Currently only `/leads` endpoints are exposed via API.** No public endpoints for:
- Deals / Contracts
- Offers
- Visits (showroom visits)
- Calls
- Users / Salespeople (only user IDs are visible in lead's `assigned_to`)
- Sales funnel stage transitions

**Implications for our project:**
- Sales funnel must be derived from **lead status transitions** (Calificare → Ofertat → Clienți)
- Showroom assignment comes from custom field `form-cf-14`, NOT a dedicated endpoint
- Marketing attribution via UTM custom fields (`form-cf-38..41`)
- Revenue estimates from `estimated_value` field (may be null if not filled by salespeople)
- Call analytics, transcripts, sentiment — NOT available via API at this time

**Workaround strategy:**
- Build MVP1 fully on `/leads` API
- Use lead statuses as proxy for funnel stages
- Request expanded API access from MEFI for future iterations
- Consider webhook-based ingestion if MEFI supports it

## Documentation versioning

| Date | Source | Notes |
|---|---|---|
| 2026-05-18 | MEFI PDF (Lead-uri create + Lead-uri citire) | Initial documentation received |

When MEFI updates their API, regenerate these files and bump the date here.
