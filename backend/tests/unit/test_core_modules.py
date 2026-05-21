"""
Tests for core module behaviors — Plan 01-03 TDD RED phase.

Task 1 behaviors:
- Settings(database_url="bad") raises ValidationError
- get_current_tenant_id() returns None when no ContextVar set
- set_tenant_id(UUID(...)) causes get_current_tenant_id() to return that UUID
- TenantIsolationError is a subclass of AppError which is a subclass of Exception
- NotFoundError("User not found") has .message attribute = "User not found"

Task 2 behaviors:
- create_access_token({"sub": "user-id"}) returns a valid JWT string
- verify_token("invalid-string") returns None (not raises)
- verify_token with expired token returns None (not raises)
- create_refresh_token produces token with "type": "refresh" in payload
- verify_token with "none" algorithm returns None (caught, not raised)
"""
from __future__ import annotations

import pytest
from uuid import UUID


class TestExceptionHierarchy:
    """Test exception class hierarchy."""

    def test_tenant_isolation_error_is_subclass_of_app_error(self):
        from app.core.exceptions import TenantIsolationError, AppError
        assert issubclass(TenantIsolationError, AppError)

    def test_app_error_is_subclass_of_exception(self):
        from app.core.exceptions import AppError
        assert issubclass(AppError, Exception)

    def test_not_found_error_is_subclass_of_app_error(self):
        from app.core.exceptions import NotFoundError, AppError
        assert issubclass(NotFoundError, AppError)

    def test_not_found_error_has_message_attribute(self):
        from app.core.exceptions import NotFoundError
        err = NotFoundError("User not found")
        assert err.message == "User not found"

    def test_authentication_error_is_subclass_of_app_error(self):
        from app.core.exceptions import AuthenticationError, AppError
        assert issubclass(AuthenticationError, AppError)

    def test_authorization_error_is_subclass_of_app_error(self):
        from app.core.exceptions import AuthorizationError, AppError
        assert issubclass(AuthorizationError, AppError)

    def test_tenant_isolation_error_has_message(self):
        from app.core.exceptions import TenantIsolationError
        err = TenantIsolationError("No tenant context set")
        assert err.message == "No tenant context set"
        assert str(err) == "No tenant context set"


class TestTenancyContextVar:
    """Test tenant ContextVar behavior."""

    def test_get_current_tenant_id_returns_none_when_not_set(self):
        from app.core.tenancy import get_current_tenant_id, _tenant_id_var
        # Reset to None
        _tenant_id_var.set(None)
        result = get_current_tenant_id()
        assert result is None

    def test_set_tenant_id_causes_get_to_return_that_uuid(self):
        from app.core.tenancy import set_tenant_id, get_current_tenant_id, _tenant_id_var
        tenant_uuid = UUID("00000000-0000-0000-0000-000000000001")
        set_tenant_id(tenant_uuid)
        result = get_current_tenant_id()
        assert result == tenant_uuid
        # Reset
        _tenant_id_var.set(None)

    def test_context_var_default_is_none(self):
        from app.core.tenancy import _tenant_id_var
        # The default must be None to prevent cross-request contamination
        assert _tenant_id_var.get(None) is None or _tenant_id_var.get() is None

    def test_require_tenant_id_raises_when_none(self):
        from app.core.tenancy import require_tenant_id, _tenant_id_var
        from app.core.exceptions import TenantIsolationError
        _tenant_id_var.set(None)
        with pytest.raises(TenantIsolationError):
            require_tenant_id()

    def test_require_tenant_id_returns_uuid_when_set(self):
        from app.core.tenancy import require_tenant_id, set_tenant_id, _tenant_id_var
        tenant_uuid = UUID("00000000-0000-0000-0000-000000000001")
        set_tenant_id(tenant_uuid)
        result = require_tenant_id()
        assert result == tenant_uuid
        # Reset
        _tenant_id_var.set(None)


