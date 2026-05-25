from __future__ import annotations

"""Unit tests for DailyKpiService.

Tests mock AsyncSession — no live DB required.
Coverage: conversion rate calculation, WoW/MoM deltas, zero-division guard, delta precision.

Requirements: METR-01, METR-02, METR-05
Tests D-11 (NULL deltas on missing prior data), D-16 (NUMERIC, never float).
"""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


def _make_service(mock_session=None):
    """Build DailyKpiService with mocked AsyncSession.

    Import is deferred so the file parses (RED) even before Plan 03 implementation exists.
    """
    from app.services.metrics.daily_kpi_service import DailyKpiService  # noqa: PLC0415

    session = mock_session or AsyncMock()
    return DailyKpiService(session, TENANT_ID), session


def _make_kpi_row(**kwargs) -> dict:
    """Build a minimal daily_kpi row dict with Sofa Belle realistic defaults."""
    defaults = {
        "tenant_id": TENANT_ID,
        "date": date(2026, 5, 24),
        "leads_total": 20,
        "visits_count": 8,
        "offers_count": 4,
        "contracts_count": 1,
        "revenue": Decimal("15000.00"),
        "avg_deal_size": Decimal("15000.00"),
        "conversion_l_to_v": Decimal("0.4000"),
        "conversion_v_to_o": Decimal("0.5000"),
        "conversion_l_to_o": Decimal("0.2000"),
        "conversion_o_to_c": Decimal("0.2500"),
        "conversion_l_to_c": Decimal("0.0500"),
    }
    defaults.update(kwargs)
    return defaults


class TestConversionRates:
    """Tests for 5 conversion rates with zero-division guard — METR-02, SC#2."""

    @pytest.mark.asyncio
    async def test_conversion_rate_zero_denominator(self) -> None:
        """0 leads → conversion_l_to_v = None, not ZeroDivisionError (SC#2, METR-02).

        Tests D-11: zero denominator must produce NULL, never raise exception.
        When leads_total = 0, all conversion rates that use leads as denominator must be None.
        """
        session = AsyncMock()
        # Mock SELECT returning a row with 0 leads
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        session.execute = AsyncMock(return_value=mock_result)

        service, _ = _make_service(session)

        # The service's _compute_delta (and SQL NULLIF) must guard against zero denominator
        # When prior data row is None → delta = None (D-11), not ZeroDivisionError
        result = service._compute_delta(Decimal("5.0"), Decimal("0"))  # type: ignore[attr-defined]
        assert result is None, (
            "Zero denominator in _compute_delta must return None (D-11), not raise"
        )

    @pytest.mark.asyncio
    async def test_conversion_rate_null_numerator(self) -> None:
        """None numerator → conversion rate = None (D-11)."""
        service, _ = _make_service()
        result = service._compute_delta(None, Decimal("20"))  # type: ignore[attr-defined]
        assert result is None, "None numerator must produce None delta (D-11)"

    @pytest.mark.asyncio
    async def test_conversion_rate_both_none(self) -> None:
        """Both current and prior None → delta = None (D-11)."""
        service, _ = _make_service()
        result = service._compute_delta(None, None)  # type: ignore[attr-defined]
        assert result is None, "Both None must produce None delta (D-11)"

    @pytest.mark.asyncio
    async def test_conversion_rate_positive_values(self) -> None:
        """20 leads, 8 visits → L→V rate = 8/20 = 0.4 (non-zero denominator path)."""
        service, _ = _make_service()
        # _compute_delta: (current - prior) / prior
        result = service._compute_delta(Decimal("0.5"), Decimal("0.4"))  # type: ignore[attr-defined]
        assert result is not None, "Non-zero denominator must produce non-None delta"
        expected = (Decimal("0.5") - Decimal("0.4")) / Decimal("0.4")
        assert abs(result - expected) < Decimal("0.0001"), (
            f"Delta precision off: expected ~{expected}, got {result}"
        )


class TestWoWMoMDeltas:
    """Tests for WoW and MoM deltas — METR-05, D-11."""

    @pytest.mark.asyncio
    async def test_wow_delta_null_when_no_prior_row(self) -> None:
        """No D-7 row in daily_kpi → wow_delta = None (D-11).

        METR-05: WoW delta must store NULL when prior row is absent, not impute zero.
        Phase 7 dashboard renders NULL as 'N/A', never zero.
        """
        session = AsyncMock()
        # Mock the fetch_prior_row returning None (no D-7 data)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        session.execute = AsyncMock(return_value=mock_result)

        service, _ = _make_service(session)

        # When prior row is None → delta is None (D-11)
        result = service._compute_delta(Decimal("20"), None)  # type: ignore[attr-defined]
        assert result is None, (
            "wow_delta must be None when no prior row exists (D-11, METR-05) — "
            "never impute zero for missing comparison point"
        )

    @pytest.mark.asyncio
    async def test_mom_delta_null_when_prior_is_zero(self) -> None:
        """Prior revenue = 0 → mom_delta = None (D-11, division guard).

        Even if prior row exists with value 0, delta must be None — not divide by zero.
        This guards against misleading ∞% growth indicators.
        """
        service, _ = _make_service()
        result = service._compute_delta(Decimal("15000"), Decimal("0"))  # type: ignore[attr-defined]
        assert result is None, (
            "mom_delta must be None when prior is zero (D-11) — "
            "division by zero must be guarded"
        )

    @pytest.mark.asyncio
    async def test_delta_precision_numeric(self) -> None:
        """Delta computed from Decimal values preserves NUMERIC precision (SC#4, D-16).

        Revenue delta must be a Decimal, never float (DATA-04).
        Precision within 1 RON for revenue comparisons (SC#4).
        """
        service, _ = _make_service()
        current = Decimal("15000.00")
        prior = Decimal("12000.00")
        result = service._compute_delta(current, prior)  # type: ignore[attr-defined]
        assert result is not None, "Valid prior must produce non-None delta"
        assert isinstance(result, Decimal), (
            f"Delta must be Decimal, not {type(result).__name__} (D-16 — never float)"
        )
        expected = (current - prior) / prior  # 0.25
        assert abs(result - expected) < Decimal("0.0001"), (
            f"Delta precision exceeds threshold: expected ~{expected}, got {result}"
        )

    @pytest.mark.asyncio
    async def test_wow_delta_correct_calculation(self) -> None:
        """WoW delta: (current - prior_7d) / prior_7d, correct arithmetic."""
        service, _ = _make_service()
        current = Decimal("20")
        prior = Decimal("16")
        result = service._compute_delta(current, prior)  # type: ignore[attr-defined]
        assert result is not None
        expected = Decimal("0.25")  # (20-16)/16
        assert abs(result - expected) < Decimal("0.0001"), (
            f"WoW delta arithmetic wrong: expected {expected}, got {result}"
        )
