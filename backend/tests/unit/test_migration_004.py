"""Unit-level tests for Alembic migration 004_metrics_schema.py.

Tests verify via AST inspection and source-text analysis — no DB or alembic import required.
This approach makes tests runnable on system Python without full app env (same pattern as 003).

Covers:
  - Revision chain (004 → 003)
  - Three metric table creation (daily_kpi, salesperson_daily_kpi, source_daily_kpi)
  - WoW/MoM delta columns added beyond SPEC.md §7 (Schema Gap 1 — METR-05)
  - data_completeness_pct added to salesperson_daily_kpi (Schema Gap 2 — METR-06)
  - BUSINESS_HOURS_PATCH dict with D-07 values (Mon-Sun 09:00-19:00 Europe/Bucharest)
  - Updated v_mefi_leads_active with mefi_lead_history JOIN (Schema Gap 5)
  - UNIQUE constraints for all three tables (UPSERT conflict targets)
  - Idempotent funnel_config seed UPDATE

Requirements: METR-01 (schema creation gate)
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# ── Locate migration file ─────────────────────────────────────────────────────

MIGRATION_PATH = (
    Path(__file__).parent.parent.parent / "alembic" / "versions" / "004_metrics_schema.py"
)


def _require_migration() -> None:
    """Fail fast with informative message if migration file doesn't exist (RED state)."""
    if not MIGRATION_PATH.exists():
        pytest.fail(
            f"Migration file not found: {MIGRATION_PATH}\n"
            "Run Plan 03-02 Task 1 implementation to create backend/alembic/versions/004_metrics_schema.py"
        )


def _get_revision_value(var_name: str) -> str | None:
    """Extract revision/down_revision string value via AST inspection.

    Pattern from test_migration_003.py — works without alembic installed.
    """
    if not MIGRATION_PATH.exists():
        return None
    source = MIGRATION_PATH.read_text()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == var_name:
                if node.value and isinstance(node.value, ast.Constant):
                    return node.value.value
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == var_name:
                    if isinstance(node.value, ast.Constant):
                        return node.value.value
    return None


# ── File existence tests ───────────────────────────────────────────────────────


def test_migration_004_file_exists() -> None:
    """Migration file 004_metrics_schema.py must exist."""
    _require_migration()
    assert MIGRATION_PATH.is_file()


def test_migration_004_parses_as_python() -> None:
    """Migration file must be valid Python (no syntax errors)."""
    _require_migration()
    source = MIGRATION_PATH.read_text()
    try:
        ast.parse(source)
    except SyntaxError as exc:
        pytest.fail(f"Migration 004 has syntax error: {exc}")


# ── Revision chain tests ───────────────────────────────────────────────────────


def test_revision_is_004() -> None:
    """revision must be '004'."""
    _require_migration()
    val = _get_revision_value("revision")
    assert val is not None, "Could not extract 'revision' from migration 004 via AST"
    assert val == "004", f"Expected revision='004', got {val!r}"


def test_down_revision_is_003() -> None:
    """down_revision must be '003' to chain after Phase 2 MEFI schema migration."""
    _require_migration()
    val = _get_revision_value("down_revision")
    assert val is not None, "Could not extract 'down_revision' from migration 004 via AST"
    assert val == "003", f"Expected down_revision='003', got {val!r}"


# ── Metric table creation tests ────────────────────────────────────────────────


def test_creates_three_metric_tables() -> None:
    """upgrade() must create all three Phase 3 metric tables (METR-01)."""
    _require_migration()
    source_text = MIGRATION_PATH.read_text()

    assert "daily_kpi" in source_text, "migration 004 must create 'daily_kpi' table (METR-01)"
    assert "salesperson_daily_kpi" in source_text, (
        "migration 004 must create 'salesperson_daily_kpi' table (METR-04)"
    )
    assert "source_daily_kpi" in source_text, (
        "migration 004 must create 'source_daily_kpi' table (METR-03)"
    )
    assert "create_table" in source_text, (
        "migration 004 must call op.create_table() for metric tables"
    )


# ── WoW/MoM delta column tests (Schema Gap 1 — METR-05) ──────────────────────


