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

from uuid import UUID

import pytest


class TestExceptionHierarchy:
    """Test exception class hierarchy."""

    def test_tenant_isolation_error_is_subclass_of_app_error(self):
        from app.core.exceptions import AppError, TenantIsolationError
        assert issubclass(TenantIsolationError, AppError)

    def test_app_error_is_subclass_of_exception(self):
        from app.core.exceptions import AppError
        assert issubclass(AppError, Exception)

    def test_not_found_error_is_subclass_of_app_error(self):
        from app.core.exceptions import AppError, NotFoundError
        assert issubclass(NotFoundError, AppError)

    def test_not_found_error_has_message_attribute(self):
        from app.core.exceptions import NotFoundError
        err = NotFoundError("User not found")
        assert err.message == "User not found"

    def test_authentication_error_is_subclass_of_app_error(self):
        from app.core.exceptions import AppError, AuthenticationError
        assert issubclass(AuthenticationError, AppError)

    def test_authorization_error_is_subclass_of_app_error(self):
        from app.core.exceptions import AppError, AuthorizationError
        assert issubclass(AuthorizationError, AppError)

    def test_tenant_isolation_error_has_message(self):
        from app.core.exceptions import TenantIsolationError
        err = TenantIsolationError("No tenant context set")
        assert err.message == "No tenant context set"
        assert str(err) == "No tenant context set"


class TestTenancyContextVar:
    """Test tenant ContextVar behavior."""

    def test_get_current_tenant_id_returns_none_when_not_set(self):
        from app.core.tenancy import _tenant_id_var, get_current_tenant_id
        # Reset to None
        _tenant_id_var.set(None)
        result = get_current_tenant_id()
        assert result is None

    def test_set_tenant_id_causes_get_to_return_that_uuid(self):
        from app.core.tenancy import _tenant_id_var, get_current_tenant_id, set_tenant_id
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
        from app.core.exceptions import TenantIsolationError
        from app.core.tenancy import _tenant_id_var, require_tenant_id
        _tenant_id_var.set(None)
        with pytest.raises(TenantIsolationError):
            require_tenant_id()

    def test_require_tenant_id_returns_uuid_when_set(self):
        from app.core.tenancy import _tenant_id_var, require_tenant_id, set_tenant_id
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
        fields = Settings.model_fields
        assert "database_url" in fields
        assert "redis_url" in fields
        assert "sofa_belle_tenant_id" in fields
        assert "log_level" in fields
        assert "engine_base_url" in fields

    def test_no_jwt_settings_remain(self):
        """Свои токены удалены вместе с входом по паролю.

        Настройка, которую никто не читает, живёт до первого человека,
        решившего, что она что-то делает. Проверка стоит здесь, чтобы поля
        не вернулись «на всякий случай» вместе с чужим кодом.
        """
        from app.core.config import Settings
        leftovers = [
            name for name in Settings.model_fields
            if name.startswith(("jwt_", "access_token_", "refresh_token_"))
        ]
        assert leftovers == [], f"остались настройки своих токенов: {leftovers}"

    def test_engine_cache_default_is_a_minute(self):
        """Отзыв сессии в движке действует с этой задержкой, поэтому она мала."""
        from app.core.config import Settings
        assert Settings.model_fields["engine_session_cache_seconds"].default == 60

    def test_sofa_belle_tenant_id_has_default(self):
        from app.core.config import Settings
        field = Settings.model_fields["sofa_belle_tenant_id"]
        assert field.default == "00000000-0000-0000-0000-000000000001"


class TestLogging:
    """Test structlog configuration."""

    def test_configure_logging_has_merge_contextvars(self):
        """Logging config must include merge_contextvars processor."""
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
