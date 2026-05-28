from __future__ import annotations

"""System prompt and user message construction for Phase 5 AI Insights.

D-07: System prompt = list of text blocks; last block has cache_control={"type": "ephemeral"}
      to cache the entire stable system prompt across daily invocations.
D-08: System prompt lives as a Python string constant — no file I/O, no DB query per call.
D-09: System prompt includes real Sofa Belle salesperson roster (6 active people + roles).
D-11: System prompt instructs Claude: 2-3 actions per problem, no more.

AI-04: build_user_message() selects top 3 problems by estimated_loss_ron descending.
GDPR PII guard: context_json stripped to non-PII fields only before sending to Claude API.
"""

import json
from decimal import Decimal


# ── System prompt string constant ────────────────────────────────────────────
# All stable content goes here — changes here invalidate the cache (costs $3.75/MTok write).
# Daily-varying data (KPI snapshot, detected_problems) stays in the USER message.

SYSTEM_PROMPT_TEXT = """Ești un consultant de business senior pentru Sofa Belle, specializat în vânzări și marketing premium de mobilă în România. Misiunea ta zilnică: analizezi datele CRM și metricile de performanță, identifici cele mai importante probleme care costă bani sau oportunități, și generezi un raport concis cu 5-7 acțiuni concrete pe care echipa le poate implementa imediat.

Ton și stil:
- Profesional, direct, fără fluff
- Folosește termenii exacti din CRM-ul Sofa Belle (Lead, Vizita, Ofertă, Contract)
- Nu folosi termeni generici: "oportunitate", "pipeline stage", "prospect", "lead scoring"
- Diacritice corecte: ș/ț (virgulă dedesubt, nu cedilă), ă, â, î
- Toate sumele în RON, etichetate ca estimate când sursa este un calcul euristic

Companie: Sofa Belle — mobilă premium, 3 showroom-uri (Brașov, București, Cluj-Napoca), ciclu de vânzare 2 săptămâni–2 luni, valoare medie contract >20.000 RON.

IMPORTANT: estimated_value este NULL pentru toate lead-urile Sofa Belle — nu prezenta valori de vânzări ca precise. Folosește "estimat" sau evită valorile monetare absolute. Cifrele de pierdere estimată provin din anomaliile detectate automat (estimated_loss_ron) — prezintă-le întotdeauna ca estimate.

Funnel Sofa Belle: Lead → Vizita (= walk-in showroom, sursa source_id=5) → Ofertă → Contract.

Showroom este canalul principal de conversie (29.5% din lead-uri, 55% din contracte, 10.8% conversie L→C). Nu confunda sursa Showroom cu etapa funnel Vizita. Showroom walk-in = lead provenit din vizita fizică la showroom, nu o etapă separată în funnel.

Mail este volum ridicat, calitate slabă: 335 lead-uri, 3.3% conversie L→C. Când regula junk_lead_quality se activează, menționează că Mail este sursa principală de junk.

Echipa de vânzări (6 persoane):
- Roibu Valeria
- Raileanu Leon (best performer: 8.3% conversie L→C)
- Godja Adina Maria
- Dragoi Mihaela (atenție: 351 lead-uri, 2.8% conversie — cu mult sub media echipei de 5.8%)
- Zagrian Emilia
- Moaca Andreea

Pentru reguli individuale (underperforming_salesperson, slow_first_touch): atribuie acțiunile persoanei specifice numite în datele de intrare.
Pentru reguli sistemice (showroom_traffic_drop, junk_lead_quality): atribuie Manager sau Marketing Sofa.

Termene relative (nu date ISO): "Azi", "Mâine", "Săptămâna aceasta", "Luna aceasta". Folosește EXCLUSIV aceste valori în câmpul deadline.

Fiecare problemă are 2-3 acțiuni concrete, nu mai mult (D-11). expected_outcome trebuie să numească o metrică și o valoare țintă concretă (ex: "Rata de răspuns scade de la 3h la sub 2h").

Maximum 3 probleme de prioritate înaltă (max_length=3 în schema). Selectează problemele cu cel mai mare impact financiar estimat.

weekly_action_plan: 5-7 acțiuni prioritizate, concise, gata de copiat în WhatsApp sau standup. Sintetizează independent din toate problemele și pozitivele — nu copia mecanic din problems[].actions[].

Zi cu zero anomalii detectate: generează raport pozitiv bazat pe metrici bune. Nu inventa probleme care nu există în datele de intrare."""


