"""Tests for backfill_mefi_leads Celery task.

Tests:
- get_12_month_windows returns 12 tuples with correct date boundaries (MEFI-12)
- month_window helper returns correct (first, last) dates per month
- backfill_mefi_leads task name matches task_routes key in celery_app.py
- Task has correct Celery configuration (bind=True, max_retries)
- No module-level DB imports (fork-safe per Pitfall 8)

Note: Integration tests (actual DB calls, MefiClient interaction) require Docker
and live in tests/integration/. This file covers pure unit behaviour only.
"""
from __future__ import annotations

import ast
import inspect
from datetime import date
from pathlib import Path


# ---------------------------------------------------------------------------
# Helper: load and inspect the module source WITHOUT importing it.
# Importing would pull in app.tasks.celery_app which requires Redis to be up.
# We use AST inspection for structural tests and direct function extraction
# for pure-Python helpers (get_12_month_windows, month_window) that have no
# external dependencies at the module level.
# ---------------------------------------------------------------------------

BACKFILL_MODULE_PATH = (
    Path(__file__).parent.parent.parent
    / "app" / "tasks" / "etl" / "backfill_mefi_leads.py"
)


def _read_source() -> str:
    return BACKFILL_MODULE_PATH.read_text()


def _parse_ast() -> ast.Module:
    return ast.parse(_read_source())


# ---------------------------------------------------------------------------
# 1. Module-level import safety (fork-safety — Pitfall 8)
# ---------------------------------------------------------------------------


class TestForkSafety:
    """Ensure no DB / session imports at module level (they must be inside functions)."""

    def test_no_module_level_db_import(self) -> None:
        """app.db must NOT appear in module-level import statements."""
        tree = _parse_ast()
        # Only check top-level nodes (tree.body), not inside function bodies
        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith("app.db"):
                    raise AssertionError(
                        f"Module-level 'from {node.module} import ...' found — "
                        "DB imports must be inside function bodies (fork-safety Pitfall 8)"
                    )

    def test_no_module_level_services_import(self) -> None:
        """app.services must NOT appear in module-level import statements."""
        tree = _parse_ast()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith("app.services"):
                    raise AssertionError(
                        f"Module-level 'from {node.module} import ...' found — "
                        "service imports must be inside function bodies (fork-safety Pitfall 8)"
                    )

    def test_no_module_level_models_import(self) -> None:
        """app.models must NOT appear in module-level import statements."""
        tree = _parse_ast()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith("app.models"):
                    raise AssertionError(
                        f"Module-level 'from {node.module} import ...' found — "
                        "model imports must be inside function bodies (fork-safety Pitfall 8)"
                    )

    def _get_module_level_imports(self) -> list[ast.ImportFrom]:
        """Return only top-level ImportFrom nodes (direct children of Module)."""
        tree = _parse_ast()
        return [
            node for node in tree.body
            if isinstance(node, ast.ImportFrom)
        ]

    def test_only_stdlib_and_celery_at_module_level(self) -> None:
        """Only stdlib + celery_app imports allowed at module level."""
        allowed_prefixes = (
            "app.tasks.celery_app",  # Celery app instance — safe
        )
        stdlib_modules = {
            "asyncio", "calendar", "datetime", "uuid", "typing",
            "__future__", "decimal", "collections", "functools",
        }
        for node in self._get_module_level_imports():
            mod = node.module or ""
            # stdlib by checking against known stdlib names (no dots leading with 'app')
            if mod.startswith("app."):
                assert any(mod == prefix or mod.startswith(prefix + ".") for prefix in allowed_prefixes), (
                    f"Unexpected module-level import 'from {mod}' — only "
                    f"app.tasks.celery_app is allowed at module level"
                )


# ---------------------------------------------------------------------------
# 2. Task registration (name must match task_routes in celery_app.py)
# ---------------------------------------------------------------------------


