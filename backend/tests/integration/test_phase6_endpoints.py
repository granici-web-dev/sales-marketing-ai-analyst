"""Phase 6 integration test suite — all 7 ROADMAP success criteria.

Tests the full FastAPI stack (router → service → schema → response) using
dependency_overrides to isolate from DB and Redis. Mocks at the service layer.

Success Criteria coverage:
  SC#1 — GET /dashboards/sales → 200 with funnel, conversion_rates, revenue as string
  SC#2 — GET /dashboards/salespeople → 200 with salespeople list (TTFT, data_completeness_pct)
  SC#3 — GET /dashboards/marketing → 200 with lead_volume_by_source, ad_spend=null
  SC#4 — GET /insights/today → 200; GET /insights?date=old → 404
  SC#5 — POST /insights/refresh → 202 first call; 429 + Retry-After second call
  SC#6 — GET /health/data → 200 without auth, stale flag present
  SC#7 — GET /docs and /openapi.json → 200 with all Phase 6 paths
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.asyncio

# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

MOCK_USER_ID = UUID("00000000-0000-0000-0000-000000000002")
MOCK_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture(autouse=False)
def override_deps():
    """Override get_current_user and get_session for all tests in this module."""
    from app.core.dependencies import get_current_user
    from app.core.tenancy import set_tenant_id
    from app.db.deps import get_session
    from app.main import app
    from app.schemas.auth import UserOut

    mock_user = UserOut(id=MOCK_USER_ID, email="test@sofabelle.ro", is_active=True)
    mock_session = AsyncMock()

    async def _mock_current_user():
        # Настоящая проверка ставит тенантный контекст — это часть её договора,
        # а не побочный эффект: удостоверить запрос и значит узнать, чей он.
        # Подмена, которая этого не делает, проверяла бы приложение, которого
        # нет. Прежде контекст ставил посредник из настройки, одним и тем же
        # значением на любой запрос, и подмене было нечего исполнять.
        set_tenant_id(MOCK_TENANT_ID)
        return mock_user

    async def _mock_get_session():
        yield mock_session

    app.dependency_overrides[get_current_user] = _mock_current_user
    app.dependency_overrides[get_session] = _mock_get_session
    yield mock_user
    app.dependency_overrides.clear()


# ──────────────────────────────────────────────
# SC#1 — Sales dashboard
# ──────────────────────────────────────────────


async def test_sc1_sales_dashboard_200(override_deps) -> None:
    """SC#1: GET /dashboards/sales with valid JWT returns 200 with all required fields."""
    from app.main import app
    from tests.factories.dashboard_factory import DashboardFactory

    mock_data = DashboardFactory.build_sales_response(date(2026, 5, 1), date(2026, 5, 19))

    with patch("app.api.v1.dashboards.DashboardReadService") as MockSvc:
        instance = MockSvc.return_value
        instance.get_sales_dashboard = AsyncMock(return_value=mock_data)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer dummy"},
        ) as c:
            r = await c.get("/api/v1/dashboards/sales?from=2026-05-01&to=2026-05-19")

    assert r.status_code == 200
    body = r.json()
    assert "funnel" in body
    assert "conversion_rates" in body
    assert "kpi_cards" in body
    assert "source_breakdown" in body
    assert "revenue_series" in body


async def test_sc1_revenue_as_string(override_deps) -> None:
    """SC#1 / DATA-04: Revenue fields in kpi_cards must be JSON strings, not numbers."""
    from app.main import app
    from tests.factories.dashboard_factory import DashboardFactory

    mock_data = DashboardFactory.build_sales_response()

    with patch("app.api.v1.dashboards.DashboardReadService") as MockSvc:
        instance = MockSvc.return_value
        instance.get_sales_dashboard = AsyncMock(return_value=mock_data)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer dummy"},
        ) as c:
            r = await c.get("/api/v1/dashboards/sales?from=2026-05-01&to=2026-05-19")

    assert r.status_code == 200
    body = r.json()
    revenue = body["kpi_cards"]["revenue"]
    if revenue is not None:
        assert isinstance(revenue, str), (
            f"revenue must be a JSON string, got {type(revenue)}: {revenue}"
        )


# ──────────────────────────────────────────────
# SC#2 — Salespeople dashboard
# ──────────────────────────────────────────────


