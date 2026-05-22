"""Unit tests for MEFI Pydantic v2 schemas.

Tests cover:
- MefiSearchResponse.model_validate with full sample JSON
- estimated_value is Decimal (not float) — DATA-04
- custom_fields defaults to empty list when missing
- MefiLeadResponse optional fields (all None-safe)
- MefiMeta pagination fields
"""
from __future__ import annotations

from decimal import Decimal

import pytest

# These imports will FAIL (RED) until the schema module is created.
from app.schemas.mefi import (
    MefiCustomField,
    MefiLeadResponse,
    MefiMeta,
    MefiSearchResponse,
    MefiStatusRef,
    MefiSourceRef,
    MefiAssignedTo,
)


SAMPLE_LEAD_JSON = {
    "id": 42,
    "status": {"id": 39, "name": "Calificare"},
    "source": {"id": 1, "name": "Google"},
    "lifecycle": "active",
    "assigned_to": {"id": 5, "name": "Popescu Ion"},
    "estimated_value": "12500.00",
    "custom_fields": [{"field_id": 14, "value": "Brașov"}],
}

SAMPLE_SEARCH_JSON = {
    "success": True,
    "data": [SAMPLE_LEAD_JSON],
    "meta": {"page": 1, "per_page": 100, "total": 543, "total_pages": 6},
}


class TestMefiCustomField:
    def test_parse_valid_custom_field(self) -> None:
        cf = MefiCustomField.model_validate({"field_id": 14, "value": "Brașov"})
        assert cf.field_id == 14
        assert cf.value == "Brașov"

    def test_parse_null_value(self) -> None:
        cf = MefiCustomField.model_validate({"field_id": 20, "value": None})
        assert cf.field_id == 20
        assert cf.value is None


class TestMefiStatusRef:
    def test_parse_status_ref(self) -> None:
        ref = MefiStatusRef.model_validate({"id": 39, "name": "Calificare"})
        assert ref.id == 39
        assert ref.name == "Calificare"


class TestMefiSourceRef:
    def test_parse_source_ref(self) -> None:
        ref = MefiSourceRef.model_validate({"id": 1, "name": "Google"})
        assert ref.id == 1
        assert ref.name == "Google"


class TestMefiAssignedTo:
    def test_parse_assigned_to(self) -> None:
        a = MefiAssignedTo.model_validate({"id": 5, "name": "Popescu Ion"})
        assert a.id == 5
        assert a.name == "Popescu Ion"


class TestMefiLeadResponse:
    def test_estimated_value_is_decimal(self) -> None:
        """DATA-04: estimated_value must be Decimal, never float."""
        lead = MefiLeadResponse.model_validate(
            {"id": 1, "lifecycle": "active", "estimated_value": "12500.50", "custom_fields": []}
        )
        assert isinstance(lead.estimated_value, Decimal)
        assert lead.estimated_value == Decimal("12500.50")

    def test_custom_fields_defaults_to_empty_list(self) -> None:
        """custom_fields must default to [] when absent from JSON."""
        lead = MefiLeadResponse.model_validate({"id": 1, "lifecycle": "active"})
        assert lead.custom_fields == []

    def test_optional_fields_are_none(self) -> None:
        """All optional fields default to None when not in payload."""
        lead = MefiLeadResponse.model_validate({"id": 1, "lifecycle": "active"})
        assert lead.status is None
        assert lead.source is None
        assert lead.assigned_to is None
        assert lead.estimated_value is None
        assert lead.phone is None
        assert lead.name is None

    def test_full_lead_parses_correctly(self) -> None:
        """Full lead JSON round-trips through the schema."""
        lead = MefiLeadResponse.model_validate(SAMPLE_LEAD_JSON)
        assert lead.id == 42
        assert lead.lifecycle == "active"
        assert lead.status is not None
        assert lead.status.id == 39
        assert lead.status.name == "Calificare"
        assert lead.source is not None
        assert lead.source.id == 1
        assert lead.assigned_to is not None
        assert lead.assigned_to.id == 5
        assert len(lead.custom_fields) == 1
        assert lead.custom_fields[0].field_id == 14
        assert lead.custom_fields[0].value == "Brașov"

    def test_estimated_value_from_numeric_json(self) -> None:
        """estimated_value coerced from numeric JSON (not string) is Decimal."""
        lead = MefiLeadResponse.model_validate(
            {"id": 1, "lifecycle": "active", "estimated_value": 12500.00}
        )
        assert isinstance(lead.estimated_value, Decimal)

    def test_is_duplicate_defaults_false(self) -> None:
        lead = MefiLeadResponse.model_validate({"id": 1, "lifecycle": "active"})
        assert lead.is_duplicate is False


class TestMefiMeta:
    def test_parse_meta(self) -> None:
        meta = MefiMeta.model_validate(
            {"page": 1, "per_page": 100, "total": 543, "total_pages": 6}
        )
        assert meta.page == 1
        assert meta.per_page == 100
        assert meta.total == 543
        assert meta.total_pages == 6


class TestMefiSearchResponse:
    def test_full_search_response(self) -> None:
        """MefiSearchResponse.model_validate succeeds on full sample JSON."""
        response = MefiSearchResponse.model_validate(SAMPLE_SEARCH_JSON)
        assert response.success is True
        assert len(response.data) == 1
        assert response.meta.total == 543

    def test_estimated_value_decimal_in_search_response(self) -> None:
        """estimated_value in search response is Decimal, not float."""
        response = MefiSearchResponse.model_validate(SAMPLE_SEARCH_JSON)
        lead = response.data[0]
        assert isinstance(lead.estimated_value, Decimal)
        assert lead.estimated_value == Decimal("12500.00")

    def test_empty_data_list(self) -> None:
        """Empty data array is valid."""
        response = MefiSearchResponse.model_validate(
            {
                "success": True,
                "data": [],
                "meta": {"page": 1, "per_page": 100, "total": 0, "total_pages": 0},
            }
        )
        assert response.data == []
        assert response.meta.total == 0
