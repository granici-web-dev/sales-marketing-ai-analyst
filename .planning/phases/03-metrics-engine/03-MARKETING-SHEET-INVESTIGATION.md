# Phase 3.5 / MarketingSheet — Investigation

**Status:** INVESTIGATION COMPLETE — **path decided: CSV Upload** (Service Account rejected, see §0). Awaiting remaining user decisions (metric naming, backfill timing) before Phase 3.5 implementation.
**Created:** 2026-06-01
**Trigger:** Sofa Belle maintains a comprehensive manual marketing/sales spreadsheet that is their **primary source of truth** for business metrics (contracts signed, revenue, ad spend, ROAS/CPL/CAC). This supersedes the assumption that MEFI alone can answer monthly business questions.
**Relationship to the contract-counting hotfix:** the hotfix (commit `61fc6431`, May=21 event model) is **kept**, but its metric is **reframed** — see §6. This document does NOT change code.

---

## 0. PATH DECISION (post-investigation) — 2026-06-01

**Google Sheets API via Service Account: REJECTED.** The user's Google Cloud account enforces the org policy **`iam.managed.disableServiceAccountApiKeyCreation`** (Active, cannot be disabled by the user), which blocks creating the JSON key a backend Service Account needs. Verified during the 2026-06-01 session. The entire live-API path (scheduled Google API sync, Drive revisions, service-account onboarding) is therefore unavailable.

**CSV Upload: SELECTED.** Implementation proceeds this direction. The marketing manager downloads the sheet as CSV and uploads it through an in-app admin button; backend parses + UPSERTs into `raw_marketing_monthly`.

Rationale (why CSV is the right call, not just the fallback):
- **Independent of cloud-provider policy** — no Google Cloud project, key, or org-policy exception required; can't be blocked by an admin toggle.
- **Matches data velocity** — the sheet is manually updated **monthly**, so a manual monthly upload is the natural cadence; no value lost vs a daily automated poll.
- **Standard B2B pattern** — file import is a well-understood, low-friction onboarding step finance/marketing users already do.
- **Least dependency / least risk** — no live external dependency to break, no credentials to rotate, no PII surface beyond the file the user chooses.

Implications: §7 (Service Account onboarding) is **superseded** → replaced by in-app help text on the import button. §10 (automated Google API sync) is **superseded** → manual upload trigger. New implementation architecture in §11.1. Roadmap (§13) and decision points (§14) updated accordingly.

---

## 0.1 TL;DR / decisions required from user

1. ✅ **DECIDED — CSV Upload** (Service Account rejected by org policy; §0). No Google Cloud setup; admin uploads the sheet's CSV export in-app. Architecture in §11.1.
2. ✅ **DECIDED — 2-source architecture** — MEFI for lead-level granularity, Sheet/CSV for monthly authoritative business metrics. See §5.
3. ⏳ **PENDING — metric naming** — `customers_won` (MEFI, Clienți promotions, recommended physical rename) vs `contracts_signed` (Sheet). See §6.
4. ⏳ **PENDING — hotfix backfill timing** — recommend running once *after* the metric rename. See §14.
5. **Schedule Phase 3.5** — estimate ~3 days (CSV path). See §13.

The single most important finding: **MEFI cannot provide revenue at all** (`estimated_value` is NULL for 100% of leads — 1238/1238). The sheet is the *only* source for revenue, ad spend, ROAS, CPL, and CAC. This is not a "nice to have second source" — for an entire class of CEO-facing metrics, the sheet is the **only** source.

---

## 1. Context — why this changes the architecture

Until now the product treated **MEFI as the single source of truth**. The Phase 3 hotfix went deep on getting "contracts" right *from MEFI* (cohort→event model). That work is correct and stays — but it answers a narrower question than the CEO actually asks.

The CEO tracks the business from a **manually-maintained Google Sheet**, monthly, in wide format (one row per metric, one column per month, April 2024 → December 2026). That sheet carries metrics MEFI structurally cannot produce:

