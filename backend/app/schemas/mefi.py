"""Pydantic v2 schemas for MEFI CRM API responses.

These models validate the JSON returned by MEFI's /leads/search endpoint.
All models use ConfigDict(populate_by_name=True) for forward compatibility
with potential future alias usage.

Note on PII fields (phone, email, name):
  These fields are RECEIVED from the MEFI API and stored temporarily for
  processing (matching, deduplication). They MUST NOT appear in any log
  statement — see CLAUDE.md no-PII rule. Omitting them from the schema
  entirely would break parsing, so they are kept here as optional fields.

Note on estimated_value:
  Uses Decimal (not float) per DATA-04. Pydantic v2 automatically coerces
  numeric JSON values and numeric strings to Decimal when the field type
  is Decimal.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class MefiCustomField(BaseModel):
    """Single custom field from the MEFI custom_fields array."""

    model_config = ConfigDict(populate_by_name=True)

    field_id: int
    value: str | None = None


class MefiStatusRef(BaseModel):
    """Embedded status reference in a MEFI lead."""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    name: str


class MefiSourceRef(BaseModel):
    """Embedded source reference in a MEFI lead."""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    name: str


class MefiAssignedTo(BaseModel):
    """Embedded salesperson reference in a MEFI lead."""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    name: str


class MefiLeadResponse(BaseModel):
    """Single lead record returned by MEFI /leads/search.

    Optional fields reflect that MEFI may not populate all fields for every lead.

    PII fields (phone, email, name) are present because MEFI sends them and we
    need them for processing — but they must NEVER appear in log statements.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: int

    # Potentially PII — do NOT log these values
    client_type: str | None = None
    name: str | None = None
    phone: str | None = None
    email: str | None = None

    status: MefiStatusRef | None = None
    source: MefiSourceRef | None = None
    lifecycle: str  # "active" | "lost" | "junk"
    assigned_to: MefiAssignedTo | None = None

    # DATA-04: revenue amounts as Decimal, never float
    estimated_value: Decimal | None = None

    priority: dict | None = None  # MEFI returns a dict or null
    is_duplicate: bool = False

    created_at: datetime | None = None
    last_contact_at: datetime | None = None
    status_changed_at: datetime | None = None

    # custom_fields defaults to [] so callers never have to handle None
    custom_fields: list[MefiCustomField] = []


class MefiMeta(BaseModel):
    """Pagination metadata in a MEFI search response."""

    model_config = ConfigDict(populate_by_name=True)

    page: int
    per_page: int
    total: int
    total_pages: int


class MefiSearchResponse(BaseModel):
    """Top-level response from MEFI /leads/search.

    Validates the full API response including success flag, data array,
    and pagination metadata.
    """

    model_config = ConfigDict(populate_by_name=True)

    success: bool
    data: list[MefiLeadResponse]
    meta: MefiMeta
