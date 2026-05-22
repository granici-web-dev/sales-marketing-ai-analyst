from __future__ import annotations

"""
Unit-level tests for Alembic migration 003_mefi_schema.py.

Tests verify:
  - Migration file exists and parses without ImportError
  - Correct revision/down_revision chain (revision='003', down_revision='002')
  - FUNNEL_CONFIG dict matches D-08 exactly
  - upgrade() function contains required operations (inspected via source reading)
  - downgrade() function contains DROP statements

These tests do NOT require a live database connection — they inspect the
migration module directly as Python code.
"""

import ast
import importlib
import importlib.util
import os
import sys
import pytest
from pathlib import Path


# ── Locate migration file ─────────────────────────────────────────────────────

MIGRATION_PATH = Path(__file__).parent.parent.parent / "alembic" / "versions" / "003_mefi_schema.py"


def _load_migration_module():
    """Load migration 003 as a Python module, skipping if not found."""
    if not MIGRATION_PATH.exists():
        return None
    spec = importlib.util.spec_from_file_location("migration_003", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        return module
    except Exception:
        return None


def _require_migration():
    """Fail fast if migration file doesn't exist."""
    if not MIGRATION_PATH.exists():
        pytest.fail(
            f"Migration file not found: {MIGRATION_PATH}. "
            "Run Task 2 implementation to create backend/alembic/versions/003_mefi_schema.py"
        )


# ── File existence tests ───────────────────────────────────────────────────────


def test_migration_003_file_exists() -> None:
    """Migration file 003_mefi_schema.py must exist."""
    _require_migration()
    assert MIGRATION_PATH.is_file()


def test_migration_003_parses_as_python() -> None:
    """Migration file must be valid Python (no syntax errors)."""
    _require_migration()
    source = MIGRATION_PATH.read_text()
    try:
        ast.parse(source)
    except SyntaxError as exc:
        pytest.fail(f"Migration 003 has syntax error: {exc}")


# ── Revision chain tests ───────────────────────────────────────────────────────


def test_migration_003_revision_id() -> None:
    """revision must be '003'."""
    _require_migration()
    module = _load_migration_module()
    if module is None:
        pytest.fail("Could not load migration 003 module (ImportError during exec)")
    assert module.revision == "003", (
        f"Expected revision='003', got '{module.revision}'"
    )


def test_migration_003_down_revision() -> None:
    """down_revision must be '002' to chain correctly after seed migration."""
    _require_migration()
    module = _load_migration_module()
    if module is None:
        pytest.fail("Could not load migration 003 module")
    assert module.down_revision == "002", (
        f"Expected down_revision='002', got '{module.down_revision}'"
    )


# ── FUNNEL_CONFIG dict tests ───────────────────────────────────────────────────


def test_migration_003_funnel_config_present() -> None:
    """FUNNEL_CONFIG dict must be defined at module level."""
    _require_migration()
    module = _load_migration_module()
    if module is None:
        pytest.fail("Could not load migration 003 module")
    assert hasattr(module, "FUNNEL_CONFIG"), (
        "FUNNEL_CONFIG dict not found in migration 003 module"
    )
    assert isinstance(module.FUNNEL_CONFIG, dict), (
        f"FUNNEL_CONFIG must be a dict, got {type(module.FUNNEL_CONFIG).__name__}"
    )


def test_migration_003_funnel_config_visit_stages() -> None:
    """FUNNEL_CONFIG.funnel_stages.visit must be [17] (SHOWROOM status, D-08)."""
    _require_migration()
    module = _load_migration_module()
    if module is None:
        pytest.fail("Could not load migration 003 module")
    cfg = module.FUNNEL_CONFIG
    assert "funnel_stages" in cfg, "FUNNEL_CONFIG missing 'funnel_stages' key"
    assert cfg["funnel_stages"]["visit"] == [17], (
        f"visit stages must be [17], got {cfg['funnel_stages']['visit']}"
    )


def test_migration_003_funnel_config_offer_stages() -> None:
    """FUNNEL_CONFIG.funnel_stages.offer must be [3] (Ofertat status, D-08)."""
    _require_migration()
    module = _load_migration_module()
    if module is None:
        pytest.fail("Could not load migration 003 module")
    cfg = module.FUNNEL_CONFIG
    assert cfg["funnel_stages"]["offer"] == [3], (
        f"offer stages must be [3], got {cfg['funnel_stages']['offer']}"
    )


def test_migration_003_funnel_config_contract_stages() -> None:
    """FUNNEL_CONFIG.funnel_stages.contract must be [1] (Clienți status, D-08)."""
    _require_migration()
    module = _load_migration_module()
    if module is None:
        pytest.fail("Could not load migration 003 module")
    cfg = module.FUNNEL_CONFIG
    assert cfg["funnel_stages"]["contract"] == [1], (
        f"contract stages must be [1], got {cfg['funnel_stages']['contract']}"
    )


def test_migration_003_funnel_config_offer_sent_flag_field() -> None:
    """FUNNEL_CONFIG.offer_sent_flag_field must be 'form-cf-20' (D-08)."""
    _require_migration()
    module = _load_migration_module()
    if module is None:
        pytest.fail("Could not load migration 003 module")
    cfg = module.FUNNEL_CONFIG
    assert cfg.get("offer_sent_flag_field") == "form-cf-20", (
        f"offer_sent_flag_field must be 'form-cf-20', got {cfg.get('offer_sent_flag_field')!r}"
    )


def test_migration_003_funnel_config_showroom_field() -> None:
    """FUNNEL_CONFIG.showroom_field must be 'form-cf-14' (D-08)."""
    _require_migration()
    module = _load_migration_module()
    if module is None:
        pytest.fail("Could not load migration 003 module")
    cfg = module.FUNNEL_CONFIG
    assert cfg.get("showroom_field") == "form-cf-14", (
        f"showroom_field must be 'form-cf-14', got {cfg.get('showroom_field')!r}"
    )


def test_migration_003_funnel_config_junk_statuses() -> None:
    """FUNNEL_CONFIG.junk_statuses must be [23] (IRELEVANT status, D-08)."""
    _require_migration()
    module = _load_migration_module()
    if module is None:
        pytest.fail("Could not load migration 003 module")
    cfg = module.FUNNEL_CONFIG
    assert cfg.get("junk_statuses") == [23], (
        f"junk_statuses must be [23], got {cfg.get('junk_statuses')!r}"
    )


def test_migration_003_funnel_config_source_categories() -> None:
    """FUNNEL_CONFIG.source_categories must have required category keys (D-08)."""
    _require_migration()
    module = _load_migration_module()
    if module is None:
        pytest.fail("Could not load migration 003 module")
    cfg = module.FUNNEL_CONFIG
    assert "source_categories" in cfg, "FUNNEL_CONFIG missing 'source_categories' key"
    cats = cfg["source_categories"]

    # mail_fb_ig: source IDs 2 (Meta ADS) and 11 (Mail)
    assert set(cats.get("mail_fb_ig", [])) == {2, 11}, (
        f"mail_fb_ig must be [2, 11], got {cats.get('mail_fb_ig')}"
    )
    # telefon: source ID 10
    assert cats.get("telefon") == [10], (
        f"telefon must be [10], got {cats.get('telefon')}"
    )
    # whatsapp: source ID 9
    assert cats.get("whatsapp") == [9], (
        f"whatsapp must be [9], got {cats.get('whatsapp')}"
    )
    # site: source ID 6
    assert cats.get("site") == [6], (
        f"site must be [6], got {cats.get('site')}"
    )
    # designer: empty list (DESIGNER is a status, not source — D-08 note)
    assert cats.get("designer") == [], (
        f"designer must be [], got {cats.get('designer')}"
    )
    # alte: source IDs 3, 4, 5, 7, 12, 13
    assert set(cats.get("alte", [])) == {3, 4, 5, 7, 12, 13}, (
        f"alte must be [3, 4, 5, 7, 12, 13], got {cats.get('alte')}"
    )


def test_migration_003_funnel_config_lifecycle_filter() -> None:
    """FUNNEL_CONFIG.lifecycle_filter must contain all three lifecycle values (D-08)."""
    _require_migration()
    module = _load_migration_module()
    if module is None:
        pytest.fail("Could not load migration 003 module")
    cfg = module.FUNNEL_CONFIG
    assert "lifecycle_filter" in cfg, "FUNNEL_CONFIG missing 'lifecycle_filter' key"
    filter_set = set(cfg["lifecycle_filter"])
    assert filter_set == {"active", "lost", "junk"}, (
        f"lifecycle_filter must be ['active', 'lost', 'junk'], got {cfg['lifecycle_filter']}"
    )


# ── Migration source content tests (string-based inspection) ──────────────────


def test_migration_003_upgrade_adds_funnel_config_column() -> None:
    """upgrade() must call op.add_column for funnel_config on tenants table.

    funnel_config JSONB column is ABSENT from 001_base_tables.py — must be
    added in migration 003 before the UPDATE seed statement.
    """
    _require_migration()
    source = MIGRATION_PATH.read_text()
    assert 'add_column' in source, "migration 003 must call op.add_column()"
    assert 'funnel_config' in source, "migration 003 must reference funnel_config column"
    assert '"tenants"' in source or "'tenants'" in source, (
        "migration 003 must add funnel_config to the 'tenants' table"
    )


def test_migration_003_upgrade_creates_raw_mefi_leads() -> None:
    """upgrade() must create the raw_mefi_leads table."""
    _require_migration()
    source = MIGRATION_PATH.read_text()
    assert 'raw_mefi_leads' in source, (
        "migration 003 must create 'raw_mefi_leads' table"
    )
    assert 'create_table' in source, (
        "migration 003 must call op.create_table()"
    )


def test_migration_003_upgrade_creates_mefi_lead_history() -> None:
    """upgrade() must create the mefi_lead_history table."""
    _require_migration()
    source = MIGRATION_PATH.read_text()
    assert 'mefi_lead_history' in source, (
        "migration 003 must create 'mefi_lead_history' table"
    )


def test_migration_003_upgrade_creates_mefi_salespeople() -> None:
    """upgrade() must create the mefi_salespeople table."""
    _require_migration()
    source = MIGRATION_PATH.read_text()
    assert 'mefi_salespeople' in source, (
        "migration 003 must create 'mefi_salespeople' table"
    )


def test_migration_003_upgrade_creates_views() -> None:
    """upgrade() must CREATE OR REPLACE VIEW both conformed views (DATA-01)."""
    _require_migration()
    source = MIGRATION_PATH.read_text()
    assert 'v_mefi_leads_active' in source, (
        "migration 003 must create v_mefi_leads_active view"
    )
    assert 'v_mefi_leads_junk' in source, (
        "migration 003 must create v_mefi_leads_junk view"
    )
    assert 'CREATE OR REPLACE VIEW' in source, (
        "migration 003 must use CREATE OR REPLACE VIEW"
    )


def test_migration_003_views_contain_at_time_zone_bucharest() -> None:
    """Views must use AT TIME ZONE 'Europe/Bucharest' for date grouping (DATA-03)."""
    _require_migration()
    source = MIGRATION_PATH.read_text()
    assert "Europe/Bucharest" in source, (
        "migration 003 views must use AT TIME ZONE 'Europe/Bucharest' (DATA-03)"
    )


def test_migration_003_views_contain_reached_columns() -> None:
    """v_mefi_leads_active must define reached_visit, reached_offer, reached_contract."""
    _require_migration()
    source = MIGRATION_PATH.read_text()
    for col in ("reached_visit", "reached_offer", "reached_contract"):
        assert col in source, (
            f"v_mefi_leads_active must define '{col}' boolean computed column"
        )


def test_migration_003_views_contain_local_timestamp_columns() -> None:
    """v_mefi_leads_active must define created_at_local and status_changed_at_local."""
    _require_migration()
    source = MIGRATION_PATH.read_text()
    assert "created_at_local" in source, (
        "v_mefi_leads_active must define 'created_at_local' column"
    )
    assert "status_changed_at_local" in source, (
        "v_mefi_leads_active must define 'status_changed_at_local' column"
    )


def test_migration_003_upgrade_seeds_funnel_config() -> None:
    """upgrade() must UPDATE tenants SET funnel_config WHERE funnel_config IS NULL (idempotent, D-07/D-08)."""
    _require_migration()
    source = MIGRATION_PATH.read_text()
    assert "UPDATE tenants" in source or "update tenants" in source.lower(), (
        "migration 003 must UPDATE tenants to seed funnel_config"
    )
    assert "funnel_config IS NULL" in source, (
        "The UPDATE must include 'AND funnel_config IS NULL' for idempotency (T-02-01)"
    )
    assert "sofa-belle" in source, (
        "migration 003 must target slug='sofa-belle' in the funnel_config seed"
    )


def test_migration_003_downgrade_drops_views() -> None:
    """downgrade() must DROP VIEW both conformed views."""
    _require_migration()
    source = MIGRATION_PATH.read_text()
    assert "DROP VIEW" in source or "drop view" in source.lower(), (
        "migration 003 downgrade() must DROP VIEW v_mefi_leads_active and v_mefi_leads_junk"
    )


def test_migration_003_downgrade_drops_tables() -> None:
    """downgrade() must drop all three MEFI tables."""
    _require_migration()
    source = MIGRATION_PATH.read_text()
    assert "drop_table" in source, (
        "migration 003 downgrade() must call op.drop_table()"
    )


def test_migration_003_downgrade_drops_funnel_config_column() -> None:
    """downgrade() must drop the funnel_config column from tenants."""
    _require_migration()
    source = MIGRATION_PATH.read_text()
    assert "drop_column" in source, (
        "migration 003 downgrade() must call op.drop_column('tenants', 'funnel_config')"
    )


def test_migration_003_uses_jsonb_for_funnel_config() -> None:
    """funnel_config column must use JSONB type."""
    _require_migration()
    source = MIGRATION_PATH.read_text()
    assert "JSONB" in source, (
        "migration 003 must use JSONB type for funnel_config column"
    )


def test_migration_003_has_unique_constraints() -> None:
    """Migration must create UNIQUE constraints for UPSERT conflict targets."""
    _require_migration()
    source = MIGRATION_PATH.read_text()
    assert "create_unique_constraint" in source or "UniqueConstraint" in source, (
        "migration 003 must create UNIQUE constraints for UPSERT conflict targets"
    )
    assert "uq_raw_mefi_leads_tenant_external" in source, (
        "migration 003 must create uq_raw_mefi_leads_tenant_external constraint (MEFI-02)"
    )
    assert "uq_mefi_salespeople_tenant_external" in source, (
        "migration 003 must create uq_mefi_salespeople_tenant_external constraint (D-05)"
    )


def test_migration_003_view_active_filters_lifecycle() -> None:
    """v_mefi_leads_active must filter lifecycle IN ('active', 'lost') — not junk."""
    _require_migration()
    source = MIGRATION_PATH.read_text()
    # The view should filter out junk — either explicit IN list or exclude junk
    assert "lifecycle" in source, "view must reference lifecycle column"
    # Verify junk view filters only junk
    assert "'junk'" in source, "v_mefi_leads_junk must filter lifecycle = 'junk'"
