"""Reconciliation test — Phase 3 contract-counting hotfix (2026-05-30).

THE GUARD that would have caught the 9-vs-21 bug: it asserts the pre-computed
aggregate (`daily_kpi.contracts_count`, summed over a month) reconciles with a
direct recomputation from the source of truth (`v_mefi_leads_active` counted by
`status_changed_at`). This is the reconciliation PATTERN to replicate for every
future aggregate metric (03-HOTFIX-contract-counting-PLAN.md §9).

Contract = a lead with status_id=1 (Clienți) whose status_changed_at (Bucharest
local) falls in the period — the EVENT model (when the deal was signed), NOT the
creation-date cohort. A lead created in February but signed in May is a MAY
contract.

Seeds its own data under a throwaway tenant inside an UNCOMMITTED transaction and
rolls back on teardown — it never pollutes real tenant data. Skips unless
TEST_DATABASE_URL is set (docker compose up -d).
"""

from __future__ import annotations

import os
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest

_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not _TEST_DB_URL,
        reason="Reconciliation test requires TEST_DATABASE_URL env var (docker compose up -d)",
    ),
]

# Throwaway tenant — distinct from Sofa Belle (…0001). Seeded + rolled back.
RECON_TENANT_ID = UUID("00000000-0000-0000-0000-0000deadbeef")


def _utc(y: int, m: int, d: int, hour: int = 12) -> datetime:
    """Build a tz-aware UTC timestamp (noon avoids any Bucharest DST date-flip)."""
    return datetime(y, m, d, hour, 0, 0, tzinfo=UTC)


# Seeded leads. Keys: ext, created, changed (status_changed_at), status, lifecycle.
# Expected contract attribution is by status_changed_at month when status_id=1
# AND lifecycle in ('active','lost') (the v_mefi_leads_active scope).
_SEED_LEADS = [
    # 1) created Feb, SIGNED May → MAY contract (the cross-month bug case)
    {
        "ext": "recon-1",
        "created": _utc(2026, 2, 10),
        "changed": _utc(2026, 5, 15),
        "status": 1,
        "lifecycle": "active",
    },
    # 2) created May, signed May → MAY contract
    {
        "ext": "recon-2",
        "created": _utc(2026, 5, 3),
        "changed": _utc(2026, 5, 20),
        "status": 1,
        "lifecycle": "active",
    },
    # 3) created May, status=3 (offer, not won) → NOT a contract
    {
        "ext": "recon-3",
        "created": _utc(2026, 5, 5),
        "changed": _utc(2026, 5, 6),
        "status": 3,
        "lifecycle": "active",
    },
    # 4) created Apr, signed Apr → APRIL contract
    {
        "ext": "recon-4",
        "created": _utc(2026, 4, 2),
        "changed": _utc(2026, 4, 25),
        "status": 1,
        "lifecycle": "active",
    },
    # 5) signed May but lifecycle=junk → excluded by the view → NOT counted
    {
        "ext": "recon-5",
        "created": _utc(2026, 5, 1),
        "changed": _utc(2026, 5, 10),
        "status": 1,
        "lifecycle": "junk",
    },
]

# Ground-truth expectation (event model): {(year, month): contracts}
_EXPECTED_BY_MONTH = {(2026, 4): 1, (2026, 5): 2}


