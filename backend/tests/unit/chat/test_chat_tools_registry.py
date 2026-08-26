"""Unit tests for the AI Chat tools registry (Phase 8 Plan 03 — D-01..D-04).

Verifies the contract of ``app.services.chat.tools``:
  - TOOLS_REGISTRY maps tool name → Tool dataclass (D-04)
  - get_all_tools() returns a list of Anthropic-formatted definition dicts
  - Each handler has the LM-3 signature contract: ``(tenant_id, session, inp)``
  - Each tool.definition has the canonical {name, description, input_schema} shape
  - Final canonical name set matches the D-02 12-tool list

Tests in this file are SHAPE tests (no DB, no Anthropic). Per-handler behavior
lives in ``test_chat_tool_handlers.py``.

LM-3 mitigation: the signature-introspection test below proves every handler
keeps the ``(tenant_id, session, inp)`` contract — preventing accidental
loss of tenant scoping when handlers are refactored.
"""

from __future__ import annotations

import inspect
from datetime import date
from uuid import UUID

import pytest

# ── Canonical D-02 tool set ────────────────────────────────────────────────────

EXPECTED_TOOL_NAMES: set[str] = {
    "get_kpi",
    "get_funnel_data",
    "get_salesperson_performance",
    "get_leads",
    "compare_periods",
    "get_loss_reasons",
    "get_lead_categories_breakdown",
    "get_showroom_performance",
    "get_recent_insight",
    "explain_metric",
    "get_stuck_leads",
    "get_trend",
}


# ── Shape tests ────────────────────────────────────────────────────────────────


class TestRegistryShape:
    """Cross-cutting contract tests for the entire TOOLS_REGISTRY."""

    def test_registry_imports(self) -> None:
        """Test 1: import surface — TOOLS_REGISTRY + get_all_tools are exported."""
        from app.services.chat.tools import TOOLS_REGISTRY, get_all_tools

        assert isinstance(TOOLS_REGISTRY, dict)
        assert callable(get_all_tools)

    def test_registry_has_canonical_twelve_tools(self) -> None:
        """Test 2: registry contains EXACTLY the 12 canonical D-02 tools.

        Task 3 of plan 08-03 strengthens this from the prior ``>= 4`` partial
        check now that every tool is registered (D-01 closed).
        """
        from app.services.chat.tools import TOOLS_REGISTRY

        assert len(TOOLS_REGISTRY) == 12, (
            f"Expected exactly 12 tools per D-02; got {len(TOOLS_REGISTRY)}: "
            f"{sorted(TOOLS_REGISTRY)}"
        )
        assert set(TOOLS_REGISTRY.keys()) == EXPECTED_TOOL_NAMES, (
            "Tool-name mismatch with canonical D-02 set. "
            f"Missing: {EXPECTED_TOOL_NAMES - set(TOOLS_REGISTRY)}; "
            f"unexpected: {set(TOOLS_REGISTRY) - EXPECTED_TOOL_NAMES}"
        )

    def test_every_handler_lm3_signature(self) -> None:
        """Test 3 (LM-3): every handler's first 3 params are tenant_id, session, inp."""
        from app.services.chat.tools import TOOLS_REGISTRY

        for name, tool in TOOLS_REGISTRY.items():
            assert inspect.iscoroutinefunction(tool.handler), (
                f"Tool {name}: handler must be `async def` (CLAUDE.md #1 async-first)"
            )
            params = list(inspect.signature(tool.handler).parameters)
            assert params[:3] == ["tenant_id", "session", "inp"], (
                f"Tool {name}: LM-3 contract requires (tenant_id, session, inp); got {params[:3]}"
            )

    def test_every_definition_has_required_keys(self) -> None:
        """Test 4: each tool.definition has {name, description, input_schema}."""
        from app.services.chat.tools import TOOLS_REGISTRY

        for name, tool in TOOLS_REGISTRY.items():
            assert isinstance(tool.definition, dict), f"Tool {name}: definition not a dict"
            assert set(tool.definition.keys()) >= {"name", "description", "input_schema"}, (
                f"Tool {name}: definition missing required keys; got {tool.definition.keys()}"
            )
            assert tool.definition["name"] == name, (
                f"Tool {name}: definition.name mismatch ({tool.definition['name']!r})"
            )
            schema = tool.definition["input_schema"]
            assert isinstance(schema, dict), (
                f"Tool {name}: input_schema must be dict, not BaseModel"
            )
            assert schema.get("type") == "object", (
                f"Tool {name}: JSON schema root must be type=object"
            )
            assert "properties" in schema, f"Tool {name}: JSON schema missing properties"

    def test_get_all_tools_returns_anthropic_format(self) -> None:
        """Test 5: get_all_tools() returns list[dict] matching registry size."""
        from app.services.chat.tools import TOOLS_REGISTRY, get_all_tools

        defs = get_all_tools()
        assert isinstance(defs, list)
        assert len(defs) == len(TOOLS_REGISTRY)
        names_in_defs = {d["name"] for d in defs}
        assert names_in_defs == set(TOOLS_REGISTRY.keys())
        for d in defs:
            assert {"name", "description", "input_schema"} <= set(d.keys())

    def test_get_all_tools_can_be_validated_via_input_schema(self) -> None:
        """Test 7: registered tools round-trip via input_schema.model_validate.

        Picks any registered tool and validates that its ``input_schema`` is a
        usable Pydantic v2 BaseModel. ``explain_metric`` is the canonical
        DB-free tool we'd love to use here, but Task 1 only ships 4 wrapping
        tools; we exercise ``get_funnel_data`` instead and switch to
        ``explain_metric`` once Task 3 lands it.
        """
        from datetime import date as _date

        from app.services.chat.tools import TOOLS_REGISTRY

        # Prefer explain_metric when available (Task 3); fall back to a tool
        # that's guaranteed to be present in Task 1.
        if "explain_metric" in TOOLS_REGISTRY:
            inp = TOOLS_REGISTRY["explain_metric"].input_schema.model_validate(
                {"metric_name": "CAC"}
            )
            assert inp.metric_name == "CAC"
        else:
            inp = TOOLS_REGISTRY["get_funnel_data"].input_schema.model_validate(
                {"date_from": "2026-05-01", "date_to": "2026-05-19"}
            )
            assert inp.date_from == _date(2026, 5, 1)


