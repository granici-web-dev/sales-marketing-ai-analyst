from __future__ import annotations

from celery import Celery
from celery.signals import worker_process_init

from app.core.config import settings

# Celery application instance.
#
# All future Celery tasks (Phase 2 ETL, Phase 3 metrics, Phase 5 AI insights)
# import `celery_app` from this module.
#
# IMPORTANT — fork-safety (INFRA-05 / T-05-04):
# Do NOT import app.db.session at module level. The module-level import would
# open an asyncpg connection pool BEFORE the Celery prefork pool forks worker
# processes. Shared file descriptors across fork boundaries cause:
#   - PostgreSQL SSL connection has been closed unexpectedly
#   - asyncpg.InterfaceError under concurrent worker load
#   - Silent data corruption
# The import is deferred to inside the _on_worker_process_init signal handler,
# which runs AFTER each worker child process is created.
celery_app = Celery(
    "sales_analyst",
    broker=settings.redis_url,
    backend=settings.redis_url,
    # List explicit task modules — pointing to the package alone (app.tasks.etl)
    # only imports the empty __init__.py and discovers no tasks.
    include=[
        "app.tasks",
        "app.tasks.etl.sync_mefi_leads",
        "app.tasks.etl.backfill_mefi_leads",
        "app.tasks.etl.calculate_daily_kpis",
        "app.tasks.etl.backfill_daily_kpis",
        "app.tasks.etl.detect_anomalies",  # Phase 4
        "app.tasks.insights.generate_daily_insights",  # Phase 5 — AI Insights
    ],
)

celery_app.conf.update(
    # Timezone — Europe/Bucharest (Romanian market pilot, INFRA-04)
    timezone="Europe/Bucharest",
    enable_utc=True,

    # celery-redbeat scheduler (INFRA-04)
    # Stores the beat schedule in Redis so it survives restarts.
    # RedBeatScheduler replaces the default file-based scheduler.
    beat_scheduler="redbeat.RedBeatScheduler",
    redbeat_redis_url=settings.redis_url,
    # redbeat_lock_timeout must be >= longest expected task runtime + loop interval.
    # Pitfall 7: if too short, beat fires the same task twice.
    # 9 hours (32400s) covers all ETL scenarios in Phase 2+ (INFRA-04 requires >= 8h).
    redbeat_lock_timeout=60 * 60 * 9,  # 32400 seconds = 9 hours
    redbeat_key_prefix="analyst:redbeat",

    # Visibility timeout (INFRA-04): Redis re-enqueues tasks that take longer
    # than visibility_timeout, causing duplicates. Must exceed the longest task runtime.
    # Phase 2 ETL backfill may take hours — 9h is safe.
    broker_transport_options={
        "visibility_timeout": 60 * 60 * 9,  # 32400 seconds = 9 hours
    },

    # Serialization — JSON only (T-05-02 mitigation).
    # pickle is disabled to prevent arbitrary code execution via malicious payloads.
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Worker reliability settings.
    # task_acks_late=True: task is acknowledged AFTER completion, not when received.
    #   Prevents task loss if worker crashes mid-execution.
    # task_reject_on_worker_lost=True: if worker dies, task is re-queued (not lost).
    # worker_prefetch_multiplier=1: one task at a time per worker — fair distribution
    #   and prevents a slow task from blocking the queue in a worker's prefetch buffer.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,

    # Task routing — backfill runs on a dedicated queue to avoid blocking
    # the default queue during 12-month historical data fetch (MEFI-12).
    #
    # WR-07: Task route keys must match the explicit name= kwarg in @celery_app.task
    # decorator. All tasks in app/tasks/etl/ MUST declare name="tasks.etl.<task_name>"
    # to match these routes. Without an explicit name=, Celery uses the module-dotted
    # path (e.g. "app.tasks.etl.backfill_mefi_leads") which does NOT match the route key.
    task_routes={
        "tasks.etl.backfill_mefi_leads": {"queue": "backfill"},
        "tasks.etl.backfill_daily_kpis": {"queue": "backfill"},
    },
)


# ── Daily pipeline beat schedule ─────────────────────────────────────────────
# Registered after conf.update() so redbeat_key_prefix is already set.
#
# Schedule: 04:00 Europe/Bucharest daily (INFRA-04, PIPE-01).
# Uses redbeat.RedBeatSchedulerEntry for Redis persistence.
#
# CR-01 fix: schedule the full daily_pipeline() chain, not standalone tasks.
# daily_pipeline() chains: sync_mefi_leads → calculate_daily_kpis →
#   detect_anomalies → generate_daily_insights (PIPE-02 chain halt semantics).
# If sync fails at 04:00, the chain halts — insights will NOT run against
# stale data. The standalone daily-insights-generation entry is removed;
# generate_daily_insights is now the 4th link in the chain.
try:
    from redbeat import RedBeatSchedulerEntry  # noqa: PLC0415
    from celery.schedules import crontab  # noqa: PLC0415

    from app.tasks.etl.sync_mefi_leads import daily_pipeline  # noqa: PLC0415

    _pipeline_sig = daily_pipeline(settings.sofa_belle_tenant_id)
    _entry = RedBeatSchedulerEntry(
        name="daily-pipeline",
        task=_pipeline_sig,  # full chain: sync → kpis → anomaly → insights
        schedule=crontab(hour=4, minute=0),
        app=celery_app,
    )
    _entry.save()
except Exception:  # noqa: BLE001
    # Beat schedule registration is best-effort at import time;
    # the beat container registers it authoritatively on startup.
    pass


@worker_process_init.connect
def _on_worker_process_init(**kwargs) -> None:  # type: ignore[no-untyped-def]
    """Create a fresh SQLAlchemy engine per Celery worker process (fork-safe).

    INFRA-05 / T-05-01 mitigation:
    This signal fires in each child process AFTER the Celery prefork pool
    creates it. By importing app.db.session HERE (not at module level), we
    ensure the asyncpg connection pool is never shared across fork boundaries.

    The import inside this function is intentional and required:
    - Module-level import would create DB connections before fork
    - Post-fork import creates a fresh engine per worker child

    D-08: worker and beat run as separate containers — this handler only runs
    in the `worker` container, never in the `beat` container.
    """
    from app.db.session import init_worker_process

    init_worker_process(**kwargs)
