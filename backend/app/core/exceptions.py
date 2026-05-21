from __future__ import annotations


class AppError(Exception):
    """Base exception for all application-level errors.

    All custom exceptions must inherit from AppError to allow
    consistent error handling at the API boundary.
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class NotFoundError(AppError):
    """Raised when a requested resource does not exist."""


class TenantIsolationError(AppError):
    """Raised when a DB query is attempted without a tenant context.

    This error is the enforcement mechanism for D-06 (SC#6):
    the SQLAlchemy do_orm_execute event raises this when no
    tenant_id ContextVar is set, preventing cross-tenant data access.
    """


class AuthenticationError(AppError):
    """Raised when authentication fails (invalid credentials, expired token, etc.)."""


class AuthorizationError(AppError):
    """Raised when an authenticated user lacks permission for the requested action."""