def test_creates_wow_mom_delta_columns() -> None:
    """upgrade() must add WoW/MoM delta columns to daily_kpi (Schema Gap 1, METR-05).

    SPEC.md §7 does NOT include delta columns. Migration 004 extends the schema.
    Delta columns cover 8 metrics × 2 deltas = 16 columns total.
    """
    _require_migration()
    source_text = MIGRATION_PATH.read_text()

    required_delta_cols = [
        "leads_total_wow_delta",
        "leads_total_mom_delta",
        "conversion_l_to_v_wow_delta",
        "conversion_l_to_v_mom_delta",
        "conversion_v_to_o_wow_delta",
        "conversion_v_to_o_mom_delta",
        "conversion_l_to_o_wow_delta",
        "conversion_l_to_o_mom_delta",
        "conversion_o_to_c_wow_delta",
        "conversion_o_to_c_mom_delta",
        "conversion_l_to_c_wow_delta",
        "conversion_l_to_c_mom_delta",
        "revenue_wow_delta",
        "revenue_mom_delta",
        "avg_deal_size_wow_delta",
        "avg_deal_size_mom_delta",
    ]
    for col in required_delta_cols:
        assert col in source_text, (
            f"migration 004 must add '{col}' to daily_kpi (Schema Gap 1, METR-05). "
            "SPEC.md §7 does not include WoW/MoM delta columns — migration must extend it."
        )


# ── data_completeness_pct column test (Schema Gap 2 — METR-06) ────────────────


def test_creates_data_completeness_pct() -> None:
    """upgrade() must add data_completeness_pct to salesperson_daily_kpi (Schema Gap 2, METR-06).

    SPEC.md §7 salesperson_daily_kpi DDL does NOT include data_completeness_pct.
    Migration 004 must extend the schema with this NUMERIC(5,2) column.
    """
    _require_migration()
    source_text = MIGRATION_PATH.read_text()
    assert "data_completeness_pct" in source_text, (
        "migration 004 must add 'data_completeness_pct' to salesperson_daily_kpi "
        "(Schema Gap 2, METR-06). SPEC.md §7 does not include this column."
    )


# ── BUSINESS_HOURS_PATCH dict test (D-07 — Schema Gap 4) ─────────────────────


def test_business_hours_patch_dict(self=None) -> None:
    """BUSINESS_HOURS_PATCH must define Mon-Sun 09:00-19:00 Europe/Bucharest (D-07).

    D-07: Sofa Belle business hours — Mon-Sun 09:00-19:00 Europe/Bucharest.
    Stored in tenants.funnel_config JSONB as 'business_hours' key.
    Migration 004 seeds this via idempotent UPDATE (Schema Gap 4).
    """
    _require_migration()
    source_text = MIGRATION_PATH.read_text()

    # BUSINESS_HOURS_PATCH must be defined as a module-level constant
    assert "BUSINESS_HOURS_PATCH" in source_text, (
        "migration 004 must define BUSINESS_HOURS_PATCH constant (D-07)"
    )
    # Verify the key D-07 values appear in source
    assert '"business_hours"' in source_text or "'business_hours'" in source_text, (
        "BUSINESS_HOURS_PATCH must contain 'business_hours' key (D-07)"
    )
    assert "09:00" in source_text, "BUSINESS_HOURS_PATCH must specify open time '09:00' (D-07)"
    assert "19:00" in source_text, "BUSINESS_HOURS_PATCH must specify close time '19:00' (D-07)"
    assert "Europe/Bucharest" in source_text, (
        "BUSINESS_HOURS_PATCH must specify timezone 'Europe/Bucharest' (D-07)"
    )
    # days: [0,1,2,3,4,5,6] — Mon-Sun (7 days/week)
    # At minimum, 0 and 6 must appear together (Mon and Sun both working)
    assert "0, 1, 2, 3, 4, 5, 6" in source_text or "[0, 1, 2, 3, 4, 5, 6]" in source_text, (
        "BUSINESS_HOURS_PATCH days must include 0-6 (Mon-Sun) for Sofa Belle 7-day week (D-07)"
    )


# ── v_mefi_leads_active history JOIN test (Schema Gap 5) ─────────────────────


