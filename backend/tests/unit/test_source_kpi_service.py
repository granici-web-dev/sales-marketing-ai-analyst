"""Unit tests for SourceKpiService.

Tests mock AsyncSession — no live DB required.

Requirements: METR-03.

## Why this file was rewritten (2026-08-25)

It encoded the pre-2026-05-28 design and had been failing ever since that
design was replaced. Five tests asserted the old shape:

  - seven categories `mail_fb_ig | telefon | whatsapp | site | designer |
    alte | google` — there are now eleven, and three of those names are gone;
  - `_categorize_lead(source_id, is_designer)` — the parameter no longer
    exists, so those tests raised TypeError rather than failing an assertion;
  - `source_id=1 → "google"` — source 1 does not occur in Sofa Belle's data at
    all; Google traffic arrives as source 6 (Site).

A sixth passed for the wrong reason: it asserted `"tiktok" not in sources`
against a mocked-empty result, so the body never ran. A test that is green
because it checked nothing is worse than a red one — it is counted as
coverage.

The categories are now read FROM the service rather than restated here. The
old copy is exactly how these tests went stale: the service changed and the
literal in this file did not, and nothing connected the two.

Designer coverage is not dropped, it moved. Designer is a MEFI *status*
(status_id=24), never a source, and it is counted in `daily_kpi.leads_designer`
by a CTE over `mefi_lead_history` in `daily_kpi_service`. The test below pins
the boundary so nobody reintroduces it here.
"""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


def _categories() -> list[str]:
    """Canonical categories, read from the service — never restated."""
    from app.services.metrics.source_kpi_service import CANONICAL_CATEGORIES

    return list(CANONICAL_CATEGORIES)


def _make_service(mock_session=None):
    """Build SourceKpiService with a mocked AsyncSession."""
    from app.services.metrics.source_kpi_service import SourceKpiService  # noqa: PLC0415

    session = mock_session or AsyncMock()
    return SourceKpiService(session, TENANT_ID), session


def _empty_session() -> AsyncMock:
    session = AsyncMock()
    result = MagicMock()
    result.__iter__ = MagicMock(return_value=iter([]))
    session.execute = AsyncMock(return_value=result)
    return session


class TestSourceCategorization:
    """One row per canonical category per day — METR-03."""

    @pytest.mark.asyncio
    async def test_every_canonical_category_emitted_even_with_no_leads(self) -> None:
        """Zero-fill is the contract: a missing row and a zero row are not the same.

        The dashboard charts a fixed set of sources. If a category with no leads
        simply vanished from the result, the chart would silently reshape itself
        day to day and a source that died would look like a source that was
        never configured.
        """
        service, _ = _make_service(_empty_session())
        rows = await service.compute_source_kpis(date(2026, 5, 24))

        sources = [r["source"] if isinstance(r, dict) else r.source for r in rows]
        expected = _categories()

        assert sources == expected, (
            "every canonical category must be emitted, in canonical order, even "
            f"on a day with no leads at all.\n  expected: {expected}\n  got:      {sources}"
        )

    @pytest.mark.asyncio
    async def test_no_category_outside_the_canonical_set(self) -> None:
        """Unmapped source IDs collapse into `other`, never into a new category.

        source_daily_kpi.source is TEXT, so a stray category name would insert
        happily and only surface as an unexplained slice on a chart.
        """
        service, _ = _make_service(_empty_session())
        rows = await service.compute_source_kpis(date(2026, 5, 24))

        allowed = set(_categories())
        seen = {r["source"] if isinstance(r, dict) else r.source for r in rows}
        assert seen <= allowed, f"categories outside the canonical set: {sorted(seen - allowed)}"


class TestLeadCategorization:
    """`_categorize_lead` — the source_id → category mapping."""

    @pytest.mark.parametrize(
        ("source_id", "expected"),
        [
            (5, "showroom"),
            (11, "mail"),
            (10, "telefon"),
            (9, "whatsapp"),
            (6, "site"),
            (2, "meta"),
            (3, "recomandare"),
            (12, "colaborare"),
            (7, "arhitect"),
            (13, "client_fidel"),
        ],
    )
    def test_known_source_ids(self, source_id: int, expected: str) -> None:
        """Verified against Sofa Belle's own source IDs on 2026-05-28."""
        service, _ = _make_service()
        assert service._categorize_lead(source_id) == expected

    @pytest.mark.parametrize("source_id", [None, 0, 1, 99, 12345])
    def test_unknown_source_ids_fall_into_other(self, source_id) -> None:
        """Including `1`.

        source_id=1 is Google in MEFI's own list, and an earlier version of this
        file asserted it produced a `google` category. It does not, and should
        not: no lead in Sofa Belle's data carries it — their Google traffic
        arrives through the website form as source 6. Inventing a `google`
        bucket would put a permanent zero on the chart.
        """
        service, _ = _make_service()
        assert service._categorize_lead(source_id) == "other"

    def test_every_mapped_category_is_canonical(self) -> None:
        """The mapping may not produce a name the zero-fill does not know about."""
        service, _ = _make_service()
        allowed = set(_categories())
        produced = {service._categorize_lead(sid) for sid in range(0, 40)}
        assert produced <= allowed, f"unmapped category names: {sorted(produced - allowed)}"


class TestDesignerIsNotASource:
    """Designer is a status, and lives in daily_kpi — not here.

    Pinned deliberately. The previous version of this file asserted the
    opposite (`is_designer=True` overriding source_id), which is how it came to
    fail: the design moved and the tests stayed. Asserting the boundary makes
    the move visible instead of leaving a hole where the old tests were.
    """

    def test_designer_is_not_a_source_category(self) -> None:
        assert "designer" not in _categories(), (
            "designer is a MEFI status (24), not a source — it is counted in "
            "daily_kpi.leads_designer, see daily_kpi_service"
        )

    def test_categorize_lead_takes_only_source_id(self) -> None:
        """No `is_designer` parameter — a status must not leak into source logic."""
        import inspect

        from app.services.metrics.source_kpi_service import SourceKpiService

        params = list(inspect.signature(SourceKpiService._categorize_lead).parameters)
        assert params == ["self", "source_id"], (
            f"_categorize_lead must classify by source alone, got {params}"
        )

    def test_designer_counting_still_exists_somewhere(self) -> None:
        """Guards against the coverage being deleted rather than relocated.

        If the CTE on status 24 disappears from daily_kpi_service, the tests
        above would keep passing while the metric quietly stopped existing.
        """
        import inspect

        from app.services.metrics import daily_kpi_service

        source = inspect.getsource(daily_kpi_service)
        assert "leads_designer" in source and "24" in source, (
            "designer leads are no longer counted in daily_kpi_service — if the "
            "metric moved again, move this assertion with it"
        )
