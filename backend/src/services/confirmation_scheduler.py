"""T+1 NAV confirmation background job.

Daily tick:
  1. Find pending transactions whose confirm_date <= now
  2. For each, fetch the actual NAV on the transaction's nav_date from AkShare
  3. Update tx with actual nav + recalculated shares; mark confirmed
  4. After N retry days with no NAV available, mark failed
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog

from ..database.repositories.job_run_repository import JobRunRepository
from ..database.repositories.transaction_repository import TransactionRepository
from .settlement import CHINA_TZ, compute_nav_date

logger = structlog.get_logger()

JOB_NAME = "tplus1_confirmation"
MAX_RETRY_DAYS = 5


async def _fetch_nav_on_date(fund_code: str, target_date: datetime) -> float | None:
    """Fetch NAV for fund_code on the given trading date.
    Returns None if NAV not yet published or fetch failed.
    """
    try:
        import akshare as ak

        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(
            None,
            lambda: ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势"),
        )
        if df.empty:
            return None
        target_str = target_date.astimezone(CHINA_TZ).strftime("%Y-%m-%d")
        for _, row in df.iterrows():
            row_date = str(row.get("净值日期", ""))
            if row_date == target_str:
                nav_val = row.get("单位净值")
                if nav_val is not None:
                    return float(nav_val)
        return None
    except Exception as e:
        logger.warning("fetch nav on date failed", code=fund_code, target=str(target_date), error=str(e))
        return None


async def confirm_pending_transactions(tx_repo: TransactionRepository) -> dict[str, int]:
    """Process all due pending transactions. Returns counts per outcome."""
    now = datetime.now(timezone.utc)
    pending = await tx_repo.list_pending_due(now)

    confirmed = 0
    still_waiting = 0
    failed = 0

    for tx in pending:
        submitted_at = tx.get("submitted_at") or tx.get("date")
        if not isinstance(submitted_at, datetime):
            continue
        nav_date = compute_nav_date(submitted_at)
        actual_nav = await _fetch_nav_on_date(tx["fund_code"], nav_date)

        if actual_nav and actual_nav > 0:
            amount = float(tx["amount"])
            tx_type = tx["tx_type"]
            new_shares = round(amount / actual_nav, 4)
            if tx_type == "sell":
                new_shares = -abs(new_shares)
            await tx_repo.confirm_transaction(
                tx_id=tx["tx_id"],
                actual_nav=actual_nav,
                actual_shares=new_shares,
                confirmed_at=now,
            )
            confirmed += 1
            logger.info(
                "T+1 confirmed",
                tx_id=tx["tx_id"],
                code=tx["fund_code"],
                est_nav=tx.get("nav"),
                actual_nav=actual_nav,
            )
            continue

        # NAV not available yet — check retry budget
        days_pending = (now - submitted_at).days
        if days_pending >= MAX_RETRY_DAYS:
            await tx_repo.mark_failed(tx["tx_id"])
            failed += 1
            logger.warning(
                "T+1 marked failed (max retries)",
                tx_id=tx["tx_id"],
                code=tx["fund_code"],
                days_pending=days_pending,
            )
        else:
            still_waiting += 1

    return {"confirmed": confirmed, "still_waiting": still_waiting, "failed": failed}


async def confirmation_loop(
    tx_repo: TransactionRepository,
    job_repo: JobRunRepository,
    interval_seconds: int = 3600,
) -> None:
    """Background loop. Wakes hourly; only does real work when due ticks land
    after 20:30 China time (when NAV is reliably published).

    Hourly cadence keeps the design symmetric with DCA scheduler and lets
    the system catch up after any restart without waiting a full day.
    """
    logger.info("T+1 confirmation scheduler started", interval=interval_seconds)
    while True:
        run_id = await job_repo.start(JOB_NAME)
        try:
            counts = await confirm_pending_transactions(tx_repo)
            total = counts["confirmed"] + counts["failed"]
            await job_repo.finish(
                run_id,
                status="ok",
                items_processed=total,
                error=None if total == 0 else f"waiting={counts['still_waiting']}",
            )
            if total > 0:
                logger.info("T+1 cycle done", **counts)
        except Exception as e:
            logger.error("T+1 confirmation tick failed", error=str(e))
            await job_repo.finish(run_id, status="error", error=str(e))
        await asyncio.sleep(interval_seconds)


async def trigger_confirmation_now(tx_repo: TransactionRepository) -> dict[str, Any]:
    """Manual trigger — for admin button / testing."""
    return await confirm_pending_transactions(tx_repo)
