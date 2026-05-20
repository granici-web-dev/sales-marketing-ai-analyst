# MEFI Enumerations for Sofa Belle

> These are the actual ID mappings for Sofa Belle's MEFI account. **They are tenant-specific** — other MEFI customers will have different IDs.
>
> When onboarding a new client, these enums must be re-discovered for that tenant.

## Status IDs

| ID | Name | Lifecycle bucket | Funnel stage | Notes |
|---|---|---|---|---|
| 16 | IN PROCES | active | Engagement | Default for API-created leads |
| 14 | Revenire 1 | active | Engagement | First follow-up needed |
| 15 | Revenire 2 | active | Engagement | Second follow-up needed |
| 2 | Revenire 3 | active | Engagement | Third follow-up needed |
| 17 | SHOWROOM | active | **Visit (V)** | Booked/completed showroom visit |
| 24 | DESIGNER | active | Engagement | Designer consultation |
| 25 | INFLUENCER | active | Engagement | Influencer-sourced |
| 3 | Ofertat | active | **Offer (O)** | Offer sent |
| 12 | Stand BY | active | Engagement | Paused |
| 1 | Clienți | active | **Contract (C) — WON** | Closed-won deal |
| 18 | NU A RASPUNS | lost | — | Loss: didn't respond |
| 19 | A REFUZAT | lost | — | Loss: refused |
| 20 | PRODUS NEPOTRIVIT | lost | — | Loss: wrong product |
| 21 | BUGET | lost | — | Loss: budget |
| 22 | CONCURENTA | lost | — | Loss: chose competitor |
| 23 | IRELEVANT | junk | — | Junk: irrelevant |
| 26 | TIMP | lost | — | Loss: timing |

### Funnel stage mapping (for Sales Dashboard)

```
Lead → Vizita → Oferta → Contract
 │       │        │         │
 │       │        │         └─ status_id = 1 (Clienți)
 │       │        └─ status_id = 3 (Ofertat) OR form-cf-20 = "✅DA"
 │       └─ status_id = 17 (SHOWROOM)
 └─ Any lead with lifecycle="active" except those above
```

### Loss reasons (for AI Insights)

When `lifecycle = "lost"`, the specific status tells us **why**:
- 18 NU A RASPUNS → "Didn't respond to outreach"
- 19 A REFUZAT → "Refused after offer"
- 20 PRODUS NEPOTRIVIT → "Product wasn't right"
- 21 BUGET → "Budget mismatch"
- 22 CONCURENTA → "Lost to competitor"
- 26 TIMP → "Bad timing"

Aggregating these reveals patterns ("40% of losses are to competitors → competitive analysis needed").

## Source IDs

| ID | Name | Maps to category (Sofa Belle Excel) |
|---|---|---|
| 1 | Google | (varies — Google Ads vs Google Organic, check UTM) |
| 2 | Meta ADS | `Leads Mail/FB/IG` |
| 3 | Recomandare | `Leads Alte` |
| 4 | Teren | `Leads Alte` |
| 5 | Showroom | `Leads Alte` (walk-in) |
| 6 | Site | `Leads Site` |
| 7 | Arhitect | `Leads Alte` |
| 9 | WhatsApp | `Leads WhatsApp` |
| 10 | Telefon | `Leads Telefon` |
| 11 | Mail | `Leads Mail/FB/IG` |
| 12 | Colaborare | `Leads Alte` |
| 13 | Client Fidel | `Leads Alte` (repeat customer) |

### ⚠️ Missing: TikTok and Designer

- **TikTok** is not in the source list. TikTok leads currently land under source `2 = Meta ADS` (combined) or `6 = Site` (with UTM). **Verify with Sofa Belle.**
- **Designer** as a lead category in client's Excel is NOT a source — it's a status (`24 = DESIGNER`) or possibly a custom field. **Verify with Sofa Belle.**

## Salesperson IDs (assigned_to / created_by)

| ID | Name | Role (assumed) |
|---|---|---|
| 2 | Palega Andrei | Salesperson |
| 4 | Potinga Dima | Salesperson |
| 6 | Iordache Razvan | Salesperson |
| 7 | Marketing Sofa | **Marketing (not salesperson)** |
| 8 | Roibu Valeria | Salesperson |
| 9 | Moaca Andreea | Salesperson |
| 10 | Godja Adina Maria | Salesperson |
| 11 | Zagrian Emilia | Salesperson |
| 12 | Dragoi Mihaela | Salesperson |
| 13 | Raileanu Leon | Salesperson |
| 14 | Elena Ureche | Salesperson |

**Total: 11 active users, ~10 actual salespeople** (assuming `Marketing Sofa` is a marketing account, not a salesperson).

**⚠️ Confirm with Sofa Belle:**
- Sofa Belle stated "6 salespeople" — but MEFI shows 11 users. Possibly:
  - Some are part-time / former employees still in the system
  - Some are managers, not direct sellers
  - Need to identify the actual 6 active sellers and their showrooms

## Showroom assignment (custom field)

Showroom is **not a separate entity** — it's a custom field on the lead:
- Field key: `form-cf-14`
- Type: `select`
- Values (exact, case-sensitive): `"Brașov"`, `"București"`, `"Cluj"`

When building the Salespeople dashboard, we need a separate mapping `salesperson_id → showroom`, which is **not available via API**. Options:
1. Manual mapping in our DB (`mefi_salespeople.showroom` column)
2. Inferred from their leads' Showroom distribution (heuristic)
3. Ask Sofa Belle to provide the list

**Recommended:** Manual mapping table maintained by us, sourced from Sofa Belle once.

## Lifecycle values

| Value | Meaning | Counts as |
|---|---|---|
| `active` | Lead is in progress | Lead in funnel |
| `lost` | Lead is lost (specific status explains why) | Lost lead |
| `junk` | Lead is junk/spam/invalid | Excluded from metrics |

## Priority values

| Slug | Label (Romanian) | Use |
|---|---|---|
| `low` | Scăzută | Low priority lead |
| `medium` | Medie | Medium |
| `high` | Ridicată | High — likely valuable, fast response needed |

Could be used for SLA rules in AI Insights: "High-priority leads with response time > 1h" as alert.

## Last updated

This file: 2026-05-18

When new statuses, sources, or users are added in MEFI, update this file.

**Detection strategy:** Our sync task should log any new `status.id`, `source.id`, or `assigned_to.id` it sees that isn't in this enum file. We then update the file manually after verification.
