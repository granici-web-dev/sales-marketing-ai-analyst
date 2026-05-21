from __future__ import annotations

"""
INFRA-05 fork-safety tests.

Verifies that worker_process_init signal:
1. Disposes the existing SQLAlchemy engine (prevents parent connection pool leaking
   into forked worker processes via shared file descriptors)
2. Creates a fresh engine for the worker process
3. Recreates AsyncSessionLocal from the new engine

These are unit tests — they mock the engine and session factory.
No DB connection required.
"""

import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

# Skipped until implementation exists — imports are stubs only
pytestmark = pytest.mark.skip(reason="Stubs — implementation pending (Wave 0 gate)")

try:
    from app.db import session as db_session_module
except ImportError:
    db_session_module = None  # type: ignore[assignment]


def test_worker_process_init_disposes_engine() -> None:
    """INFRA-05: worker_process_init must call engine.dispose() before creating a new engine.

    After a fork(), asyncpg connections from the parent process are invalid in the
    child process (shared file descriptors). engine.dispose() closes all connections
    in the pool before the worker creates new ones.

    Pattern (from RESEARCH.md Pattern 4):
        @worker_process_init.connect
        def init_worker_process(**kwargs):
            asyncio.run(db_session.engine.dispose())
            db_session.engine = db_session._create_engine()
            db_session.AsyncSessionLocal = db_session._create_session_factory(db_session.engine)
    """
    if db_session_module is None:
        pytest.fail(
            "app.db.session module not importable — implementation pending (INFRA-05)"
        )

    # Mock the existing engine
    mock_old_engine = MagicMock()
    mock_old_engine.dispose = AsyncMock()  # engine.dispose() is async

    # Mock the new engine that _create_engine() will return
    mock_new_engine = MagicMock()

    # Patch the module-level engine and factory functions
    with (
        patch.object(db_session_module, "engine", mock_old_engine),
        patch.object(db_session_module, "_create_engine", return_value=mock_new_engine),
    ):
        # Call the worker init function
        db_session_module.init_worker_process()

        # Verify the old engine was disposed
        mock_old_engine.dispose.assert_called_once()

        # Verify the module-level engine was replaced with the new one
        assert db_session_module.engine is mock_new_engine, (
            "db_session.engine must be replaced with the new engine after init_worker_process()"
        )


def test_worker_process_init_recreates_session_factory() -> None:
    """INFRA-05: worker_process_init must recreate AsyncSessionLocal from the new engine.

    After dispose + engine recreate, the session factory must also be rebuilt
    so that new sessions use connections from the fresh engine (not the disposed one).
    """
    if db_session_module is None:
        pytest.fail(
            "app.db.session module not importable — implementation pending (INFRA-05)"
        )

    mock_old_engine = MagicMock()
    mock_old_engine.dispose = AsyncMock()
    mock_new_engine = MagicMock()
    mock_new_session_factory = MagicMock()

    with (
        patch.object(db_session_module, "engine", mock_old_engine),
        patch.object(db_session_module, "_create_engine", return_value=mock_new_engine),
        patch.object(
            db_session_module,
            "_create_session_factory",
            return_value=mock_new_session_factory,
        ),
    ):
        db_session_module.init_worker_process()

        # Verify AsyncSessionLocal was replaced
        assert db_session_module.AsyncSessionLocal is not None, (
            "db_session.AsyncSessionLocal must not be None after init_worker_process()"
        )
        # Verify _create_session_factory was called with the new engine
        db_session_module._create_session_factory.assert_called_once_with(mock_new_engine)
