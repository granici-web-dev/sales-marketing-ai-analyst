from __future__ import annotations

"""Unit tests for `app.services.chat.hallucination_guard` (Plan 08-04 Task 2).

Coverage per <behavior> Tests HG1-HG10:
  - HG1: number within ±1% tool result → PASS
  - HG2: number outside ±1% → flagged "number:..."
  - HG3: derived percent allowed (a/b*100)
  - HG4: numbers <= 10 skipped (LM-11)
  - HG5: years 1900-2100 skipped
  - HG6: link not in whitelist → "link:..."
  - HG7: link in whitelist → PASS
  - HG8: capitalized entity not in whitelist → "entity:..."
  - HG9: salesperson in whitelist → PASS
  - HG10: empty tool_results allows only common-knowledge numbers
"""

import pytest


class TestHallucinationGuard:
    def test_hg1_number_within_one_percent_passes(self) -> None:
        from app.services.chat.hallucination_guard import check_response

        # tool_result revenue_delta = 23400; text says "23.400 RON" (Romanian thousands)
        unsupported = check_response(
            "Vânzările au crescut cu 23.400 RON",
            tool_results=[{"revenue_delta": "23400"}],
            entity_whitelist={},
        )
        assert unsupported == []

    def test_hg2_number_outside_tolerance_flagged(self) -> None:
        from app.services.chat.hallucination_guard import check_response

        unsupported = check_response(
            "Vânzările au crescut cu 99.999 RON",
            tool_results=[{"revenue_delta": "23400"}],
            entity_whitelist={},
        )
        # Some number flag must include "99999"
        assert any("number:" in u and "99999" in u for u in unsupported)

    def test_hg3_derived_percentage_allowed(self) -> None:
        from app.services.chat.hallucination_guard import check_response

        # tool says a=100, b=50; a/b*100 = 200(%) — should be a derived allowed value
        unsupported = check_response(
            "Conversia a crescut la 200%",
            tool_results=[{"a": 100, "b": 50}],
            entity_whitelist={},
        )
        assert all("number:" not in u for u in unsupported)

    def test_hg4_small_counts_skipped(self) -> None:
        from app.services.chat.hallucination_guard import check_response

        # Numbers like "3", "5", "9" must not flag (LM-11 list-marker guard)
        unsupported = check_response(
            "Trei probleme principale: 1. ceva, 2. altceva, 3. final",
            tool_results=[],
            entity_whitelist={},
        )
        assert all("number:" not in u for u in unsupported)

    def test_hg5_years_skipped(self) -> None:
        from app.services.chat.hallucination_guard import check_response

        unsupported = check_response(
            "În 2026 lucrurile au mers bine; și în 1999 erau diferite.",
            tool_results=[],
            entity_whitelist={},
        )
        # Both 2026 and 1999 are in [1900,2100] → skipped
        for n in ("number:2026", "number:1999"):
            assert n not in unsupported

    def test_hg6_external_link_flagged(self) -> None:
        from app.services.chat.hallucination_guard import check_response

        unsupported = check_response(
            "Vezi [Sales](https://evil.com) pentru detalii",
            tool_results=[],
            entity_whitelist={},
        )
        assert any(u.startswith("link:") and "evil.com" in u for u in unsupported)

    def test_hg7_dashboard_link_passes(self) -> None:
        from app.services.chat.hallucination_guard import check_response

        unsupported = check_response(
            "Vezi [Sales Dashboard](/sales) pentru detalii",
            tool_results=[],
            entity_whitelist={},
        )
        assert all(not u.startswith("link:") for u in unsupported)

    def test_hg8_unknown_entity_flagged(self) -> None:
        from app.services.chat.hallucination_guard import check_response

        wl = {
            "salespeople": {"Raileanu Leon", "Roibu Valeria"},
            "showrooms": {"Brașov", "București", "Cluj-Napoca"},
            "categories": set(),
        }
        unsupported = check_response(
            "Maria Popescu a închis cel mai mult",
            tool_results=[],
            entity_whitelist=wl,
        )
        assert any(u.startswith("entity:") and "Maria Popescu" in u for u in unsupported)

    def test_hg9_known_salesperson_passes(self) -> None:
        from app.services.chat.hallucination_guard import check_response

        wl = {
            "salespeople": {"Raileanu Leon", "Roibu Valeria"},
            "showrooms": {"Brașov"},
            "categories": set(),
        }
        unsupported = check_response(
            "Raileanu Leon a închis 22 contracte luna asta",
            tool_results=[{"contracts": 22}],
            entity_whitelist=wl,
        )
        assert all(not u.startswith("entity:") for u in unsupported)

    def test_hg10_empty_tool_results_blocks_business_numbers(self) -> None:
        from app.services.chat.hallucination_guard import check_response

        # No tool results — only common-knowledge numbers (days, years, round %) allowed.
        # 12500 is none of those → must flag.
        unsupported = check_response(
            "Vânzările totale: 12.500 RON",
            tool_results=[],
            entity_whitelist={},
        )
        assert any("number:" in u and "12500" in u for u in unsupported)

    def test_extract_numbers_reuses_phase5_pattern(self) -> None:
        """Phase 5 NUMBER_PATTERN + extract_numbers_from_text must be imported,
        not forked."""
        import app.services.chat.hallucination_guard as guard

        source = open(guard.__file__).read()
        assert (
            "from app.services.insights.number_validator import" in source
        ), "Hallucination guard must reuse Phase 5 NUMBER_PATTERN — no fork"
        assert "extract_numbers_from_text" in source
        assert "NUMBER_PATTERN" in source

    @pytest.mark.asyncio
    async def test_build_entity_whitelist_returns_expected_keys(self) -> None:
        """`build_entity_whitelist` returns {salespeople, showrooms, categories}."""
        from unittest.mock import AsyncMock, MagicMock
        from uuid import UUID

        from app.services.chat.hallucination_guard import build_entity_whitelist

        session = AsyncMock()
        result = MagicMock()
        scalars = MagicMock()
        scalars.all = MagicMock(return_value=[("Raileanu Leon",), ("Roibu Valeria",)])
        result.all = MagicMock(return_value=[("Raileanu Leon",), ("Roibu Valeria",)])
        session.execute = AsyncMock(return_value=result)

        tenant_id = UUID("00000000-0000-0000-0000-000000000001")
        wl = await build_entity_whitelist(session, tenant_id)
        assert set(wl.keys()) >= {"salespeople", "showrooms", "categories"}
        assert "Brașov" in wl["showrooms"]
        assert "București" in wl["showrooms"]
        assert "Cluj-Napoca" in wl["showrooms"]
        # categories from 11-source mapping
        assert "showroom" in wl["categories"]
        assert "mail" in wl["categories"]
