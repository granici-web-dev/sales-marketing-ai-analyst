from __future__ import annotations

import structlog
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

logger = structlog.get_logger(__name__)

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


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
    if not _pwd_context.verify(password, user.hashed_password):
        return None
    return user


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)