def test_replaces_v_mefi_leads_active_with_history_join(self=None) -> None:
    """upgrade() must update v_mefi_leads_active with mefi_lead_history JOIN (Schema Gap 5).

    Migration 003 comment: 'True ever reached requires mefi_lead_history join — planned Phase 3'.
    Migration 004 must update the view to use history-based reached_* booleans (D-13).
    Without this, funnel conversion counts are inaccurate for multi-step leads.
    """
    _require_migration()
    source_text = MIGRATION_PATH.read_text()

    # The updated view DDL must JOIN mefi_lead_history
    assert "mefi_lead_history" in source_text, (
        "migration 004 must update v_mefi_leads_active to JOIN mefi_lead_history "
        "(Schema Gap 5 — 'ever reached' funnel logic requires history join, D-13)"
    )
    # Must CREATE OR REPLACE the view (not just reference it in downgrade)
    assert "CREATE OR REPLACE VIEW" in source_text, (
        "migration 004 must CREATE OR REPLACE VIEW v_mefi_leads_active with history-based logic"
    )
    assert "v_mefi_leads_active" in source_text, (
        "migration 004 must recreate v_mefi_leads_active with history-based reached_* columns"
    )


# ── UNIQUE constraint tests ───────────────────────────────────────────────────


def test_unique_constraints_present() -> None:
    """Migration must create UNIQUE constraints for all three metric table UPSERT targets."""
    _require_migration()
    source_text = MIGRATION_PATH.read_text()

    # All three constraint names must appear
    assert "uq_daily_kpi_tenant_date" in source_text, (
        "migration 004 must create constraint 'uq_daily_kpi_tenant_date' on daily_kpi"
    )
    assert "uq_salesperson_daily_kpi_tenant_sp_date" in source_text, (
        "migration 004 must create constraint 'uq_salesperson_daily_kpi_tenant_sp_date' "
        "on salesperson_daily_kpi (3-col: tenant_id + salesperson_external_id + date)"
    )
    assert "uq_source_daily_kpi_tenant_source_date" in source_text, (
        "migration 004 must create constraint 'uq_source_daily_kpi_tenant_source_date' "
        "on source_daily_kpi (3-col: tenant_id + source + date — Pitfall 5)"
    )


# ── Idempotent seed UPDATE test ───────────────────────────────────────────────


def test_business_hours_seed_is_idempotent() -> None:
    """upgrade() must seed business_hours in funnel_config with idempotency guard (D-07).

    The UPDATE must include a guard so re-running the migration doesn't overwrite
    manually configured business hours. Same pattern as migration 003 funnel_config seed.
    """
    _require_migration()
    source_text = MIGRATION_PATH.read_text()

    assert "UPDATE tenants" in source_text or "update tenants" in source_text.lower(), (
        "migration 004 must UPDATE tenants SET funnel_config to seed business_hours"
    )
    assert "business_hours" in source_text, (
        "migration 004 UPDATE must reference 'business_hours' key (D-07)"
    )
    # Idempotency guard — same pattern as migration 003
    assert "IS NULL" in source_text, (
        "business_hours seed UPDATE must include IS NULL idempotency guard — "
        "prevents overwriting manual edits on re-run (same pattern as 003)"
    )


# ── Downgrade function tests ──────────────────────────────────────────────────


def test_downgrade_drops_metric_tables() -> None:
    """downgrade() must drop all three Phase 3 metric tables."""
    _require_migration()
    source_text = MIGRATION_PATH.read_text()
    assert "drop_table" in source_text, (
        "migration 004 downgrade() must call op.drop_table() for metric tables"
    )
    # All three table names must appear in downgrade context
    assert "source_daily_kpi" in source_text, "downgrade() must drop 'source_daily_kpi'"
    assert "salesperson_daily_kpi" in source_text, "downgrade() must drop 'salesperson_daily_kpi'"


def test_downgrade_restores_view() -> None:
    """downgrade() must restore v_mefi_leads_active to its migration 003 definition."""
    _require_migration()
    source_text = MIGRATION_PATH.read_text()
    # downgrade must drop/recreate the view
    assert "DROP VIEW" in source_text or "drop view" in source_text.lower(), (
        "migration 004 downgrade() must DROP VIEW v_mefi_leads_active to restore 003 version"
    )
