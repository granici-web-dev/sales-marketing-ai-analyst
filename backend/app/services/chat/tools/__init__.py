from __future__ import annotations

"""Chat tool registry — single source of truth for Anthropic Tool Use.

Implements D-01..D-04:
  - D-01: ship all 12 tools backed by Phase 3/5/6 services
  - D-02: canonical 12-tool name set built up across plan 08-03 Tasks 1/2/3
          (4 + 4 + 4 = 12). This module is EXTENDED in subsequent tasks.
  - D-03: every handler thinly wraps an existing Phase 3/5/6 service —
          NO inline SQL except the 3 documented thin
          ``v_mefi_leads_active`` text() queries
          (``get_leads``, ``get_loss_reasons``, ``get_showroom_performance``)
          and the static ``explain_metric`` glossary.
  - D-04: ``TOOLS_REGISTRY: dict[str, Tool]`` and
          ``get_all_tools() -> list[dict]`` (Anthropic ToolParam format).

The orchestrator dispatches via::

    tool = TOOLS_REGISTRY[name]
    validated = tool.input_schema.model_validate(claude_input)
    result   = await tool.handler(tenant_id, session, validated)

LM-3: every handler keeps the ``(tenant_id, session, inp)`` signature
contract (see ``tests/unit/chat/test_chat_tools_registry.py``).
"""

from typing import Any

from app.services.chat.tools.base import Tool

# ── Task 1 tools (4 of 12) — wrap existing Phase 3/6 services ─────────────────
from app.services.chat.tools.get_funnel_data import TOOL as _GET_FUNNEL_DATA
from app.services.chat.tools.get_kpi import TOOL as _GET_KPI
from app.services.chat.tools.get_lead_categories_breakdown import (
    TOOL as _GET_LEAD_CATEGORIES_BREAKDOWN,
)
from app.services.chat.tools.get_salesperson_performance import (
    TOOL as _GET_SALESPERSON_PERFORMANCE,
)


# Canonical name → Tool mapping (D-04). The registry is EXTENDED in plan
# 08-03 Tasks 2 and 3 — never replaced; only add entries here.
TOOLS_REGISTRY: dict[str, Tool] = {
    # Task 1
    _GET_KPI.name: _GET_KPI,
    _GET_FUNNEL_DATA.name: _GET_FUNNEL_DATA,
    _GET_SALESPERSON_PERFORMANCE.name: _GET_SALESPERSON_PERFORMANCE,
    _GET_LEAD_CATEGORIES_BREAKDOWN.name: _GET_LEAD_CATEGORIES_BREAKDOWN,
}


def get_all_tools() -> list[dict[str, Any]]:
    """Return the list of Anthropic-formatted tool definitions.

    Each definition has keys ``{name, description, input_schema}`` where
    ``input_schema`` is a JSON Schema dict (Pydantic v2
    ``model_json_schema()`` output) — not a BaseModel class. The orchestrator
    passes this list directly to ``messages.stream(tools=...)``.
    """
    return [tool.definition for tool in TOOLS_REGISTRY.values()]


__all__ = ["Tool", "TOOLS_REGISTRY", "get_all_tools"]