| Metric class | MEFI can produce? | Sheet has it? |
|---|---|---|
| Lead detail, salesperson attribution, daily velocity, per-lead source | ✅ yes (authoritative) | ❌ no (no lead-level / no salesperson breakdown) |
| Contracts signed (count) | ⚠️ proxy only (Clienți promotions = 21 for May) | ✅ authoritative (22 for May) |
| Revenue / payments received (Încasări) | ❌ **NULL for all leads** | ✅ authoritative (358,978 RON May) |
| Ad spend (Meta/Google/TikTok) | ❌ not synced (Phase 4+ not built) | ✅ authoritative, since Apr 2024 |
| Pre-computed ROAS / CPL / CAC | ❌ no (no spend, no revenue) | ✅ authoritative |
| Website traffic (sessions) | ❌ no (GA4 not integrated) | ✅ (likely typed from GA4) |

**Conclusion:** neither source dominates. They are **complementary**: MEFI = lead-level/operational granularity; Sheet = monthly business truth. The new architecture must join them, not pick one.

---

## 2. Sheet structure

**URL:** https://docs.google.com/spreadsheets/d/1GxITJQBMwZTF3-wlc03MhCsEVyQaTRn7aVQcDgGrXA8/edit
**Format:** wide — metric per **row**, month per **column**.
**Column span:** Aprilie 2024 → Decembrie 2026 (some rows start later; see "first populated").
**Maintenance:** manual entry by Sofa Belle finance/marketing, updated monthly.

### Rows (metric labels — Romanian, exact-match required)

| Row label (sheet) | Meaning | First populated | Proposed field |
|---|---|---|---|
| Buget META (lei) | Meta Ads spend / month | Apr 2024 | `meta_spend_ron` |
| Buget Google (lei) | Google Ads spend | Apr 2024 | `google_spend_ron` |
| Buget Tik-tok (lei) | TikTok spend | **Jan 2026** | `tiktok_spend_ron` |
| Buget Digital Total | sum of the above | Apr 2024 | `digital_total_ron` |
| Trafic (sesiuni) | website sessions (GA4) | ? | `traffic_sessions` |
| Leads Mail/FB/IG | channel breakdown | **Jan 2025** | `leads_mail_fb_ig` |
| Leads Telefon | phone leads | Jan 2025 | `leads_telefon` |
| Leads WhatsApp | WhatsApp leads | Jan 2025 | `leads_whatsapp` |
| Leads Total Site | site leads total | Jan 2025 | `leads_site_total` |
| Leads Designer | designer-referred | Jan 2025 | `leads_designer` |
| Leads Alte | other | Jan 2025 | `leads_other` |
| Leads Total | total leads | Apr 2024 | `leads_total` |
| Cost per Lead | pre-computed CPL | Apr 2024 | `cost_per_lead` |
| Conversie site | site conversion % | ? | `site_conversion` |
| Vizita | showroom visits | Apr 2024 | `vizits` |
| Oferta | offers sent | Apr 2024 | `offers` |
| Conversie vizita | visit conversion % | ? | `conversie_vizita` |
| Conversie Oferta (V/O) | offer conv. visit→offer | ? | `conversie_oferta_vo` |
| Conversie Oferta (L/O) | offer conv. lead→offer | ? | `conversie_oferta_lo` |
| Conversie Contract (O/C) | contract conv. offer→contract | ? | `conversie_contract_oc` |
| **Contract** | **signed contracts (authoritative)** | Apr 2024 | `contracts_signed` |
| Cost Aquisiton Contract | pre-computed CAC | Apr 2024 | `cac` |
| **Încasări** | **revenue / payments received (authoritative)** | Apr 2024 | `revenue_ron` |
| Cec mediu / zi | average daily check | ? | `daily_avg_check` |
| ROAS | pre-computed ROAS | Apr 2024 | `roas_pct` |
| YoY | year-over-year % | ? (needs ≥13 months) | `yoy_pct` |

### Column pattern

- Header cells like `Aprilie 2024`, `Mai 2026` — Romanian month name + year → parse to first-of-month `date`.
- Romanian month map: Ianuarie, Februarie, Martie, Aprilie, Mai, Iunie, Iulie, August, Septembrie, Octombrie, Noiembrie, Decembrie.
- A **new month = a new column** appended to the right. Parser must discover columns dynamically (header scan), never hardcode column letters/indexes.

