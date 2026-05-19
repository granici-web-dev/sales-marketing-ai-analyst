# Feature Landscape — Sales & Marketing AI Analyst

**Domain:** B2B SaaS analytics for SMB (Romanian premium furniture pilot)
**Milestone:** Iteration 1 / MVP1 — MEFI CRM only, no ad platforms yet
**Researched:** 2026-05-19

---

## Research Method & Confidence Note

**Constraint:** Live web search (WebSearch, WebFetch, Brave, Exa, Firecrawl) was not
available in this environment. This research therefore leans on:

1. **HIGH confidence** — Direct project artifacts (`SPEC.md`, `docs/SOFABELLE.md`,
   `PROJECT.md`). These are ground truth, validated by the pilot client.
2. **MEDIUM confidence** — Training knowledge of comparable platforms (HubSpot,
   Pipedrive, Gong.io, Looker Studio, Salesforce, Tableau). Snapshots ~12–18 months
   stale; feature sets evolve.
3. **LOW confidence** — Inferences about what "good" AI sales insight UX looks like,
   based on academic + community discussions in training data. **Flag for validation
   with Sofa Belle during demo phase.**

Where competitor feature claims are made, treat them as "this is generally true of
the category" rather than "verified against current product page in May 2026."

---

## Framing: This Is Not a Generic Analytics Dashboard

Critical context that shapes every feature decision below:

| Dimension | This product | Generic analytics tool |
|---|---|---|
| **Primary deliverable** | A daily Romanian-language action plan | A dashboard |
| **Who reads it** | SMB owner (non-analyst, time-poor) | A data analyst |
| **Asks the user to** | Execute 5–7 tasks today | Explore data and form their own conclusions |
| **Sales cycle assumed** | 2 weeks – 2 months, high-ticket (20k+ RON) | Generic / e-commerce assumptions |
| **Funnel** | Lead → Vizita → Oferta → Contract (visit is mandatory) | Generic Lead → Deal |
| **Language** | Romanian first, action-oriented | English, neutral |

This framing means **many "table stakes" of BI tools (custom report builders, ad-hoc
SQL, pivot tables) are actually anti-features for this product.** The user does not
want to build reports; they want answers.

---

## Table Stakes

Features users expect in MVP1. Missing any of these = product feels incomplete and
the pilot fails.

