"""INFRA-06 — structlog configuration and the no-PII rule.

## Why this file was rewritten (2026-08-25)

It was a Wave 0 stub: disabled by a module-level `pytest.mark.skip(reason=
"Stubs — implementation pending")` and written to tolerate a missing
`configure_logging`, which has existed since Phase 1. Neither test had run.

The PII test was worse than dormant — it was **vacuous by construction**. It
logged an event carrying no PII, then asserted that `"Ion Popescu"`,
`"0721000000"` and `"ion@test.ro"` were absent from the output. They were never
put there. The assertion could not fail, and its own comment says as much:
"These must NOT appear in the output — they are reference values to check",
next to a `logger.info()` call that passes none of them.

Un-skipping it would have produced a green test guarding nothing, which is how
the rest of this suite came to be trusted while stale.

## What is actually guaranteed, and therefore what is tested here

There is no scrubbing processor. Nothing inspects a log call and removes a
phone number. Read the chain in `app/core/logging.py`: the guarantee is
`merge_contextvars` plus explicit kwargs and nothing else — structlog never
harvests locals, arguments or object attributes on its own. PII reaches a log
line only when a developer writes it there.

That splits the promise in two, and each half needs a different kind of test:

  - **the mechanism** — JSON renders, bound context arrives, and nothing
    appears that no one asked for. Checked at runtime, below.
  - **the discipline** — no call site passes PII. That is a property of the
    source, not of a run, so it is checked by walking the AST of `app/`, in the
    spirit of the CHAT-08 grep gate in `tests/unit/chat/test_chat_router.py`.

CLAUDE.md: "Never log: phone numbers, email addresses, customer names,
transcript content."
"""
from __future__ import annotations

import ast
import io
import json
import logging
from pathlib import Path

import pytest
import structlog

from app.core.logging import configure_logging

APP_DIR = Path(__file__).resolve().parents[2] / "app"

# Names that carry customer PII. A log call may not take any of them as a
# keyword. `*_id` is deliberately absent: an opaque identifier is what we log
# INSTEAD of the value, and banning it would push people back to logging names.
PII_KEYWORDS = {
    "email",
    "e_mail",
    "phone",
    "phone_number",
    "customer_name",
    "customer_email",
    "customer_phone",
    "client_name",
    "lead_name",
    "full_name",
    "address",
    "transcript",
    "user_text",
    "message_text",
    "message_content",
}

LOG_METHODS = {"debug", "info", "warning", "warn", "error", "exception", "critical"}
LOG_RECEIVERS = {"log", "logger", "_log", "self._log", "structlog"}


@pytest.fixture
def captured_log() -> io.StringIO:
    """Route structlog output into a buffer, then put logging back as it was.

    `configure_logging` calls `logging.basicConfig`, and structlog caches bound
    loggers (`cache_logger_on_first_use=True`), so a test that swaps handlers
    without restoring them changes the behaviour of every test after it.
    """
    configure_logging()
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setLevel(logging.DEBUG)

    root = logging.getLogger()
    saved_handlers, saved_level = root.handlers[:], root.level
    root.handlers = [handler]
    root.setLevel(logging.DEBUG)
    structlog.contextvars.clear_contextvars()
    try:
        yield buf
    finally:
        structlog.contextvars.clear_contextvars()
        root.handlers, root.level = saved_handlers, saved_level


def _last_line(buf: io.StringIO) -> dict:
    output = buf.getvalue().strip()
    assert output, "no log output captured — is configure_logging() still wiring stdlib logging?"
    return json.loads(output.splitlines()[-1])


