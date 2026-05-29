from __future__ import annotations

"""AI Chat service package (Phase 8).

Provides the tool registry (D-01..D-04), orchestrator, hallucination guard,
prompt builder, and conversation repositories used by ``app.api.v1.chat``.

Phase 8 documented exception (D-25): AI Chat is the only HTTP path that
calls Anthropic synchronously. All OTHER Claude calls remain in Celery
tasks (Phase 5 daily insights).
"""