| # | Feature | Why Expected | Complexity | Notes |
|---|---|---|---|---|
| TS-1 | **Sales funnel visualization (Lead → Vizita → Oferta → Contract)** with stage-by-stage conversion rates | This IS the product's core view; client already tracks this in Excel | Medium | Use Tremor `FunnelChart` or custom SVG. Show count + % at each step |
| TS-2 | **Lead source breakdown** (Mail/FB/IG, Telefon, WhatsApp, Site, Designer, Alte) | Client's existing Excel structure — they will literally check our numbers against theirs on day 1 | Low | Pie/bar chart + table. Categories MUST match `docs/SOFABELLE.md` exactly |
| TS-3 | **Revenue tracking (Încasări) with Cec mediu (avg deal size)** | Most important business metric — owner checks it daily | Low | Big number card + sparkline. Group by day/week/month |
| TS-4 | **Per-salesperson KPI leaderboard** (6 reps): leads handled, visits, offers, contracts, revenue, win-rate | "Не знаю кто из продавцов лучше работает" is pain point #2 in SOFABELLE.md | Medium | Sortable table. Per-person drilldown page |
| TS-5 | **Date range picker with period comparisons** (vs prev period, vs YoY) | Excel sheet has `YoY` column; client thinks in this comparison | Low | Use shadcn `DateRangePicker` + toggle. Default: last 30 days vs prev 30 |
| TS-6 | **WoW / MoM / YoY delta indicators** on every KPI card | Trend direction matters more than raw number for SMB owner | Low | Up/down arrow + % delta + color (green/red/grey) |
| TS-7 | **Daily AI insights page with top-3 problems + 5–7 action items** in Romanian | This IS the product's value proposition (PROJECT.md line 14–15) | High | Structured Claude JSON output → rendered as cards with checkboxes |
| TS-8 | **Insight archive (browse previous days)** | Owner wants to verify "did I do what AI told me last week?" | Low | List view + per-date page. Already in spec (`/insights/[date]`) |
| TS-9 | **Authentication (login + protected routes)** | Any SaaS expectation, plus GDPR (client data) | Low | JWT, MVP1 single-tenant Sofa Belle seed. No SSO needed yet |
| TS-10 | **Last-sync indicator + manual "Sync now" button** on integrations page | When numbers look wrong, first question is "is data fresh?" | Low | Show timestamp + status (✅/⚠️/❌) + last error message |
| TS-11 | **Stale-data warning** if MEFI sync is >24h old | Avoid silently showing stale dashboards | Low | Banner at top of dashboard pages |
| TS-12 | **Loading + empty + error states** for every chart and table | SMB users panic at blank screens | Low | shadcn `Skeleton` + empty illustrations + retry buttons |
| TS-13 | **Romanian-first UI** with English fallback | Owner and salespeople are Romanian speakers; the product is sold in RO | Medium | `next-intl`, all strings externalized. Translation pass before pilot |
| TS-14 | **Time-to-first-touch metric** (< 4h target highlighted) | SOFABELLE.md flags this as "главная операционная метрика" | Medium | Calc from MEFI lead history + call events. Color-code by threshold |
| TS-15 | **Stuck-offers widget** (offers `sent` with no activity > 14d) | Listed in spec § 12.4 and detected_problems rule | Low | Sidebar widget + drilldown list |
| TS-16 | **Funnel-stage active counts** ("how many deals are at each stage right now") | Pipeline visibility is universal CRM analytics expectation | Low | Static counts derived from current MEFI statuses |
| TS-17 | **Responsive layout (desktop + tablet)** | Owner reviews from laptop, may also use iPad in showroom | Medium | TailwindCSS responsive utilities; no mobile-app needed (yet) |

**Complexity totals:** ~3 High, ~5 Medium, ~9 Low. The bulk is achievable in the
3–4 week MVP1 window if foundation work goes smoothly.

---

## Differentiators

Features that set this product apart from MEFI's built-in BI, Looker Studio,
HubSpot, and Pipedrive. **Build these in MVP1 — they are the reason a client pays
for this instead of using existing tools.**

| # | Feature | Value Proposition | Complexity | Notes |
|---|---|---|---|---|
| D-1 | **Romanian-language AI insights, every morning, with RON-quantified impact per problem** | Nobody else does this for SMB Romanian market in their language. MEFI BI shows numbers, not interpretation | High | The flagship feature. Quality of Claude prompt = quality of product |
| D-2 | **"Action plan" framing — owner gets a to-do list, not a dashboard** | Differentiates from Looker/Power BI ("here's data, you figure it out") | Medium | UX angle: checkboxes, "mark complete", per-action owner + deadline |
| D-3 | **Sofa Belle's Excel structure mirrored 1:1 in the Marketing dashboard** | Zero learning curve — owner recognizes their own metrics | Medium | Specifically: Buget META/Google/TikTok, Cec mediu/zi, Conversie vizita |
| D-4 | **Domain-aware insights ("long sales cycle, visit-driven, premium ticket")** in Claude prompt | Generic AI gives generic advice. Context in prompt = relevant advice | Medium | System prompt explicitly includes industry specifics (SPEC.md § 10) |
| D-5 | **Anomaly detection runs deterministically before LLM** — Claude gets pre-computed problems, not raw data | Avoids LLM hallucination on numbers; makes outputs reproducible & cheap | High | Already in spec § 9. ~12 rules to start. Critical for quality |
| D-6 | **"Estimated loss in RON" per problem** ("you're losing ~30,000 RON/month because of slow response") | SMB owners think in money, not percentages | Medium | Calculation logic per anomaly rule (avg deal × est lost deals). Spec § 9 rules already include `estimated_impact_revenue` |
| D-7 | **Bottleneck detection at funnel stage (L→V, V→O, O→C)** with which stage is breaking | Standard funnel viz shows numbers; we show "this is the broken stage" | Medium | Compare each stage's conversion to baseline; flag biggest drop |
| D-8 | **Per-salesperson under/over-performance flagging in insights** | Owner pain #2 ("don't know who works best"). HubSpot shows leaderboard but not narrative | Medium | Anomaly rule + insight section. Sensitive — frame as "data shows X, consider Y" |
| D-9 | **Daily "What's going well" section** alongside problems | Most BI tools only surface negatives; balance avoids alarm fatigue | Low | Already in spec output schema as `positives[]` |
| D-10 | **Refresh-insights button with rate-limit** (re-run Claude on demand) | Owner wants to verify "is this still true after we acted?" | Low | Celery task + 1/hour cooldown |
| D-11 | **No setup beyond MEFI API key** | HubSpot/Salesforce require weeks of configuration; Looker requires a data analyst | Medium (operationally) | Pre-built schemas, hard-coded funnel for furniture vertical in MVP1 |

