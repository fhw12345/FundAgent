"""Tests for T+1 settlement date logic."""

from datetime import datetime, timedelta, timezone

from src.services.settlement import (
    CHINA_TZ,
    compute_confirm_date,
    compute_nav_date,
)


def _cn(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=CHINA_TZ)


def test_weekday_before_cutoff_uses_same_day_nav():
    # Monday 2026-04-27 10:00 CST → NAV date = 2026-04-27, confirm = 2026-04-28
    submitted = _cn(2026, 4, 27, 10, 0)
    nav_date = compute_nav_date(submitted).astimezone(CHINA_TZ)
    confirm = compute_confirm_date(submitted).astimezone(CHINA_TZ)
    assert nav_date.date() == _cn(2026, 4, 27).date()
    assert confirm.date() == _cn(2026, 4, 28).date()


def test_weekday_at_cutoff_uses_next_day():
    # Monday exactly 15:00 → next trading day's NAV
    submitted = _cn(2026, 4, 27, 15, 0)
    nav_date = compute_nav_date(submitted).astimezone(CHINA_TZ)
    confirm = compute_confirm_date(submitted).astimezone(CHINA_TZ)
    assert nav_date.date() == _cn(2026, 4, 28).date()
    assert confirm.date() == _cn(2026, 4, 29).date()


def test_weekday_after_cutoff_uses_next_day():
    submitted = _cn(2026, 4, 27, 16, 30)
    nav_date = compute_nav_date(submitted).astimezone(CHINA_TZ)
    assert nav_date.date() == _cn(2026, 4, 28).date()


def test_friday_after_cutoff_skips_weekend():
    # Friday 2026-05-01 16:00 → NAV = Monday 2026-05-04, confirm = Tuesday 2026-05-05
    submitted = _cn(2026, 5, 1, 16, 0)
    nav_date = compute_nav_date(submitted).astimezone(CHINA_TZ)
    confirm = compute_confirm_date(submitted).astimezone(CHINA_TZ)
    assert nav_date.weekday() == 0  # Monday
    assert confirm.weekday() == 1   # Tuesday


def test_saturday_uses_monday_nav():
    submitted = _cn(2026, 5, 2, 10, 0)  # Saturday
    nav_date = compute_nav_date(submitted).astimezone(CHINA_TZ)
    confirm = compute_confirm_date(submitted).astimezone(CHINA_TZ)
    assert nav_date.weekday() == 0  # Monday
    assert confirm.weekday() == 1   # Tuesday


def test_sunday_uses_monday_nav():
    submitted = _cn(2026, 5, 3, 14, 0)
    nav_date = compute_nav_date(submitted).astimezone(CHINA_TZ)
    assert nav_date.weekday() == 0  # Monday


def test_utc_input_converted_correctly():
    # 2026-04-27 06:59 UTC = 14:59 CST → still before cutoff
    submitted = datetime(2026, 4, 27, 6, 59, tzinfo=timezone.utc)
    nav_date = compute_nav_date(submitted).astimezone(CHINA_TZ)
    assert nav_date.date() == _cn(2026, 4, 27).date()

    # 2026-04-27 07:00 UTC = 15:00 CST → at cutoff, push to next day
    submitted2 = datetime(2026, 4, 27, 7, 0, tzinfo=timezone.utc)
    nav_date2 = compute_nav_date(submitted2).astimezone(CHINA_TZ)
    assert nav_date2.date() == _cn(2026, 4, 28).date()


def test_confirm_returned_at_21_cst():
    submitted = _cn(2026, 4, 27, 10, 0)
    confirm = compute_confirm_date(submitted).astimezone(CHINA_TZ)
    assert confirm.hour == 21
    assert confirm.minute == 0
