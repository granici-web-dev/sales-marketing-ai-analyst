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

from __future__ import annotations

from typing import Any, cast

from anthropic.types import ToolParam

from app.services.chat.tools.base import Tool

# ── Task 2 tools (4 of 12) — thin text() queries + delta math ─────────────────
from app.services.chat.tools.compare_periods import TOOL as _COMPARE_PERIODS

# ── Task 3 tools (4 of 12) — insight read + static glossary + stuck + trend ──
from app.services.chat.tools.explain_metric import TOOL as _EXPLAIN_METRIC

# ── Task 1 tools (4 of 12) — wrap existing Phase 3/6 services ─────────────────
from app.services.chat.tools.get_funnel_data import TOOL as _GET_FUNNEL_DATA
from app.services.chat.tools.get_kpi import TOOL as _GET_KPI
from app.services.chat.tools.get_lead_categories_breakdown import (
    TOOL as _GET_LEAD_CATEGORIES_BREAKDOWN,
)
from app.services.chat.tools.get_leads import TOOL as _GET_LEADS
from app.services.chat.tools.get_loss_reasons import TOOL as _GET_LOSS_REASONS
from app.services.chat.tools.get_recent_insight import TOOL as _GET_RECENT_INSIGHT
from app.services.chat.tools.get_salesperson_performance import (
    TOOL as _GET_SALESPERSON_PERFORMANCE,
)
from app.services.chat.tools.get_showroom_performance import (
    TOOL as _GET_SHOWROOM_PERFORMANCE,
)
from app.services.chat.tools.get_stuck_leads import TOOL as _GET_STUCK_LEADS
from app.services.chat.tools.get_trend import TOOL as _GET_TREND

# Canonical name → Tool mapping (D-04). Final 12-tool registry per D-01 + D-02.
# `Tool[Any]`: the registry is keyed by name and holds tools of differing
# input models; each entry stays precise at its own definition site.
TOOLS_REGISTRY: dict[str, Tool[Any]] = {
    # Task 1
    _GET_KPI.name: _GET_KPI,
    _GET_FUNNEL_DATA.name: _GET_FUNNEL_DATA,
    _GET_SALESPERSON_PERFORMANCE.name: _GET_SALESPERSON_PERFORMANCE,
    _GET_LEAD_CATEGORIES_BREAKDOWN.name: _GET_LEAD_CATEGORIES_BREAKDOWN,
    # Task 2
    _GET_LEADS.name: _GET_LEADS,
    _COMPARE_PERIODS.name: _COMPARE_PERIODS,
    _GET_LOSS_REASONS.name: _GET_LOSS_REASONS,
    _GET_SHOWROOM_PERFORMANCE.name: _GET_SHOWROOM_PERFORMANCE,
    # Task 3
    _GET_RECENT_INSIGHT.name: _GET_RECENT_INSIGHT,
    _EXPLAIN_METRIC.name: _EXPLAIN_METRIC,
    _GET_STUCK_LEADS.name: _GET_STUCK_LEADS,
    _GET_TREND.name: _GET_TREND,
}


def get_all_tools() -> list[ToolParam]:
    """Return the list of Anthropic-formatted tool definitions.

    Each definition has keys ``{name, description, input_schema}`` where
    ``input_schema`` is a JSON Schema dict (Pydantic v2
    ``model_json_schema()`` output) — not a BaseModel class. The orchestrator
    passes this list directly to ``messages.stream(tools=...)``.
    """
    return [cast("ToolParam", tool.definition) for tool in TOOLS_REGISTRY.values()]


__all__ = ["Tool", "TOOLS_REGISTRY", "get_all_tools"]
