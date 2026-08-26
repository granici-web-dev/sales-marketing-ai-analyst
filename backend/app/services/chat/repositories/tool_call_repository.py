"""ToolCallRepository — audit row per tool invocation (D-21).

Every tool call by the orchestrator writes exactly one `chat_tool_calls` row.
On handler exception, `output_data` is NULL and `error` is populated with
the (truncated) exception message. The SSE `tool_result` event carries the
matching `error: bool` flag so the frontend can render the failed pill state.

WR-04: NO commit — caller commits atomically.
T-08-01: tenant_id is set explicitly to `self._tenant_id` — handlers never
         pass it via `row` so cross-tenant audit pollution is structurally
         impossible.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatToolCall


class ToolCallRepository:
    """Per-invocation audit log for chat tool calls."""

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def insert_tool_call(
        self,
        *,
        message_id: UUID,
        tool_name: str,
        input_args: dict,
        output_data: dict | None,
        duration_ms: int | None,
        error: str | None,
    ) -> UUID:
        """INSERT a single audit row. Returns the new id.

        Tenant scoping is structural: `tenant_id` is sourced from `self._tenant_id`
        and never accepted as an argument, so cross-tenant write blocked by design
        — no row dict can carry a foreign tenant id into this method.

        Args:
            message_id: parent chat_messages.id (ON DELETE CASCADE in DDL).
            tool_name: name of the registered tool (one of the 12 D-02 names).
            input_args: validated Pydantic input passed to the handler.
            output_data: handler's dict result; None when the call errored.
            duration_ms: handler runtime in milliseconds; may be None.
            error: exception message (truncated); None on success.

        Returns:
            UUID of the newly persisted audit row.
        """
        new_id = uuid4()
        row = ChatToolCall(
            id=new_id,
            tenant_id=self._tenant_id,
            message_id=message_id,
            tool_name=tool_name,
            input_args=input_args,
            output_data=output_data,
            duration_ms=duration_ms,
            error=error,
        )
        self._session.add(row)
        await self._session.flush()
        return new_id