class TestSettings:
    """Test Pydantic Settings class."""

    def test_settings_has_all_required_fields(self):
        """Settings class should have all required fields defined."""
        from app.core.config import Settings
        import inspect
        fields = Settings.model_fields
        assert "database_url" in fields
        assert "redis_url" in fields
        assert "jwt_secret_key" in fields
        assert "jwt_algorithm" in fields
        assert "access_token_expire_minutes" in fields
        assert "refresh_token_expire_days" in fields
        assert "sofa_belle_tenant_id" in fields
        assert "log_level" in fields

    def test_jwt_algorithm_default_is_hs256(self):
        """JWT algorithm should default to HS256."""
        from app.core.config import Settings
        field = Settings.model_fields["jwt_algorithm"]
        assert field.default == "HS256"

    def test_access_token_expire_minutes_default_is_15(self):
        from app.core.config import Settings
        field = Settings.model_fields["access_token_expire_minutes"]
        assert field.default == 15

    def test_refresh_token_expire_days_default_is_30(self):
        from app.core.config import Settings
        field = Settings.model_fields["refresh_token_expire_days"]
        assert field.default == 30

    def test_sofa_belle_tenant_id_has_default(self):
        from app.core.config import Settings
        field = Settings.model_fields["sofa_belle_tenant_id"]
        assert field.default == "00000000-0000-0000-0000-000000000001"


class TestSecurity:
    """Test PyJWT security utilities."""

    def _make_settings_env(self, monkeypatch):
        """Set environment variables for settings."""
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
        monkeypatch.setenv("REDIS_URL", "redis://localhost/0")
        monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-32chars-minimum-abc")

    def test_create_access_token_returns_string(self, monkeypatch):
        self._make_settings_env(monkeypatch)
        from app.core.security import create_access_token
        token = create_access_token({"sub": "user-id"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_verify_token_decodes_valid_access_token(self, monkeypatch):
        self._make_settings_env(monkeypatch)
        from app.core.security import create_access_token, verify_token
        token = create_access_token({"sub": "user-id"})
        result = verify_token(token)
        assert result is not None
        assert result["sub"] == "user-id"

    def test_verify_token_returns_none_for_invalid_string(self, monkeypatch):
        self._make_settings_env(monkeypatch)
        from app.core.security import verify_token
        result = verify_token("not-a-jwt-token")
        assert result is None

    def test_verify_token_returns_none_for_garbage(self, monkeypatch):
        self._make_settings_env(monkeypatch)
        from app.core.security import verify_token
        result = verify_token("garbage.garbage.garbage")
        assert result is None

    def test_create_refresh_token_has_type_refresh(self, monkeypatch):
        self._make_settings_env(monkeypatch)
        from app.core.security import create_refresh_token, verify_token
        token = create_refresh_token({"sub": "user-id"})
        result = verify_token(token)
        assert result is not None
        assert result.get("type") == "refresh"

    def test_security_module_uses_pyjwt_not_jose(self):
        """Verify the security module uses PyJWT (import jwt) not python-jose."""
        import ast
        import os
        security_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "app", "core", "security.py"
        )
        with open(security_path) as f:
            source = f.read()
        # Must not contain jose import
        assert "from jose" not in source
        assert "import jose" not in source
        # Must contain PyJWT import
        assert "import jwt" in source


class TestLogging:
    """Test structlog configuration."""

    def test_configure_logging_has_merge_contextvars(self):
        """Logging config must include merge_contextvars processor."""
        import ast
        import os
        logging_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "app", "core", "logging.py"
        )
        with open(logging_path) as f:
            source = f.read()
        assert "merge_contextvars" in source

    def test_configure_logging_has_json_renderer(self):
        """Logging config must include JSONRenderer."""
        import os
        logging_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "app", "core", "logging.py"
        )
        with open(logging_path) as f:
            source = f.read()
        assert "JSONRenderer" in source

    def test_configure_logging_callable(self, monkeypatch):
        """configure_logging() should be callable without error."""
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
        monkeypatch.setenv("REDIS_URL", "redis://localhost/0")
        monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-32chars-minimum-abc")
        from app.core.logging import configure_logging
        # Should not raise
        configure_logging("INFO")
