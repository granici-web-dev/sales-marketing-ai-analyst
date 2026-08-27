"""Гоняет настоящий код чтения дашбордов, чтобы auto_explain снял планы.

Запросы не переписаны от руки: их выдаёт сам сервис. Переписанный от руки
запрос проверяет переписывание, а не продукт — а расходятся они как раз там,
где интересно (ORM добавляет условие изоляции, вид разворачивается в подзапрос).

Планы пишет база, а не этот файл:

    for s in "auto_explain.log_min_duration = 0" "auto_explain.log_analyze = on" \
             "auto_explain.log_buffers = on" "auto_explain.log_nested_statements = on"; do
      psql ... -c "ALTER SYSTEM SET $s"
    done
    # session_preload_libraries = 'auto_explain' требует перезапуска

Между дашбордами вставляется запрос-метка, чтобы в журнале базы было видно,
где кончается один и начинается другой.

    DATABASE_URL=... PYTHONPATH=. python backend/scripts/query-plans.py [slug] [дней]
"""

from __future__ import annotations

import asyncio
import sys
import time
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import text

from app.core.tenancy import set_tenant_id
from app.db.session import AsyncSessionLocal, engine
from app.services.dashboards.dashboard_read_service import DashboardReadService

SLUG = sys.argv[1] if len(sys.argv) > 1 else "sofa-belle"
DAYS = int(sys.argv[2]) if len(sys.argv) > 2 else 90


async def main() -> None:
    async with AsyncSessionLocal() as session:
        tenant_id = UUID(
            str(
                (
                    await session.execute(
                        text("SELECT id FROM tenants WHERE slug = :slug"), {"slug": SLUG}
                    )
                ).scalar_one()
            )
        )
    set_tenant_id(tenant_id)

    to_date = date.today()
    from_date = to_date - timedelta(days=DAYS - 1)
    print(f"клиент {SLUG} ({tenant_id}), окно {from_date} … {to_date}")

    async with AsyncSessionLocal() as session:
        service = DashboardReadService(session, tenant_id)
        cases = (
            ("SALES", lambda: service.get_sales_dashboard(from_date, to_date)),
            ("SALESPEOPLE", lambda: service.get_salespeople_dashboard(from_date, to_date)),
            ("MARKETING", lambda: service.get_marketing_dashboard(from_date, to_date)),
            ("STUCK", lambda: service.get_stuck_offers(from_date, to_date)),
        )
        for label, call in cases:
            await session.execute(text(f"SELECT 'РАЗДЕЛ {label}' AS mark"))
            started = time.perf_counter()
            await call()
            print(f"  {label}: {(time.perf_counter() - started) * 1000:.0f} ms")
        await session.execute(text("SELECT 'РАЗДЕЛ КОНЕЦ' AS mark"))

    await engine.dispose()


asyncio.run(main())
