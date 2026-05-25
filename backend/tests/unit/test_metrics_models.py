from __future__ import annotations

"""Unit tests for Phase 3 SQLAlchemy metric models.

Tests cover: __tablename__ values, UniqueConstraint declarations in __table_args__.
No database connection required — pure model introspection.

Requirements: METR-01 (schema gate)
Tests UniqueConstraint names (UPSERT conflict target identifiers),
2-col key for daily_kpi, 3-col keys for salesperson and source tables.
"""

import pytest
from sqlalchemy import UniqueConstraint


# ── Import stubs ──────────────────────────────────────────────────────────────
# Wrapped in try/except so test collection succeeds (RED state) even before
# Plan 02 model implementation exists. Tests explicitly fail with descriptive
# messages when models are not yet importable.

try:
    from app.models.metrics.daily_kpi import DailyKpi

    _daily_kpi_import_error: Exception | None = None
except (ImportError, ModuleNotFoundError) as exc:
    DailyKpi = None  # type: ignore[assignment, misc]
    _daily_kpi_import_error = exc

try:
    from app.models.metrics.salesperson_kpi import SalespersonDailyKpi

    _sp_kpi_import_error: Exception | None = None
except (ImportError, ModuleNotFoundError) as exc:
    SalespersonDailyKpi = None  # type: ignore[assignment, misc]
    _sp_kpi_import_error = exc

try:
    from app.models.metrics.source_kpi import SourceDailyKpi

    _source_kpi_import_error: Exception | None = None
except (ImportError, ModuleNotFoundError) as exc:
    SourceDailyKpi = None  # type: ignore[assignment, misc]
    _source_kpi_import_error = exc


# ── Helpers ───────────────────────────────────────────────────────────────────


def _require_daily_kpi() -> None:
    if DailyKpi is None:
        pytest.fail(
            f"Cannot import DailyKpi: {_daily_kpi_import_error}. "
            "Run Plan 03-02 Task 1 (models) before these tests."
        )


def _require_salesperson_kpi() -> None:
    if SalespersonDailyKpi is None:
        pytest.fail(
            f"Cannot import SalespersonDailyKpi: {_sp_kpi_import_error}. "
            "Run Plan 03-02 Task 1 (models) before these tests."
        )


def _require_source_kpi() -> None:
    if SourceDailyKpi is None:
        pytest.fail(
            f"Cannot import SourceDailyKpi: {_source_kpi_import_error}. "
            "Run Plan 03-02 Task 1 (models) before these tests."
        )


def _get_unique_constraint(model, name: str) -> UniqueConstraint | None:
    """Find a UniqueConstraint by name in model.__table_args__."""
    table_args = getattr(model, "__table_args__", ())
    if isinstance(table_args, tuple):
        for arg in table_args:
            if isinstance(arg, UniqueConstraint) and arg.name == name:
                return arg
    return None


# ── DailyKpi model tests ──────────────────────────────────────────────────────


def test_daily_kpi_tablename() -> None:
    """DailyKpi.__tablename__ must be 'daily_kpi'."""
    _require_daily_kpi()
    assert DailyKpi.__tablename__ == "daily_kpi", (  # type: ignore[union-attr]
        f"DailyKpi.__tablename__ must be 'daily_kpi', got '{DailyKpi.__tablename__}'"  # type: ignore[union-attr]
    )


def test_daily_kpi_unique_constraint_two_cols() -> None:
    """DailyKpi must have UniqueConstraint on (tenant_id, date) named 'uq_daily_kpi_tenant_date'.

    2-column UNIQUE constraint: (tenant_id, date).
    UPSERT conflict target for MetricsRepository.upsert_daily_kpi().
    """
    _require_daily_kpi()
    uc = _get_unique_constraint(DailyKpi, "uq_daily_kpi_tenant_date")
    assert uc is not None, (
        "DailyKpi must declare UniqueConstraint(name='uq_daily_kpi_tenant_date') "
        "in __table_args__ — required for UPSERT conflict target (METR-01)"
    )
    # Verify it covers the right columns
    col_names = {col.key for col in uc.columns}
    assert "tenant_id" in col_names, "uq_daily_kpi_tenant_date must include 'tenant_id'"
    assert "date" in col_names, "uq_daily_kpi_tenant_date must include 'date'"
    assert len(col_names) == 2, (
        f"uq_daily_kpi_tenant_date must have exactly 2 columns (tenant_id, date), "
        f"got {col_names}"
    )


def test_daily_kpi_has_date_column() -> None:
    """DailyKpi must have a 'date' column (NOT NULL, Date type)."""
    _require_daily_kpi()
    table = DailyKpi.__table__  # type: ignore[union-attr]
    assert "date" in table.columns, "DailyKpi must have 'date' column"
    col = table.columns["date"]
    assert not col.nullable, "DailyKpi.date must be NOT NULL"


# ── SalespersonDailyKpi model tests ───────────────────────────────────────────


def test_salesperson_kpi_tablename() -> None:
    """SalespersonDailyKpi.__tablename__ must be 'salesperson_daily_kpi'."""
    _require_salesperson_kpi()
    assert SalespersonDailyKpi.__tablename__ == "salesperson_daily_kpi", (  # type: ignore[union-attr]
        f"SalespersonDailyKpi.__tablename__ must be 'salesperson_daily_kpi', "
        f"got '{SalespersonDailyKpi.__tablename__}'"  # type: ignore[union-attr]
    )