@pytest.fixture
async def seeded_session():
    """Yield an AsyncSession with the recon tenant + leads seeded (uncommitted).

    Everything happens in one transaction that is rolled back on teardown, so the
    view sees the seeded rows during the test but nothing persists.
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    from app.core.tenancy import set_tenant_id

    engine = create_async_engine(_TEST_DB_URL, echo=False)
    session = AsyncSession(engine, expire_on_commit=False)
    set_tenant_id(RECON_TENANT_ID)

    try:
        await session.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            {"id": RECON_TENANT_ID, "name": "Recon Test", "slug": "recon-test-deadbeef"},
        )
        for lead in _SEED_LEADS:
            await session.execute(
                text(
                    """
                    INSERT INTO raw_mefi_leads
                        (id, tenant_id, external_id, status_id, source_id, lifecycle,
                         created_at_source, status_changed_at, estimated_value, is_duplicate)
                    VALUES
                        (gen_random_uuid(), :tid, :ext, :status, 5, :lifecycle,
                         :created, :changed, NULL, false)
                    """
                ),
                {
                    "tid": RECON_TENANT_ID,
                    "ext": lead["ext"],
                    "status": lead["status"],
                    "lifecycle": lead["lifecycle"],
                    "created": lead["created"],
                    "changed": lead["changed"],
                },
            )
        await session.flush()  # visible to subsequent SELECTs in this txn; not committed
        yield session
    finally:
        await session.rollback()
        await session.close()
        await engine.dispose()


async def _direct_contract_count(session, year: int, month: int) -> int:
    """Source-of-truth count: status_id=1 contracts by status_changed_at month."""
    from sqlalchemy import text

    first = date(year, month, 1)
    nxt = date(year + (month // 12), (month % 12) + 1, 1)
    result = await session.execute(
        text(
            """
            SELECT COUNT(*) FROM v_mefi_leads_active
            WHERE tenant_id = :tid
              AND status_id = 1
              AND (status_changed_at AT TIME ZONE 'Europe/Bucharest')::date >= :first
              AND (status_changed_at AT TIME ZONE 'Europe/Bucharest')::date < :nxt
            """
        ),
        {"tid": RECON_TENANT_ID, "first": first, "nxt": nxt},
    )
    return int(result.scalar_one())


@pytest.mark.asyncio
async def test_daily_kpi_contracts_reconcile_with_status_changed_at(seeded_session) -> None:
    """SUM(daily_kpi.contracts_count over a month) == direct status_changed_at count.

    RED before the hotfix: DailyKpiService counts contracts by created_at_source,
    so the Feb-created/May-signed lead lands in February and May undercounts (1
    instead of 2). GREEN after: contracts are counted by status_changed_at.
    """
    from app.services.metrics.daily_kpi_service import DailyKpiService

    svc = DailyKpiService(seeded_session, RECON_TENANT_ID)

    # Compute daily rows for every distinct event date in the seed; any other date
    # contributes 0 contracts, so summing the event dates == summing all dates.
    event_dates = sorted(
        {lead["created"].date() for lead in _SEED_LEADS}
        | {lead["changed"].date() for lead in _SEED_LEADS}
    )
    contracts_by_month: dict[tuple[int, int], int] = {}
    for d in event_dates:
        row = await svc.compute_for_date(d)
        cc = int(row.get("contracts_count") or 0)
        key = (d.year, d.month)
        contracts_by_month[key] = contracts_by_month.get(key, 0) + cc

    # 1) Service aggregates match the ground-truth expectation (event model).
    assert contracts_by_month.get((2026, 5), 0) == _EXPECTED_BY_MONTH[(2026, 5)], (
        f"May contracts: expected 2 (event model), got {contracts_by_month.get((2026, 5), 0)}. "
        "Feb-created/May-signed lead must count in MAY, not February."
    )
    assert contracts_by_month.get((2026, 4), 0) == _EXPECTED_BY_MONTH[(2026, 4)], (
        f"April contracts: expected 1, got {contracts_by_month.get((2026, 4), 0)}"
    )
    # The offer (status=3) and the junk-lifecycle lead must NOT inflate any month.
    assert contracts_by_month.get((2026, 2), 0) == 0, (
        "February must have 0 contracts — a lead created in Feb but signed in May "
        "must NOT be counted as a February contract (cohort bug)."
    )

    # 2) Reconciliation invariant: service aggregate == direct source-of-truth count.
    for (year, month), expected in _EXPECTED_BY_MONTH.items():
        direct = await _direct_contract_count(seeded_session, year, month)
        assert direct == expected, f"direct count {year}-{month}: expected {expected}, got {direct}"
        assert contracts_by_month.get((year, month), 0) == direct, (
            f"RECONCILIATION FAILURE {year}-{month}: daily_kpi sum "
            f"{contracts_by_month.get((year, month), 0)} != direct status_changed_at count {direct}"
        )


@pytest.mark.asyncio
async def test_daily_kpi_revenue_follows_signing_date(seeded_session) -> None:
    """Revenue is attributed to the signing month (status_changed_at), like contracts.

    estimated_value is NULL in seed data (mirrors the live data gap), so revenue is
    None — this test asserts the attribution wiring, i.e. no revenue leaks into
    February from the Feb-created/May-signed lead.
    """
    from app.services.metrics.daily_kpi_service import DailyKpiService

    svc = DailyKpiService(seeded_session, RECON_TENANT_ID)
    feb_row = await svc.compute_for_date(date(2026, 2, 10))
    assert (feb_row.get("contracts_count") or 0) == 0, (
        "No contract should be attributed to February for a lead signed in May"
    )
    assert feb_row.get("revenue") in (None, Decimal("0")), (
        "No revenue should be attributed to February for a May-signed contract"
    )
