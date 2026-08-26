"""CHAT-08 grep gate (inverse of Phase 5's AI-09 grep gate).

CHAT-08 / D-25 / D-39: `app/api/v1/chat.py` is the project-wide DOCUMENTED
EXCEPTION to CLAUDE.md rule #5 ("Backend never calls third-party APIs
synchronously"). AI Chat requires low-latency SSE streaming inside the
FastAPI request handler, which is incompatible with Celery's batch model.

This gate ensures:
  1. `AsyncAnthropic` (and `client.messages.stream` / `client.messages.create`)
     appears in `app/api/v1/chat.py` ONLY — never in any sibling API module.
     (Phase 5's AI-09 gate locks `insights.py` against it; this gate generalizes
     that lock to every API file EXCEPT `chat.py`.)
  2. The gate runs in the standing test suite (NOT nightly-gated) per
     VALIDATION § sign-off, so any future PR that re-introduces AsyncAnthropic
     into auth.py / dashboards.py / sync.py / etc. fails CI.

Dual-state behavior (BEFORE vs AFTER plan 08-05 lands `chat.py`):

  BEFORE 08-05 (current state — `chat.py` does NOT exist):
    - The gate scans `app/api/v1/` and finds NO file matching `chat.py`.
    - The strict-inclusion assertion (AsyncAnthropic MUST be in chat.py) is
      guarded behind `if (api_dir / "chat.py").exists():` so it doesn't fail.
    - The strict-exclusion assertion (AsyncAnthropic NOT in any other file)
      runs against every other API module — currently NONE contain
      AsyncAnthropic — vacuous pass.

  AFTER 08-05 (chat.py landed):
    - The strict-inclusion assertion ACTIVATES — chat.py source must contain
      "AsyncAnthropic" exactly once at import + call site.
    - The strict-exclusion assertion still runs against every other API file
      — auth.py / dashboards.py / health.py / insights.py / router.py / sync.py
      must NOT contain "AsyncAnthropic".

References:
  CHAT-08 (REQUIREMENTS.md)
  D-25 (08-CONTEXT.md): documented exception note in chat.py + CLAUDE.md
  D-39 (08-CONTEXT.md): CHAT-08 grep gate part of integration suite
  Phase 5 inverse: backend/tests/unit/test_insights_router.py:84-101
"""

from __future__ import annotations

from pathlib import Path

# Files that aggregate routers and never own Anthropic logic — excluded from
# both strict inclusion (chat.py) and strict exclusion (everything else).
EXCLUDED_AGGREGATORS = {"__init__.py", "router.py"}

# The single documented-exception file. Plan 08-05 creates it.
CHAT_API_FILENAME = "chat.py"

# Forbidden substrings — any of these in a sibling file is a CHAT-08 violation.
FORBIDDEN_ANTHROPIC_TOKENS = ("AsyncAnthropic", "client.messages")


def _resolve_api_v1_dir() -> Path:
    """Locate backend/app/api/v1/ relative to this test file.

    The test file lives at backend/tests/unit/chat/test_anthropic_scope.py,
    so app/api/v1/ is four levels up + into app/api/v1/.
    """
    here = Path(__file__).resolve()
    backend_root = here.parents[3]  # tests/unit/chat/test_*.py → backend/
    return backend_root / "app" / "api" / "v1"


def test_chat08_async_anthropic_only_in_chat() -> None:
    """CHAT-08 / D-25 / D-39 grep gate (inverse of AI-09).

    BEFORE plan 08-05: chat.py absent → strict-inclusion clause skipped,
        strict-exclusion clause runs against every other API module and
        currently passes vacuously (no module imports AsyncAnthropic).

    AFTER plan 08-05: chat.py present → strict-inclusion clause enforces
        AsyncAnthropic ∈ chat.py, strict-exclusion clause continues to
        enforce AsyncAnthropic ∉ siblings.

    Either state is a PASS for the gate; only a violation
    (AsyncAnthropic leaking into auth.py / dashboards.py / etc., OR
    chat.py existing but missing the AsyncAnthropic import) fails it.
    """
    api_dir = _resolve_api_v1_dir()
    assert api_dir.exists(), f"Expected API directory at {api_dir} — backend layout drifted?"

    chat_file = api_dir / CHAT_API_FILENAME

    # ── Strict inclusion: AsyncAnthropic MUST appear in chat.py (when present)
    if chat_file.exists():
        chat_source = chat_file.read_text(encoding="utf-8")
        assert "AsyncAnthropic" in chat_source, (
            f"CHAT-08 violation: {chat_file} exists but does not import AsyncAnthropic. "
            "AI Chat requires AsyncAnthropic at the SSE handler call site per D-25/D-29."
        )

    # ── Strict exclusion: NO sibling API module may import AsyncAnthropic
    siblings = [p for p in api_dir.glob("*.py") if p.name not in EXCLUDED_AGGREGATORS]
    for sibling in siblings:
        if sibling.name == CHAT_API_FILENAME:
            continue  # chat.py is the documented exception — covered above
        source = sibling.read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_ANTHROPIC_TOKENS:
            assert forbidden not in source, (
                f"CHAT-08 violation: '{forbidden}' found in {sibling} — "
                "Anthropic SDK calls outside chat.py must live in Celery tasks "
                "(CLAUDE.md rule #5). Only app/api/v1/chat.py is exempt (D-25)."
            )
