from __future__ import annotations

"""Business-hours-adjusted duration utility.

Provides business_minutes_between() — the core helper for computing
time_to_first_touch with working-minutes-only counting.

D-06: avg_time_to_first_touch_minutes is business-hours-adjusted.
D-07: Default Sofa Belle schedule is Mon-Sun 09:00-19:00 Europe/Bucharest.
Pitfall 1: DST transitions handled via zoneinfo (never fixed UTC offset).

Phase 3 Plan 03 — pure Python, no async, no DB dependency.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


def _next_open(
    current: datetime,
    open_time: time,
    work_days: list[int],
    tz: ZoneInfo,
) -> datetime:
    """Advance current to the next valid business-hours open boundary.

    Iterates forward (one calendar day at a time) until finding a work day,
    then returns that day's open_time. The returned datetime is tz-aware in
    the given timezone.

    Args:
        current: Starting point (tz-aware, local timezone).
        open_time: Business open time (local).
        work_days: ISO weekday ints (Mon=0 … Sun=6).
        tz: ZoneInfo timezone (used to construct the open boundary datetime).

    Returns:
        tz-aware datetime at the next valid open_time on a work day.
    """
    # Build a candidate "open" datetime on the same calendar day as current.
    # We advance by whole days until we land on a work day.
    candidate_date = current.date()
    # Start from current.date() if current is in the morning (pre-open)
    # Otherwise start from the next day.
    while True:
        if candidate_date.weekday() in work_days:
            open_dt = datetime(
                candidate_date.year,
                candidate_date.month,
                candidate_date.day,
                open_time.hour,
                open_time.minute,
                0,
                0,
                tzinfo=tz,
            )
            return open_dt
        candidate_date += timedelta(days=1)


def business_minutes_between(
    start_utc: datetime,
    end_utc: datetime,
    open_time: time,
    close_time: time,
    work_days: list[int],
    tz: ZoneInfo | None = None,
) -> int:
    """Count business minutes between two UTC timestamps.

    DST-safe via zoneinfo. Counts minutes in [open_time, close_time) windows
    on work_days. If start_utc is outside business hours, counting begins at
    the next valid open boundary.

    D-06: business-hours adjustment — only working minutes count.
    D-07: Default Sofa Belle schedule is Mon-Sun 09:00-19:00 Bucharest.
    Pitfall 1: zoneinfo handles Romanian EET↔EEST transitions correctly.

    Args:
        start_utc: Lead creation time (TIMESTAMPTZ from DB, tz-aware).
        end_utc: First history row changed_at (TIMESTAMPTZ, tz-aware).
        open_time: Business hours open (local time, e.g. time(9, 0)).
        close_time: Business hours close (local time, e.g. time(19, 0)).
        work_days: ISO weekday ints (Mon=0 … Sun=6).
        tz: ZoneInfo timezone; defaults to Europe/Bucharest if None (D-07).

    Returns:
        Integer count of business minutes elapsed. Returns 0 when
        end_utc <= start_utc (data quality guard — D-05).
    """
    if tz is None:
        tz = ZoneInfo("Europe/Bucharest")

    # CR-04 FIX: defence-in-depth guard against empty work_days.
    # _next_open loops forever when work_days is [] (while True: weekday() in [] → always False).
    # The primary guard is in salesperson_kpi_service._get_business_hours which raises
    # ValueError for empty work_days; this guard catches any other call paths.
    if not work_days:
        return 0

    # Guard: data quality — first touch before creation time returns 0.
    if end_utc <= start_utc:
        return 0

    # Convert both endpoints to the local timezone for day/time comparisons.
    # ZoneInfo handles DST automatically (Pitfall 1).
    start_local = start_utc.astimezone(tz)
    end_local = end_utc.astimezone(tz)

    total_minutes = 0
    current = start_local

    while current < end_local:
        day_of_week = current.weekday()

        # Not a work day — jump to the next open window.
        if day_of_week not in work_days:
            next_day_date = current.date() + timedelta(days=1)
            next_day_start = datetime(
                next_day_date.year,
                next_day_date.month,
                next_day_date.day,
                0, 0, 0, 0,
                tzinfo=tz,
            )
            current = _next_open(next_day_start, open_time, work_days, tz)
            continue

        # Build open/close boundaries for the current calendar day.
        open_dt = datetime(
            current.year,
            current.month,
            current.day,
            open_time.hour,
            open_time.minute,
            0, 0,
            tzinfo=tz,
        )
        close_dt = datetime(
            current.year,
            current.month,
            current.day,
            close_time.hour,
            close_time.minute,
            0, 0,
            tzinfo=tz,
        )

        # Before open: advance to open without counting.
        if current < open_dt:
            current = open_dt
            continue

        # At or after close: jump to next work day's open.
        if current >= close_dt:
            next_day_date = current.date() + timedelta(days=1)
            next_day_start = datetime(
                next_day_date.year,
                next_day_date.month,
                next_day_date.day,
                0, 0, 0, 0,
                tzinfo=tz,
            )
            current = _next_open(next_day_start, open_time, work_days, tz)
            continue

        # current is within business hours — count to min(close_dt, end_local).
        count_until = min(close_dt, end_local)
        minutes = int((count_until - current).total_seconds() / 60)
        total_minutes += minutes
        current = count_until

    return total_minutes