# ── Per-handler smoke tests (mocked wrapped service) ──────────────────────────


TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
FROM_DATE = date(2026, 5, 1)
TO_DATE = date(2026, 5, 19)


class TestGetKpiHandler:
    """Test 6: get_kpi wraps DailyKpiService."""

    @pytest.mark.asyncio
    async def test_get_kpi_uses_daily_kpi_service(self, monkeypatch) -> None:
        from unittest.mock import AsyncMock, MagicMock

        from app.services.chat.tools.get_kpi import GetKpiInput, _handler

        # Patch DailyKpiService inside the tool module
        fake_svc = MagicMock()
        fake_svc.compute_for_date = AsyncMock(
            return_value={
                "leads_total": 17,
                "revenue": "85000.00",
                "contracts_count": 3,
            }
        )
        fake_ctor = MagicMock(return_value=fake_svc)
        monkeypatch.setattr("app.services.chat.tools.get_kpi.DailyKpiService", fake_ctor)

        session = AsyncMock()
        inp = GetKpiInput(
            date_from=FROM_DATE,
            date_to=FROM_DATE,
            metrics=["leads", "revenue"],
        )
        result = await _handler(TENANT_ID, session, inp)

        # Constructor called with (session, tenant_id) per RESEARCH §"Tenant Isolation"
        fake_ctor.assert_called_once_with(session, TENANT_ID)
        # Service called for the single date
        fake_svc.compute_for_date.assert_awaited()
        # Result is a JSON-serializable dict
        assert isinstance(result, dict)


class TestGetFunnelDataHandler:
    """Test 7: get_funnel_data wraps DashboardReadService.get_sales_dashboard."""

    @pytest.mark.asyncio
    async def test_get_funnel_data_uses_dashboard_read_service(self, monkeypatch) -> None:
        from unittest.mock import AsyncMock, MagicMock

        from app.services.chat.tools.get_funnel_data import (
            GetFunnelDataInput,
            _handler,
        )

        fake_svc = MagicMock()
        fake_svc.get_sales_dashboard = AsyncMock(
            return_value={
                "period": {"from": FROM_DATE, "to": TO_DATE},
                "funnel": {"leads": 100, "visits": 30, "offers": 40, "contracts": 10},
            }
        )
        fake_ctor = MagicMock(return_value=fake_svc)
        monkeypatch.setattr(
            "app.services.chat.tools.get_funnel_data.DashboardReadService", fake_ctor
        )

        session = AsyncMock()
        inp = GetFunnelDataInput(date_from=FROM_DATE, date_to=TO_DATE)
        result = await _handler(TENANT_ID, session, inp)

        fake_ctor.assert_called_once_with(session, TENANT_ID)
        fake_svc.get_sales_dashboard.assert_awaited_once_with(FROM_DATE, TO_DATE)
        assert isinstance(result, dict)
        assert result["funnel"]["leads"] == 100


