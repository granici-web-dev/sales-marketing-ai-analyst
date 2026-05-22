from __future__ import annotations

import asyncio
from calendar import monthrange
from datetime import UTC, date, datetime
from uuid import UUID

import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


def get_cf(fields: list[dict] | None, field_id: int) -> object:
    """Extract a custom field value by form-cf-ID from MEFI custom_fields list.

    Duplicated from sync_mefi_leads to avoid circular imports and satisfy
    fork-safety (no module-level cross-task imports allowed — Pitfall 8).
    """
    if not fields:
        return None
    for f in fields:
        if f.get("field_id") == field_id or f.get("id") == field_id:
            return f.get("value")
    return None


def month_window(year: int, month: int) -> tuple[date, date]:
    """Return (first_day, last_day) for the given calendar month."""
    first = date(year, month, 1)
    last = date(year, month, monthrange(year, month)[1])
    return first, last


def get_12_month_windows(reference_date: date) -> list[tuple[date, date]]:
    """Return 12 complete calendar month windows ending at the last full month.

    Excludes the current partial month (handled by incremental sync — D-04).
    Returns months oldest-first: [12 months ago, 11 months ago, ..., last month].

    Example: reference_date=2026-05-21 →
      [(2025-05-01, 2025-05-31), ..., (2026-04-01, 2026-04-30)]
    """
    windows = []
    for i in range(12, 0, -1):  # 12 months ago down to 1 month ago
        m = reference_date.month - i
        y = reference_date.year
        while m <= 0:
            m += 12
            y -= 1
        windows.append(month_window(y, m))
    return windows


@celery_app.task(
    bind=True,
    max_retries=5,
    default_retry_delay=120,
    name="tasks.etl.backfill_mefi_leads",
)
def backfill_mefi_leads(self, tenant_id: str) -> dict:  # type: ignore[no-untyped-def]
    """One-time historical backfill for 12 months of MEFI lead data.

    Auto-triggered by sync_mefi_leads when raw_mefi_leads count is 0 (first sync).
    Runs on the 'backfill' Celery queue to avoid blocking the daily default queue.

    Idempotent — uses the same bulk UPSERT path as sync_mefi_leads, safe to re-run.
    Does NOT trigger metrics/anomaly/insights chain — standalone data fill only.

    Args:
        tenant_id: UUID string for the tenant to backfill.
    """
    return asyncio.run(_backfill_async(UUID(tenant_id)))


async def _backfill_async(tenant_id: UUID) -> dict:
    """Core backfill coroutine — all I/O imports deferred to this body (Pitfall 8)."""
    # Deferred imports — must stay inside this function body (Pitfall 8 / INFRA-05)
    from app.core.config import settings
    from app.core.tenancy import set_tenant_id
    from app.db.session import AsyncSessionLocal
    from app.services.integrations.mefi import MefiClient
    from app.services.repositories.mefi_repository import MefiRepository

    set_tenant_id(tenant_id)
    today = datetime.now(UTC).date()
    windows = get_12_month_windows(today)

    log = logger.bind(
        tenant_id=str(tenant_id),
        task="backfill_mefi_leads",
        total_months=len(windows),
    )
    log.info("backfill.start", first_month=str(windows[0][0]), last_month=str(windows[-1][0]))

    total_synced = 0

    async with AsyncSessionLocal() as session:
        repo = MefiRepository(session, tenant_id)

        async with MefiClient(api_key=settings.mefi_api_key) as client:
            for month_start, month_end in windows:
                month_count = 0
                page = 1

                while True:
                    response = await client.search_leads(
                        filters={
                            "lifecycle": ["active", "lost", "junk"],
                            "date_from": month_start.isoformat(),
                            "date_to": month_end.isoformat(),
                            "date_field": "created_at",
                        },
                        page=page,
                        per_page=100,
                        sort="created_at",
                        order="asc",
                    )

                    if not response.leads:
                        break

                    rows = []
                    salesperson_pairs: list[tuple[int, str]] = []
                    now = datetime.now(UTC)

                    for lead in response.leads:
                        cf = lead.custom_fields if lead.custom_fields else []
                        offer_raw = get_cf(cf, 20)
                        offer_flag: bool | None = None
                        if offer_raw == "✅DA":
                            offer_flag = True
                        elif offer_raw == "❌NU":
                            offer_flag = False

                        rows.append({
                            "tenant_id": tenant_id,
                            "external_id": str(lead.id),
                            "status_id": lead.status.id if lead.status else None,
                            "status_name": lead.status.name if lead.status else None,
                            "source_id": lead.source.id if lead.source else None,
                            "source_name": lead.source.name if lead.source else None,
                            "lifecycle": lead.lifecycle or "active",
                            "assigned_to_id": lead.assigned_to.id if lead.assigned_to else None,
                            "assigned_to_name": lead.assigned_to.name if lead.assigned_to else None,
                            "estimated_value": lead.estimated_value,
                            "priority": lead.priority,
                            "is_duplicate": lead.is_duplicate or False,
                            "created_at_source": lead.created_at,
                            "last_contact_at": lead.last_contact_at,
                            "status_changed_at": lead.status_changed_at,
                            "showroom": get_cf(cf, 14),
                            "offer_sent_flag": offer_flag,
                            "utm_source": get_cf(cf, 38),
                            "utm_campaign": get_cf(cf, 39),
                            "utm_content": get_cf(cf, 40),
                            "utm_medium": get_cf(cf, 41),
                            "custom_fields_raw": [f.model_dump() for f in cf] if cf else None,
                            "raw_payload": lead.model_dump(),
                            "synced_at": now,
                        })

                        if lead.assigned_to and lead.assigned_to.id:
                            salesperson_pairs.append(
                                (lead.assigned_to.id, lead.assigned_to.name or "")
                            )

                    await repo.bulk_upsert_leads(rows)
                    await repo.upsert_salespeople(salesperson_pairs)
                    month_count += len(rows)

                    if len(response.leads) < 100:
                        break
                    page += 1

                total_synced += month_count
                log.info(
                    "backfill.month_complete",
                    month=str(month_start),
                    leads_synced=month_count,
                    total_so_far=total_synced,
                )

    log.info("backfill.complete", total_synced=total_synced)
    return {"status": "success", "total_synced": total_synced}
