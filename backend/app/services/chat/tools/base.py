from __future__ import annotations

"""Tool dataclass + handler type alias for the chat tool registry (D-04).

Every chat tool is a thin wrapper around an existing Phase 3/5/6 service
(D-03). The ``Tool`` frozen dataclass binds together:

  - ``name``        — canonical D-02 identifier (Claude calls the tool by this)
  - ``definition``  — Anthropic ToolParam dict {name, description, input_schema}
  - ``input_schema``— Pydantic v2 BaseModel that validates ``input`` from Claude
  - ``handler``     — async callable with the LM-3 contract:
                      ``async def _handler(tenant_id: UUID, session: AsyncSession,
                                          inp: <Input>) -> dict``

LM-3 contract: the first parameter MUST be ``tenant_id`` so every handler
re-enforces tenant scoping. The registry test in
``tests/unit/chat/test_chat_tools_registry.py`` asserts this via
``inspect.signature(...).parameters[:3]``.

References:
  - RESEARCH §4 lines 821-836 — Tool dataclass shape
  - PATTERNS § "Shared Patterns → Tenant Isolation"
  - CONTEXT D-04 — TOOLS_REGISTRY contract
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession


# LM-3 handler signature: (tenant_id, session, validated_input) -> dict
ToolHandler = Callable[[UUID, AsyncSession, BaseModel], Awaitable[dict]]


@dataclass(frozen=True)
class Tool:
    """A single chat tool registered in ``TOOLS_REGISTRY``.

    Attributes:
        name: Canonical D-02 name passed to Anthropic and used as the
            registry key.
        definition: Anthropic ``ToolParam`` dict with keys
            ``{name, description, input_schema}`` where ``input_schema``
            is the Pydantic-generated JSON Schema (NOT the BaseModel).
        input_schema: Pydantic v2 BaseModel subclass; the orchestrator
            calls ``model_validate(claude_input_dict)`` before invoking
            the handler.
        handler: Async coroutine implementing the LM-3 contract.
    """

    name: str
    definition: dict[str, Any]
    input_schema: type[BaseModel]
    handler: ToolHandler
