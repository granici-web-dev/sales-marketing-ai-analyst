# Phase 3 Hotfix — Contract Counting (Cohort → Event Model)

**Status:** PLAN — awaiting approval
**Severity:** CRITICAL (CEO-facing data discrepancy; erodes trust in the product)
**Created:** 2026-05-30
**Blocks:** Phase 8 closure (08-08 and further chat work paused until contract counting is correct end-to-end)

---

## 1. Problem statement

Our metrics engine counts **"contracts in period"** as *leads CREATED in the period whose current status = Clienți (status_id=1)* — a **cohort model**. MEFI (and the CEO) count it as *leads whose status CHANGED TO Clienți in the period* — an **event model**.

| Query | May 2026 result |
|---|---|
| `created_at_source` in May AND `status_id=1` (current system) | **9** |
| `status_changed_at` in May AND `status_id=1` (MEFI's definition) | **21** |
| By showroom (status_changed_at): București 11, Brașov 8, Cluj 2 | 21 |

A lead created in February but signed in May is a **May contract** — that is when revenue lands and what the CEO tracks. Our system attributes it to February (and only if it's still status 1 today), so May shows 9 instead of ~16–21.

**This is a Phase 3 oversight, not a documented decision.** The Phase 3 docs (D-10, D-13) specify *which* date to compute and *which statuses* map to funnel stages, but never specify the **time-basis** for counting. No reconciliation against MEFI totals was ever planned (03-VALIDATION.md only checks internal SQL consistency).

---

## 2. Key technical constraint (changes the naive fix)

The transition log table `mefi_lead_history` **cannot** be used as the event-date source:

- `mefi_repository.detect_and_record_history()` writes every history row with `"changed_at": datetime.now(UTC)` — our **sync-detection time**, not MEFI's real transition time ([mefi_repository.py:120,131](../../backend/app/services/repositories/mefi_repository.py#L120)).
- On the initial backfill, every lead got a single history row stamped at backfill-time. So `mefi_lead_history.changed_at` is **useless for historical "when did it transition" questions**.

**The only reliable event timestamp is `raw_mefi_leads.status_changed_at`** — synced straight from MEFI (the real value), already exposed by `v_mefi_leads_active` as `status_changed_at` / `status_changed_at_local`. This is the field the verification query used to get 21.

This is sound because **"won" (status 1) is terminal**: a status-1 lead's last status change *is* its signing date.

---

## 3. Decisions (locked with user 2026-05-30)

1. **Scope:** **Contracts + revenue only.** Leads stay creation-date (correct). Visits stay `source_id=5` (walk-in date = creation date, already effectively event-based). Offers stay cohort — they **cannot** be reliably event-counted (no offer timestamp; `status_changed_at` is overwritten once an offered lead progresses to won). See §8.
2. **Conversion rates:** **Period funnel ratios.** Contract-involving rates (`o_to_c`, `l_to_c`, source `conversion_rate`, salesperson `conversion_o_to_c`/`conversion_l_to_c`, `win_rate`) are computed at **read time from summed counts over the range** — not from last-day or averaged daily rates. Accepts that these are period ratios, not strict cohort conversions (matches how MEFI / CRM dashboards present a monthly funnel).
3. **No Alembic migration.** All target columns already exist. We change computation + re-run the backfill.

---

## 4. Affected metrics — final disposition

| Metric | Current basis | New basis | Action |
|---|---|---|---|
| Leads (total, by source) | `created_at_source` | unchanged (creation = event) | none |
| Visits | `source_id=5` on `created_at_source` | unchanged (walk-in = creation) | none |
| Offers | `reached_offer` on creation cohort | unchanged (not reliably fixable) | none — document limitation |
| **Contracts** | `reached_contract` on creation cohort | `status_id=1 AND status_changed_at::date = D` | **FIX** |
| **Revenue** | `estimated_value` of cohort contracts | `estimated_value` of contracts signed on D | **FIX** |
| **deals_won** (salesperson) | cohort | signed-on-D (per rep) | **FIX** |
| **deals_won / revenue** (source) | cohort | signed-on-D (per source) | **FIX** |
| Conversion `l_to_v`, `v_to_o` | cohort (within creation cohort) | unchanged | none |
| Conversion `o_to_c`, `l_to_c` | cohort/cohort | period ratio from summed counts at read time | **FIX (read path)** |

---

## 5. Code changes

### 5.1 `daily_kpi_service.py` — split the aggregate query

Currently one query filters everything by `created_at_source = kpi_date`. Split into:

- **Query A** (unchanged WHERE `created_at_source = kpi_date`): `leads_total`, `leads_*` by source (incl. designer CTE), `visits_count`, `offers_count`. Drop `contracts_count`/`revenue` from this query.
- **Query B** (new, WHERE `status_id = 1 AND (status_changed_at AT TIME ZONE 'Europe/Bucharest')::date = :kpi_date`): `contracts_count = COUNT(*)`, `revenue = SUM(estimated_value)`.

```sql
-- Query B (contracts signed on kpi_date)
SELECT
    COUNT(*) AS contracts_count,
    SUM(v.estimated_value) AS revenue
FROM v_mefi_leads_active v
WHERE v.tenant_id = :tid
  AND v.status_id = 1
  AND (v.status_changed_at AT TIME ZONE 'Europe/Bucharest')::date = :kpi_date
```

- `avg_deal_size` = `revenue / contracts_count` (unchanged formula, new inputs).
- Stored daily `conversion_o_to_c` / `conversion_l_to_c`: still computed from this row's counts (now event-num / cohort-den at daily grain). They remain for the single-day view and WoW/MoM deltas, **but period reads recompute from sums** (§5.4). Add a docstring note that these daily columns are not meaningful cohort conversions and period consumers must recompute. `conversion_l_to_v` / `conversion_v_to_o` are unchanged (both within the creation cohort).
- Update the module docstring: contracts/revenue use `status_changed_at` (event/signing date); all other counts use `created_at_source`.

### 5.2 `salesperson_kpi_service.py` — per-rep contracts by signing date

The per-rep query (`per_rep_sql`) selects leads by `created_at_source = kpi_date` and derives `deals_won`/`revenue` from `reached_contract` in Python. Change `deals_won` + `revenue` to a **separate per-rep query** keyed on `status_changed_at`:

```sql
-- per-rep contracts signed on kpi_date
SELECT v.external_id, v.estimated_value
FROM v_mefi_leads_active v
WHERE v.tenant_id = :tid
  AND v.assigned_to_id = :sp_id
  AND v.status_id = 1
  AND (v.status_changed_at AT TIME ZONE 'Europe/Bucharest')::date = :kpi_date
```

- `deals_won` = row count; `revenue` = SUM(estimated_value); `avg_deal_size` = revenue/deals_won.
- `leads_assigned`, `leads_contacted`, `visits_conducted`, `offers_sent`, `deals_lost`, TTFT, `data_completeness_pct` stay on the creation-cohort query (unchanged).
- `deals_lost` stays cohort (out of scope; not a MEFI-comparison metric). Note the minor deals_won(event)/deals_lost(cohort) inconsistency in the docstring.
- Stored `conversion_o_to_c` / `conversion_l_to_c` per rep: same treatment as 5.1 (period reads recompute).

### 5.3 `source_kpi_service.py` — per-source contracts by signing date

The single `categorized` CTE filters by `created_at_source = kpi_date` and aggregates `deals_won`/`revenue`. Add a **second categorized CTE** for contracts keyed on `status_changed_at`, joined per category:

- `leads`, `offers`, `visits` stay on the creation-cohort CTE.
- `deals_won`, `revenue` come from the status_changed_at CTE, grouped by the same source-category CASE.
- `conversion_rate` (= deals_won/leads) per source: at daily grain becomes event/cohort; period reads recompute from sums (§5.4).
- Zero-fill semantics for all 11 canonical categories unchanged.

### 5.4 `dashboard_read_service.py` — recompute period rates from sums

Currently: sales dashboard reads conversion rates from the **last day** (`order_by(date.desc()).limit(1)`); salespeople/source use `func.avg(daily_rate)`. With period funnel ratios, recompute the **contract-involving** rates from the summed counts already selected:

- `get_sales_dashboard`: compute `o_to_c = contracts_count / offers_count` and `l_to_c = contracts_count / leads_total` from the Step-1 SUMs (NULLIF guard). Keep `l_to_v`, `v_to_o` from last-day OR (preferred for consistency) also recompute from sums (`visits/leads`, `offers/visits`). **Recommend recomputing all five from sums** for one coherent period-ratio definition. WoW/MoM deltas: see §7 (open item).
- `get_salespeople_dashboard`: replace `func.avg(conversion_o_to_c)` / `func.avg(conversion_l_to_c)` with Python recompute from summed `deals_won`/`offers_sent`/`leads_assigned`. `win_rate` already recomputes from sums — no change. Recommend recomputing `l_to_v`/`v_to_o` from sums too for consistency.
- `get_marketing_dashboard`: `site_conversion_rate` replace `func.avg(SourceDailyKpi.conversion_rate)` for `site` with `SUM(deals_won)/SUM(leads)` over the range.

### 5.5 `get_kpi.py` chat tool — recompute rates from sums

`contracts`/`revenue`/`leads`/`visits`/`offers` already sum daily values → automatically correct once §5.1 lands. Change conversion handling: instead of averaging daily rate values ([get_kpi.py:136-139](../../backend/app/services/chat/tools/get_kpi.py#L136)), accumulate the underlying counts (`contracts_total`, `offers_total`, `leads_total`, `visits_total`) and compute the requested rates from those sums with NULLIF guards. Keep `avg_deal_size` logic (already sum-based).

### 5.6 Other chat tools — verify, likely no change

`get_funnel_data` delegates to `get_sales_dashboard` (fixed in 5.4). `compare_periods`, `get_trend`, `get_salesperson_performance`, `get_showroom_performance` — audit during implementation to confirm they read summed counts / the fixed read service and don't independently average daily rates. Patch any that do.

---

## 6. Backfill procedure

No schema change → just recompute. Upserts are idempotent on `(tenant_id, date)`.

1. Determine the full historical range: earliest `created_at_source` (or earliest `status_changed_at`, whichever is earlier) through yesterday (Bucharest). The status_changed_at basis means a contract can land on a date with no new leads — backfill must cover every date in the range regardless.
2. Re-run for the tenant:
   ```
   tasks.etl.backfill_daily_kpis(tenant_id, date_from, date_to)
   ```
   This recomputes `daily_kpi`, `salesperson_daily_kpi`, `source_daily_kpi` for every date, overwriting via UPSERT.
3. A pre-DELETE is optional (UPSERT overwrites). Only `DELETE FROM ... WHERE date >= date_from` if there are stale dates outside the recompute range — otherwise skip to avoid an unnecessary destructive step.
4. WoW/MoM deltas recompute correctly because backfill runs chronologically (prior rows exist before later ones).

---

## 7. Open implementation item — WoW/MoM deltas on rates

The stored `*_wow_delta` / `*_mom_delta` columns compare a day's stored rate to the rate 7/30 days prior. For contract-involving rates at daily grain these are now noisy (event-num / cohort-den). Options to resolve during implementation:
- **(a)** Leave count deltas (leads, revenue) as-is — they're valid; accept that rate deltas are daily-grain artifacts and the dashboard surfaces them only on the last-day row.
- **(b)** Recompute WoW/MoM at the period level in the read service (compare this-period ratio vs prior-equal-length-period ratio).

**Recommendation:** (a) for the hotfix (smallest change; counts are what the CEO disputes), file (b) as a Phase 3 follow-up. Flag for decision at implementation time.

---

## 8. Why offers are NOT in scope (answer to the open question)

"Offers sent in period" needs the offer-transition date. We don't have it reliably:
- `offer_sent_flag` has no timestamp.
- `mefi_lead_history.changed_at` = sync time (unreliable for historical data, §2).
- `status_changed_at` is **overwritten** when an offered lead progresses to won (then it points at the win date, status_id=1) — so for any lead past the offer stage the offer date is lost.

Reliable event-based offer counting would require capturing real per-transition timestamps going forward, or MEFI exposing a status-history endpoint (per CLAUDE.md, MEFI currently exposes lead endpoints only). **Out of scope; documented as a known limitation.** Visits are fine because for `source_id=5` (walk-in) the creation date *is* the visit date.

> Separate latent issue (not this hotfix): visits via `source_id=5` contradicts spec D-13 (visit = reached status 17). The implementation deliberately overrode D-13 to match the client's Excel "Vizita." Worth a follow-up ticket to reconcile spec vs implementation.

---

## 9. Tests

- **Unit — daily_kpi_service:** seed leads created in month A but signed (status_changed_at) in month B; assert `contracts_count`/`revenue` land in month B, leads land in month A. Cover: signed-this-month / created-prior, created-this-month / not-yet-signed (excluded from contracts), signed-this-month / created-this-month.
- **Unit — salesperson_kpi_service:** per-rep deals_won attributed by signing date; rep with a contract signed today for a lead created last month.
- **Unit — source_kpi_service:** per-source deals_won/revenue by signing date; zero-fill intact.
- **Unit — get_kpi:** conversion rates computed from summed counts, not averaged daily rates; `contracts` sum matches event model.
- **Unit — dashboard_read_service:** period `o_to_c`/`l_to_c` recomputed from sums; salespeople `conversion_o_to_c` from sums; marketing `site_conversion_rate` from sums.
- **Reconciliation test (new — closes the gap 03-VALIDATION never had):** a fixture/integration check asserting `daily_kpi` contracts for a month equals the direct `status_changed_at` query against `raw_mefi_leads` for the same tenant/month. This is the guard that would have caught the 9-vs-21 bug.
- Update existing Phase 3 metrics tests that assert cohort-based contract counts (expect failures — update expected values to event-based).

## 10. Acceptance criteria

- [ ] Chat: "Câte contracte în mai 2026?" returns ~16–21 (matching MEFI), not 9.
- [ ] Showroom split via status_changed_at: București 11, Brașov 8, Cluj 2 (or current live values) reproduced by `source_daily_kpi` sums for May.
- [ ] `/sales`, `/salespeople`, `/marketing` dashboards show event-based contracts/revenue for May.
- [ ] AI Insights problems detector (reads `daily_kpi`) reflects corrected contracts.
- [ ] Period conversion rates are funnel ratios from summed counts (not last-day / averaged).
- [ ] Reconciliation test passes against `raw_mefi_leads` status_changed_at counts.
- [ ] Backfill re-run completed for full historical range; all three KPI tables recomputed.

## 11. Docs to update

- `get_kpi` / `get_funnel_data` tool definitions: add "Definition: a contract is a lead **signed (status→Clienți) in the period**, by status-change date; revenue is recognized on the signing date." So Claude explains the number correctly.
- `prompt_builder.py` / chat system prompt: add the contract definition note if metric definitions are surfaced there (verify).
- Phase 3 decision record (03-CONTEXT.md or a new D-NN): document the event-vs-cohort time-basis decision so it's no longer an implicit default.
- `docs/SOFABELLE.md` metric definitions section if it states contract counting.

## 12. Rollout & risk

- **Risk:** other consumers (anomaly rules, insights) that independently read `reached_contract` on a creation-cohort basis. **Mitigation:** grep for `reached_contract` / `contracts_count` / `deals_won` consumers during implementation; confirm each reads the fixed tables or is patched.
- **Risk:** estimated_value nulls inflate/deflate revenue. **Mitigation:** unchanged null-handling; revenue is `SUM` (nulls ignored), avg_deal_size already guards contracts>0.
- **Reversibility:** pure recompute; re-running the old code + backfill reverts. No destructive migration.

## 13. Sequencing

1. Service changes (5.1 → 5.3) + unit tests.
2. Read-path changes (5.4 → 5.6) + tests.
3. Reconciliation test (§9).
4. Run backfill (§6) in dev; verify acceptance criteria (§10) against live data.
5. Doc updates (§11).
6. Then resume Phase 8 (08-08).
