"""MEFI CRM integration client.

MefiClient is the single HTTP client for all MEFI API calls.
It is used exclusively from Celery tasks — NEVER from HTTP handlers.

Authentication: Bearer token (lrd_* read key) in Authorization header.
Rate limit: 600 req/min for lrd_* keys. Reads X-RateLimit-Remaining and
raises RateLimitError on 429 with Retry-After countdown.

Usage (inside async Celery task helper):
    async with MefiClient(api_key=settings.mefi_api_key) as client:
        alive = await client.health_check()
        response = await client.search_leads(filters={...}, page=1)

PII note (CLAUDE.md no-PII rule):
  Authorization header, phone, email, and name values from MEFI lead records
  are NEVER logged. Only safe metrics (page count, total, rate_limit_remaining)
  appear in log output.

Source: docs/api-references/mefi/leads-read.md (rate limit headers, request shape)
        .planning/phases/02-mefi-etl/02-RESEARCH.md (Q8 MefiClient pattern)
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
import structlog

from app.schemas.mefi import MefiSearchResponse
from app.services.integrations.base import BaseIntegration, SyncResult

logger = structlog.get_logger()


class RateLimitError(Exception):
    """Raised when MEFI API returns 429 Too Many Requests.

    Attributes:
        retry_after: Seconds to wait before retrying, from the Retry-After header.
    """

    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__(f"MEFI rate limit hit — retry after {retry_after}s")


class MefiClient(BaseIntegration):
    """Async HTTP client for the MEFI CRM /leads/search API.

    All external MEFI requests go through this class. Celery tasks import
    MefiClient and never construct httpx requests directly.

    Class attributes:
        BASE_URL: MEFI base URL for Sofa Belle's instance.
        source_name: Integration identifier used in SyncResult and logs.
        _REQUEST_INTERVAL: Minimum seconds between requests — proactive
            throttle to stay under the 100 req/10s burst limit (10 req/s).
            0.15s ≈ 6.7 req/s, ~33% headroom below the hard ceiling.
            Tune this if MEFI tightens limits or concurrent tasks share the token.
    """

    BASE_URL: str = "https://bellesofa.meficrm.com/api/v1"
    source_name: str = "mefi"
    _REQUEST_INTERVAL: float = 0.15  # seconds between requests (~6.7 req/s)

    def __init__(self, api_key: str) -> None:
        """Create a MefiClient with a read key.

        Args:
            api_key: MEFI lrd_* read API key. Loaded from settings.mefi_api_key.
                     NEVER log this value.
        """
        # Authorization header is set here and never logged
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(30.0),
        )

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "MefiClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------
    # BaseIntegration abstract methods
    # ------------------------------------------------------------------

    async def authenticate(self, credentials: dict) -> bool:
        """Verify the API key by attempting a minimal /leads/search call.

        Returns True on 200, False on 401/403 or any HTTP error.
        Does NOT raise — returns False on all failures.
        """
        try:
            await self._request("POST", "/leads/search", json={"per_page": 1})
            return True
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (401, 403):
                return False
            return False
        except (httpx.HTTPError, RateLimitError):
            return False

    async def sync(
        self,
        tenant_id: UUID,
        since: datetime | None = None,
    ) -> SyncResult:
        """Full sync entry point (called by Celery task layer).

        The actual pagination and UPSERT logic lives in the Celery task and
        MefiRepository. This method provides the BaseIntegration contract.
        Raises NotImplementedError until Plan 02-04 wires the task layer.
        """
        raise NotImplementedError(
            "MefiClient.sync() is implemented in the Celery task layer (Plan 02-04). "
            "Call sync_mefi_leads.delay() from the task scheduler instead."
        )

    async def health_check(self) -> bool:
        """Liveness probe: POST /leads/search with no date filter.

        Returns True if MEFI responds with total > 0 (data exists).
        Returns False (not raises) if total == 0 — may indicate API down
        or an authentication issue.

        MEFI-09: this is the pre-sync liveness check in the ETL task.
        """
        try:
            response = await self._request("POST", "/leads/search", json={})
            parsed = MefiSearchResponse.model_validate(response)
            return parsed.meta.total > 0
        except (httpx.HTTPStatusError, httpx.HTTPError, RateLimitError):
            return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def search_leads(
        self,
        filters: dict,
        page: int = 1,
        per_page: int = 100,
        sort: str = "status_changed_at",
        order: str = "asc",
    ) -> MefiSearchResponse:
        """POST /leads/search — paginated lead retrieval.

        Args:
            filters: MEFI filter parameters (lifecycle, date_from, date_to, etc.)
            page: Page number (1-indexed).
            per_page: Number of leads per page (max 100).
            sort: Sort field — typically 'status_changed_at' for incremental sync.
            order: Sort direction — 'asc' or 'desc'.

        Returns:
            MefiSearchResponse with validated lead data and pagination metadata.

        Raises:
            RateLimitError: On 429 response.
            httpx.HTTPStatusError: On non-2xx responses (except 429).
        """
        body = {
            **filters,
            "page": page,
            "per_page": per_page,
            "sort": sort,
            "order": order,
        }
        raw = await self._request("POST", "/leads/search", json=body)
        parsed = MefiSearchResponse.model_validate(raw)

        # Safe logging — no PII, no auth header
        logger.info(
            "mefi.search_leads",
            page=page,
            total=parsed.meta.total,
            records_on_page=len(parsed.data),
        )
        return parsed

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict:
        """Execute an HTTP request with proactive throttling and rate-limit awareness.

        Sleeps _REQUEST_INTERVAL before every request (proactive throttle) so
        the call rate stays below the 100 req/10s burst ceiling regardless of
        how many concurrent tasks share the same API token.

        Also reads X-RateLimit-Remaining after every response and adds an extra
        proportional pause when the remaining budget drops below 20 — a reactive
        safety net on top of the proactive sleep.

        On 429: raises RateLimitError with Retry-After. The Celery task handles
        this by calling self.retry(countdown=retry_after).

        Args:
            method: HTTP method string ('POST', 'GET', etc.)
            path: URL path relative to BASE_URL.
            **kwargs: Passed directly to httpx.AsyncClient.request().

        Returns:
            Parsed JSON response as a dict.

        Raises:
            RateLimitError: If the server returns 429.
            httpx.HTTPStatusError: For other 4xx/5xx responses.
        """
        # Proactive throttle — fires before every request, including retries.
        # Keeps sustained rate at ~6.7 req/s, well under 10 req/s burst limit.
        await asyncio.sleep(self._REQUEST_INTERVAL)

        response = await self._client.request(method, path, **kwargs)

        # Read rate-limit header before raising — always present on 200 and 429
        try:
            remaining = int(response.headers.get("X-RateLimit-Remaining", 600))
        except (ValueError, TypeError):
            remaining = 600  # malformed header — assume plenty left

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            logger.warning(
                "mefi.rate_limit_hit",
                retry_after=retry_after,
                rate_limit_remaining=0,
            )
            raise RateLimitError(retry_after=retry_after)

        # Reactive safety net: extra pause proportional to how close we are to the
        # burst ceiling. Fires only when remaining < 20 (i.e. < 20% of burst budget).
        # extra_sleep ramps from 0.0s (at remaining=20) up to 2.0s (at remaining=0).
        if remaining < 20:
            extra_sleep = (20 - remaining) * 0.1  # 0.1s per missing credit, max 2.0s
            logger.info(
                "mefi.rate_limit_low",
                rate_limit_remaining=remaining,
                extra_sleep=round(extra_sleep, 2),
            )
            await asyncio.sleep(extra_sleep)

        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]
