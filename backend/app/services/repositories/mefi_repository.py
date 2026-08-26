from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import CursorResult, func, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession


class MefiRepository:
    """Database write layer for MEFI CRM raw data.

    All write operations go through SQLAlchemy Core (pg_insert) with explicit
    tenant_id in every row dict — bypasses the ORM tenant filter which only
    fires on SELECT statements. CLAUDE.md Principle #3: every INSERT row MUST
    carry tenant_id or bulk_upsert_leads raises ValueError.

    Phase 2 Plan 03 — called by sync_mefi_leads and backfill_mefi_leads tasks.
    """

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def bulk_upsert_leads(self, rows: list[dict]) -> int:
        """Upsert a batch of lead rows into raw_mefi_leads.

        Uses PostgreSQL INSERT ... ON CONFLICT DO UPDATE so the operation is
        idempotent — safe to re-run on the same data (MEFI-02).

        Args:
            rows: List of dicts, each MUST contain tenant_id (validated here).

        Returns:
            Number of rows affected (inserted + updated).

        Raises:
            ValueError: If any row is missing tenant_id.
        """
        if not rows:
            return 0

        for row in rows:
            if "tenant_id" not in row or row["tenant_id"] is None:
                raise ValueError(
                    f"MefiRepository.bulk_upsert_leads: row missing tenant_id — "
                    f"external_id={row.get('external_id', '<unknown>')}"
                )

        from app.models.mefi import RawMefiLead  # deferred — fork-safe

        update_cols = [
            "status_id",
            "status_name",
            "source_id",
            "source_name",
            "lifecycle",
            "assigned_to_id",
            "assigned_to_name",
            "estimated_value",
            "priority",
            "is_duplicate",
            "last_contact_at",
            "status_changed_at",
            "showroom",
            "offer_sent_flag",
            "utm_source",
            "utm_campaign",
            "utm_content",
            "utm_medium",
            "custom_fields_raw",
            "raw_payload",
            "synced_at",
            "updated_at",  # keep updated_at current on every sync
        ]

        stmt = pg_insert(RawMefiLead).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["tenant_id", "external_id"],
            set_={col: stmt.excluded[col] for col in update_cols},
        )
        result = cast("CursorResult[Any]", await self._session.execute(stmt))
        await self._session.commit()
        return result.rowcount

    async def detect_and_record_history(self, incoming_rows: list[dict]) -> list[dict]:
        """Detect status changes between stored and incoming data.

        SELECTs current status_id for all incoming external_ids, compares
        against the incoming status_id, and returns history row dicts for
        any detected changes.

        Args:
            incoming_rows: Lead row dicts from the current sync batch.

        Returns:
            List of history row dicts ready for insert_history_rows().
        """
        if not incoming_rows:
            return []

        from app.models.mefi import RawMefiLead  # deferred — fork-safe

        external_ids = [r["external_id"] for r in incoming_rows]

        stmt = select(
            RawMefiLead.external_id,
            RawMefiLead.status_id,
            RawMefiLead.status_name,
        ).where(
            RawMefiLead.tenant_id == self._tenant_id,
            RawMefiLead.external_id.in_(external_ids),
        )
        result = cast("CursorResult[Any]", await self._session.execute(stmt))
        stored = {row.external_id: row for row in result}

        history_rows = []
        now = datetime.now(UTC)
        for row in incoming_rows:
            ext_id = row["external_id"]
            new_status_id = row.get("status_id")
            new_status_name = row.get("status_name")

            # Skip leads with no status — to_status_id is NOT NULL in schema (MEFI-06)
            if new_status_id is None:
                continue

            if ext_id not in stored:
                # New lead — record initial status as a history entry
                history_rows.append(
                    {
                        "tenant_id": self._tenant_id,
                        "lead_external_id": ext_id,
                        "changed_at": now,
                        "from_status_id": None,
                        "from_status_name": None,
                        "to_status_id": new_status_id,
                        "to_status_name": new_status_name,
                    }
                )
            elif stored[ext_id].status_id != new_status_id:
                # Status changed — record the transition
                history_rows.append(
                    {
                        "tenant_id": self._tenant_id,
                        "lead_external_id": ext_id,
                        "changed_at": now,
                        "from_status_id": stored[ext_id].status_id,
                        "from_status_name": stored[ext_id].status_name,
                        "to_status_id": new_status_id,
                        "to_status_name": new_status_name,
                    }
                )

        return history_rows

    async def insert_history_rows(self, history_rows: list[dict]) -> None:
        """Bulk-insert status change history rows.

        No ON CONFLICT — multiple history rows per lead are expected and correct
        (one per detected change per sync).

        Args:
            history_rows: List of dicts from detect_and_record_history().
        """
        if not history_rows:
            return

        from app.models.mefi import MefiLeadHistory  # deferred — fork-safe

        stmt = insert(MefiLeadHistory).values(history_rows)
        await self._session.execute(stmt)
        await self._session.commit()

    async def upsert_salespeople(self, assigned_to_pairs: list[tuple[int, str]]) -> None:
        """Upsert salesperson records discovered from lead assignment data.

        Uses ON CONFLICT DO NOTHING — existing records are not overwritten
        because is_active and showroom are set manually by admins (D-06).

        Args:
            assigned_to_pairs: List of (external_id, name) tuples.
        """
        if not assigned_to_pairs:
            return

        from app.models.mefi import MefiSalesperson  # deferred — fork-safe

        rows = [
            {
                "tenant_id": self._tenant_id,
                "external_id": sp_id,
                "name": sp_name,
                "is_active": None,
                "showroom": None,
            }
            for sp_id, sp_name in assigned_to_pairs
            if sp_id is not None
        ]
        if not rows:
            return

        stmt = pg_insert(MefiSalesperson).values(rows).on_conflict_do_nothing()
        await self._session.execute(stmt)
        await self._session.commit()

    async def get_lead_count_for_tenant(self) -> int:
        """Return total number of raw_mefi_leads rows for this tenant.

        Used by sync_mefi_leads to detect first-ever sync and trigger backfill.
        """
        from app.models.mefi import RawMefiLead  # deferred — fork-safe

        stmt = (
            select(func.count())
            .select_from(RawMefiLead)
            .where(RawMefiLead.tenant_id == self._tenant_id)
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def get_last_sync_at(self) -> datetime | None:
        """Return completed_at of the most recent successful MEFI sync.

        Returns None if no prior successful sync exists (first run).
        """
        from app.models.pipeline import SyncRun  # deferred — fork-safe

        stmt = select(func.max(SyncRun.completed_at)).where(
            SyncRun.tenant_id == self._tenant_id,
            SyncRun.source == "mefi",
            SyncRun.status == "success",
        )
        result = cast("CursorResult[Any]", await self._session.execute(stmt))
        return result.scalar_one_or_none()
