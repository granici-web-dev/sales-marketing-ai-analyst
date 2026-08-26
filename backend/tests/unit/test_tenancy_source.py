"""One source of truth for the tenant on the HTTP request path.

## Why this file exists

The tenant reaches an endpoint by two roads, and one of them leads elsewhere.

`StructlogContextMiddleware` puts `tenant_id` into a ContextVar on every
request; `require_tenant_id()` reads it back. That is the right road — every
Celery task takes it, and so do the six chat endpoints.

The second road is `settings.sofa_belle_tenant_id`, read straight from config.
Today it gives the same answer: one tenant, both values equal, no way to see
the difference. The difference appears the day the ContextVar starts being
filled from the JWT: chat will serve whoever logged in, and everything reading
config will keep serving Sofa Belle. Same 200, wrong data, nothing in the log.

Review does not catch this. Both lines look equally correct, and they diverge
not when they are written but when someone else changes what fills the
ContextVar. So the check lives next to the code instead of in someone's memory.

Same shape as the PII check in `test_logging.py`: a property of the source is
checked by walking the AST, not by running anything.
"""

from __future__ import annotations

import ast
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[2] / "app" / "api"

# The one setting that has no business on the request path. A single name, on
# purpose: a list of forbidden names would make sense if there were many tenant
# sources, and there must remain exactly one.
FORBIDDEN_ATTR = "sofa_belle_tenant_id"


def _api_sources() -> list[Path]:
    return sorted(API_DIR.rglob("*.py"))


def _forbidden_reads(tree: ast.AST) -> list[int]:
    """Line numbers where the forbidden setting is read."""
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr == FORBIDDEN_ATTR
    ]


def test_the_sweep_actually_reads_files() -> None:
    """Guard the guard.

    A sweep over an empty file list passes silently and looks exactly like a
    sweep over clean code. Rename the directory and the check below goes green
    forever with nobody the wiser.
    """
    sources = _api_sources()
    assert len(sources) >= 5, f"only {len(sources)} modules found under {API_DIR}"


def test_no_api_module_reads_the_tenant_from_settings() -> None:
    offenders: list[str] = []
    for path in _api_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        offenders += [
            f"{path.relative_to(API_DIR.parent.parent)}:{lineno}"
            for lineno in _forbidden_reads(tree)
        ]

    assert not offenders, (
        "tenant read from settings, bypassing the request context: "
        + ", ".join(offenders)
        + " — use require_tenant_id() instead"
    )


def test_the_check_catches_a_violation() -> None:
    """The check must fail on a violation, or it is guarding nothing."""
    source = "svc = ReadService(session, UUID(settings.sofa_belle_tenant_id))"
    assert _forbidden_reads(ast.parse(source)) == [1]
