"""
Tests for celery_app module behaviors — Plan 01-05 TDD RED phase.

Task 1 behaviors tested:
- celery_app.conf.timezone == "Europe/Bucharest"
- celery_app.conf.beat_scheduler == "redbeat.RedBeatScheduler"
- celery_app.conf.broker_transport_options["visibility_timeout"] == 32400
- celery_app.conf.redbeat_lock_timeout == 32400
- celery_app.conf.task_acks_late == True
- celery_app.conf.worker_prefetch_multiplier == 1
- celery_app.conf.task_serializer == "json"
- celery_app.conf.result_serializer == "json"
- celery_app.conf.accept_content == ["json"]
- celery_app.conf.task_reject_on_worker_lost == True
- celery_app.conf.enable_utc == True
- celery_app broker and backend are set to settings.redis_url
- app.db.session is NOT imported at module level of celery_app (fork-safety T-05-04)
- worker_process_init signal is connected (worker_process_init.receivers is non-empty)
"""
from __future__ import annotations


class TestCeleryAppConfig:
    """Verify the Celery application configuration for INFRA-04."""

    def test_timezone_is_europe_bucharest(self):
        from app.tasks.celery_app import celery_app
        assert celery_app.conf.timezone == "Europe/Bucharest"

    def test_enable_utc_is_true(self):
        from app.tasks.celery_app import celery_app
        assert celery_app.conf.enable_utc is True

    def test_beat_scheduler_is_redbeat(self):
        from app.tasks.celery_app import celery_app
        assert celery_app.conf.beat_scheduler == "redbeat.RedBeatScheduler"

    def test_visibility_timeout_is_9h(self):
        """INFRA-04: visibility_timeout must be >= 8h (32400 = 9h)."""
        from app.tasks.celery_app import celery_app
        vt = celery_app.conf.broker_transport_options["visibility_timeout"]
        assert vt == 32400, f"Expected 32400 (9h), got {vt}"

    def test_visibility_timeout_meets_8h_minimum(self):
        """INFRA-04: visibility_timeout >= 28800 (8 hours)."""
        from app.tasks.celery_app import celery_app
        vt = celery_app.conf.broker_transport_options["visibility_timeout"]
        assert vt >= 28800, f"visibility_timeout {vt} is less than 8h (28800s)"

    def test_redbeat_lock_timeout_is_9h(self):
        """Pitfall 7: redbeat_lock_timeout too short causes duplicate tasks."""
        from app.tasks.celery_app import celery_app
        assert celery_app.conf.redbeat_lock_timeout == 32400

    def test_task_serializer_is_json(self):
        """T-05-02: no pickle deserialization (arbitrary code execution risk)."""
        from app.tasks.celery_app import celery_app
        assert celery_app.conf.task_serializer == "json"

    def test_result_serializer_is_json(self):
        from app.tasks.celery_app import celery_app
        assert celery_app.conf.result_serializer == "json"

    def test_accept_content_is_json_only(self):
        """T-05-02: accept_content must not include 'pickle'."""
        from app.tasks.celery_app import celery_app
        assert celery_app.conf.accept_content == ["json"]
        assert "pickle" not in celery_app.conf.accept_content

    def test_task_acks_late_is_true(self):
        """Worker reliability: task only ACKed after successful completion."""
        from app.tasks.celery_app import celery_app
        assert celery_app.conf.task_acks_late is True

    def test_task_reject_on_worker_lost_is_true(self):
        from app.tasks.celery_app import celery_app
        assert celery_app.conf.task_reject_on_worker_lost is True

    def test_worker_prefetch_multiplier_is_1(self):
        """One task at a time per worker — fair task distribution."""
        from app.tasks.celery_app import celery_app
        assert celery_app.conf.worker_prefetch_multiplier == 1

    def test_redbeat_redis_url_matches_settings(self):
        from app.core.config import settings
        from app.tasks.celery_app import celery_app
        assert celery_app.conf.redbeat_redis_url == settings.redis_url

    def test_broker_is_redis_url(self):
        from app.core.config import settings
        from app.tasks.celery_app import celery_app
        assert celery_app.conf.broker_url == settings.redis_url

    def test_backend_is_redis_url(self):
        from app.core.config import settings
        from app.tasks.celery_app import celery_app
        assert celery_app.conf.result_backend == settings.redis_url


class TestCeleryForkSafety:
    """Verify fork-safe design for INFRA-05 / T-05-04."""

    def test_app_db_session_not_imported_at_module_level(self):
        """T-05-04: DB must not be imported at module level — only inside signal handler.

        If app.db.session is imported at module level of celery_app, the
        asyncpg connection pool is created before fork, causing data corruption
        under concurrent worker load (Pitfall 4 / T-05-04).
        """
        import ast
        import pathlib

        celery_app_path = pathlib.Path(__file__).parent.parent.parent / "app" / "tasks" / "celery_app.py"
        source = celery_app_path.read_text()
        tree = ast.parse(source)

        # Collect all module-level import statements (not inside any function/class)
        module_level_imports = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                # Module-level import
                if isinstance(node, ast.ImportFrom) and node.module:
                    module_level_imports.append(node.module)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        module_level_imports.append(alias.name)

        # app.db.session or app.db must not appear as a module-level import
        for imp in module_level_imports:
            assert "app.db" not in imp, (
                f"Found module-level import of '{imp}' in celery_app.py — "
                "this violates T-05-04 (DB connections before fork). "
                "Move 'from app.db.session import init_worker_process' inside the signal handler."
            )

    def test_worker_process_init_signal_connected(self):
        """INFRA-05: worker_process_init signal must have a receiver registered."""
        from celery.signals import worker_process_init


        # celery signals use Django-style dispatch; receivers is a list of weak refs
        assert len(worker_process_init.receivers) > 0, (
            "worker_process_init signal has no receivers — "
            "_on_worker_process_init was not connected via @worker_process_init.connect"
        )