**Strategic note:** Differentiators D-1 through D-6 are the moat. If any of these
ship at low quality, the product feels like "yet another dashboard with a chatbot
bolted on." Invest disproportionate time in D-1 (prompt engineering) and D-5
(anomaly rules calibration).

---

## Differentiators — Future (post-MVP1, do NOT build now)

Documented here to keep the team aligned that these are intentional Phase-2+ work.

| Feature | Iteration | Why deferred |
|---|---|---|
| Ad-platform ROAS/CAC by channel (Meta/Google/TikTok) | Iter 2 | Requires Ads API access not yet provisioned |
| GA4 + GSC integration (web behavior, SEO queries) | Iter 3 | Same — dependencies on external API access |
| Call sentiment dashboard (from MonitorAI in MEFI) | When client adopts DOTRO | Data source doesn't exist yet |
| Showroom-level analytics (Brașov/București/Cluj split) | When IP-telephony deployed | No 3-number split in current data |
| Cross-tenant benchmarks ("you vs other furniture stores") | After 5+ clients | Need data volume + consent |
| Forecasting (revenue forecast, deal-close probability) | Backlog | Needs 12+ months of clean data to be useful |
| Email/Slack/Telegram digest of daily insights | Backlog | Pull (UI) before push (notifications) |
| Mobile app / PWA | Backlog | Owner uses laptop; not validated as need |

---

## Anti-Features

Features the team will be tempted to build but must NOT add in MVP1. Each comes
with a warning so future contributors don't reintroduce them.

