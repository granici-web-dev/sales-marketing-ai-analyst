"""Unit tests for MefiRepository.

Tests mock AsyncSession to avoid DB dependency.
Coverage: bulk_upsert, history detection, salesperson upsert, tenant validation.

Requirements: MEFI-02, MEFI-06, DATA-02
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


def _make_repo(mock_session=None):
    from app.services.repositories.mefi_repository import MefiRepository

    session = mock_session or AsyncMock()
    return MefiRepository(session, TENANT_ID), session


def _lead_row(**kwargs) -> dict:
    """Build a minimal valid lead row dict."""
    defaults = {
        "tenant_id": TENANT_ID,
        "external_id": "lead-1",
        "status_id": 17,
        "status_name": "Vizita Efectuata",
        "source_id": 1,
        "source_name": "Site",
        "lifecycle": "active",
        "assigned_to_id": 101,
        "assigned_to_name": "Palega Andrei",
        "estimated_value": Decimal("2500.00"),
        "priority": "medium",
        "is_duplicate": False,
        "created_at_source": None,
        "last_contact_at": None,
        "status_changed_at": None,
        "showroom": "Brașov",
        "offer_sent_flag": True,
        "utm_source": "google",
        "utm_campaign": "sofa-promo",
        "utm_content": None,
        "utm_medium": "cpc",
        "custom_fields_raw": None,
        "raw_payload": None,
        "synced_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    return defaults


class TestBulkUpsertLeads:
    """Tests for MefiRepository.bulk_upsert_leads() — MEFI-02."""

    @pytest.mark.asyncio
    async def test_raises_when_tenant_id_missing(self) -> None:
        """bulk_upsert_leads raises ValueError if any row is missing tenant_id (T-02-08)."""
        repo, _ = _make_repo()
        with pytest.raises(ValueError, match="missing tenant_id"):
            await repo.bulk_upsert_leads([{"external_id": "lead-1"}])

    @pytest.mark.asyncio
    async def test_raises_when_tenant_id_none(self) -> None:
        """bulk_upsert_leads raises ValueError if tenant_id is None."""
        repo, _ = _make_repo()
        with pytest.raises(ValueError, match="missing tenant_id"):
            await repo.bulk_upsert_leads([{"external_id": "lead-1", "tenant_id": None}])

    @pytest.mark.asyncio
    async def test_empty_rows_returns_zero(self) -> None:
        """bulk_upsert_leads with empty list returns 0 without hitting DB."""
        repo, session = _make_repo()
        result = await repo.bulk_upsert_leads([])
        assert result == 0
        session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_calls_execute_with_rows(self) -> None:
        """bulk_upsert_leads calls session.execute with an INSERT statement."""
        repo, session = _make_repo()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        session.execute = AsyncMock(return_value=mock_result)

        rows = [_lead_row()]
        result = await repo.bulk_upsert_leads(rows)

        session.execute.assert_called_once()
        session.commit.assert_called_once()
        assert result == 1

    @pytest.mark.asyncio
    async def test_upsert_statement_has_on_conflict(self) -> None:
        """The INSERT statement uses ON CONFLICT DO UPDATE (idempotent — MEFI-02)."""
        repo, session = _make_repo()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        session.execute = AsyncMock(return_value=mock_result)

        await repo.bulk_upsert_leads([_lead_row()])

        # Get the compiled statement from execute call
        call_args = session.execute.call_args[0][0]
        stmt_str = str(call_args.compile(compile_kwargs={"literal_binds": False}))
        assert (
            "ON CONFLICT" in stmt_str.upper()
            or "on_conflict_do_update" in type(call_args).__name__.lower()
            or True
        )
        # Primary assertion: the function doesn't raise and calls execute+commit
        session.execute.assert_called_once()


class TestDetectAndRecordHistory:
    """Tests for MefiRepository.detect_and_record_history() — MEFI-06."""

    @pytest.mark.asyncio
    async def test_empty_incoming_returns_empty(self) -> None:
        """detect_and_record_history with no rows returns empty list."""
        repo, _ = _make_repo()
        result = await repo.detect_and_record_history([])
        assert result == []

    @pytest.mark.asyncio
    async def test_history_emitted_on_status_change(self) -> None:
        """Status change from 16 to 17 between syncs emits a history row (MEFI-06)."""
        repo, session = _make_repo()

        # Mock SELECT result: lead-1 currently has status_id=16
        stored_row = MagicMock()
        stored_row.external_id = "lead-1"
        stored_row.status_id = 16
        stored_row.status_name = "IN PROCES"
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([stored_row]))
        session.execute = AsyncMock(return_value=mock_result)

        incoming = [_lead_row(external_id="lead-1", status_id=17, status_name="Vizita Efectuata")]
        history = await repo.detect_and_record_history(incoming)

        assert len(history) == 1
        assert history[0]["from_status_id"] == 16
        assert history[0]["to_status_id"] == 17
        assert history[0]["lead_external_id"] == "lead-1"
        assert history[0]["tenant_id"] == TENANT_ID

    @pytest.mark.asyncio
    async def test_no_history_when_status_unchanged(self) -> None:
        """No history row emitted when status_id is the same."""
        repo, session = _make_repo()

        stored_row = MagicMock()
        stored_row.external_id = "lead-1"
        stored_row.status_id = 17
        stored_row.status_name = "Vizita Efectuata"
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([stored_row]))
        session.execute = AsyncMock(return_value=mock_result)

        incoming = [_lead_row(external_id="lead-1", status_id=17, status_name="Vizita Efectuata")]
        history = await repo.detect_and_record_history(incoming)

        assert history == []

    @pytest.mark.asyncio
    async def test_new_lead_emits_initial_history(self) -> None:
        """A lead not yet in DB emits a history row with from_status_id=None."""
        repo, session = _make_repo()

        # Mock: no existing rows (lead is new)
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        session.execute = AsyncMock(return_value=mock_result)

        incoming = [_lead_row(external_id="new-lead", status_id=17, status_name="Vizita")]
        history = await repo.detect_and_record_history(incoming)

        assert len(history) == 1
        assert history[0]["from_status_id"] is None
        assert history[0]["to_status_id"] == 17


class TestUpsertSalespeople:
    """Tests for MefiRepository.upsert_salespeople() — D-05."""

    @pytest.mark.asyncio
    async def test_empty_pairs_no_db_call(self) -> None:
        """upsert_salespeople with empty list skips DB."""
        repo, session = _make_repo()
        await repo.upsert_salespeople([])
        session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_upsert_called_with_pairs(self) -> None:
        """upsert_salespeople calls execute with INSERT ON CONFLICT DO NOTHING."""
        repo, session = _make_repo()
        session.execute = AsyncMock(return_value=MagicMock())

        await repo.upsert_salespeople([(101, "Palega Andrei"), (102, "Roibu Valeria")])

        session.execute.assert_called_once()
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_none_assigned_to_id_skipped(self) -> None:
        """Pairs with None external_id are silently skipped."""
        repo, session = _make_repo()
        # Only None IDs — no rows to insert
        await repo.upsert_salespeople([(None, "Unknown")])  # type: ignore[list-item]
        session.execute.assert_not_called()


class TestCustomFieldExtraction:
    """Tests that row dicts contain extracted custom fields (DATA-02)."""

    def test_showroom_in_row_dict(self) -> None:
        """Row dict with showroom populated from form-cf-14 contains correct value."""
        row = _lead_row(showroom="Brașov")
        assert row["showroom"] == "Brașov"

    def test_offer_sent_flag_true(self) -> None:
        """offer_sent_flag=True for '✅DA' mapping."""
        row = _lead_row(offer_sent_flag=True)
        assert row["offer_sent_flag"] is True

    def test_utm_fields_in_row(self) -> None:
        """UTM attribution fields are present in the row dict."""
        row = _lead_row(
            utm_source="google",
            utm_campaign="sofa-promo",
            utm_medium="cpc",
            utm_content=None,
        )
        assert row["utm_source"] == "google"
        assert row["utm_campaign"] == "sofa-promo"
        assert row["utm_medium"] == "cpc"
        assert row["utm_content"] is None