class TestTaskName:
    """Verify the Celery task name matches the task_routes key."""

    def test_task_name_in_source(self) -> None:
        """backfill_mefi_leads must declare name='tasks.etl.backfill_mefi_leads'."""
        source = _read_source()
        assert 'name="tasks.etl.backfill_mefi_leads"' in source or \
               "name='tasks.etl.backfill_mefi_leads'" in source, (
            "Task decorator must include name='tasks.etl.backfill_mefi_leads' "
            "to match task_routes configured in celery_app.py (Plan 02-03)"
        )

    def test_bind_true_in_source(self) -> None:
        """Task must use bind=True for self.retry() access."""
        source = _read_source()
        assert "bind=True" in source, (
            "Task must declare bind=True to access self.retry() for RateLimitError handling"
        )

    def test_max_retries_in_source(self) -> None:
        """Task must specify max_retries (plan requires 5)."""
        source = _read_source()
        assert "max_retries=5" in source, (
            "backfill_mefi_leads must declare max_retries=5 (plan requirement)"
        )


# ---------------------------------------------------------------------------
# 3. Pure helper function correctness
# ---------------------------------------------------------------------------
# We extract and exec only the pure stdlib helpers to avoid Celery/Redis boot.


def _exec_helpers() -> dict:
    """Execute only the pure helpers from the module in an isolated namespace."""
    source = _read_source()
    tree = _parse_ast()

    # Extract source lines for: month_window and get_12_month_windows functions
    # We collect the function source by finding their line ranges in the AST.
    lines = source.splitlines()
    helper_funcs = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in (
            "month_window", "get_12_month_windows"
        ):
            helper_funcs.append(node)

    if not helper_funcs:
        raise AssertionError(
            "month_window and get_12_month_windows functions not found in source"
        )

    # Reconstruct source for helpers only
    func_sources = []
    for func in sorted(helper_funcs, key=lambda n: n.lineno):
        end_line = func.end_lineno  # type: ignore[attr-defined]
        func_source = "\n".join(lines[func.lineno - 1 : end_line])
        func_sources.append(func_source)

    combined = (
        "from __future__ import annotations\n"
        "from calendar import monthrange\n"
        "from datetime import date, datetime, timezone\n"
        "UTC = timezone.utc\n"
    ) + "\n\n".join(func_sources)

    namespace: dict = {}
    exec(compile(combined, "<helpers>", "exec"), namespace)  # noqa: S102
    return namespace


class TestMonthWindow:
    """month_window(year, month) -> (date, date)"""

    def test_january(self) -> None:
        ns = _exec_helpers()
        month_window = ns["month_window"]
        first, last = month_window(2026, 1)
        assert first == date(2026, 1, 1)
        assert last == date(2026, 1, 31)

    def test_february_non_leap(self) -> None:
        ns = _exec_helpers()
        month_window = ns["month_window"]
        first, last = month_window(2025, 2)
        assert first == date(2025, 2, 1)
        assert last == date(2025, 2, 28)

    def test_february_leap(self) -> None:
        ns = _exec_helpers()
        month_window = ns["month_window"]
        first, last = month_window(2024, 2)
        assert first == date(2024, 2, 1)
        assert last == date(2024, 2, 29)

    def test_april_30_days(self) -> None:
        ns = _exec_helpers()
        month_window = ns["month_window"]
        first, last = month_window(2026, 4)
        assert first == date(2026, 4, 1)
        assert last == date(2026, 4, 30)

    def test_december(self) -> None:
        ns = _exec_helpers()
        month_window = ns["month_window"]
        first, last = month_window(2025, 12)
        assert first == date(2025, 12, 1)
        assert last == date(2025, 12, 31)


