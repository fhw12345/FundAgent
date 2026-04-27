"""DCA (Dollar-Cost Averaging) auto-executor.

Supports 4 frequencies:
- daily: every day
- weekly: every week on day_of_week
- biweekly: every 14 days from anchor_date
- monthly: every month on day_of_month
"""

import asyncio
from datetime import datetime, timezone, timedelta

import structlog

from ..database.repositories.job_run_repository import JobRunRepository
from ..database.repositories.transaction_repository import (
    DCAPlanRepository,
    TransactionRepository,
)
from .portfolio_enrichment import enrich_holding
from .settlement import compute_confirm_date, compute_nav_date

JOB_NAME = "dca_scheduler"

logger = structlog.get_logger()


def _is_due(plan: dict, now: datetime) -> bool:
    """Determine if this plan should fire today, given last_executed."""
    freq = plan.get("frequency", "monthly")
    last = plan.get("last_executed")

    if freq == "daily":
        if last and isinstance(last, datetime):
            # already done today?
            if last.date() == now.date():
                return False
        return True

    if freq == "weekly":
        target_dow = plan.get("day_of_week")
        if target_dow is None:
            return False
        # Python: Monday=0..Sunday=6; our 1=Mon..7=Sun
        if (now.weekday() + 1) != target_dow:
            return False
        if last and isinstance(last, datetime):
            if last.date() == now.date():
                return False
            # extra safety: don't execute again in same week
            week_start = now - timedelta(days=now.weekday())
            if last.date() >= week_start.date():
                return False
        return True

    if freq == "biweekly":
        anchor = plan.get("anchor_date")
        if not anchor or not isinstance(anchor, datetime):
            return False
        days_since = (now.date() - anchor.date()).days
        if days_since < 0 or days_since % 14 != 0:
            return False
        if last and isinstance(last, datetime):
            if last.date() == now.date():
                return False
        return True

    if freq == "monthly":
        target_dom = plan.get("day_of_month")
        if target_dom is None or now.day != target_dom:
            return False
        if last and isinstance(last, datetime):
            if last.year == now.year and last.month == now.month:
                return False
        return True

    return False


async def execute_due_dca_plans(
    dca_repo: DCAPlanRepository, tx_repo: TransactionRepository
) -> int:
    """Check active plans and create buy transactions for those due."""
    now = datetime.now(timezone.utc)
    plans = await dca_repo.list_active()
    executed = 0

    for plan in plans:
        if not _is_due(plan, now):
            continue

        try:
            enriched = await enrich_holding({"fund_code": plan["fund_code"]})
            nav = enriched.get("nav")
            if not nav:
                logger.warning("DCA skip: no nav", fund_code=plan["fund_code"])
                continue

            shares = round(plan["amount"] / nav, 4)
            tx = {
                "user_id": plan["user_id"],
                "fund_code": plan["fund_code"],
                "fund_name": enriched.get("fund_name", plan.get("fund_name", "")),
                "tx_type": "buy",
                "date": now,
                "submitted_at": now,
                "confirm_date": compute_confirm_date(now),
                "status": "pending",
                "nav_source": "estimated",
                "amount": plan["amount"],
                "shares": shares,
                "nav": nav,
                "fee": 0.0,
                "source_fund_code": None,
                "notes": f"定投自动执行 ({plan.get('frequency', 'monthly')})",
                "is_dca": True,
                "dca_plan_id": plan["plan_id"],
            }
            await tx_repo.insert(tx)
            await dca_repo.mark_executed(plan["plan_id"], now)
            executed += 1
            logger.info(
                "DCA executed",
                plan_id=plan["plan_id"],
                fund_code=plan["fund_code"],
                amount=plan["amount"],
                frequency=plan.get("frequency"),
            )
        except Exception as e:
            logger.error("DCA execution failed", plan_id=plan.get("plan_id"), error=str(e))

    return executed


async def dca_scheduler_loop(
    dca_repo: DCAPlanRepository,
    tx_repo: TransactionRepository,
    job_repo: JobRunRepository,
    interval_seconds: int = 3600,
) -> None:
    """Background loop — wake up every hour and check for due DCA plans.
    Each tick is recorded to job_runs collection for cross-restart visibility.
    """
    logger.info("DCA scheduler started", interval=interval_seconds)
    while True:
        run_id = await job_repo.start(JOB_NAME)
        try:
            count = await execute_due_dca_plans(dca_repo, tx_repo)
            await job_repo.finish(run_id, status="ok", items_processed=count)
            if count > 0:
                logger.info("DCA cycle done", executed=count)
        except Exception as e:
            logger.error("DCA scheduler tick failed", error=str(e))
            await job_repo.finish(run_id, status="error", error=str(e))
        await asyncio.sleep(interval_seconds)


def compute_next_execution(plan: dict, from_date: datetime | None = None) -> datetime | None:
    """Compute next scheduled execution date for UI preview."""
    now = from_date or datetime.now(timezone.utc)
    freq = plan.get("frequency", "monthly")

    if freq == "daily":
        return now if not plan.get("last_executed") else now + timedelta(days=1)

    if freq == "weekly":
        target = plan.get("day_of_week")
        if not target:
            return None
        current_dow = now.weekday() + 1  # 1..7
        days_ahead = (target - current_dow) % 7
        if days_ahead == 0 and plan.get("last_executed"):
            days_ahead = 7
        return now + timedelta(days=days_ahead)

    if freq == "biweekly":
        anchor = plan.get("anchor_date")
        if not anchor:
            return None
        if isinstance(anchor, str):
            anchor = datetime.fromisoformat(anchor.replace("Z", "+00:00"))
        days_since = (now.date() - anchor.date()).days
        if days_since < 0:
            return anchor
        next_offset = 14 - (days_since % 14)
        if next_offset == 14 and not plan.get("last_executed"):
            next_offset = 0
        return now + timedelta(days=next_offset)

    if freq == "monthly":
        target = plan.get("day_of_month")
        if not target:
            return None
        if now.day < target:
            return now.replace(day=target)
        # next month
        if now.month == 12:
            return now.replace(year=now.year + 1, month=1, day=target)
        return now.replace(month=now.month + 1, day=target)

    return None
