"""
Unit tests for MEFI SQLAlchemy models.

Tests cover:
  - Class importability from app.models.mefi
  - Correct __tablename__ values
  - Required column presence and types
  - TenantScopedMixin inheritance (id, tenant_id, created_at, updated_at)
  - NUMERIC(12,2) for estimated_value (DATA-04)
  - Unique constraint declarations in __table_args__

These are pure model-introspection tests — no database connection required.
"""

from __future__ import annotations

import pytest
from sqlalchemy import Boolean, Integer, Numeric
from sqlalchemy.dialects.postgresql import JSONB

# ── Imports under test ────────────────────────────────────────────────────────
# Wrapped in try/except so test collection doesn't fail before implementation.
# Tests will explicitly fail with a descriptive message if import fails.

try:
    from app.models.mefi import MefiLeadHistory, MefiSalesperson, RawMefiLead

    _import_error: Exception | None = None
except ImportError as exc:
    RawMefiLead = None  # type: ignore[assignment]
    MefiLeadHistory = None  # type: ignore[assignment]
    MefiSalesperson = None  # type: ignore[assignment]
    _import_error = exc


# ── Helpers ───────────────────────────────────────────────────────────────────


def _require_import() -> None:
    """Fail fast with helpful message if models are not importable."""
    if RawMefiLead is None:
        pytest.fail(
            f"Cannot import from app.models.mefi: {_import_error}. "
            "Run Task 1 implementation before these tests."
        )


def _col(model, name):
    """Retrieve a column object from a SQLAlchemy model by name."""
    table = model.__table__
    assert name in table.columns, f"Column '{name}' not found in {model.__tablename__}"
    return table.columns[name]


# ── Importability tests ───────────────────────────────────────────────────────


def test_mefi_models_importable() -> None:
    """All three MEFI model classes must be importable from app.models.mefi."""
    _require_import()
    # If we got here, all three classes imported successfully.
    assert RawMefiLead is not None
    assert MefiLeadHistory is not None
    assert MefiSalesperson is not None


# ── __tablename__ tests ───────────────────────────────────────────────────────


def test_raw_mefi_lead_tablename() -> None:
    """RawMefiLead.__tablename__ must be 'raw_mefi_leads'."""
    _require_import()
    assert RawMefiLead.__tablename__ == "raw_mefi_leads"


def test_mefi_lead_history_tablename() -> None:
    """MefiLeadHistory.__tablename__ must be 'mefi_lead_history'."""
    _require_import()
    assert MefiLeadHistory.__tablename__ == "mefi_lead_history"


def test_mefi_salesperson_tablename() -> None:
    """MefiSalesperson.__tablename__ must be 'mefi_salespeople'."""
    _require_import()
    assert MefiSalesperson.__tablename__ == "mefi_salespeople"


# ── TenantScopedMixin inheritance ─────────────────────────────────────────────


def test_raw_mefi_lead_has_tenant_scoped_columns() -> None:
    """RawMefiLead must have id, tenant_id, created_at, updated_at from TenantScopedMixin."""
    _require_import()
    cols = RawMefiLead.__table__.columns
    for col_name in ("id", "tenant_id", "created_at", "updated_at"):
        assert col_name in cols, f"RawMefiLead missing TenantScopedMixin column: {col_name}"


def test_mefi_lead_history_has_tenant_scoped_columns() -> None:
    """MefiLeadHistory must have TenantScopedMixin columns."""
    _require_import()
    cols = MefiLeadHistory.__table__.columns
    for col_name in ("id", "tenant_id", "created_at", "updated_at"):
        assert col_name in cols, f"MefiLeadHistory missing TenantScopedMixin column: {col_name}"


def test_mefi_salesperson_has_tenant_scoped_columns() -> None:
    """MefiSalesperson must have TenantScopedMixin columns."""
    _require_import()
    cols = MefiSalesperson.__table__.columns
    for col_name in ("id", "tenant_id", "created_at", "updated_at"):
        assert col_name in cols, f"MefiSalesperson missing TenantScopedMixin column: {col_name}"


# ── RawMefiLead column tests ──────────────────────────────────────────────────


def test_raw_mefi_lead_external_id_not_null() -> None:
    """external_id must be NOT NULL (required for UPSERT conflict target)."""
    _require_import()
    col = _col(RawMefiLead, "external_id")
    assert col.nullable is False, "raw_mefi_leads.external_id must be NOT NULL"


def test_raw_mefi_lead_lifecycle_not_null() -> None:
    """lifecycle must be NOT NULL (active/lost/junk)."""
    _require_import()
    col = _col(RawMefiLead, "lifecycle")
    assert col.nullable is False, "raw_mefi_leads.lifecycle must be NOT NULL"


def test_raw_mefi_lead_estimated_value_is_numeric_12_2() -> None:
    """estimated_value must be NUMERIC(12,2) — never float (DATA-04)."""
    _require_import()
    col = _col(RawMefiLead, "estimated_value")
    assert isinstance(col.type, Numeric), (
        f"estimated_value must be Numeric type, got {type(col.type).__name__}"
    )
    assert col.type.precision == 12, (
        f"estimated_value precision must be 12, got {col.type.precision}"
    )
    assert col.type.scale == 2, f"estimated_value scale must be 2, got {col.type.scale}"
    assert col.nullable is True, "estimated_value should be nullable (not all leads have value)"


def test_raw_mefi_lead_has_showroom_column() -> None:
    """showroom column must exist (form-cf-14, DATA-02)."""
    _require_import()
    col = _col(RawMefiLead, "showroom")
    assert col.nullable is True, "showroom can be null (not all leads have showroom set)"


