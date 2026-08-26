"""Unit tests for MefiClient integration class and related components.

Covers MEFI-01, MEFI-03, MEFI-09, MEFI-10 requirements.
Uses respx to mock httpx requests (no real MEFI API calls).
"""

from __future__ import annotations

import httpx
import pytest
import respx

from app.schemas.mefi import MefiSearchResponse

# These imports will FAIL (RED) until the integration module is created.
from app.services.integrations.mefi import MefiClient, RateLimitError

VALID_SEARCH_RESPONSE = {
    "success": True,
    "data": [
        {
            "id": 42,
            "status": {"id": 39, "name": "Calificare"},
            "source": {"id": 1, "name": "Google"},
            "lifecycle": "active",
            "assigned_to": {"id": 5, "name": "Popescu Ion"},
            "estimated_value": "12500.00",
            "custom_fields": [{"field_id": 14, "value": "Brașov"}],
        }
    ],
    "meta": {"page": 1, "per_page": 100, "total": 543, "total_pages": 1},
}

EMPTY_SEARCH_RESPONSE = {
    "success": True,
    "data": [],
    "meta": {"page": 1, "per_page": 100, "total": 0, "total_pages": 0},
}

BASE_URL = "https://bellesofa.meficrm.com/api/v1"


class TestMefiClientInstantiation:
    def test_instantiation_with_api_key(self) -> None:
        """MefiClient can be instantiated with an API key."""
        client = MefiClient(api_key="lrd_test_key")
        assert client is not None

    def test_source_name_attribute(self) -> None:
        """MefiClient has source_name = 'mefi'."""
        client = MefiClient(api_key="lrd_test_key")
        assert client.source_name == "mefi"

    def test_base_url_class_attribute(self) -> None:
        """BASE_URL is the correct Sofa Belle MEFI endpoint."""
        assert MefiClient.BASE_URL == BASE_URL


class TestMefiClientSearchLeads:
    @pytest.mark.asyncio
    async def test_search_leads_returns_mefi_search_response(self) -> None:
        """search_leads returns a MefiSearchResponse instance on 200."""
        with respx.mock:
            respx.post(f"{BASE_URL}/leads/search").mock(
                return_value=httpx.Response(
                    200,
                    json=VALID_SEARCH_RESPONSE,
                    headers={"X-RateLimit-Remaining": "599"},
                )
            )
            async with MefiClient(api_key="lrd_test_key") as client:
                result = await client.search_leads(filters={})
            assert isinstance(result, MefiSearchResponse)
            assert result.meta.total == 543
            assert len(result.data) == 1

    @pytest.mark.asyncio
    async def test_search_includes_auth_header(self) -> None:
        """MEFI-01: POST /leads/search includes Authorization: Bearer header."""
        with respx.mock:
            route = respx.post(f"{BASE_URL}/leads/search").mock(
                return_value=httpx.Response(
                    200,
                    json=VALID_SEARCH_RESPONSE,
                    headers={"X-RateLimit-Remaining": "599"},
                )
            )
            async with MefiClient(api_key="lrd_my_key") as client:
                await client.search_leads(filters={})

            assert route.called
            request = route.calls[0].request
            assert request.headers["authorization"] == "Bearer lrd_my_key"

    @pytest.mark.asyncio
    async def test_search_posts_to_correct_endpoint(self) -> None:
        """search_leads POSTs to /leads/search."""
        with respx.mock:
            route = respx.post(f"{BASE_URL}/leads/search").mock(
                return_value=httpx.Response(
                    200,
                    json=VALID_SEARCH_RESPONSE,
                    headers={"X-RateLimit-Remaining": "599"},
                )
            )
            async with MefiClient(api_key="lrd_test_key") as client:
                await client.search_leads(filters={"lifecycle": ["active"]})
            assert route.called

    @pytest.mark.asyncio
    async def test_search_passes_pagination_params(self) -> None:
        """search_leads includes page, per_page, sort, order in request body."""
        import json

        with respx.mock:
            route = respx.post(f"{BASE_URL}/leads/search").mock(
                return_value=httpx.Response(
                    200,
                    json=VALID_SEARCH_RESPONSE,
                    headers={"X-RateLimit-Remaining": "599"},
                )
            )
            async with MefiClient(api_key="lrd_test_key") as client:
                await client.search_leads(
                    filters={},
                    page=2,
                    per_page=50,
                    sort="status_changed_at",
                    order="asc",
                )
            request = route.calls[0].request
            body = json.loads(request.content)
            assert body["page"] == 2
            assert body["per_page"] == 50
            assert body["sort"] == "status_changed_at"
            assert body["order"] == "asc"


