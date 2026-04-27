"""T+1 settlement date logic for Chinese mutual funds.

Rules (simplified, holidays ignored in v1):
- Submit before 15:00 CST on a trading day → uses today's NAV → confirmed next trading day
- Submit after 15:00 CST OR on weekend → uses next trading day's NAV → confirmed the day after
- Trading days: Mon-Fri (holidays not yet handled)

NAV is published ~20:00 CST on the trading day, so the actual confirmation job
should run after 20:30 CST.
"""

from datetime import datetime, timedelta, timezone

CHINA_TZ = timezone(timedelta(hours=8))
CUTOFF_HOUR = 15  # 15:00 CST


def _is_trading_day(d: datetime) -> bool:
    """Mon-Fri only (TODO: integrate Chinese holiday calendar)."""
    return d.weekday() < 5


def _next_trading_day(d: datetime) -> datetime:
    nxt = d + timedelta(days=1)
    while not _is_trading_day(nxt):
        nxt += timedelta(days=1)
    return nxt


def compute_nav_date(submitted_at: datetime) -> datetime:
    """The trading day whose NAV will be applied to this submission.

    - submitted_at is timezone-aware; converted to China time for cutoff comparison.
    - Returns midnight (00:00) China time of the chosen NAV date, in UTC.
    """
    if submitted_at.tzinfo is None:
        submitted_at = submitted_at.replace(tzinfo=timezone.utc)
    cn = submitted_at.astimezone(CHINA_TZ)

    if _is_trading_day(cn) and cn.hour < CUTOFF_HOUR:
        nav_day_cn = cn
    else:
        nav_day_cn = _next_trading_day(cn)

    return nav_day_cn.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)


def compute_confirm_date(submitted_at: datetime) -> datetime:
    """When the share count will be confirmed (next trading day after NAV date).

    Returns 21:00 China time on that day in UTC — slightly after NAV publication.
    """
    nav_day = compute_nav_date(submitted_at).astimezone(CHINA_TZ)
    confirm_cn = _next_trading_day(nav_day).replace(
        hour=21, minute=0, second=0, microsecond=0
    )
    return confirm_cn.astimezone(timezone.utc)