| # | Anti-Feature | Why Avoid (warning) | What to Do Instead |
|---|---|---|---|
| AF-1 | **Custom report builder / ad-hoc SQL / drag-drop fields** | Looker, Tableau, and Metabase already do this 10× better. Building it = months of work + we still lose. Also: target user is an SMB owner, not an analyst | Ship a fixed, opinionated set of dashboards that mirror the client's Excel. If owner wants a custom view, add it for them as a hard-coded panel |
| AF-2 | **Free-form chat with AI** ("ask anything about your data") | LLM hallucination on aggregated metrics is high-risk. Owner will lose trust on first wrong number. Also: chat is a UX dead-end for daily-cadence product | Ship structured daily insights only. If owner asks "what about X?", that becomes a new anomaly rule (deterministic), not a chat turn |
| AF-3 | **Real-time / live dashboards** (websockets, auto-refresh every 5 sec) | Nightly batch is fine for this use case. Real-time adds infra cost, complexity, and zero value for a long-cycle product (2 weeks – 2 months per deal) | Nightly ETL at 03:00, fresh-data badge at top. Manual refresh button on insights only |
| AF-4 | **Building our own call transcription / sentiment / NLP** | DOTRO MonitorAI + 3CX AI already do this; results land in MEFI. Doing our own = GPU server, Whisper/pyannote pipeline, months of model tuning. Explicitly listed as out-of-scope in `CLAUDE.md` | Read MEFI's `transcript_summary`, `sentiment_score`, `topics` as-is. Add value by aggregating + correlating with funnel metrics |
| AF-5 | **Lead-scoring ML model** | Sample size too small (Sofa Belle: ~150 leads/month) for a meaningful model. ML lead-scoring is a 6-month research project that adds noise, not signal, at this scale | Use deterministic anomaly rules + Claude's qualitative interpretation. Revisit only after 10+ clients with 1+ year of data |
| AF-6 | **Duplicating MEFI BI dashboards** (raw lists of leads, deals, calls) | Explicitly out-of-scope in SPEC.md § 1. The client already has MEFI BI for raw data. Building this gets us a "me-too" tool with no differentiation | If owner wants raw drilldown, deep-link to MEFI BI. Our job is aggregation + interpretation, not raw data viewing |
| AF-7 | **Editing CRM data from our UI** (creating leads, updating deals, sending offers) | Becomes "a worse MEFI." Massive scope creep. Two-way sync conflicts. Audit trail nightmares. Tenant onboarding becomes 10× harder | Read-only analytics. If user wants to act, link them to MEFI |
| AF-8 | **Multi-currency / multi-language insights** in MVP1 | Sofa Belle = RON only, Romanian only. Adding currency conversion + en/ro/ru insights = 2× LLM cost + translation QA burden | RON-only, Romanian-only insights in MVP1. UI strings have en fallback (different concern) |
| AF-9 | **Generic anomaly thresholds** (e.g., "alert if conversion drops 10%") not tuned to industry | Furniture sales cycle is 2 weeks – 2 months. A 7-day dip is noise, not signal. Generic thresholds = alarm fatigue → owner ignores insights | Use baselines computed over 30–90 day windows. Calibrate rule severity with Sofa Belle owner in week 2 of pilot |
| AF-10 | **In-app salesperson-facing dashboard** ("Maria, here's your performance today") | Scope explosion: now we need 6 logins, role-based access, sensitive data filters, comp plan integration… | Owner-only access in MVP1. Salespeople see their data via owner reports (printed/emailed). Per-salesperson UI is Iteration 4+ |
| AF-11 | **PDF export / "share via email" of daily insight** (mentioned in SPEC § 12.7) | Listed as a button in spec but actually high-complexity (PDF rendering, email infra, attachment limits, GDPR on email). Owner can screenshot or use browser-print | Defer to Iteration 2. If urgent, use browser-native print (CSS `@media print`) |
| AF-12 | **Configurable funnel stages per tenant** (admin UI to define stages) | Adds tenant-config layer, schema flexibility, UI complexity. In MVP1 we have ONE tenant with a known funnel | Hard-code Sofa Belle funnel (Lead/Vizita/Oferta/Contract). Add config table only when client #2 onboards with different funnel |
| AF-13 | **Anomaly-rule UI / no-code rule builder** | Owner won't use it; we will. Building a rules engine UI = full week of dev for zero MVP value | Define rules in Python (`app/services/anomaly_detection/rules.py`). Edit via PR. Revisit if 10+ clients each want different rules |
| AF-14 | **"Refresh insights" with no rate limit** | Each Claude call costs ~$0.05 and takes 10–30 sec. Owner clicks button 50× in panic = $2.50 + bad UX. Also: insights based on same data won't change | Rate-limit to 1/hour per tenant (already in spec § 10). Show "Last regenerated: 14:22" timestamp |
| AF-15 | **Showroom dimension before IP-telephony is deployed** | The data attribution doesn't exist yet. Faking it (e.g., "assign by salesperson's home showroom") gives wrong numbers that erode trust | Wait until 3 inbound numbers exist. Documented as "Out of Scope" in PROJECT.md |
| AF-16 | **Multi-tenant enforcement** (filtering, isolation tests, tenant claims) in MVP1-3 | PROJECT.md explicitly defers this to Iteration 4. Pre-mature isolation work = ~30% extra dev time + zero pilot value | Schema has `tenant_id` columns (cheap, avoids future migration). Code does NOT filter in MVP1-3. Hard-code Sofa Belle tenant ID |

---

## Feature Dependencies