class TestMefiClientRateLimit:
    @pytest.mark.asyncio
    async def test_429_raises_rate_limit_error(self) -> None:
        """MEFI-10: 429 response raises RateLimitError."""
        with respx.mock:
            respx.post(f"{BASE_URL}/leads/search").mock(
                return_value=httpx.Response(
                    429,
                    headers={"Retry-After": "30"},
                )
            )
            async with MefiClient(api_key="lrd_test_key") as client:
                with pytest.raises(RateLimitError) as exc_info:
                    await client.search_leads(filters={})
            assert exc_info.value.retry_after == 30

    @pytest.mark.asyncio
    async def test_429_default_retry_after_60(self) -> None:
        """If Retry-After header is absent, RateLimitError.retry_after defaults to 60."""
        with respx.mock:
            respx.post(f"{BASE_URL}/leads/search").mock(
                return_value=httpx.Response(429, headers={})
            )
            async with MefiClient(api_key="lrd_test_key") as client:
                with pytest.raises(RateLimitError) as exc_info:
                    await client.search_leads(filters={})
            assert exc_info.value.retry_after == 60

    def test_rate_limit_error_stores_retry_after(self) -> None:
        """RateLimitError stores retry_after attribute."""
        err = RateLimitError(retry_after=45)
        assert err.retry_after == 45


class TestMefiClientHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check_returns_true_when_total_positive(self) -> None:
        """MEFI-09: health_check returns True when total > 0."""
        with respx.mock:
            respx.post(f"{BASE_URL}/leads/search").mock(
                return_value=httpx.Response(
                    200,
                    json=VALID_SEARCH_RESPONSE,
                    headers={"X-RateLimit-Remaining": "599"},
                )
            )
            async with MefiClient(api_key="lrd_test_key") as client:
                result = await client.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_returns_false_when_total_zero(self) -> None:
        """MEFI-09: health_check returns False (not raises) when total = 0."""
        with respx.mock:
            respx.post(f"{BASE_URL}/leads/search").mock(
                return_value=httpx.Response(
                    200,
                    json=EMPTY_SEARCH_RESPONSE,
                    headers={"X-RateLimit-Remaining": "599"},
                )
            )
            async with MefiClient(api_key="lrd_test_key") as client:
                result = await client.health_check()
            # Must return False, not raise
            assert result is False

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_401(self) -> None:
        """health_check returns False on auth error — does not propagate."""
        with respx.mock:
            respx.post(f"{BASE_URL}/leads/search").mock(return_value=httpx.Response(401))
            async with MefiClient(api_key="bad_key") as client:
                result = await client.health_check()
            assert result is False


class TestMefiClientAuthenticate:
    @pytest.mark.asyncio
    async def test_authenticate_returns_true_on_200(self) -> None:
        """authenticate returns True when MEFI returns 200."""
        with respx.mock:
            respx.post(f"{BASE_URL}/leads/search").mock(
                return_value=httpx.Response(
                    200,
                    json=VALID_SEARCH_RESPONSE,
                    headers={"X-RateLimit-Remaining": "599"},
                )
            )
            async with MefiClient(api_key="lrd_valid") as client:
                result = await client.authenticate(credentials={})
            assert result is True

    @pytest.mark.asyncio
    async def test_authenticate_returns_false_on_401(self) -> None:
        """authenticate returns False on 401 (invalid key)."""
        with respx.mock:
            respx.post(f"{BASE_URL}/leads/search").mock(return_value=httpx.Response(401))
            async with MefiClient(api_key="bad_key") as client:
                result = await client.authenticate(credentials={})
            assert result is False

    @pytest.mark.asyncio
    async def test_authenticate_returns_false_on_403(self) -> None:
        """authenticate returns False on 403 (forbidden)."""
        with respx.mock:
            respx.post(f"{BASE_URL}/leads/search").mock(return_value=httpx.Response(403))
            async with MefiClient(api_key="expired_key") as client:
                result = await client.authenticate(credentials={})
            assert result is False


class TestMefiClientContextManager:
    @pytest.mark.asyncio
    async def test_async_context_manager_returns_self(self) -> None:
        """MefiClient async context manager __aenter__ returns self."""
        async with MefiClient(api_key="lrd_test") as client:
            assert isinstance(client, MefiClient)


class TestSettingsMefiApiKey:
    def test_mefi_api_key_field_exists_in_settings(self) -> None:
        """Settings model has mefi_api_key field."""
        from app.core.config import Settings

        fields = Settings.model_fields
        assert "mefi_api_key" in fields

    def test_mefi_api_key_has_no_default(self) -> None:
        """mefi_api_key has no default value — startup fails without MEFI_API_KEY env var."""
        from app.core.config import Settings

        field = Settings.model_fields["mefi_api_key"]
        # Pydantic v2: required field has no default
        assert field.is_required()
