from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async SQLAlchemy session.

    Usage:
        @router.get("/items")
        async def list_items(session: AsyncSession = Depends(get_session)):
            ...

    The session is automatically closed when the request completes (or errors).
    Tenant isolation is enforced at the session level via the do_orm_execute
    event listener in session.py — no additional filtering required at the
    endpoint or service layer.
    """
    async with AsyncSessionLocal() as session:
        yield session