---

## 3. Authoritative numbers (from the sheet)

**Access status:** export endpoint returns **HTTP 401** (sheet is private; not link-exportable) and the Service Account path is blocked (§0). Only the **May 2026** figures the user supplied are confirmed here. April / March 2026 are **pending the first CSV upload** — do not treat the placeholders as real.

| Metric | May 2026 (confirmed) | Apr 2026 | Mar 2026 |
|---|---|---|---|
| Contracts signed (`Contract`) | **22** | TBD | TBD |
| Revenue / Încasări (RON) | **358,978** | TBD | TBD |
| ROAS | **1447%** | TBD | TBD |
| Digital spend total | ~24,800 RON* | TBD | TBD |
| Cost per Lead | TBD | TBD | TBD |
| CAC | TBD | TBD | TBD |

\* *Derived sanity-check, not from the sheet: ROAS 1447% = revenue / spend ⇒ spend ≈ 358,978 / 14.47 ≈ **24,800 RON**. To be confirmed against `Buget Digital Total` once access is granted. If the sheet's digital total deviates materially from ~24.8k, the ROAS cell may use a different denominator (e.g. excludes one platform) — flag during parser validation.*

**Action:** with the first CSV in hand, capture a full Apr/Mar/May ground-truth table (every row) into this section before any parser is written — it becomes the parser's regression fixture, exactly as `03-HOTFIX-GROUND-TRUTH.md` did for the contract hotfix.

---

## 4. Cross-reference with MEFI ground truth — mismatch analysis

MEFI event-model contracts (from `v_mefi_leads_active`, `status_id=1` by `status_changed_at`, captured this session — matches `03-HOTFIX-GROUND-TRUTH.md`):

| Month | MEFI (Clienți promotions, event model) | Sheet (`Contract`) | Δ |
|---|---|---|---|
| Jan 2026 | 1 | TBD | — |
| Feb 2026 | 0 | TBD | — |
| Mar 2026 | 21 | TBD | — |
| Apr 2026 | 29 | TBD | — |
| **May 2026** | **21** | **22** | **+1 (sheet higher)** |

### 4.1 Contracts: 21 (MEFI) vs 22 (Sheet) — why they differ

The two numbers measure **near-identical but not identical** events. Candidate causes for the +1, in order of likelihood:

1. **Manual-entry timing / definition.** The sheet's "Contract" is what finance counts as a signed contract; MEFI's is a CRM status promotion to *Clienți*. A deal signed (paper/payment) but not yet flipped to *Clienți* in MEFI — or flipped on a different calendar day that lands the `status_changed_at` outside May — produces a ±1 gap.
2. **Off-CRM deal.** A contract closed without a corresponding MEFI lead (e.g. repeat client entered straight into finance), present in the sheet, absent from MEFI.
3. **Timezone / boundary.** A signing near the month boundary attributed to May in the sheet but to a neighbouring month by `status_changed_at AT TIME ZONE 'Europe/Bucharest'` (or vice-versa).

**This is expected and acceptable.** A ±1 difference between a CRM-derived count and a manually-maintained finance ledger is normal. The architectural response is **not to reconcile them to a single number** but to **name them distinctly** (§6) and let the chat router pick the right one per question. The sheet's `22` is authoritative for "how many contracts did we sign"; MEFI's `21` is authoritative for "how many leads did we promote to Clienți and who/where/when."

### 4.2 Revenue: NULL (MEFI) vs 358,978 RON (Sheet) — not a mismatch, a gap

MEFI `estimated_value` is **NULL for all 1238 leads** (see `PHASE-9-BACKLOG.md`). MEFI's revenue is therefore **0/unavailable, period**. The sheet's `Încasări` = **358,978 RON** is the *only* revenue figure in the system.

