"""``explain_metric`` chat tool — static Romanian metric glossary (D-02 + D-03).

**NEW PATTERN** — pure Python dict lookup. No DB hit. The only tool in the
registry without a wrapped service. Glossary entries cover the 9 metrics
called out by SPEC.md §6 and docs/CHAT.md plus the Sofa Belle-specific
``Stuck Offer`` term.

D-03: NO new SQL — and no service call either. Pure dict.
LM-3: handler signature ``(tenant_id, session, inp)`` (session unused).
LM-10: required field ``metric_name`` uses ``Field(..., description=...)``.

Each glossary entry is a dict with:
  - ``name``: canonical short name (CAC, ROAS, ...)
  - ``definition_ro``: Romanian one-sentence definition
  - ``formula``: math/SQL-flavored formula
  - ``relevant_for_sofa_belle``: bool — false for ad-spend metrics until
    Iteration 2 lands Meta/Google/TikTok ingestion (Phase 8 D-26 MVP1 data
    limits block).
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.chat.tools.base import Tool

# 9 entries per CONTEXT specifics + SPEC.md §6 + docs/CHAT.md.
# Keys are upper-case canonical names; the handler lookup is
# case-insensitive (it normalizes the user input before lookup).
GLOSSARY: dict[str, dict] = {
    "CAC": {
        "name": "CAC",
        "definition_ro": (
            "Customer Acquisition Cost — costul total de marketing și "
            "vânzări pentru a câștiga un client nou."
        ),
        "formula": "(total cheltuieli reclame + alte costuri de achiziție) / contracte semnate",
        "relevant_for_sofa_belle": False,
        "note_ro": (
            "Nu este disponibil în MVP1 — datele de cheltuieli din "
            "Meta/Google/TikTok lipsesc până la Iterația 2."
        ),
    },
    "ROAS": {
        "name": "ROAS",
        "definition_ro": (
            "Return on Ad Spend — venitul generat per leu cheltuit pe reclame."
        ),
        "formula": "venitul atribuit reclamelor / cheltuieli reclame",
        "relevant_for_sofa_belle": False,
        "note_ro": "Necesită integrare cu Meta/Google/TikTok (Iterația 2).",
    },
    "CPL": {
        "name": "CPL",
        "definition_ro": (
            "Cost per Lead — cât costă, în medie, să obții un lead "
            "(înainte de calificare)."
        ),
        "formula": "cheltuieli reclame / lead-uri generate de campanii",
        "relevant_for_sofa_belle": False,
        "note_ro": "Necesită integrare cu Meta/Google/TikTok (Iterația 2).",
    },
    "CONVERSIE L→V": {
        "name": "Conversie L→V",
        "definition_ro": (
            "Rata de conversie de la lead la vizita în showroom. La Sofa "
            "Belle, „vizita” = sursa Showroom (source_id=5) — un walk-in "
            "fizic la unul dintre cele 3 showroom-uri."
        ),
        "formula": "vizite / total lead-uri",
        "relevant_for_sofa_belle": True,
    },
    "CONVERSIE L→C": {
        "name": "Conversie L→C",
        "definition_ro": (
            "Rata de conversie de la lead la contract — măsură de top-line "
            "a eficienței funnel-ului. Baseline Sofa Belle: 5.8%."
        ),
        "formula": "contracte semnate / total lead-uri",
        "relevant_for_sofa_belle": True,
    },
    "AOV": {
        "name": "AOV / Cec mediu",
        "definition_ro": (
            "Average Order Value (Cec mediu) — valoarea medie a unui "
            "contract semnat. La Sofa Belle, peste 20.000 RON."
        ),
        "formula": "venit total / contracte semnate",
        "relevant_for_sofa_belle": True,
    },
    "TTFT": {
        "name": "TTFT",
        "definition_ro": (
            "Time To First Touch — minute scurse de la crearea lead-ului "
            "până la primul contact cu vânzătorul, măsurate în orele de "
            "lucru (Lu–Du 09:00–19:00, ora Bucureștiului). Țintă: < 4 ore "
            "(< 240 minute)."
        ),
        "formula": "primul status_change al lead-ului - created_at_source (în minute business)",
        "relevant_for_sofa_belle": True,
    },
    "DATA COMPLETENESS": {
        "name": "Data Completeness",
        "definition_ro": (
            "Procentul de lead-uri pentru care vânzătorul a completat "
            "câmpul estimated_value. La Sofa Belle, în MVP1, această "
            "valoare este ~0% (toți estimated_value sunt NULL)."
        ),
        "formula": "lead-uri cu estimated_value IS NOT NULL / total lead-uri",
        "relevant_for_sofa_belle": True,
    },
    "STUCK OFFER": {
        "name": "Stuck Offer",
        "definition_ro": (
            "O ofertă care nu a avut nicio activitate (schimbare de "
            "status sau contact) timp de mai mult de 14 zile. Pragul "
            "implicit de 14 zile vine din regula ANOM-03."
        ),
        "formula": "today - max(mefi_lead_history.changed_at) > 14 days",
        "relevant_for_sofa_belle": True,
    },
}


_ALIASES: dict[str, str] = {
    # Friendly aliases → canonical key for lookup.
    "CONVERSIE LEAD VIZITA": "CONVERSIE L→V",
    "CONVERSIE LEAD CONTRACT": "CONVERSIE L→C",
    "CEC MEDIU": "AOV",
    "AVERAGE ORDER VALUE": "AOV",
    "STUCK": "STUCK OFFER",
    "TIME TO FIRST TOUCH": "TTFT",
    "DATA-COMPLETENESS": "DATA COMPLETENESS",
}


def _normalize(name: str) -> str:
    """Case-fold + strip + collapse internal whitespace for lookup."""
    return " ".join(name.upper().split())


class ExplainMetricInput(BaseModel):
    """Input schema for ``explain_metric``."""

    metric_name: str = Field(
        ...,
        description=(
            "Metric name to explain. Examples: CAC, ROAS, CPL, Conversie "
            "L→V, Conversie L→C, AOV (Cec mediu), TTFT, Data Completeness, "
            "Stuck Offer."
        ),
    )


async def _handler(
    tenant_id: UUID,
    session: AsyncSession,
    inp: ExplainMetricInput,
) -> dict:
    # Pure dict lookup — session intentionally unused (per D-03 NEW pattern).
    key = _normalize(inp.metric_name)
    if key in _ALIASES:
        key = _ALIASES[key]
    if key in GLOSSARY:
        return dict(GLOSSARY[key])  # shallow copy so callers can't mutate
    return {
        "name": inp.metric_name,
        "definition_ro": (
            "Această metrică nu este definită încă în glosar. Verifică "
            "lista de metrici suportate: CAC, ROAS, CPL, Conversie L→V, "
            "Conversie L→C, AOV (Cec mediu), TTFT, Data Completeness, "
            "Stuck Offer."
        ),
        "formula": None,
        "relevant_for_sofa_belle": None,
    }


TOOL = Tool(
    name="explain_metric",
    definition={
        "name": "explain_metric",
        "description": (
            "Returns the Romanian definition + formula for a marketing or "
            "sales metric (CAC, ROAS, CPL, Conversie L→V, Conversie L→C, "
            "AOV, TTFT, Data Completeness, Stuck Offer). Does NOT query the "
            "database — pure static glossary lookup. Use this when the user "
            "asks 'what does X mean?' or 'how is Y calculated?'."
        ),
        "input_schema": ExplainMetricInput.model_json_schema(),
    },
    input_schema=ExplainMetricInput,
    handler=_handler,
)
