"""
INFRA-04 and SC#4 integration tests.

Verifies that:
1. celery-redbeat stores schedule keys in Redis after beat starts (INFRA-04, SC#4)
2. Celery worker responds to ping (manual gate — requires running worker)

These tests require a running Redis instance.
They will skip if REDIS_URL is not set.
"""

from __future__ import annotations

import os

import pytest

try:
    import redis
except ImportError:
    redis = None  # type: ignore[assignment]

try:
    from app.tasks.celery_app import celery_app
except ImportError:
    celery_app = None  # type: ignore[assignment]

pytestmark = pytest.mark.integration


def test_redbeat_alive() -> None:
    """INFRA-04, SC#4: celery-redbeat stores schedule keys in Redis after beat starts.

    Connects to Redis and checks for keys matching 'redbeat::*' pattern.
    These keys are created when celery-redbeat (beat container) starts and
    registers scheduled tasks.

    Run: `docker compose up -d beat` before this test.

    Note: This test verifies that beat has stored its schedule, not that
    tasks are being executed. For execution verification, see test_celery_worker_pings.
    """
    if redis is None:
        pytest.skip("redis package not installed — install with: uv pip install redis")

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    r = redis.from_url(redis_url)
    try:
        # Verify Redis is accessible
        r.ping()

        # Check for redbeat schedule keys
        # redbeat_key_prefix is set to "analyst:redbeat" in celery_app.py
        # but the base "redbeat::" prefix is also used by redbeat internals
        redbeat_keys = r.keys("redbeat::*")

        # If using custom prefix from celery_app.py config
        analyst_redbeat_keys = r.keys("analyst:redbeat*")

        all_keys = list(redbeat_keys) + list(analyst_redbeat_keys)

        assert len(all_keys) > 0, (
            "No redbeat schedule keys found in Redis. "
            "Expected keys matching 'redbeat::*' or 'analyst:redbeat*'. "
            "Is the beat container running? Run: docker compose up -d beat"
        )
    except redis.ConnectionError as e:
        pytest.skip(f"Cannot connect to Redis at {redis_url}: {e}")
    finally:
        r.close()


@pytest.mark.skip(reason="Requires running worker — manual gate test (docker compose up -d worker)")
def test_celery_worker_pings() -> None:
    """INFRA-04, SC#4: Celery worker responds to inspect ping.

    Manually gated — requires a running Celery worker.
    Run: `docker compose up -d worker` before removing the skip marker.

    Verifies that at least one worker is alive and connected to Redis.
    """
    if celery_app is None:
        pytest.skip("app.tasks.celery_app not importable — implementation pending")

    inspector = celery_app.control.inspect(timeout=5)
    ping_response = inspector.ping()

    assert ping_response is not None, (
        "celery inspect ping returned None — no workers responding. "
        "Run: docker compose up -d worker"
    )
    assert len(ping_response) > 0, (
        f"celery inspect ping returned empty dict — no workers registered. "
        f"Response: {ping_response}"
    )

    # Each worker returns {"ok": "pong"}
    for worker_name, response in ping_response.items():
        assert response == {"ok": "pong"}, (
            f"Worker '{worker_name}' responded with unexpected value: {response}"
        )
