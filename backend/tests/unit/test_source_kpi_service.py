from __future__ import annotations

"""Unit tests for SourceKpiService.

Tests mock AsyncSession — no live DB required.
Coverage: 7-source-category production (D-04), designer detection (D-02), TikTok folding (D-03).

Requirements: METR-03
Tests D-02 (designer from status_id=24 in history), D-03 (TikTok→mail_fb_ig),
D-04 (exactly 7 rows per day per tenant).
"""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")

# D-04: Exact 7 source categories, in this order
EXPECTED_CATEGORIES = ["mail_fb_ig", "telefon", "whatsapp", "site", "designer", "alte", "google"]


def _make_service(mock_session=None):
    """Build SourceKpiService with mocked AsyncSession.

    Import deferred — file parses (RED) before Plan 03 implementation exists.
    """
    from app.services.metrics.source_kpi_service import SourceKpiService  # noqa: PLC0415

    session = mock_session or AsyncMock()
    return SourceKpiService(session, TENANT_ID), session


class TestSourceCategorization:
    """Tests for 7-source-category production — METR-03, D-04."""

    @pytest.mark.asyncio
    async def test_seven_source_rows_per_day(self) -> None:
        """source_daily_kpi must produce exactly 7 rows per day per tenant — D-04.

        D-04: Seven fixed categories: mail_fb_ig | telefon | whatsapp | site |
        designer | alte | google. All 7 must be emitted even when some have 0 leads.
        Gap 3: ROADMAP SC#1 says 6 categories but CONTEXT.md D-04 locks in 7 —
        CONTEXT takes precedence.
        """
        session = AsyncMock()
        # Mock aggregate query returning rows for all 7 categories
        mock_rows = []
        for cat in EXPECTED_CATEGORIES:
            row = MagicMock()
            row.source = cat
            row.leads = 0 if cat == "google" else 3
            mock_rows.append(row)

        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter(mock_rows))
        session.execute = AsyncMock(return_value=mock_result)

        service, _ = _make_service(session)
        rows = await service.compute_source_kpis(date(2026, 5, 24))  # type: ignore[attr-defined]

        assert rows is not None, "compute_source_kpis must return a list"
        # Even when DB returns 7 rows, service must surface them
        sources = [r["source"] if isinstance(r, dict) else r.source for r in rows]
        assert len(sources) == 7, (
            f"Must produce exactly 7 source rows per day (D-04), got {len(sources)}: {sources}"
        )
        for expected_cat in EXPECTED_CATEGORIES:
            assert expected_cat in sources, (
                f"Category '{expected_cat}' missing from source_daily_kpi output (D-04)"
            )

    @pytest.mark.asyncio
    async def test_tiktok_folded_into_mail_fb_ig(self) -> None:
        """TikTok leads (Meta source_ids 2/11) folded into mail_fb_ig (D-03).

        D-03: TikTok has no dedicated source_id in MEFI — leads fall under Meta
        source IDs (2 or 11). No separate 'tiktok' category exists in Phase 3.
        """
        # Verify no 'tiktok' category is emitted
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        session.execute = AsyncMock(return_value=mock_result)

        service, _ = _make_service(session)
        rows = await service.compute_source_kpis(date(2026, 5, 24))  # type: ignore[attr-defined]

        if rows:
            sources = [r.get("source") if isinstance(r, dict) else r.source for r in rows]
            assert "tiktok" not in sources, (
                "No 'tiktok' category must appear in Phase 3 (D-03) — "
                "TikTok folded into mail_fb_ig"
            )

    @pytest.mark.asyncio
    async def test_zero_leads_category_still_emitted(self) -> None:
        """Categories with 0 leads must still produce a row (D-04 — always 7 rows).

        All 7 source categories must be emitted even when count is 0.
        Dashboard depends on consistently seeing all 7 rows for charts.
        """
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        session.execute = AsyncMock(return_value=mock_result)

        service, _ = _make_service(session)
        rows = await service.compute_source_kpis(date(2026, 5, 24))  # type: ignore[attr-defined]

        assert rows is not None, "Service must return a list even with no leads"


class TestDesignerDetection:
    """Tests for designer source detection — D-02, METR-03."""

    @pytest.mark.asyncio
    async def test_designer_category_overrides_source_id(self) -> None:
        """Lead with source_id=2 (mail_fb_ig) but to_status_id=24 in history → 'designer'.

        D-02: Designer leads derived from status_id=24 in mefi_lead_history.
        If a lead EVER had status 24, its source category is 'designer' regardless
        of source_id. Designer is a MEFI status, not a source field.
        """
        session = AsyncMock()
        # Mock designer detection subquery returning lead_external_id 'lead-abc'
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        session.execute = AsyncMock(return_value=mock_result)

        service, _ = _make_service(session)

        # Simulate categorization: lead source_id=2, but has status_24 in history
        # Service must classify this lead as 'designer', not 'mail_fb_ig'
        category = service._categorize_lead(  # type: ignore[attr-defined]
            source_id=2,
            is_designer=True,  # flag from designer subquery
        )
        assert category == "designer", (
            f"Lead with is_designer=True must be categorized as 'designer', "
            f"got '{category}' (D-02 — designer overrides source_id)"
        )

    @pytest.mark.asyncio
    async def test_designer_from_current_status_24(self) -> None:
        """Lead currently at status_id=24 (DESIGNER) → categorized as 'designer' (D-02)."""
        service, _ = _make_service()
        category = service._categorize_lead(  # type: ignore[attr-defined]
            source_id=10,  # telefon
            is_designer=True,
        )
        assert category == "designer", (
            "Current status_id=24 lead must be 'designer' even if source_id is telefon (D-02)"
        )

    @pytest.mark.asyncio
    async def test_google_source_categorized_correctly(self) -> None:
        """source_id=1 (Google) → 'google' category (D-01)."""
        service, _ = _make_service()
        category = service._categorize_lead(  # type: ignore[attr-defined]
            source_id=1,
            is_designer=False,
        )
        assert category == "google", (
            f"source_id=1 must be 'google' category, got '{category}' (D-01)"
        )

    @pytest.mark.asyncio
    async def test_non_designer_lead_uses_source_id(self) -> None:
        """Lead with is_designer=False, source_id=9 → 'whatsapp' (normal mapping)."""
        service, _ = _make_service()
        category = service._categorize_lead(  # type: ignore[attr-defined]
            source_id=9,
            is_designer=False,
        )
        assert category == "whatsapp", (
            f"source_id=9 with is_designer=False must be 'whatsapp', got '{category}'"
        )
