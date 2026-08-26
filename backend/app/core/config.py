from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed configuration loaded from environment variables and .env file.

    All secrets are read from the environment — never hardcoded.
    Required fields (database_url, redis_url, jwt_secret_key) must be set
    via environment variables or .env file; startup will fail if missing.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str

    # Redis (Celery broker + backend + celery-redbeat)
    redis_url: str

    # Своих токенов у кабинета больше нет: сессию выдаёт и отзывает движок.
    # Поля JWT удалены вместе с входом по паролю — настройка, которую никто
    # не читает, живёт до первого человека, решившего, что она что-то делает.

    # MEFI CRM API read key (lrd_* prefix)
    mefi_api_key: str

    # Anthropic API key for Claude Sonnet 4.5 (Phase 5 AI Insights, Phase 8 AI Chat)
    # Required for production; tests mock AsyncAnthropic so this field is optional in test env.
    anthropic_api_key: str = ""

    # Multi-tenancy seam (D-05): hardcoded for MVP1-3; replaced by JWT claim in Iteration 4
    sofa_belle_tenant_id: str = "00000000-0000-0000-0000-000000000001"

    # Движок (assistwidget) — источник личности. Пусто значит «сводить не с чем»:
    # вход через движок отключён, и остаётся собственный вход по паролю.
    engine_base_url: str = ""
    # Сколько держать разобранную сессию, прежде чем спросить движок снова.
    # Отзыв в движке действует с этой задержкой, поэтому она маленькая.
    engine_session_cache_seconds: int = 60

    # Logging
    log_level: str = "INFO"


# Module-level singleton — imported throughout the application
settings = Settings()
