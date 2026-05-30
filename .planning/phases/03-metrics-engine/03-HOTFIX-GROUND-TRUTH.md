# Phase 3 Hotfix — Ground Truth (Contract Counting)

**Captured:** 2026-05-30 against the live dev DB (`db_sofabelle_analytics`, tenant `00000000-0000-0000-0000-000000000001` = Sofa Belle).
**Source:** `v_mefi_leads_active` — exactly the path the fixed metrics services use.
**Definition (event model):** a contract is a lead with `status_id = 1` (Clienți) whose `status_changed_at` (Bucharest local) falls in the period. Revenue = `SUM(estimated_value)` of those contracts.

These numbers are the **regression fixtures and UAT checklist** for the hotfix. After backfill, the system MUST reproduce them.

---

## Contracts by month (event model)

| Period | Contracts | Old cohort model (buggy) |
|---|---|---|
| January 2026 (full) | **1** | — |
| January 23–31, 2026 | **1** | — |
| February 2026 | **0** | — |
| March 2026 | **21** | — |
| April 2026 | **29** | — |
| **May 2026** | **21** | **9** |

All-time contracts (`status_id=1`, all `lifecycle=active`): **72** = 1 + 0 + 21 + 29 + 21. ✓
Old cohort query for May returns **9** — reproduces the bug exactly (delta confirmed).

## May 2026 by showroom (physical location field)

| Showroom | Contracts |
|---|---|
| București | 11 |
| Brașov | 8 |
| Cluj | 2 |
| **Total** | **21** ✓ |

## May 2026 by salesperson

| Salesperson | external_id | Contracts |
|---|---|---|
| Raileanu Leon | 13 | 9 |
| Roibu Valeria | 8 | 7 |
| Zagrian Emilia | 11 | 2 |
| Dragoi Mihaela | 12 | 2 |
| Moaca Andreea | 9 | 1 |
| Godja Adina Maria | 10 | 0 |
| **Total** | | **21** ✓ |

Ranking narrative: **Raileanu leads (9), Roibu close second (7)** — NOT the old "Raileanu 5 vs 2 dominates". Chat answer tested 2026-05-29 ("Raileanu Leon cu 5 contracte") is now WRONG.

## April 2026 by salesperson (for cross-month UAT)

| Salesperson | Contracts |
|---|---|
| Raileanu Leon | 10 |
| Roibu Valeria | 6 |
| Dragoi Mihaela | 5 |
| Zagrian Emilia | 4 |
| Godja Adina Maria | 3 |
| Moaca Andreea | 1 |
| **Total** | **29** ✓ |

## May 2026 by source category (marketing dashboard)

| Source | Contracts |
|---|---|
| showroom | 8 |
| whatsapp | 3 |
| site | 3 |
| telefon | 2 |
| colaborare | 2 |
| recomandare | 1 |
| client_fidel | 1 |
| arhitect | 1 |
| **Total** | **21** ✓ |

## April → May contract trend (for problem-detector / insights sanity)

29 → 21 = **−27.6%** (NOT the old cohort comparison of −65%). Insights severity must reflect the milder, correct drop.

---

## ⚠️ Revenue data gap (separate track)

`estimated_value` is **NULL for all 1238 leads** (and all 72 contracts). Therefore:
- Total revenue (any period) = NULL/0; `avg_deal_size`, revenue series, ROAS = unavailable.
- The hotfix revenue logic is correct but emits NULL until `estimated_value` is populated.
- Tracked separately as a Phase 9 backlog item (MEFI deal-value field mapping / custom-field extraction). NOT part of contract-counting hotfix.

---

## Reconciliation query (canonical — used by the §9 reconciliation test)

```sql
SELECT
  to_char(date_trunc('month', (status_changed_at AT TIME ZONE 'Europe/Bucharest')), 'YYYY-MM') AS month,
  COUNT(*) AS contracts
FROM v_mefi_leads_active
WHERE tenant_id = :tid
  AND status_id = 1
  AND (status_changed_at AT TIME ZONE 'Europe/Bucharest')::date >= :from_date
GROUP BY 1 ORDER BY 1;
```

The reconciliation test asserts: for each of the last 5 months, `SUM(daily_kpi.contracts_count)` over the month == this direct count.
