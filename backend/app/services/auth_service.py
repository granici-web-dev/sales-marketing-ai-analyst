from __future__ import annotations

import bcrypt
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

logger = structlog.get_logger(__name__)

# bcrypt's hard limit is 72 bytes; truncate to avoid ValueError on longer inputs.
_MAX_BYTES = 72


async def authenticate_user(
    session: AsyncSession,
    email: str,
    password: str,
) -> User | None:
    logger.info("login_attempt")
    result = await session.execute(
        select(User).where(User.email == email, User.is_active == True)  # noqa: E712
    )
    user = result.scalar_one_or_none()
    if user is None:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode()[:_MAX_BYTES], hashed.encode())


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode()[:_MAX_BYTES], bcrypt.gensalt(rounds=12)).decode()
