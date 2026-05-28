# Phase 4: Anomaly Detection - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-28
**Phase:** 4-Anomaly-Detection
**Areas discussed:** Row granularity, Loss formula source, Rule architecture, Baseline window fallback

---

## Row Granularity

| Option | Description | Selected |
|--------|-------------|----------|
| One aggregate row per rule per day | UPSERT on (tenant_id, date, rule_id). context_json holds count + IDs + key metric. Matches SC wording "a stuck_offer row". | ✓ |
| One row per offending lead | UPSERT on (tenant_id, date, rule_id, lead_external_id). More granular but harder for Phase 5 to consume many rows. | |
| You decide | Claude picks whichever fits the Phase 5 prompt structure better. | |

**User's choice:** One aggregate row per rule per day (Recommended)
**Notes:** Consistent with SC wording ("a slow_first_touch row", "a stuck_offer row"). context_json format: count + lead_ids/salesperson_ids + key metric value (e.g., worst_hours_elapsed).

---

| Option | Description | Selected |
|--------|-------------|----------|
| Count + list of lead/salesperson IDs | {count: 3, lead_ids: [...], worst_hours: 8.5}. Enough for Claude to narrate specifics and Phase 6 API to surface offenders. | ✓ |
| Count only | {count: 3}. Simpler but Phase 5 can't reference specific leads. | |
| Full row details per offender | {offenders: [{lead_id, hours_elapsed, salesperson}, ...]}. Rich but potentially large JSON. | |

**User's choice:** Count + list of IDs (Recommended)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — one row per rule, salesperson_ids in context_json | Consistent aggregate model for all rules. | ✓ |
| One row per underperforming salesperson | More granular; breaks consistent model. | |
| You decide | — | |

**User's choice:** Yes — consistent aggregate for salesperson rules too

---

## Loss Formula Source

| Option | Description | Selected |
|--------|-------------|----------|
| Trailing 30-day avg from daily_kpi | Dynamic, improves as more data accumulates. Falls back to 7-day window when <30 days exist. | ✓ |
| Single empirical constant (5.8%) | Hardcode L→C = 71/1219 = 5.83%. Simple but never updates automatically. | |
| Read from tenants.funnel_config JSONB | Tenant-configurable, migration seeds 5.8%. | |

**User's choice:** Trailing 30-day avg from daily_kpi (Recommended)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Lost-opportunity formula | showroom_traffic_drop: (expected_visits - actual_visits) × avg_deal_size × trailing_close_rate. underperforming_salesperson: (team_avg_contracts - actual_contracts) × avg_deal_size. | ✓ |
| 0 for non-revenue rules | Set estimated_loss_ron = 0 for trend/performance rules. Simpler but incomplete. | |
| You decide per rule | Claude defines formula per rule based on business sense. | |

**User's choice:** Lost-opportunity formula (Recommended)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Count × avg_deal_size × drop factor | count_affected × avg_deal_size × 0.25. Conservative 25% reduced close probability. | ✓ |
| sum(estimated_value) × trailing close rate | Falls back to 0 on NULL estimated_value (many leads have NULL). | |
| You decide | — | |

**User's choice:** Count × avg_deal_size × drop factor (Recommended). Drop factor = 0.25 — business assumption, to be reviewed after seeing first reports.

---

## Rule Architecture

| Option | Description | Selected |
|--------|-------------|----------|
| Single AnomalyService class, one method per rule | Consistent with DailyKpiService pattern from Phase 3. No new patterns. | ✓ |
| Rule registry — list of callable rule objects | BaseRule ABC + 6 concrete classes. Extensible but adds abstraction premature for 6 rules. | |
| You decide | Claude picks the approach that fits Phase 3 patterns best. | |

**User's choice:** Single AnomalyService class (Recommended)

---

| Option | Description | Selected |
|--------|-------------|----------|
| junk_lead_quality is one of the 6 standard rules | Uniform treatment. Each non-junk rule excludes junk IDs via shared subquery. | ✓ |
| Separate junk filter step before rules run | Task fetches junk IDs first and passes them to all rules as an exclusion set. | |

**User's choice:** junk_lead_quality as standard rule, shared subquery for exclusion

---

| Option | Description | Selected |
|--------|-------------|----------|
| New app/services/anomaly/ directory | Clean separation from metrics/. Mirrors DailyKpiService/MetricsRepository split. | ✓ |
| Inside app/services/metrics/ | Less directory creation but mixes concerns. | |

**User's choice:** New app/services/anomaly/ directory (Recommended)

---

## Baseline Window Fallback

| Option | Description | Selected |
|--------|-------------|----------|
| Use available data with 7-day minimum | ≥7 rows: use available data. <7 rows: skip rule for the day. Logged at INFO level. | ✓ |
| Always require 30 days; skip otherwise | Stricter. Fine for Sofa Belle (148 days available) but poor UX for future tenants. | |
| Hardcode Sofa Belle baseline as global fallback | Breaks multi-tenancy in Iteration 4. | |

**User's choice:** Use available data with 7-day minimum (Recommended)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yesterday only | Only leads created on kpi_date with time_to_first_touch > 300 business minutes. Consistent daily-snapshot model. | ✓ |
| All active leads with no contact yet | More comprehensive but may flag leads already in later funnel stages. | |

**User's choice:** Yesterday only (Recommended)

---

## Claude's Discretion

None — all areas had clear user selections.

## Deferred Ideas

- **Dynamic rule thresholds** — configurable via funnel_config. Deferred to multi-tenant iteration.
- **Rule enable/disable toggle** — per-tenant. Phase 4 always runs all 6 rules.
- **Historical anomaly trends** — frequency charts over time. Phase 9 / Iteration 2.
- **Additional rules** — `missed_callback`, `evening_lead_response`. Not in ANOM-01..07 scope.
- **Backfill support** — `backfill_anomalies` task. Anomalies are point-in-time; lower priority.