class TestGetSalespersonPerformanceHandler:
    """Test 8: get_salesperson_performance wraps get_salespeople_dashboard."""

    @pytest.mark.asyncio
    async def test_get_salesperson_performance_no_filter(self, monkeypatch) -> None:
        from unittest.mock import AsyncMock, MagicMock

        from app.services.chat.tools.get_salesperson_performance import (
            GetSalespersonPerformanceInput,
            _handler,
        )

        salespeople = [
            {"external_id": 1, "name": "Raileanu Leon", "deals_won": 22},
            {"external_id": 2, "name": "Roibu Valeria", "deals_won": 16},
        ]
        fake_svc = MagicMock()
        fake_svc.get_salespeople_dashboard = AsyncMock(
            return_value={
                "period": {"from": FROM_DATE, "to": TO_DATE},
                "salespeople": salespeople,
            }
        )
        fake_ctor = MagicMock(return_value=fake_svc)
        monkeypatch.setattr(
            "app.services.chat.tools.get_salesperson_performance.DashboardReadService",
            fake_ctor,
        )

        session = AsyncMock()
        inp = GetSalespersonPerformanceInput(date_from=FROM_DATE, date_to=TO_DATE)
        result = await _handler(TENANT_ID, session, inp)

        fake_ctor.assert_called_once_with(session, TENANT_ID)
        fake_svc.get_salespeople_dashboard.assert_awaited_once_with(FROM_DATE, TO_DATE)
        assert isinstance(result, dict)
        assert len(result["salespeople"]) == 2

    @pytest.mark.asyncio
    async def test_get_salesperson_performance_filters_by_external_id(self, monkeypatch) -> None:
        """When salesperson_external_id provided, filter the response."""
        from unittest.mock import AsyncMock, MagicMock

        from app.services.chat.tools.get_salesperson_performance import (
            GetSalespersonPerformanceInput,
            _handler,
        )

        salespeople = [
            {"external_id": 1, "name": "Raileanu Leon", "deals_won": 22},
            {"external_id": 2, "name": "Roibu Valeria", "deals_won": 16},
        ]
        fake_svc = MagicMock()
        fake_svc.get_salespeople_dashboard = AsyncMock(
            return_value={
                "period": {"from": FROM_DATE, "to": TO_DATE},
                "salespeople": salespeople,
            }
        )
        fake_ctor = MagicMock(return_value=fake_svc)
        monkeypatch.setattr(
            "app.services.chat.tools.get_salesperson_performance.DashboardReadService",
            fake_ctor,
        )

        session = AsyncMock()
        inp = GetSalespersonPerformanceInput(
            date_from=FROM_DATE, date_to=TO_DATE, salesperson_external_id=1
        )
        result = await _handler(TENANT_ID, session, inp)

        # Post-filter to one rep
        assert len(result["salespeople"]) == 1
        assert result["salespeople"][0]["name"] == "Raileanu Leon"


class TestGetLeadCategoriesBreakdownHandler:
    """Test 9: get_lead_categories_breakdown wraps get_marketing_dashboard."""

    @pytest.mark.asyncio
    async def test_get_lead_categories_breakdown_uses_marketing_dashboard(
        self, monkeypatch
    ) -> None:
        from unittest.mock import AsyncMock, MagicMock

        from app.services.chat.tools.get_lead_categories_breakdown import (
            GetLeadCategoriesBreakdownInput,
            _handler,
        )

        fake_svc = MagicMock()
        fake_svc.get_marketing_dashboard = AsyncMock(
            return_value={
                "period": {"from": FROM_DATE, "to": TO_DATE},
                "lead_volume_by_source": [
                    {"source": "showroom", "total_leads": 360},
                    {"source": "mail", "total_leads": 335},
                ],
            }
        )
        fake_ctor = MagicMock(return_value=fake_svc)
        monkeypatch.setattr(
            "app.services.chat.tools.get_lead_categories_breakdown.DashboardReadService",
            fake_ctor,
        )

        session = AsyncMock()
        inp = GetLeadCategoriesBreakdownInput(date_from=FROM_DATE, date_to=TO_DATE)
        result = await _handler(TENANT_ID, session, inp)

        fake_ctor.assert_called_once_with(session, TENANT_ID)
        fake_svc.get_marketing_dashboard.assert_awaited_once_with(FROM_DATE, TO_DATE)
        assert isinstance(result, dict)
        assert result["lead_volume_by_source"][0]["source"] == "showroom"
