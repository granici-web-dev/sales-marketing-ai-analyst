from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# Alembic Config object — provides access to alembic.ini values
config = context.config

# Configure logging from alembic.ini [loggers] section
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inject DATABASE_URL from environment variable into Alembic config.
# This is the T-04-04 mitigation: no credentials in alembic.ini.
# The DATABASE_URL must be set before running `alembic upgrade head`.
config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])

# CRITICAL: Import ALL model modules BEFORE setting target_metadata.
# If models are not imported here, Base.metadata will be empty and
# `alembic revision --autogenerate` will produce empty migration files.
# See: RESEARCH.md Common Pitfalls #6.
from app.db.base import Base  # noqa: E402
import app.models.tenant  # noqa: E402, F401
import app.models.user  # noqa: E402, F401
import app.models.pipeline  # noqa: E402, F401

# Alembic uses this metadata object to detect schema changes for autogenerate.
target_metadata = Base.metadata


def do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    """Configure Alembic context and run migrations synchronously.

    Called inside `connection.run_sync()` which bridges the async/sync
    boundary. Alembic's migration execution is inherently synchronous;
    `run_sync` wraps it for use with an async engine connection.
    """
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations via the sync bridge.

    Uses pool.NullPool so each migration run opens and closes its own
    connection without pooling — correct for one-off migration execution.
    The `async_engine_from_config` reads sqlalchemy.url from alembic.ini
    (already overridden with DATABASE_URL above).
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for Alembic online migration mode.

    Alembic calls this function when running `alembic upgrade head` or
    any other migration command that requires a live database connection.
    `asyncio.run()` bridges the sync Alembic entry point to our async engine.
    """
    asyncio.run(run_async_migrations())


run_migrations_online()
