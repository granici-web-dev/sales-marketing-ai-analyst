"""INFRA-05 — fork safety for the Celery prefork pool.

After `fork()`, the asyncpg connections a parent process held are not usable in
the child: both processes now own the same file descriptors, and two workers
reading the same socket corrupt each other's traffic. The failure does not look
like a connection error — it looks like intermittent, unreproducible garbage
under load.

So each child disposes the inherited pool and builds its own engine, wired to
Celery's `worker_process_init` signal, which fires in the child after the pool
creates it.

## Why this file was rewritten (2026-08-25)

The two tests below were sound in intent — unlike some of their neighbours they
did assert something real. They had simply never run: a module-level
`pytest.mark.skip(reason="Stubs — implementation pending")` disabled them, and
each body opened by tolerating an absent `app.db.session`, which has existed
since Phase 1. Removing that scaffolding was the whole fix.

One check was missing and has been added. Both original tests call
`init_worker_process()` directly, so they verify the function does the right
thing — and would keep passing if nothing ever called it. The `@connect`
decorator in `celery_app.py` is the load-bearing part: without it every worker
child would quietly inherit the parent's pool, and the tests would stay green.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from app.db import session as db_session_module


class TestEngineReplacement:
    def test_inherited_engine_is_disposed(self) -> None:
        """The parent's pool is closed before a new one is built.

        Order matters: creating the new engine first and disposing afterwards
        would leave a window in which both exist, and `dispose()` would then be
        closing sockets the child had already begun using.
        """
        old_engine = MagicMock()
        old_engine.dispose = AsyncMock()
        new_engine = MagicMock()

        with (
            patch.object(db_session_module, "engine", old_engine),
            patch.object(db_session_module, "_create_engine", return_value=new_engine),
            patch.object(db_session_module, "_create_session_factory", MagicMock()),
        ):
            db_session_module.init_worker_process()

            old_engine.dispose.assert_awaited_once()
            assert db_session_module.engine is new_engine, (
                "module-level engine must be replaced — a child that keeps the "
                "parent's engine is exactly the bug this signal exists to prevent"
            )

    def test_session_factory_is_rebuilt_on_the_new_engine(self) -> None:
        """`AsyncSessionLocal` is rebound, and to the NEW engine.

        Disposing the engine while leaving the factory bound to it is the subtle
        half of this bug: sessions would keep being handed out from a pool that
        was just closed.
        """
        old_engine = MagicMock()
        old_engine.dispose = AsyncMock()
        new_engine = MagicMock()
        new_factory = MagicMock()

        with (
            patch.object(db_session_module, "engine", old_engine),
            patch.object(db_session_module, "_create_engine", return_value=new_engine),
            patch.object(
                db_session_module, "_create_session_factory", return_value=new_factory
            ) as make_factory,
        ):
            db_session_module.init_worker_process()

            make_factory.assert_called_once_with(new_engine)
            assert db_session_module.AsyncSessionLocal is new_factory

    def test_rebinding_is_visible_to_other_modules(self) -> None:
        """The rebind must reach callers that resolve it through the module.

        `init_worker_process` assigns via `sys.modules[__name__]` rather than
        `global`. Code that did `from app.db.session import AsyncSessionLocal`
        keeps the pre-fork object forever; code that reaches
        `session_mod.AsyncSessionLocal` at call time sees the new one. This
        pins that the module attribute really moves — the chat orchestrator's
        detached title task depends on it.
        """
        old_engine = MagicMock()
        old_engine.dispose = AsyncMock()
        new_factory = MagicMock(name="post-fork-factory")

        with (
            patch.object(db_session_module, "engine", old_engine),
            patch.object(db_session_module, "_create_engine", return_value=MagicMock()),
            patch.object(
                db_session_module, "_create_session_factory", return_value=new_factory
            ),
        ):
            db_session_module.init_worker_process()

            import importlib

            reread = importlib.import_module("app.db.session")
            assert reread.AsyncSessionLocal is new_factory


class TestSignalWiring:
    """A correct handler nobody calls protects nothing."""

    def test_handler_is_connected_to_worker_process_init(self) -> None:
        from celery.signals import worker_process_init

        from app.tasks import celery_app as celery_module

        receivers = [
            r() if callable(r) and not hasattr(r, "__name__") else r
            for _, r in worker_process_init.receivers
        ]
        names = {getattr(r, "__name__", "") for r in receivers if r is not None}
        assert "_on_worker_process_init" in names, (
            "celery_app._on_worker_process_init is not connected to "
            f"worker_process_init — every worker child would inherit the parent's "
            f"connection pool. Connected receivers: {sorted(names)}"
        )
        assert hasattr(celery_module, "_on_worker_process_init")

    def test_handler_delegates_to_init_worker_process(self) -> None:
        """And that the handler actually calls it, rather than merely existing."""
        from app.tasks.celery_app import _on_worker_process_init

        with patch.object(db_session_module, "init_worker_process") as init:
            _on_worker_process_init(sender="worker-1")
            init.assert_called_once()

    def test_session_is_not_imported_at_celery_module_level(self) -> None:
        """The import must stay inside the handler — that is the point of it.

        Importing `app.db.session` at module scope in `celery_app.py` would build
        the engine in the PARENT, before the fork, so every child would start
        from an inherited pool no matter what the handler does afterwards.
        """
        import ast
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[2] / "app" / "tasks" / "celery_app.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)

        for node in tree.body:  # module level only — nested imports are the fix
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("app.db"):
                raise AssertionError(
                    f"celery_app.py imports {node.module} at module level (line "
                    f"{node.lineno}) — this creates the engine before fork (INFRA-05)"
                )
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("app.db"), (
                        f"celery_app.py imports {alias.name} at module level "
                        f"(line {node.lineno}) — engine created before fork"
                    )
