"""Pydantic v2 schemas (DTOs) for request/response validation.

Imports expose top-level names for convenient usage across the application.
"""
from __future__ import annotations

from app.schemas.auth import LoginRequest, TokenResponse, UserOut
from app.schemas.mefi import (
    MefiAssignedTo,
    MefiCustomField,
    MefiLeadResponse,
    MefiMeta,
    MefiSearchResponse,
    MefiSourceRef,
    MefiStatusRef,
)

__all__ = [
    # Auth
    "LoginRequest",
    "TokenResponse",
    "UserOut",
    # MEFI
    "MefiAssignedTo",
    "MefiCustomField",
    "MefiLeadResponse",
    "MefiMeta",
    "MefiSearchResponse",
    "MefiSourceRef",
    "MefiStatusRef",
]
