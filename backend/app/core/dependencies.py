from __future__ import annotations

"""FastAPI dependencies for Phase 6 Backend HTTP API.

T-06-01-01: get_current_user validates Bearer JWT signature and expiry via
            verify_token(); invalid or missing token → 401, never 403.
T-06-01-02: Returns UserOut(id, email, is_active) only — no password hash,
            no tenant_id leakage in the returned object.

Note on tenant context: StructlogContextMiddleware in main.py sets the
tenant_id ContextVar (hardcoded settings.sofa_belle_tenant_id) on every HTTP
request BEFORE routing runs.  get_current_user does NOT need to set tenant
context — it only validates the JWT and provides user.id for rate-limit keying.
"""

from uuid import UUID

import structlog
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_token
from app.db.deps import get_session
from app.models.user import User
from app.schemas.auth import UserOut

logger = structlog.get_logger(__name__)

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    """FastAPI dependency — validate Bearer JWT and return the active user.

    Behaviour contract (T-06-01-01):
    - Missing Authorization header → FastAPI raises 403 automatically (HTTPBearer
      auto_error=True default); callers see 401 from the router's exception handler.
    - Invalid / expired token (verify_token returns None) → 401 "Invalid or expired token"
    - Valid JWT for unknown user or is_active=False → 401 "User not found or inactive"
    - Valid JWT for active user → UserOut with id=UUID, email, is_active=True

    Args:
        credentials: Bearer token extracted by HTTPBearer security scheme.
        session: Async SQLAlchemy session from get_session dependency.

    Returns:
        UserOut with id, email, is_active — no password hash, no tenant_id (T-06-01-02).

    Raises:
        HTTPException(401): For all authentication failures.
    """
    # Step 1: decode and verify the JWT signature + expiry
    payload = verify_token(credentials.credentials)
    if payload is None:
        logger.warning("auth_token_invalid")
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # Step 2: extract user_id from "sub" claim
    try:
        user_id = UUID(payload["sub"])
    except (KeyError, ValueError):
        logger.warning("auth_token_missing_sub")
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # Step 3: confirm user exists and is active (SELECT specific columns — no SELECT *)
    stmt = select(User.id, User.email, User.is_active).where(
        User.id == user_id,
        User.is_active.is_(True),
    )
    result = await session.execute(stmt)
    row = result.first()

    if row is None:
        logger.warning("auth_user_not_found_or_inactive", user_id=str(user_id))
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return UserOut(id=row.id, email=row.email, is_active=row.is_active)