Important semantic nuance: **`Încasări` = payments *received* (cash collected in the month)**, which is *not* the same as "value of contracts signed in the month." A May contract may be paid across several months; a May payment may be for an April contract. So:
- `contracts_signed` (count) and `revenue_ron` (cash) are **different bases** (accrual-ish vs cash). Do not compute `avg_deal_size = revenue / contracts` from the sheet and present it as "average contract value" — it's `Cec mediu` territory and the sheet already provides `Cec mediu / zi`. Flag this in chat-tool descriptions so Claude doesn't invent a misleading per-contract average.

### 4.3 Implication for the hotfix backfill (paused)

The contract-counting backfill (step b of the hotfix sequence) is **on hold** pending this decision. If we adopt `customers_won` semantics (§6), the backfill still runs — it just populates a column that means "Clienți promotions (21)", not "contracts signed (22)". The sheet supplies the authoritative `22` separately. **No conflict** — both can land. Sequencing in §13.

---

## 5. Architecture proposal — 2-source

```
                 ┌─────────────────────────────┐
                 │   Source 1: MEFI (syncing)   │
                 │   raw_mefi_leads             │
                 │   • lead detail              │
                 │   • salesperson attribution  │
                 │   • daily velocity           │
                 │   • per-lead source          │
                 └───────────────┬──────────────┘
                                 │ lead-level / daily / weekly
                                 ▼
   ┌──────────────────────────────────────────────────────────┐
   │  Chat tools + dashboards (smart-route by question grain)  │
   └──────────────────────────────────────────────────────────┘
                                 ▲
                                 │ monthly / business-truth
                 ┌───────────────┴──────────────┐
                 │  Source 2: Google Sheet (NEW)│
                 │  raw_marketing_monthly       │
                 │  • contracts signed (22)     │
                 │  • revenue / Încasări        │
                 │  • ad spend (Meta/Goog/TikTok)│
                 │  • pre-computed ROAS/CPL/CAC │
                 │  • traffic sessions          │
                 └──────────────────────────────┘
```

### Routing rules

| Question grain | Source | Rationale |
|---|---|---|
| Monthly aggregate (contracts, revenue, spend, ROAS, CPL, CAC) | **Sheet** | Authoritative business truth; MEFI lacks revenue/spend entirely |
| Daily / weekly velocity, "how are we tracking this week" | **MEFI** | Sheet is monthly-only |
| Salesperson performance / ranking | **MEFI** | Sheet has no salesperson breakdown |
| Lead source quality, per-lead drill-down | **MEFI** | Lead-level only in MEFI |
| Marketing dashboard (spend × lead quality) | **Both (join)** | Sheet spend + MEFI lead quality, joined on month |

### New chat tools (sheet-backed)

- `get_monthly_metrics(month, year)` → high-level row read for a month.
- `get_marketing_costs(month)` → Meta/Google/TikTok/digital-total spend.
- `get_revenue(month)` → Încasări.
- `get_roas(month)` → pre-computed `roas_pct` (or computed from spend+revenue, flag which).
- `get_cpl(month, source?)` → cost per lead (sheet pre-computed; channel breakdown if present).

### Existing chat tools — disposition

- `get_kpi` → **smart-route**: monthly aggregate → sheet; daily/weekly → MEFI.
- `get_salespeople_dashboard` → **MEFI** (unchanged).
- `get_marketing_dashboard` → **sheet costs + MEFI lead quality, joined**.
- `get_showroom_performance`, `get_funnel_data`, `compare_periods`, `get_trend` → audit each for grain; route monthly business numbers to the sheet. (Detailed audit deferred to implementation.)

---

## 6. Phase 3 hotfix reconsideration — metric naming

**Decision proposed (user to confirm):** keep commit `61fc6431`, reframe the metric.

| Aspect | Before | After (proposed) |
|---|---|---|
| `daily_kpi.contracts_count` | "contracts" (ambiguous) | **rename → `customers_won`** = Clienți promotions by event date (MEFI, 21 for May) |
| Authoritative "contracts signed" | — | **NEW** `raw_marketing_monthly.contracts_signed` (Sheet, 22 for May) |
| Co-existence | — | Both, with distinct semantics; chat router disambiguates |

