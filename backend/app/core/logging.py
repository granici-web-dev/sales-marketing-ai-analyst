from __future__ import annotations

import logging

import structlog


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structlog for JSON output with async context propagation.

    Processor chain (T-03-03 — no PII in logs):
    1. merge_contextvars — injects tenant_id, request_id, task_id bound via
       bind_contextvars() in middleware/tasks; nothing else is auto-logged.
    2. add_log_level — adds the log level string to the event dict.
    3. add_logger_name — adds the Python logger name for easy filtering.
    4. TimeStamper — ISO 8601 timestamp.
    5. StackInfoRenderer — renders stack_info if present.
    6. format_exc_info — renders exc_info as structured exception dict.
    7. JSONRenderer — final output as a single-line JSON string.

    IMPORTANT: Uses pure structlog configuration, not BaseHTTPMiddleware.
    BaseHTTPMiddleware wraps endpoints in a new asyncio task group, which
    copies the context; bind_contextvars calls inside endpoints would NOT
    propagate back to a BaseHTTPMiddleware finally block. This configuration
    is safe for use with pure ASGI middleware. (RESEARCH.md Pitfall 5)

    Args:
        log_level: Python logging level string (e.g., "INFO", "DEBUG", "WARNING").
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(level=log_level)
