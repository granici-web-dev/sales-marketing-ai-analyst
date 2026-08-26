"""Unit tests for business-hours-adjusted time_to_first_touch calculation.

Pure Python — no AsyncSession or DB required.
Tests DST transitions, edge cases, and boundary conditions (D-06, D-07).

Requirements: METR-04
Tests D-06 (business-hours-adjusted only working minutes count),
D-07 (Mon-Sun 09:00-19:00 Europe/Bucharest).

Import at module top (no try/except) — makes file RED at collection if
app.services.metrics.business_hours does not exist (desired RED state for Wave 0).
"""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

from app.services.metrics.business_hours import business_minutes_between

BUCHAREST = ZoneInfo("Europe/Bucharest")

# D-07: Sofa Belle business hours — Mon-Sun, 09:00-19:00 Europe/Bucharest
WORK_DAYS = [0, 1, 2, 3, 4, 5, 6]  # Mon=0 … Sun=6 (7 days/week)
OPEN_TIME = time(9, 0)
CLOSE_TIME = time(19, 0)


def _buch(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    """Create a Bucharest-local datetime (tz-aware)."""
    return datetime(year, month, day, hour, minute, tzinfo=BUCHAREST)


def _utc_from_buch(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    """Create a UTC datetime from Bucharest local time."""
    local = _buch(year, month, day, hour, minute)
    return local.astimezone(ZoneInfo("UTC"))


class TestBusinessMinutesBetween:
    """Tests for business_minutes_between() — core utility for time_to_first_touch."""

    def test_lead_created_inside_hours_first_touch_same_window(self) -> None:
        """Lead created 10:00, first touch 10:30 → 30 business minutes (D-06).

        Both timestamps within business hours (09:00-19:00 Bucharest, D-07).
        No window crossing — simple elapsed time.
        """
        start_utc = _utc_from_buch(2026, 5, 24, 10, 0)   # Sunday 10:00 Bucharest
        end_utc = _utc_from_buch(2026, 5, 24, 10, 30)    # Sunday 10:30 Bucharest
        result = business_minutes_between(
            start_utc, end_utc, OPEN_TIME, CLOSE_TIME, WORK_DAYS
        )
        assert result == 30, (
            f"Lead created 10:00, first touch 10:30 → 30 business minutes, got {result}"
        )

    def test_lead_created_outside_hours_first_touch_next_window(self) -> None:
        """Lead created Friday 20:00, first touch Saturday 09:30 → 30 minutes (D-07).

        Lead created outside hours (20:00 > 19:00 close). Clock starts at 09:00 next day.
        Since D-07: Mon-Sun (Sofa Belle works 7 days), Saturday is a work day.
        First touch at Saturday 09:30 = 30 business minutes from window open.
        """
        start_utc = _utc_from_buch(2026, 5, 22, 20, 0)   # Friday 20:00 Bucharest (outside hours)
        end_utc = _utc_from_buch(2026, 5, 23, 9, 30)     # Saturday 09:30 Bucharest
        result = business_minutes_between(
            start_utc, end_utc, OPEN_TIME, CLOSE_TIME, WORK_DAYS
        )
        assert result == 30, (
            f"Created 20:00 Fri, touched 09:30 Sat → 30 minutes (D-07: Sat is work day), got {result}"
        )

    def test_lead_created_at_close(self) -> None:
        """Lead created at exactly 19:00, first touch next day 09:01 → 1 minute (D-07).

        19:00 is the close time (exclusive end of window). Lead created AT close → 0 min today.
        Next open window starts 09:00 next day. First touch 09:01 = 1 minute.
        """
        start_utc = _utc_from_buch(2026, 5, 24, 19, 0)   # Sunday 19:00 Bucharest (at close)
        end_utc = _utc_from_buch(2026, 5, 25, 9, 1)      # Monday 09:01 Bucharest
        result = business_minutes_between(
            start_utc, end_utc, OPEN_TIME, CLOSE_TIME, WORK_DAYS
        )
        assert result == 1, (
            f"Created at 19:00 (close), touched 09:01 next day → 1 business minute, got {result}"
        )

    def test_end_before_start_returns_zero(self) -> None:
        """end_utc <= start_utc (data quality issue) → 0, not negative, not error (D-06).

        This guards against corrupt history data where changed_at < lead.created_at.
        Must return 0 silently — not raise ValueError.
        """
        start_utc = _utc_from_buch(2026, 5, 24, 10, 30)
        end_utc = _utc_from_buch(2026, 5, 24, 10, 0)    # BEFORE start
        result = business_minutes_between(
            start_utc, end_utc, OPEN_TIME, CLOSE_TIME, WORK_DAYS
        )
        assert result == 0, (
            f"end_utc <= start_utc must return 0 (not raise, not negative), got {result}"
        )

    def test_equal_start_end_returns_zero(self) -> None:
        """Identical timestamps → 0 business minutes."""
        ts = _utc_from_buch(2026, 5, 24, 10, 0)
        result = business_minutes_between(ts, ts, OPEN_TIME, CLOSE_TIME, WORK_DAYS)
        assert result == 0, f"Identical timestamps → 0 business minutes, got {result}"

    def test_dst_spring_forward_bucharest(self) -> None:
        """Lead straddling EET→EEST spring-forward → zoneinfo handles DST correctly.

        Romania spring-forward 2026: last Sunday of March, 2026-03-29 at 03:00 EET.
        Clocks jump from 03:00 EET to 04:00 EEST (UTC+3). The hour 03:00-04:00 doesn't exist.

        Test: Lead created 2026-03-28 18:30 (Sat, during business hours, EET),
        first touch 2026-03-29 09:30 (Sun, EEST — after spring forward).
        Expected: 30 minutes from 18:30 to 19:00 (Sat) + 30 minutes from 09:00 to 09:30 (Sun)
        = 60 business minutes total.

        zoneinfo must produce DST-correct result (fixed UTC offset would give wrong answer).
        """
        # 2026-03-28 18:30 EET (UTC+2) = 16:30 UTC
        start_utc = datetime(2026, 3, 28, 16, 30, 0, tzinfo=ZoneInfo("UTC"))
        # 2026-03-29 09:30 EEST (UTC+3) = 06:30 UTC
        end_utc = datetime(2026, 3, 29, 6, 30, 0, tzinfo=ZoneInfo("UTC"))

        result = business_minutes_between(
            start_utc, end_utc, OPEN_TIME, CLOSE_TIME, WORK_DAYS
        )
        # 30 min Sat + 30 min Sun = 60 business minutes
        assert result == 60, (
            f"DST spring-forward: 18:30 Sat to 09:30 Sun → 60 business minutes, got {result}. "
            "zoneinfo must correctly handle EET→EEST transition (Pitfall 1)."
        )

    def test_full_day_inside_hours(self) -> None:
        """Lead created 09:00, first touch 19:00 → 600 business minutes (full day)."""
        start_utc = _utc_from_buch(2026, 5, 24, 9, 0)
        end_utc = _utc_from_buch(2026, 5, 24, 19, 0)
        result = business_minutes_between(
            start_utc, end_utc, OPEN_TIME, CLOSE_TIME, WORK_DAYS
        )
        assert result == 600, (
            f"09:00 to 19:00 (full business day) → 600 minutes, got {result}"
        )

    def test_multi_day_span(self) -> None:
        """Lead created Sunday 10:00, first touch Monday 10:00 → 540+60 = 600 minutes.

        Sun 10:00→19:00 = 540 min, Mon 09:00→10:00 = 60 min → 600 total.
        """
        start_utc = _utc_from_buch(2026, 5, 24, 10, 0)   # Sunday 10:00
        end_utc = _utc_from_buch(2026, 5, 25, 10, 0)     # Monday 10:00
        result = business_minutes_between(
            start_utc, end_utc, OPEN_TIME, CLOSE_TIME, WORK_DAYS
        )
        assert result == 600, (
            f"Sun 10:00 to Mon 10:00 → 600 business minutes (9h Sun + 1h Mon), got {result}"
        )