**Chat routing for the two contract-ish concepts:**
- "câte **contracte semnate** / contracts signed / contracte în mai" → **Sheet** `contracts_signed` (22).
- "câți **clienți noi** / customers won / câte lead-uri promovate la Clienți" → **MEFI** `customers_won` (21).
- When ambiguous ("câte contracte"), prefer the **Sheet** (business truth) and have Claude note the MEFI operational figure if the user wants the CRM-side number.

**Cost of the rename (Phase 3.5 scope, not now):** `daily_kpi.contracts_count` → `customers_won` touches: the model column, Alembic migration, `daily_kpi_service` / `salesperson_kpi_service` / `source_kpi_service` (writers), `dashboard_read_service` + chat tools (readers), the reconciliation test, and the `03-HOTFIX-*` docs. Non-trivial but mechanical. **Alternative:** keep the column name `contracts_count` physically and only reframe at the semantic/label layer (cheaper, but leaves a misleading name in the schema). Decide at Phase 3.5 kickoff.

> ⚠️ Naming caution: the reconciliation test and `03-HOTFIX-GROUND-TRUTH.md` are written against "contracts = 21 (event model)". If we rename to `customers_won`, update those artifacts in lockstep so the guard keeps asserting the MEFI 21, while a **new** sheet-vs-stored guard asserts the 22.

---

## 7. ~~Service Account setup — Sofa Belle CEO onboarding~~ (REJECTED, see §0)

> ~~Backend reads the sheet via a Google Cloud Service Account with a JSON key, shared as Viewer.~~
>
> **REJECTED 2026-06-01.** The user's Google Cloud account enforces org policy `iam.managed.disableServiceAccountApiKeyCreation` (Active, not user-disablable), which blocks JSON-key creation — the Service Account path is impossible on this account.

**Replaced by CSV upload — no Google Cloud setup needed.** Onboarding documentation moves to **user-facing in-app help text on the import button** (a short "How to export your sheet as CSV and import it" tooltip/modal). Implementation architecture: §11.1.

---

## 8. Risk analysis

| Risk | Severity | Mitigation |
|---|---|---|
| **Schema drift** — row label renamed/reordered, new metric row inserted | High | Parser keys on a `sheet_label_to_field.yaml` map with **exact-match + fail-loud**: an unmapped/!missing required row raises, never silently zero-fills. Alert on drift. |
| **Wide-format column growth** — new month = new column | Medium | Discover columns by header scan (parse `Mai 2026`), never hardcode column index. |
| **Manual-entry delay** — month not filled until mid-next-month | Medium | Store `synced_at` + treat a blank current-month column as "not yet reported", surface "N/A — pending finance update" in UI, never 0. |
| **Dirty cells** — `#DIV/0!`, empty, `"11 579"` thousand-sep, `%` strings, `-` | High | Robust normalizer (§11): strip spaces/`%`, map error strings → NULL, parse RON integers. Validate ranges (spend ≥ 0, conversion 0–100%). |
| **Two contradictory "contract" numbers** confuse users/Claude | Medium | Distinct field names + chat-router disambiguation (§6); tool descriptions state the definition. |
| **Revenue semantics** — Încasări (cash) ≠ contract value | Medium | Tool descriptions spell out "payments received in month"; do not derive per-contract averages from it. |
| **Single-sheet dependency / availability** — Google API down, sheet deleted, perms revoked | Medium | Cache last good sync in `raw_marketing_monthly`; serve last-synced with a staleness badge; alert on sync failure. |
| **Source revision tracking** — silent edits to past months | Low/Med | Store `source_revision` (hash of the uploaded CSV); each upload re-parses all months, so historical edits land on the next import. |
| **PII** — sheet is business aggregates, low PII risk | Low | Still respect logging rules (CLAUDE.md §6); log months/counts, not raw cells. |

---

## 9. Storage schema (proposal — Alembic migration, Phase 3.5)

`raw_marketing_monthly` — one row per (tenant, month):