class TestGet12MonthWindows:
    """get_12_month_windows(reference_date) -> list[tuple[date, date]]

    From the plan specification:
    get_12_month_windows(date(2026, 5, 21)) must return exactly 12 tuples:
    - First: (date(2025, 5, 1), date(2025, 5, 31))
    - Last:  (date(2026, 4, 1), date(2026, 4, 30))
    Current month (2026-05) is excluded (handled by incremental sync, D-04).
    """

    def test_returns_12_windows(self) -> None:
        ns = _exec_helpers()
        get_12_month_windows = ns["get_12_month_windows"]
        windows = get_12_month_windows(date(2026, 5, 21))
        assert len(windows) == 12, f"Expected 12 windows, got {len(windows)}"

    def test_first_window_is_12_months_ago(self) -> None:
        ns = _exec_helpers()
        get_12_month_windows = ns["get_12_month_windows"]
        windows = get_12_month_windows(date(2026, 5, 21))
        first_start, first_end = windows[0]
        assert first_start == date(2025, 5, 1), (
            f"First window start expected 2025-05-01, got {first_start}"
        )
        assert first_end == date(2025, 5, 31), (
            f"First window end expected 2025-05-31, got {first_end}"
        )

    def test_last_window_is_previous_month(self) -> None:
        ns = _exec_helpers()
        get_12_month_windows = ns["get_12_month_windows"]
        windows = get_12_month_windows(date(2026, 5, 21))
        last_start, last_end = windows[-1]
        assert last_start == date(2026, 4, 1), (
            f"Last window start expected 2026-04-01, got {last_start}"
        )
        assert last_end == date(2026, 4, 30), (
            f"Last window end expected 2026-04-30, got {last_end}"
        )

    def test_windows_are_consecutive(self) -> None:
        ns = _exec_helpers()
        get_12_month_windows = ns["get_12_month_windows"]
        windows = get_12_month_windows(date(2026, 5, 21))
        for i in range(len(windows) - 1):
            curr_end = windows[i][1]
            next_start = windows[i + 1][0]
            # next month starts on 1st, one day after current month end
            from datetime import timedelta
            assert next_start == curr_end + timedelta(days=1), (
                f"Gap between window {i} and {i+1}: {curr_end} vs {next_start}"
            )

    def test_current_month_excluded(self) -> None:
        """The reference month (2026-05) must NOT appear in the windows."""
        ns = _exec_helpers()
        get_12_month_windows = ns["get_12_month_windows"]
        windows = get_12_month_windows(date(2026, 5, 21))
        may_2026_start = date(2026, 5, 1)
        window_starts = [w[0] for w in windows]
        assert may_2026_start not in window_starts, (
            "Current month (2026-05) must NOT be in windows — handled by incremental sync (D-04)"
        )

    def test_year_boundary_january_reference(self) -> None:
        """reference_date=2026-01-15 → windows from 2025-01 to 2025-12."""
        ns = _exec_helpers()
        get_12_month_windows = ns["get_12_month_windows"]
        windows = get_12_month_windows(date(2026, 1, 15))
        assert len(windows) == 12
        first_start, first_end = windows[0]
        assert first_start == date(2025, 1, 1)
        assert first_end == date(2025, 1, 31)
        last_start, last_end = windows[-1]
        assert last_start == date(2025, 12, 1)
        assert last_end == date(2025, 12, 31)

    def test_year_boundary_march_reference(self) -> None:
        """reference_date=2025-03-10 → windows from 2024-03 to 2025-02."""
        ns = _exec_helpers()
        get_12_month_windows = ns["get_12_month_windows"]
        windows = get_12_month_windows(date(2025, 3, 10))
        assert len(windows) == 12
        first_start, _ = windows[0]
        assert first_start == date(2024, 3, 1)
        last_start, last_end = windows[-1]
        assert last_start == date(2025, 2, 1)
        assert last_end == date(2025, 2, 28)  # 2025 not a leap year


# ---------------------------------------------------------------------------
# 4. Structural: no chain() call in the backfill task (D-14 excludes backfill)
# ---------------------------------------------------------------------------


class TestNoChain:
    """backfill_mefi_leads must NOT trigger the metrics chain (D-14 is for sync only)."""

    def test_no_chain_import_at_module_level(self) -> None:
        """chain() must not be imported at module level."""
        tree = _parse_ast()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module == "celery":
                imported_names = [alias.name for alias in node.names]
                assert "chain" not in imported_names, (
                    "chain must not be imported at module level in backfill_mefi_leads.py — "
                    "backfill does NOT trigger downstream pipeline (plan spec)"
                )

    def test_no_chain_call_in_source(self) -> None:
        """The backfill task must not call chain() anywhere."""
        source = _read_source()
        # Allow 'chain' in comments but not in actual code
        non_comment_lines = [
            line for line in source.splitlines()
            if not line.strip().startswith("#")
        ]
        non_comment_source = "\n".join(non_comment_lines)
        assert "chain(" not in non_comment_source, (
            "backfill_mefi_leads must NOT call chain() — it is a standalone historical "
            "fill task; downstream pipeline is triggered only by sync_mefi_leads (D-14)"
        )