```
TS-1 Funnel viz  ────► requires TS-10 (data freshness signal) for trust
TS-7 AI Insights ────► requires D-5 (anomaly detection) ────► requires Metrics layer
                  └─► requires Romanian prompt + Claude integration
TS-4 Salesperson lb ─► requires per-salesperson KPI calc layer
TS-14 Time-to-first-touch ─► requires MEFI lead_history + calls data (both via MEFI)
D-6 Estimated RON impact ─► requires Cec mediu (avg deal) → drives most rule impact calcs
D-7 Bottleneck detection ─► requires 30-day baseline conversion rates (cold-start: first 30 days have weaker insights)
```

**Critical path for MVP1:**
1. MEFI ETL working (leads, history, derived visits/offers/deals)
2. Daily metrics calc (KPI tables populated)
3. Anomaly rules engine + 12 starter rules
4. Claude integration + prompt + JSON parser
5. Insights UI page
6. Dashboard pages (Sales, Salespeople, Marketing)

Anything in steps 4–5 is blocked by steps 1–3. Backend before frontend, but
mockable.

---

## MVP1 Recommendation — Build / Defer

**Build (in priority order):**

1. **TS-1, TS-2, TS-16** — Sales funnel + lead sources + active-stage counts
   (the "I recognize my Excel" moment for the client)
2. **TS-5, TS-6** — Date picker + delta indicators (YoY toggle is non-negotiable
   because Excel has it)