```
id                       uuid pk
tenant_id                uuid  -- multi-tenancy (CLAUDE.md §3); FK tenants
year_month               date  -- first of month; UNIQUE (tenant_id, year_month)

-- spend
meta_spend_ron           numeric
google_spend_ron         numeric
tiktok_spend_ron         numeric   -- NULL before Jan 2026
digital_total_ron        numeric

-- traffic & leads
traffic_sessions         integer
leads_mail_fb_ig         integer   -- NULL before Jan 2025
leads_telefon            integer
leads_whatsapp           integer
leads_site_total         integer
leads_designer           integer
leads_other              integer
leads_total              integer

-- funnel & conversion (store as fraction or %? decide: keep % as sheet shows, 0–100)
cost_per_lead            numeric
site_conversion          numeric
vizits                   integer
offers                   integer
conversie_vizita         numeric
conversie_oferta_vo      numeric
conversie_oferta_lo      numeric
conversie_contract_oc    numeric

-- business truth
contracts_signed         integer   -- authoritative (22 for May 2026)
cac                      numeric
revenue_ron              numeric   -- Încasări (cash received)
daily_avg_check          numeric
roas_pct                 numeric   -- pre-computed (1447 for May)
yoy_pct                  numeric

-- provenance
synced_at                timestamptz
source_revision          text      -- hash of the uploaded CSV (no Drive revision id on the CSV path, §0)
uploaded_by              text      -- uploader identity for the "Ultima actualizare" display
```

Notes:
- **UPSERT key** `(tenant_id, year_month)` — mirrors the existing KPI-table idempotency pattern.
- **Numeric vs integer:** spend/revenue/ratios `numeric`; counts `integer`. Nullable everywhere (manual gaps are normal).
- **Conversion unit:** decide once — store as the sheet shows (percent 0–100) or as fraction 0–1. Recommend storing exactly as the sheet (percent), and document it, to keep pre-computed values round-trippable.
- Consider a sibling `raw_marketing_monthly_raw` JSON column (full parsed row) for audit/debug, like `raw_payload` on MEFI leads.

---

## 10. Sync strategy (CSV upload — automated Google API sync REJECTED, see §0)

> ~~Scheduled daily Celery Beat task polling the Google Sheets API; Drive `revisions` API for change detection.~~ **REJECTED** — depends on the Service Account path (§0). No automated external sync.

CSV-upload trigger model (detail in §11.1):
- **Manual only:** admin clicks "Importă date marketing" on `/marketing` and selects the downloaded CSV. No scheduler.
- **Frequency:** monthly, matching the sheet's manual-update cadence.
- **Idempotent:** UPSERT on `(tenant_id, year_month)`; re-uploading the same/updated CSV is safe and overwrites historical months (captures silent edits to past months automatically, since the whole file is re-parsed).
- **Provenance:** store `synced_at` + uploader identity; `source_revision` becomes a hash of the uploaded file (no Drive revision id available).
- **Staleness:** dashboard shows a "stale data" warning if no import in 35+ days (one monthly cycle + grace).
- **Failure handling:** parse failure returns structured errors/warnings to the uploader (line numbers) and **does not** partially write; last good rows remain. Optionally record an import attempt in `SyncRun` for audit.

---

## 11. Data normalization plan

- **Thousand separators:** `"11 579"`, `"11.579"`, non-breaking spaces → strip → `11579`. Watch RO decimal comma vs thousands dot.
- **Percent strings:** `"1447%"` → `1447` (store as the unit you chose in §9).
- **Error/empty cells:** `#DIV/0!`, `#N/A`, `""`, `"-"` → `NULL` (never 0 — 0 is a real value, missing is not).
- **Month headers:** `"Aprilie 2024"` → `date(2024,4,1)` via the RO month map (§2).
- **Label→field map:** `sheet_label_to_field.yaml`, exact-match, fail-loud on unknown/missing required rows.
- **Range validation:** spend ≥ 0; conversions within sane bounds; counts non-negative integers; log+flag outliers (e.g. ROAS denominator mismatch from §3).

---

## 11.1 CSV Upload Implementation Architecture (SELECTED path)

The marketing manager exports the Google Sheet to CSV and uploads it in-app; the backend parses and UPSERTs it. No external API, no credentials.

