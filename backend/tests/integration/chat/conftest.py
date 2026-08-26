"""Shared fixtures for Phase 8 AI Chat integration tests.

Integration tests drive the full FastAPI request → SSE response loop with
mocked AsyncAnthropic (via respx-style intercept at the SDK boundary or by
patching the orchestrator's `AsyncAnthropic` class). Phase 5 carry-forward:
the `_integration_skip` decorator pattern from Phase 5 plan 01 lets the suite
be collected without a live DB and a configured ANTHROPIC_API_KEY.

Wave 0 contract: this conftest creates the seams. Plan 08-05 (chat router)
fills in the seeded-conversation fixtures with real persistence calls.
"""

from __future__ import annotations

import os
from uuid import UUID, uuid4

import pytest

# Sofa Belle pilot tenant — must match unit conftest constants
SOFA_BELLE_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
SOFA_BELLE_USER_ID = UUID("00000000-0000-0000-0000-000000000010")


def integration_skip_if_no_anthropic_key() -> None:
    """Phase 5 carry-forward — gate decorator analog.

    Integration tests that mock AsyncAnthropic at the SDK boundary still need
    the orchestrator to instantiate the client; that constructor requires an
    api_key (even if unused after mocking). If ANTHROPIC_API_KEY is unset
    AND no `monkeypatch.setenv` is in play, skip cleanly rather than crash.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        pytest.skip(
            "ANTHROPIC_API_KEY not set; chat integration tests require either a real key "
            "or a monkeypatch.setenv('ANTHROPIC_API_KEY', 'test') applied before request"
        )


# ── Identity fixtures (mirror unit conftest) ───────────────────────────────────


@pytest.fixture
def chat_tenant_id() -> UUID:
    return SOFA_BELLE_TENANT_ID


@pytest.fixture
def chat_user_id() -> UUID:
    return SOFA_BELLE_USER_ID


# ── Streaming AsyncClient fixture ──────────────────────────────────────────────


@pytest.fixture
async def streaming_client():
    """httpx.AsyncClient configured for SSE response consumption.

    Wave 0 stub: imports inside body so test collection doesn't require app
    to be importable. After plans 08-04/05 land the orchestrator + router,
    this fixture yields a real AsyncClient streaming against the FastAPI app.
    """
    try:
        from httpx import ASGITransport, AsyncClient  # deferred (INFRA-05)

        from app.main import app as _app  # deferred (INFRA-05)
    except ImportError:
        yield None
        return

    async with AsyncClient(
        transport=ASGITransport(app=_app),
        base_url="http://test",
        timeout=30.0,
    ) as client:
        yield client


# ── Seeded conversation fixture ────────────────────────────────────────────────


@pytest.fixture
def seeded_conversation(chat_tenant_id: UUID, chat_user_id: UUID) -> dict:
    """Returns a minimal seeded conversation dict + initial user message.

    Wave 0: a plain dict that later integration tests can pass to the
    chat router. Plan 08-05 swaps this for an actual DB seed once the
    chat_conversations table migration exists (009_chat_tables).
    """
    conversation_id = uuid4()
    message_id = uuid4()
    return {
        "conversation_id": conversation_id,
        "tenant_id": chat_tenant_id,
        "user_id": chat_user_id,
        "title": "Conversație nouă",
        "first_user_message": {
            "id": message_id,
            "conversation_id": conversation_id,
            "tenant_id": chat_tenant_id,
            "role": "user",
            "content": "Cum stăm cu vânzările luna asta?",
        },
    }