def build_system_prompt() -> list[dict]:
    """Build the system prompt block list for Claude API with prompt caching.

    D-07: Returns 2-element list of text blocks.
    - Block 0: all stable system prompt content (SYSTEM_PROMPT_TEXT).
    - Block 1 (last): cache sentinel with cache_control={"type": "ephemeral"}.
      Placing cache_control on the LAST block caches all preceding stable content.
      This maximizes cache hits — only ~500 tokens change per invocation (user message).

    Returns:
        list[dict]: Two text blocks suitable for Claude messages.create(system=...).
    """
    return [
        {
            "type": "text",
            "text": SYSTEM_PROMPT_TEXT,
        },
        {
            "type": "text",
            "text": "Format de răspuns: JSON conform schemei specificate în tool.",
            "cache_control": {"type": "ephemeral"},
        },
    ]


def build_user_message(kpi_row: dict | None, problems_rows: list[dict]) -> str:
    """Build the user message JSON string for Claude API.

    D-02: Selects top 3 problems by estimated_loss_ron descending.
    D-06: User message = compact KPI snapshot + detected_problems rows.
    D-13: Zero-anomaly day → detected_problems=[] → valid JSON returned.
    GDPR PII guard: context_json stripped to non-PII fields only (AI-SPEC §6).
      Allowed: rule_id, severity, estimated_loss_ron, current_value, expected_value.
      Stripped: lead_ids, salesperson_ids, customer names, phone numbers, emails.

    Args:
        kpi_row: daily_kpi row dict or None (if no KPI data for date).
        problems_rows: list of detected_problems row dicts (may be empty for D-13).

    Returns:
        str: JSON string with keys "date", "kpi_snapshot", "detected_problems".
    """
    # D-02: top-3 by estimated_loss_ron descending
    def _sort_key(row: dict) -> Decimal:
        val = row.get("estimated_loss_ron", Decimal("0"))
        if val is None:
            return Decimal("0")
        return Decimal(str(val)) if not isinstance(val, Decimal) else val

    top3 = sorted(problems_rows, key=_sort_key, reverse=True)[:3]

    # GDPR PII guard: extract only non-PII fields from each problem row
    cleaned_problems = []
    for row in top3:
        # Serialize Decimal values to strings for JSON compatibility
        cleaned = {
            "rule_id": row.get("rule_id"),
            "severity": row.get("severity"),
            "estimated_loss_ron": str(row["estimated_loss_ron"]) if row.get("estimated_loss_ron") is not None else None,
            "current_value": str(row["current_value"]) if row.get("current_value") is not None else None,
            "expected_value": str(row["expected_value"]) if row.get("expected_value") is not None else None,
        }
        cleaned_problems.append(cleaned)

    # Build KPI snapshot — serialize Decimal values to strings
    kpi_snapshot: dict = {}
    if kpi_row is not None:
        kpi_fields = [
            "leads_total", "visits_count", "offers_count", "contracts_closed",
            "conversion_l_to_v", "conversion_v_to_o", "conversion_o_to_c", "conversion_l_to_c",
            "avg_deal_size", "wow_delta_pct", "mom_delta_pct",
        ]
        for field in kpi_fields:
            val = kpi_row.get(field)
            if val is not None:
                kpi_snapshot[field] = str(val) if isinstance(val, Decimal) else val

    # Build date string
    date_str = None
    if kpi_row is not None:
        d = kpi_row.get("date")
        if d is not None:
            date_str = d.isoformat() if hasattr(d, "isoformat") else str(d)

    payload = {
        "date": date_str,
        "kpi_snapshot": kpi_snapshot,
        "detected_problems": cleaned_problems,
    }

    return json.dumps(payload, ensure_ascii=False)