### Endpoint

- `POST /api/v1/marketing/import-csv` — `multipart/form-data` (the CSV file).
- **Admin role required** (RBAC check — reuse the existing role guard).
- Returns: `{ "imported_months": int, "errors": [], "warnings": [] }`.
- **Idempotent:** UPSERT on `(tenant_id, year_month)` — re-uploading overwrites.
- Thin endpoint per Clean Architecture: validate → delegate to the parser/service → UPSERT via repository. No parsing logic in the handler.

### Service module

`backend/app/services/marketing/csv_parser.py`:
- Parses **wide-format** CSV (rows = metric labels, columns = months `"Aprilie 2024"` style).
- **Romanian month mapping** (Ianuarie=01 … Decembrie=12) → first-of-month `date`.
- **Number parser:** `"11 579"` (incl. non-breaking space) → `11579`; `"#DIV/0!"`/`"#N/A"`/`"-"`/empty → `NULL`; `"1447%"` → `1447`. (Shares the normalizer rules in §11.)
- **Schema validator:** required rows present — **`Buget META`, `Contract`, `Încasări` mandatory**; missing required row → fail-loud with the offending label. Unknown rows → warning (forward-compatible), via `sheet_label_to_field.yaml` exact-match.
- Returns **structured rows** (one dict per month) ready for `(tenant_id, year_month)` UPSERT into `raw_marketing_monthly`.
- **Partial-failure policy:** on any required-row/parse error, return errors with **line numbers** and write **nothing** (all-or-nothing per upload); warnings (e.g. an unmapped optional row, a `#DIV/0!` cell coerced to NULL) do not block the import.

### UI

`frontend/src/app/(dashboard)/marketing/page.tsx`:
- **"Importă date marketing"** button (admin role only).
- **Modal:** file picker (**`.csv` only**) + **5 MB size limit** (client-side guard + server enforcement).
- Upload progress indicator → **success toast** with month count + an error list carrying **line numbers** on failure.
- **Last-upload display:** e.g. *"Ultima actualizare: 15 mai 2026 de admin@sofabelle.ro"* (from `synced_at` + uploader identity).
- In-app **help text** on the button: how to export the sheet as CSV (replaces the old Service Account onboarding doc, §7).

### How Sofa Belle uses it (end-to-end)

1. Marketing manager opens the Google Sheet.
2. **File → Download → Comma-separated values (.csv)**.
3. Opens our `/marketing` dashboard.
4. Clicks **"Importă date marketing"**.
5. Selects the downloaded CSV.
6. Sees a success toast: *"Importat 26 luni (Aprilie 2024 – Mai 2026). 0 erori."*
7. Dashboard refreshes with the new data.

### Triggers (no automated sync)

