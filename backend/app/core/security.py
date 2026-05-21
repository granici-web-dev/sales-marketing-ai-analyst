from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from jwt.exceptions import PyJWTError

from app.core.config import settings


def create_access_token(data: dict) -> str:
    """Create a signed JWT access token with a 15-minute expiry.

    Args:
        data: Payload claims to embed (e.g., {"sub": user_id, "tenant_id": tenant_id}).

    Returns:
        Encoded JWT string signed with HS256.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    return jwt.encode(
        {**data, "exp": expire},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(data: dict) -> str:
    """Create a signed JWT refresh token with a 30-day expiry.

    Refresh tokens include {"type": "refresh"} in the payload to
    distinguish them from access tokens at the validation layer.

    Args:
        data: Payload claims to embed (e.g., {"sub": user_id}).

    Returns:
        Encoded JWT string signed with HS256.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
    return jwt.encode(
        {**data, "exp": expire, "type": "refresh"},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def verify_token(token: str) -> dict | None:
    """Verify and decode a JWT token.

    Uses explicit algorithms=[settings.jwt_algorithm] to prevent algorithm
    confusion attacks (T-03-01: an attacker cannot craft a "alg:none" token
    that bypasses signature verification).

    Args:
        token: JWT string to decode and verify.

    Returns:
        Decoded payload dict if the token is valid and not expired.
        None if the token is invalid, expired, or malformed — never raises.
    """
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except PyJWTError:
        return None