def test_salesperson_kpi_unique_constraint_three_cols() -> None:
    """SalespersonDailyKpi must have 3-col UniqueConstraint (tenant_id, salesperson_external_id, date).

    3-column UNIQUE constraint allows multiple salespeople per date (one row per SP per day).
    Named 'uq_salesperson_daily_kpi_tenant_sp_date'.
    UPSERT conflict target: index_elements=["tenant_id", "salesperson_external_id", "date"].
    """
    _require_salesperson_kpi()
    uc = _get_unique_constraint(SalespersonDailyKpi, "uq_salesperson_daily_kpi_tenant_sp_date")
    assert uc is not None, (
        "SalespersonDailyKpi must declare "
        "UniqueConstraint(name='uq_salesperson_daily_kpi_tenant_sp_date') in __table_args__"
    )
    col_names = {col.key for col in uc.columns}
    assert "tenant_id" in col_names, "uq_salesperson_daily_kpi_tenant_sp_date must include 'tenant_id'"
    assert "salesperson_external_id" in col_names, (
        "uq_salesperson_daily_kpi_tenant_sp_date must include 'salesperson_external_id'"
    )
    assert "date" in col_names, "uq_salesperson_daily_kpi_tenant_sp_date must include 'date'"
    assert len(col_names) == 3, (
        f"uq_salesperson_daily_kpi_tenant_sp_date must have exactly 3 columns, got {col_names}"
    )


def test_salesperson_kpi_has_data_completeness_pct() -> None:
    """SalespersonDailyKpi must have 'data_completeness_pct' column (Schema Gap 2, METR-06)."""
    _require_salesperson_kpi()
    table = SalespersonDailyKpi.__table__  # type: ignore[union-attr]
    assert "data_completeness_pct" in table.columns, (
        "SalespersonDailyKpi must have 'data_completeness_pct' column "
        "(Schema Gap 2 — not in SPEC.md §7, added by migration 004, METR-06)"
    )


def test_salesperson_kpi_has_salesperson_external_id() -> None:
    """SalespersonDailyKpi must have 'salesperson_external_id' column (NOT NULL, Text)."""
    _require_salesperson_kpi()
    table = SalespersonDailyKpi.__table__  # type: ignore[union-attr]
    assert "salesperson_external_id" in table.columns, (
        "SalespersonDailyKpi must have 'salesperson_external_id' column"
    )
    col = table.columns["salesperson_external_id"]
    assert not col.nullable, "salesperson_external_id must be NOT NULL"


# ── SourceDailyKpi model tests ────────────────────────────────────────────────


def test_source_kpi_tablename() -> None:
    """SourceDailyKpi.__tablename__ must be 'source_daily_kpi'."""
    _require_source_kpi()
    assert SourceDailyKpi.__tablename__ == "source_daily_kpi", (  # type: ignore[union-attr]
        f"SourceDailyKpi.__tablename__ must be 'source_daily_kpi', "
        f"got '{SourceDailyKpi.__tablename__}'"  # type: ignore[union-attr]
    )


def test_source_kpi_unique_constraint_three_cols() -> None:
    """SourceDailyKpi must have 3-col UniqueConstraint (tenant_id, source, date) — Pitfall 5.

    3-column UNIQUE constraint: (tenant_id, source, date).
    Pitfall 5: Using only (tenant_id, date) as conflict target causes UniqueViolationError
    when inserting the second source category. Must include 'source' as third column.
    Named 'uq_source_daily_kpi_tenant_source_date'.
    """
    _require_source_kpi()
    uc = _get_unique_constraint(SourceDailyKpi, "uq_source_daily_kpi_tenant_source_date")
    assert uc is not None, (
        "SourceDailyKpi must declare "
        "UniqueConstraint(name='uq_source_daily_kpi_tenant_source_date') in __table_args__. "
        "Pitfall 5: 3-col key (tenant_id, source, date) required to handle 7 source categories."
    )
    col_names = {col.key for col in uc.columns}
    assert "tenant_id" in col_names, "uq_source_daily_kpi_tenant_source_date must include 'tenant_id'"
    assert "source" in col_names, "uq_source_daily_kpi_tenant_source_date must include 'source'"
    assert "date" in col_names, "uq_source_daily_kpi_tenant_source_date must include 'date'"
    assert len(col_names) == 3, (
        f"uq_source_daily_kpi_tenant_source_date must have exactly 3 columns, got {col_names}"
    )


def test_source_kpi_has_source_column() -> None:
    """SourceDailyKpi must have 'source' TEXT column (NOT NULL, D-09)."""
    _require_source_kpi()
    table = SourceDailyKpi.__table__  # type: ignore[union-attr]
    assert "source" in table.columns, "SourceDailyKpi must have 'source' column (D-09)"
    col = table.columns["source"]
    assert not col.nullable, "SourceDailyKpi.source must be NOT NULL"


# ── TenantScopedMixin inheritance tests ──────────────────────────────────────


def test_all_models_have_tenant_scoped_columns() -> None:
    """All three metric models must inherit TenantScopedMixin columns (id, tenant_id)."""
    models = [
        (DailyKpi, "DailyKpi"),
        (SalespersonDailyKpi, "SalespersonDailyKpi"),
        (SourceDailyKpi, "SourceDailyKpi"),
    ]
    for model, name in models:
        if model is None:
            continue  # Will be caught by individual _require_ tests
        table = model.__table__
        for col_name in ("id", "tenant_id"):
            assert col_name in table.columns, (
                f"{name} must inherit TenantScopedMixin with '{col_name}' column (CLAUDE.md Principle #3)"
            )