- **Manual:** user clicks the button.
- **Frequency:** monthly (matches the sheet's update cadence).
- **Notification:** dashboard shows a **"stale data"** warning if no import in **35+ days**.

---

## 12. Cross-source consistency guard (new reconciliation, mirrors the hotfix)

Add a reconciliation check (in the spirit of `test_contract_reconciliation.py`):
- **MEFI `customers_won` (21)** vs **Sheet `contracts_signed` (22)** for each month → assert the gap is within a small tolerance (e.g. |Δ| ≤ 2 or ≤ 10%); alert if it widens, which signals a CRM-hygiene or finance-entry drift worth a human look.
- This does **not** force them equal — it monitors the gap as a data-quality signal.

---

## 13. Implementation roadmap — phase splits (CSV path)

**Estimate: ~3 days.** No Service Account / live-API work; ingestion is a CSV parser + upload endpoint.

| Sub-phase | Scope | Est. |
|---|---|---|
| **3.5a** | CSV parser (`services/marketing/csv_parser.py`) — wide-format, RO month map, number normalizer, schema validator (`Buget META`/`Contract`/`Încasări` mandatory) + `sheet_label_to_field.yaml` + Alembic migration `raw_marketing_monthly` (§9) + parser unit tests against the Apr/Mar/May ground-truth fixture (captured from the first CSV) | **1 d** |
| **3.5b** | Upload endpoint `POST /api/v1/marketing/import-csv` (multipart, **admin RBAC**, all-or-nothing UPSERT on `(tenant_id, year_month)`, structured errors/warnings) | **0.5 d** |
| **3.5c** | UI: "Importă date marketing" button + modal (`.csv` only, 5 MB), upload progress, success toast (month count), error list with line numbers, last-upload + staleness display | **0.5 d** |
| **3.5d** | Chat tools: `get_monthly_metrics`, `get_revenue`, `get_roas`, `get_marketing_costs`, `get_cpl`; smart-route `get_kpi`; join `get_marketing_dashboard` (§5) | **0.5 d** |
| **3.5e** | Dashboard updates: revenue card (real numbers, no longer N/A), ROAS chart, spend/CPL/CAC surfaced from the sheet | **0.5 d** |
| **3.5f** | UAT + docs (`docs/INTEGRATIONS.md` CSV import, `docs/SOFABELLE.md` metric definitions, decision record for 2-source + naming) + cross-source consistency guard (§12) + commit | **0.5 d** |

**Total: ~3 days.**

**Prerequisite (not dev time):** the user produces the first CSV export of the sheet so §3 ground-truth can be captured as the parser's regression fixture.

**Dependencies / sequencing vs the paused hotfix:**
- The contract-counting **backfill (hotfix step b)** can proceed independently — it populates the MEFI side (`customers_won`=21). Recommend: **decide naming (§6) first**, then run the backfill once, writing the final column name, to avoid a double-backfill.
- Phase 8 chat work stays paused until 3.5d lands the routing (otherwise chat answers "contracts" from the wrong source).

---

## 14. Decision points

**Resolved**
- ✅ **DECIDED — CSV Upload over Service Account.** Org policy `iam.managed.disableServiceAccountApiKeyCreation` blocks the JSON key (§0). Implementation goes CSV.
- ✅ **DECIDED — 2-source architecture** (MEFI lead-level + Sheet/CSV monthly). (§5)

**Pending**
- ⏳ **Metric naming:** physical rename `contracts_count → customers_won` (**recommended** — removes the misleading name; touches model/migration/services/readers/tests in lockstep) vs semantic-only reframe (cheaper, leaves a misleading column name). (§6)
- ⏳ **When to run the hotfix backfill:** **recommend after the metric rename, single-pass** (write the final column name once; avoid a double-backfill). (§4.3, §13)
- ⏳ **Ambiguous "câte contracte":** default to Sheet (22, business truth) with an optional MEFI note — confirm? (§6)
- ⏳ **Conversion unit** in storage: percent (0–100, as sheet) or fraction (0–1)? (§9)
- ⏳ **"Contracts signed" trust threshold:** if MEFI and Sheet disagree by >2, which wins in the UI, and do we surface the discrepancy to the CEO? (§12)
- ⏳ **Phase numbering:** keep as "Phase 3.5 / MarketingSheet", or insert as a formal phase in `ROADMAP.md`?

> Note: the earlier "sync cadence (08:00 daily)" question is **moot** — the CSV path has no automated sync (manual monthly upload, §10/§11.1).

---

## 15. Verified facts in this document

- Sheet export → **HTTP 401** (private; not link-exportable). Verified 2026-06-01.
- **Service Account path blocked** by Google Cloud org policy `iam.managed.disableServiceAccountApiKeyCreation` (Active, not user-disablable). Verified 2026-06-01. → **CSV Upload selected** (§0).
- MEFI event-model contracts (live `v_mefi_leads_active`, this session): Jan 1, Feb 0, Mar 21, Apr 29, **May 21**; total 72.
- MEFI `estimated_value` **NULL for all 1238 leads** → MEFI revenue unavailable (per `PHASE-9-BACKLOG.md` + ground truth).
- Sheet May 2026 (user-supplied, authoritative): Contracts **22**, Revenue **358,978 RON**, ROAS **1447%**.
- April/March 2026 sheet numbers: **NOT yet captured** — pending the first CSV upload.

**No code was changed. No backfill was run. No Phase 8 work dispatched.**