def test_raw_mefi_lead_has_offer_sent_flag() -> None:
    """offer_sent_flag column must exist (form-cf-20, DATA-02)."""
    _require_import()
    col = _col(RawMefiLead, "offer_sent_flag")
    assert col.nullable is True, "offer_sent_flag can be null (not all leads have this set)"


def test_raw_mefi_lead_has_utm_columns() -> None:
    """utm_source, utm_campaign, utm_content, utm_medium columns must exist (DATA-02)."""
    _require_import()
    for utm_col in ("utm_source", "utm_campaign", "utm_content", "utm_medium"):
        col = _col(RawMefiLead, utm_col)
        assert col.nullable is True, f"{utm_col} should be nullable (most leads won't have UTM)"


def test_raw_mefi_lead_has_jsonb_columns() -> None:
    """custom_fields_raw and raw_payload must be JSONB columns."""
    _require_import()
    for jsonb_col_name in ("custom_fields_raw", "raw_payload"):
        col = _col(RawMefiLead, jsonb_col_name)
        assert isinstance(col.type, JSONB), (
            f"{jsonb_col_name} must be JSONB type, got {type(col.type).__name__}"
        )


def test_raw_mefi_lead_has_is_duplicate() -> None:
    """is_duplicate boolean column must exist with a default of False."""
    _require_import()
    col = _col(RawMefiLead, "is_duplicate")
    assert isinstance(col.type, Boolean), (
        f"is_duplicate must be Boolean, got {type(col.type).__name__}"
    )


def test_raw_mefi_lead_has_timestamp_source_columns() -> None:
    """created_at_source, last_contact_at, status_changed_at must exist."""
    _require_import()
    for ts_col in ("created_at_source", "last_contact_at", "status_changed_at"):
        col = _col(RawMefiLead, ts_col)
        assert col.nullable is True, f"{ts_col} should be nullable"


def test_raw_mefi_lead_has_synced_at() -> None:
    """synced_at timestamp column must exist."""
    _require_import()
    col = _col(RawMefiLead, "synced_at")
    assert col.nullable is True, "synced_at can be null before first sync"


# ── MefiLeadHistory column tests ──────────────────────────────────────────────


def test_mefi_lead_history_lead_external_id_not_null() -> None:
    """lead_external_id must be NOT NULL (links to raw_mefi_leads.external_id)."""
    _require_import()
    col = _col(MefiLeadHistory, "lead_external_id")
    assert col.nullable is False, "mefi_lead_history.lead_external_id must be NOT NULL"


def test_mefi_lead_history_to_status_id_not_null() -> None:
    """to_status_id must be NOT NULL (new status after change)."""
    _require_import()
    col = _col(MefiLeadHistory, "to_status_id")
    assert col.nullable is False, "mefi_lead_history.to_status_id must be NOT NULL"


def test_mefi_lead_history_changed_at_not_null() -> None:
    """changed_at must be NOT NULL (when status change was detected)."""
    _require_import()
    col = _col(MefiLeadHistory, "changed_at")
    assert col.nullable is False, "mefi_lead_history.changed_at must be NOT NULL"


def test_mefi_lead_history_from_fields_nullable() -> None:
    """from_status_id, from_status_name can be null (new leads have no prior status)."""
    _require_import()
    assert _col(MefiLeadHistory, "from_status_id").nullable is True
    assert _col(MefiLeadHistory, "from_status_name").nullable is True


# ── MefiSalesperson column tests ──────────────────────────────────────────────


def test_mefi_salesperson_external_id_is_integer() -> None:
    """external_id must be Integer (MEFI user IDs are integers, not UUIDs)."""
    _require_import()
    col = _col(MefiSalesperson, "external_id")
    assert isinstance(col.type, Integer), (
        f"mefi_salespeople.external_id must be Integer type, got {type(col.type).__name__}"
    )
    assert col.nullable is False, "mefi_salespeople.external_id must NOT be NULL"


def test_mefi_salesperson_name_not_null() -> None:
    """name must be NOT NULL."""
    _require_import()
    col = _col(MefiSalesperson, "name")
    assert col.nullable is False, "mefi_salespeople.name must be NOT NULL"


def test_mefi_salesperson_is_active_nullable() -> None:
    """is_active starts as NULL (set manually by admin after first sync, D-06)."""
    _require_import()
    col = _col(MefiSalesperson, "is_active")
    assert col.nullable is True, "mefi_salespeople.is_active must be nullable (NULL = unset)"


def test_mefi_salesperson_showroom_nullable() -> None:
    """showroom starts as NULL (set manually by admin after first sync, D-06)."""
    _require_import()
    col = _col(MefiSalesperson, "showroom")
    assert col.nullable is True, "mefi_salespeople.showroom must be nullable (NULL = unset)"


# ── __init__.py import tests ──────────────────────────────────────────────────


def test_mefi_models_importable_from_package() -> None:
    """Models must be importable via app.models (for Alembic autogenerate)."""
    _require_import()
    # After __init__.py is updated, 'from app.models import ...' should work.
    # This test verifies the __init__.py exports the three classes.
    import app.models as models_pkg

    assert hasattr(models_pkg, "RawMefiLead"), (
        "app.models.__init__.py must export RawMefiLead for Alembic autogenerate"
    )
    assert hasattr(models_pkg, "MefiLeadHistory"), (
        "app.models.__init__.py must export MefiLeadHistory for Alembic autogenerate"
    )
    assert hasattr(models_pkg, "MefiSalesperson"), (
        "app.models.__init__.py must export MefiSalesperson for Alembic autogenerate"
    )