class TestLogFormat:
    def test_output_is_single_line_json(self, captured_log: io.StringIO) -> None:
        """Log shipping parses one JSON object per line; a pretty-printed dict breaks it."""
        structlog.get_logger("t").info("an_event", action="unit_test")

        raw = captured_log.getvalue().strip()
        assert len(raw.splitlines()) == 1, f"one event must render as one line, got:\n{raw}"

        line = json.loads(raw)
        assert line["event"] == "an_event"
        assert line["level"] == "info"
        assert line["action"] == "unit_test"
        assert "timestamp" in line

    def test_bound_context_reaches_the_line(self, captured_log: io.StringIO) -> None:
        """tenant_id / request_id are bound by middleware and tasks, never passed by hand.

        This is the whole reason `merge_contextvars` is first in the chain: a
        log line with no tenant is unattributable, and in a product that will
        eventually be multi-tenant that makes an incident unreadable.
        """
        structlog.contextvars.bind_contextvars(
            tenant_id="00000000-0000-0000-0000-000000000001",
            request_id="req-42",
        )
        structlog.get_logger("t").info("scoped_event")

        line = _last_line(captured_log)
        assert line["tenant_id"] == "00000000-0000-0000-0000-000000000001"
        assert line["request_id"] == "req-42"

    def test_nothing_arrives_that_nobody_bound(self, captured_log: io.StringIO) -> None:
        """The actual PII guarantee, stated as a test.

        structlog adds only what the configured processors add. It does not
        reach into the caller's frame. So with nothing bound and nothing passed,
        the key set must be exactly the four the chain produces — and a
        processor added later that harvests context wholesale would fail here
        rather than start quietly writing customer data to disk.
        """
        structlog.get_logger("t").info("bare_event")

        assert set(_last_line(captured_log)) == {"event", "level", "logger", "timestamp"}

    def test_context_does_not_leak_between_bindings(self, captured_log: io.StringIO) -> None:
        """A cleared context must not survive into the next event.

        Celery reuses worker processes across tasks. A tenant_id that outlived
        its task would label another tenant's log lines — the failure would look
        like a data leak long before anyone suspected the logger.
        """
        structlog.contextvars.bind_contextvars(tenant_id="tenant-a")
        structlog.get_logger("t").info("first")
        structlog.contextvars.clear_contextvars()
        structlog.get_logger("t").info("second")

        lines = [json.loads(line) for line in captured_log.getvalue().strip().splitlines()]
        assert lines[0]["tenant_id"] == "tenant-a"
        assert "tenant_id" not in lines[1], f"tenant_id survived the clear: {lines[1]}"


class TestNoPiiAtCallSites:
    """The discipline half — a property of the source, checked in the source."""

    @staticmethod
    def _log_calls(tree: ast.AST):
        """Yield every `<something>.info(...)`-shaped call in a module."""
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in LOG_METHODS:
                continue
            receiver = ast.unparse(node.func.value)
            if receiver.split(".")[-1] in LOG_RECEIVERS or receiver in LOG_RECEIVERS:
                yield node

    def test_the_sweep_actually_finds_log_calls(self) -> None:
        """Guard the guard.

        The check below iterates over discovered call sites. If the matcher
        stopped recognising them — a renamed logger variable, a change in how
        `ast.unparse` renders a receiver — it would sweep an empty set and pass
        for the same reason the stub it replaces used to.
        """
        found = sum(
            len(list(self._log_calls(ast.parse(p.read_text(encoding="utf-8")))))
            for p in APP_DIR.rglob("*.py")
        )
        assert found >= 50, f"only {found} log calls found across app/ — is the matcher still right?"

    def test_no_log_call_passes_pii_as_a_keyword(self) -> None:
        """CLAUDE.md: never log names, phone numbers, e-mail addresses, transcripts.

        Nothing at runtime enforces this — structlog will serialise whatever it
        is handed. The only place it can be enforced is here.
        """
        offenders: list[str] = []

        for path in sorted(APP_DIR.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for call in self._log_calls(tree):
                for keyword in call.keywords:
                    if keyword.arg in PII_KEYWORDS:
                        rel = path.relative_to(APP_DIR.parent)
                        offenders.append(f"{rel}:{call.lineno} — {keyword.arg}=")

        assert not offenders, (
            "log calls passing customer PII (CLAUDE.md, INFRA-06). Log an opaque "
            "id instead, and look the value up when investigating:\n  "
            + "\n  ".join(offenders)
        )

    def test_the_pii_check_catches_a_violation(self) -> None:
        """Prove the matcher would fail on a real offence, rather than trusting it."""
        source = 'logger.info("lead_created", lead_id=str(lead.id), email=lead.email)'
        call = next(self._log_calls(ast.parse(source)))
        assert {k.arg for k in call.keywords} & PII_KEYWORDS == {"email"}