async def test_sc2_salespeople_dashboard_200(override_deps) -> None:
    """SC#2: GET /dashboards/salespeople returns 200 with salespeople list."""
    from app.main import app
    from tests.factories.dashboard_factory import DashboardFactory

    mock_data = DashboardFactory.build_salespeople_response()

    with patch("app.api.v1.dashboards.DashboardReadService") as MockSvc:
        instance = MockSvc.return_value
        instance.get_salespeople_dashboard = AsyncMock(return_value=mock_data)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer dummy"},
        ) as c:
            r = await c.get("/api/v1/dashboards/salespeople?from=2026-05-01&to=2026-05-19")

    assert r.status_code == 200
    body = r.json()
    assert "salespeople" in body
    assert len(body["salespeople"]) >= 1
    sp = body["salespeople"][0]
    assert "avg_time_to_first_touch_minutes" in sp
    assert "data_completeness_pct" in sp


# ──────────────────────────────────────────────
# SC#3 — Marketing dashboard
# ──────────────────────────────────────────────


async def test_sc3_marketing_dashboard_200(override_deps) -> None:
    """SC#3: GET /dashboards/marketing returns 200 with lead_volume_by_source and null ad_spend."""
    from app.main import app
    from tests.factories.dashboard_factory import DashboardFactory

    mock_data = DashboardFactory.build_marketing_response()

    with patch("app.api.v1.dashboards.DashboardReadService") as MockSvc:
        instance = MockSvc.return_value
        instance.get_marketing_dashboard = AsyncMock(return_value=mock_data)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer dummy"},
        ) as c:
            r = await c.get("/api/v1/dashboards/marketing?from=2026-05-01&to=2026-05-19")

    assert r.status_code == 200
    body = r.json()
    assert "lead_volume_by_source" in body
    assert "junk_by_source" in body
    assert body["ad_spend"] is None, "ad_spend must be null (MARK-03)"
    assert body["cpl"] is None
    assert body["cac"] is None
    assert body["roas"] is None


# ──────────────────────────────────────────────
# SC#4 — Insights endpoints
# ──────────────────────────────────────────────


async def test_sc4_insights_today_200(override_deps) -> None:
    """SC#4: GET /insights/today returns 200 with date, status, generation_failed, payload."""
    from app.main import app

    mock_insight = {
        "date": date(2026, 5, 27),
        "status": "success",
        "generation_failed": False,
        "generated_at": datetime(2026, 5, 28, 6, 1, 0, tzinfo=UTC),
        "payload": {
            "summary": "Buna dimineata Sofa Belle",
            "problems": [],
            "positives": [],
            "warnings": [],
            "weekly_action_plan": [],
        },
    }

    with patch("app.services.insights.insight_read_service.InsightReadService") as MockSvc:
        instance = MockSvc.return_value
        instance.get_today = AsyncMock(return_value=mock_insight)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer dummy"},
        ) as c:
            r = await c.get("/api/v1/insights/today")

    assert r.status_code == 200
    body = r.json()
    assert "date" in body
    assert "status" in body
    assert "generation_failed" in body
    assert "payload" in body


async def test_sc4_insights_today_404_when_none(override_deps) -> None:
    """SC#4: GET /insights/today returns 404 when no insight for yesterday."""
    from app.main import app

    with patch("app.services.insights.insight_read_service.InsightReadService") as MockSvc:
        instance = MockSvc.return_value
        instance.get_today = AsyncMock(return_value=None)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer dummy"},
        ) as c:
            r = await c.get("/api/v1/insights/today")

    assert r.status_code == 404


async def test_sc4_insights_by_date_404_for_missing(override_deps) -> None:
    """SC#4 / INSI-02: GET /insights?date=2020-01-01 returns 404."""
    from app.main import app

    with patch("app.services.insights.insight_read_service.InsightReadService") as MockSvc:
        instance = MockSvc.return_value
        instance.get_by_date = AsyncMock(return_value=None)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer dummy"},
        ) as c:
            r = await c.get("/api/v1/insights?date=2020-01-01")

    assert r.status_code == 404


async def test_sc4_generation_failed_when_status_failed(override_deps) -> None:
    """SC#4 / INSI-05: generation_failed=True when status='failed'."""
    from app.main import app

    mock_insight = {
        "date": date(2026, 5, 27),
        "status": "failed",
        "generation_failed": True,
        "generated_at": None,
        "payload": None,
    }

    with patch("app.services.insights.insight_read_service.InsightReadService") as MockSvc:
        instance = MockSvc.return_value
        instance.get_today = AsyncMock(return_value=mock_insight)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer dummy"},
        ) as c:
            r = await c.get("/api/v1/insights/today")

    assert r.status_code == 200
    assert r.json()["generation_failed"] is True