3. **TS-4** — Per-salesperson leaderboard (pain point #2)
4. **TS-14, TS-15** — Time-to-first-touch + stuck offers (operational pain points)
5. **D-5** — Anomaly rules engine (foundation for all insights)
6. **D-1, D-4, D-6** — AI insights with Romanian, domain-aware prompt, RON impact
7. **D-7, D-8** — Bottleneck + per-salesperson insights (the "wow" moments)
8. **D-2** — Action plan UX with checkboxes (the differentiating frame)
9. **TS-8, D-10** — Insight archive + refresh button
10. **TS-13** — Romanian translation pass
11. **TS-9, TS-10, TS-11, TS-12** — Auth, data freshness, error states (last because
    they're blockers for demo, not blockers for development)

**Explicitly defer to Iter 2+:**

- AF-11 (PDF export) → use browser print
- AF-10 (per-salesperson login) → owner-only
- AF-12 (configurable funnel) → hard-coded
- Showroom analytics → wait for telephony
- All ad-platform features → Iteration 2

**Explicitly never build (without strategic shift):**

- AF-1 (custom report builder)
- AF-2 (free-form AI chat)
- AF-4 (own call transcription)
- AF-7 (CRM editing from our UI)

---

## What "Good" AI Insights Look Like for Sales Teams

**Confidence: LOW–MEDIUM** (training-knowledge synthesis; should be validated with
Sofa Belle owner during pilot weeks 1–2)

### Format patterns that work for SMB owners

| Pattern | Why it works | Implementation note |
|---|---|---|
| **Top-3 problems only, not top-10** | Cognitive load; owner needs to act, not read | Already in spec § 10 system prompt |
| **Money amounts (RON), not percentages** | "Losing 30,000 RON" hits harder than "down 12%" | Anomaly rule must compute `estimated_loss_ron` |
| **Specific person/team named** ("Maria reacted in 8h avg, target is <4h") | Generic advice ignored; specific advice acted on | Requires per-salesperson rule layer |
| **Concrete deadline on each action** ("by Friday") | "Soon" doesn't get done; "by Friday" does | LLM output schema has `deadline` field |
| **One sentence summary per problem before details** | Owner scans first, drills second | Use `<h3>` + 1-line `<p>` then collapsible details |
| **"What's going well" section** | Pure-negative reports cause defensive reactions | Already in spec output schema |
| **Reference to prior recommendation** ("last week we said X, status: done/not done") | Closes the loop; builds trust that AI remembers | **Add later (Iter 2):** requires action-completion tracking |

### Format patterns that get ignored

- **Long preambles** ("Based on analysis of your data over the past 30 days, we observed...") → owner skips
- **Percentage-only language** ("conversion down 12%") → no felt urgency
- **Generic recommendations** ("optimize your sales funnel") → not actionable
- **Lists of 10+ items** → none get done
- **No owner / no deadline** → diffuses responsibility
- **Hedging language** ("you might consider potentially exploring") → erodes confidence

### Anti-patterns specific to AI insights

- **Hallucinated numbers** — disaster. Mitigated by D-5 (pre-compute, pass to LLM as
  structured input; never let LLM derive numbers from raw data)
- **Same insight repeated daily** — owner stops reading by day 3. Mitigation: track
  insight identity (rule_id + entity); de-prioritize if seen N times without metric change
- **Insights about data the owner can't influence** ("traffic from Romania is up
  during work hours") — feels like noise. Mitigation: every insight must map to a
  controllable lever (a person, a budget, a process)

---

## Quick Competitor Reference Table

**Confidence: MEDIUM** (general category knowledge; specific feature claims may be
stale by 6–18 months).

| Tool | Strength | Why we're different (for this audience) |
|---|---|---|
| **MEFI BI** (built-in) | Raw CRM data, free for users | We add cross-source view + AI interpretation; we're not in their CRM-vendor business |
| **HubSpot Sales Hub Analytics** | Polished, broad CRM | Requires HubSpot as your CRM ($$); generic; English/multi-lang but not Romanian-native; pricing way above Romanian SMB band |
| **Pipedrive Insights / Reports** | Pipeline-centric, affordable | Requires Pipedrive CRM; reports are user-built, not AI-narrated; English-first |
| **Salesforce Einstein Analytics** | Powerful, enterprise | Massive overkill + enterprise pricing for Romanian SMB; long implementation; English-first |
| **Gong.io / Chorus.ai** | Call intelligence + revenue intelligence | Call-focused; expensive ($$$$); enterprise-tier; we focus on full funnel and lean on MEFI for call data |
| **Looker Studio / Power BI / Tableau** | Flexible BI, free–cheap | Self-serve dashboards, requires analyst to build; no AI narrative; no CRM-aware semantics |
| **Metabase / Cube / Lightdash** | Open-source BI | Same problem — they're tools for analysts, not products for owners |

**Positioning summary:** We're not competing on "more charts" or "more data
sources." We compete on "answers in your language, every morning, scoped to your
industry." For Romanian SMB on MEFI, no current tool occupies that slot.

---

## Open Questions for Pilot Validation

Confidence on the following is LOW; validate with Sofa Belle owner in pilot weeks 1–2:

1. **Insight cadence**: Daily is the spec. Is weekly digest enough for some owners?
   (Lower LLM cost; might lose "daily habit" engagement.)
2. **Action-completion tracking** (checkboxes that persist): nice-to-have or critical?
3. **Alert when severity = "high"**: email/SMS push? Or daily-only is fine?
4. **Comparison to last year (YoY)** vs comparison to plan/target: which framing
   does owner trust more?
5. **Per-salesperson insights**: how sensitive is the owner about us naming reps
   directly in AI output? (Cultural / managerial nuance.)
6. **Loss-reason analysis**: spec § 12.4 mentions a pie chart of `loss_reason`. Is
   this data clean in MEFI today? If not, drop in MVP1 and add in MVP2.

---

## Sources

- `/Users/sergheigranici/Desktop/sofabelle/sales-marketing-ai-analyst/SPEC.md`
  (HIGH confidence — project ground truth)
- `/Users/sergheigranici/Desktop/sofabelle/sales-marketing-ai-analyst/docs/SOFABELLE.md`
  (HIGH confidence — pilot client context, Excel structure, pain points)
- `/Users/sergheigranici/Desktop/sofabelle/sales-marketing-ai-analyst/.planning/PROJECT.md`
  (HIGH confidence — milestone scope and key decisions)
- `/Users/sergheigranici/Desktop/sofabelle/sales-marketing-ai-analyst/CLAUDE.md`
  (HIGH confidence — engineering constraints affecting feature feasibility)
- Training-data knowledge of HubSpot, Pipedrive, Salesforce, Gong.io, Looker
  Studio, Tableau (MEDIUM confidence — feature sets evolve; verify before public
  positioning claims)
- Training-data synthesis on AI-insight UX patterns (LOW–MEDIUM confidence;
  validate with pilot)

**Web search and web fetch tools were unavailable in this environment** — recommend
a follow-up research pass (with web access) before any external pricing / marketing
claim is made about competitors.
