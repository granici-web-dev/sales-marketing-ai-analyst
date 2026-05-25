# Phase 3: Metrics Engine - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-25
**Phase:** 3-Metrics-Engine
**Areas discussed:** Source categorization, time_to_first_touch basis, Schema scope (ad-spend fields), Metrics date window & deltas

---

## Source Categorization

### Google handling

| Option | Description | Selected |
|--------|-------------|----------|
| Single 'google' row | No UTM split — simple and honest for MVP1 | ✓ |
| UTM-based split | Inspect utm_source+utm_medium to separate Ads vs Organic | |
| Skip Google entirely | Exclude source_id=1 until Iteration 2 | |

**User's choice:** Single 'google' row (recommended)

---

### Designer source

| Option | Description | Selected |
|--------|-------------|----------|
| Derive from status_id=24 | If lead ever had Designer status, classify source as 'designer' | ✓ |
| Skip designer category | Designer leads fall into 'alte' | |
| Leave as NULL | TBD pending Sofa Belle clarification | |

**User's choice:** Derive designer from status (recommended)

---

### TikTok handling

| Option | Description | Selected |
|--------|-------------|----------|
| Fold into 'mail_fb_ig' | TikTok lands under Meta source IDs in MEFI | ✓ |
| Add 'tiktok' row with NULLs | Placeholder row for future | |
| Flag for Sofa Belle verification | Skip TikTok entirely | |

**User's choice:** Fold into 'mail_fb_ig' (recommended)

---

### Source row count

| Option | Description | Selected |
|--------|-------------|----------|
| 7 rows: add 'google' to existing 6 | mail_fb_ig + telefon + whatsapp + site + designer + alte + google | ✓ |
| Keep 6 rows, roll Google into 'site' | Simpler schema | |
| Keep 6 rows, roll Google into 'alte' | Catch-all | |

**User's choice:** 7 rows (recommended)

---

## time_to_first_touch Basis

### First touch definition

| Option | Description | Selected |
|--------|-------------|----------|
| First status change in mefi_lead_history | Earliest recorded salesperson activity | ✓ |
| Use lead updated_at as proxy | Simpler but measures last update, not first touch | |
| Leave as NULL for Phase 3 | Defer until MEFI exposes explicit timestamps | |

**User's choice:** First status change in mefi_lead_history (recommended)

---

### Business hours adjustment

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — business-hours-adjusted | Subtract non-working time; aligns with 4h target | ✓ |
| No — raw elapsed minutes | Simple but penalizes after-hours leads | |
| You decide | Leave to planner | |

**User's choice:** Yes — business-hours-adjusted (recommended)

---

### Business hours definition

| Option | Description | Selected |
|--------|-------------|----------|
| Mon–Fri 09:00–18:00 Bucharest | Standard Romanian hours | |
| Mon–Sat 09:00–18:00 Bucharest | Include Saturday | |
| Mon–Sat 09:00–20:00 Bucharest | Extended evening hours | |
| Other (free text) | User provided custom hours | ✓ |

**User's choice:** Mon–Sun 09:00–19:00 Europe/Bucharest (7 days/week)
**Notes:** Sofa Belle showrooms are open 7 days a week with 10-hour windows.

---

## Schema Scope (ad-spend fields)

### daily_kpi schema completeness

| Option | Description | Selected |
|--------|-------------|----------|
| Full SPEC.md schema, all ad-spend nullable | Future-ready; no additional migrations needed | ✓ |
| Minimal subset — only Phase 3 columns | Smaller now, requires future migrations | |
| You decide | Leave to planner | |

**User's choice:** Full SPEC.md schema (recommended)

---

### source_daily_kpi.source naming

| Option | Description | Selected |
|--------|-------------|----------|
| Use funnel_config category names | mail_fb_ig, telefon, etc. — matches existing DB keys | ✓ |
| Use SPEC.md generic names | meta, google, organic — cleaner for multi-tenant | |
| Dual — store both | source + source_canonical columns | |

**User's choice:** Use funnel_config category names (recommended)

---

## Metrics Date Window & Deltas

### Which date to calculate

| Option | Description | Selected |
|--------|-------------|----------|
| Yesterday (last completed day) | Previous full calendar day — all leads synced | ✓ |
| Today (current partial day) | Intraday numbers that change throughout day | |
| Date-parameterized only | No default, explicit date always required | |

**User's choice:** Yesterday (recommended)

---

### Missing prior data for deltas

| Option | Description | Selected |
|--------|-------------|----------|
| Store NULL for deltas if prior missing | Honest; dashboard renders as N/A | ✓ |
| Skip daily_kpi row entirely | No row = Phase 4 has nothing to query | |
| Zero out missing deltas | Misleading "no change" signal | |

**User's choice:** Store NULL (recommended)

---

### Date parameterization

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — optional date param, default yesterday | calculate_daily_kpis(date: date | None = None) | ✓ |
| No — yesterday only | Simpler signature, no backfill support | |
| Separate backfill task | Clean separation but more code | |

**User's choice:** Yes — accept optional date param (recommended)

---

## Claude's Discretion

None — user selected an option for every question.

## Deferred Ideas

- UTM-based Google Ads vs Organic split → Iteration 2
- TikTok source category → Iteration 2
- CPL, CAC, ROAS calculation → Iteration 2 (columns nullable in Phase 3 schema)
- GA4 web_sessions → Iteration 3
- Calls data → Future iteration (DOTRO telephony)
- Real-time/intraday KPIs → Out of v1 scope