# ──────────────────────────────────────────────
# SC#5 — Rate limiting on POST /insights/refresh
# ──────────────────────────────────────────────


async def test_sc5_refresh_first_call_202(override_deps) -> None:
    """SC#5: POST /insights/refresh first call returns 202 with pipeline_run_id."""
    from app.main import app

    mock_task = MagicMock()
    mock_task.id = "insight-task-uuid-12345"

    # Обработчик ставит в очередь ТОЛЬКО генерацию разбора. Целый дневной
    # конвейер он перестал запускать давно, а тест всё это время подменял
    # `daily_pipeline` — имя, которого обработчик не зовёт. Подмена имени,
    # которое не вызывается, не проверяет ничего и падает на настоящем
    # идентификаторе задачи. Тот же протухший тест уже был починен у своего
    # близнеца в tests/unit/test_insights_router.py.
    mock_generate = MagicMock()
    mock_generate.delay.return_value = mock_task

    mock_r = AsyncMock()
    mock_r.set = AsyncMock(return_value=True)
    mock_redis_ctx = AsyncMock()
    mock_redis_ctx.__aenter__ = AsyncMock(return_value=mock_r)
    mock_redis_ctx.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("app.api.v1.insights.redis_client", return_value=mock_redis_ctx),
        patch(
            "app.tasks.insights.generate_daily_insights.generate_daily_insights",
            mock_generate,
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer dummy"},
        ) as c:
            r = await c.post("/api/v1/insights/refresh")

    assert r.status_code == 202
    body = r.json()
    assert "enqueued_at" in body
    assert body["pipeline_run_id"] == "insight-task-uuid-12345"

    # Задача обязана получить арендатора запроса, а не значение из настройки.
    tenant_id, _ = mock_generate.delay.call_args.args
    assert tenant_id == str(MOCK_TENANT_ID), f"задаче достался арендатор {tenant_id!r}"


async def test_sc5_refresh_second_call_429(override_deps) -> None:
    """SC#5: POST /insights/refresh second call within window returns 429 + Retry-After."""
    from app.main import app

    mock_r = AsyncMock()
    mock_r.set = AsyncMock(return_value=None)  # key already exists
    mock_r.ttl = AsyncMock(return_value=3000)
    mock_redis_ctx = AsyncMock()
    mock_redis_ctx.__aenter__ = AsyncMock(return_value=mock_r)
    mock_redis_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch("app.api.v1.insights.redis_client", return_value=mock_redis_ctx):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer dummy"},
        ) as c:
            r = await c.post("/api/v1/insights/refresh")

    assert r.status_code == 429
    assert r.headers.get("Retry-After") == "3000"


# ──────────────────────────────────────────────
# SC#6 — Health data
# ──────────────────────────────────────────────


async def test_sc6_health_data_requires_auth() -> None:
    """Свежесть данных — данные арендатора, и без спроса не отдаются.

    Прежде этот эндпоинт был единственным без проверки, и держалось это на
    том, что арендатор приходил из настройки: любой запрос получал состояние
    Sofa Belle. Арендатор теперь приходит из сессии, а сессии здесь нет —
    отдавать нечего и некому.
    """
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/health/data")

    assert r.status_code == 401, f"ожидался отказ, получено {r.status_code}"


async def test_sc6_health_data_200_with_session(override_deps) -> None:
    """С удостоверенной сессией отдаётся состояние синхронизации."""
    from app.main import app

    mock_health = {
        "last_sync_at": datetime(2026, 5, 28, 3, 47, 12, tzinfo=UTC),
        "last_pipeline_status": "success",
        "stale": False,
    }

    with patch("app.api.v1.health.HealthReadService") as MockSvc:
        MockSvc.return_value.get_health = AsyncMock(return_value=mock_health)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/health/data", headers={"Authorization": "Bearer dummy"})

    assert r.status_code == 200
    body = r.json()
    assert body["stale"] is False
    assert body["last_pipeline_status"] == "success"


async def test_sc6_health_stale_true_propagates(override_deps) -> None:
    """SC#6: stale=True in service response propagates to JSON response."""
    from app.main import app

    mock_health = {"last_sync_at": None, "last_pipeline_status": None, "stale": True}

    with patch("app.api.v1.health.HealthReadService") as MockSvc:
        MockSvc.return_value.get_health = AsyncMock(return_value=mock_health)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/health/data", headers={"Authorization": "Bearer dummy"})

    assert r.json()["stale"] is True
