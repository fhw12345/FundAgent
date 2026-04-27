"""Transaction & DCA plan API endpoints."""

from datetime import datetime, timezone
from typing import Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..database.mongodb import MongoDB
from ..database.repositories.transaction_repository import (
    DCAPlanRepository,
    TransactionRepository,
)
from ..services.cost_basis import calc_fund_summary
from ..services.market_data import (
    get_fund_estimation_map,
    get_sectors_today,
)
from ..services.portfolio_enrichment import enrich_holding
from ..services.sector_classifier import classify_fund_sectors
from ..services.settlement import compute_confirm_date, compute_nav_date
from .dependencies.auth import get_current_user, get_mongodb

logger = structlog.get_logger()
router = APIRouter(prefix="/api/transactions", tags=["transactions"])


def get_tx_repo(mongodb: MongoDB = Depends(get_mongodb)) -> TransactionRepository:
    return TransactionRepository(mongodb.get_collection("transactions"))


def get_dca_repo(mongodb: MongoDB = Depends(get_mongodb)) -> DCAPlanRepository:
    return DCAPlanRepository(mongodb.get_collection("dca_plans"))


# ── Schemas ──────────────────────────────────────────────────────────


class TransactionRequest(BaseModel):
    fund_code: str = Field(..., pattern=r"^\d{6}$")
    tx_type: Literal["buy", "sell", "convert", "dividend_invest"]
    date: datetime
    amount: float = Field(..., gt=0, description="金额（元）")
    shares: float | None = Field(None, description="份额（不填则用 amount/nav 算）")
    nav: float | None = Field(None, description="当日净值（不填则自动抓取）")
    fee: float = 0.0
    source_fund_code: str | None = None
    notes: str = ""


class DCAPlanRequest(BaseModel):
    fund_code: str = Field(..., pattern=r"^\d{6}$")
    frequency: Literal["daily", "weekly", "biweekly", "monthly"]
    amount: float = Field(..., gt=0)
    day_of_month: int | None = Field(None, ge=1, le=28)
    day_of_week: int | None = Field(None, ge=1, le=7)
    anchor_date: datetime | None = None


# ── Transaction endpoints ────────────────────────────────────────────


@router.post("")
async def create_transaction(
    request: TransactionRequest,
    user: dict = Depends(get_current_user),
    repo: TransactionRepository = Depends(get_tx_repo),
):
    enriched = await enrich_holding({"fund_code": request.fund_code, "nav": request.nav})
    nav = request.nav or enriched.get("nav")
    if not nav:
        raise HTTPException(status_code=400, detail="无法获取净值，请手动填写")

    shares = request.shares
    if shares is None:
        shares = round(request.amount / nav, 4)
    if request.tx_type == "sell":
        shares = -abs(shares)

    submitted_at = datetime.now(timezone.utc)
    nav_date = compute_nav_date(submitted_at)
    confirm_date = compute_confirm_date(submitted_at)

    tx = {
        "user_id": user["user_id"],
        "fund_code": request.fund_code,
        "fund_name": enriched.get("fund_name", ""),
        "tx_type": request.tx_type,
        "date": request.date,
        "submitted_at": submitted_at,
        "confirm_date": confirm_date,
        "status": "pending",
        "nav_source": "estimated",
        "amount": request.amount,
        "shares": shares,
        "nav": nav,
        "fee": request.fee,
        "source_fund_code": request.source_fund_code,
        "notes": request.notes,
        "is_dca": False,
    }
    logger.info(
        "Transaction created (pending T+1)",
        fund_code=request.fund_code,
        nav_date=nav_date.isoformat(),
        confirm_date=confirm_date.isoformat(),
    )
    return await repo.insert(tx)


@router.get("")
async def list_transactions(
    fund_code: str | None = None,
    tx_type: str | None = None,
    limit: int = 200,
    user: dict = Depends(get_current_user),
    repo: TransactionRepository = Depends(get_tx_repo),
):
    txs = await repo.list_for_user(user["user_id"], fund_code, tx_type, limit)
    return {"transactions": txs, "count": len(txs)}


@router.delete("/{tx_id}")
async def delete_transaction(
    tx_id: str,
    user: dict = Depends(get_current_user),
    repo: TransactionRepository = Depends(get_tx_repo),
):
    deleted = await repo.delete(user["user_id"], tx_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="交易记录不存在")
    return {"deleted": True}


@router.get("/summary")
async def get_summary(
    request: Request,
    user: dict = Depends(get_current_user),
    repo: TransactionRepository = Depends(get_tx_repo),
):
    """Per-fund cost basis + cumulative return + today's est. PnL + sectors.
    Excludes pending T+1 transactions to avoid estimated-NAV noise.
    """
    redis_cache = request.app.state.redis
    sector_repo = request.app.state.sector_repo
    fund_codes = await repo.get_distinct_funds(user["user_id"])

    # Fetch market data once for all funds
    est_map = await get_fund_estimation_map(redis_cache) if fund_codes else {}
    sectors_map = await get_sectors_today(redis_cache) if fund_codes else {}
    available_sectors = list(sectors_map.keys())

    summaries = []
    total_pending = 0
    today_total_est_pnl = 0.0

    for code in fund_codes:
        all_txs = await repo.list_for_fund(user["user_id"], code)
        confirmed_txs = [t for t in all_txs if t.get("status") != "pending"]
        pending_for_fund = sum(1 for t in all_txs if t.get("status") == "pending")
        total_pending += pending_for_fund

        enriched = await enrich_holding({"fund_code": code})
        nav = enriched.get("nav")
        summary = calc_fund_summary(confirmed_txs, current_nav=nav)
        if summary["total_shares"] > 0 or summary.get("realized_pnl"):
            fund_name = next(
                (t.get("fund_name", "") for t in all_txs if t.get("fund_name")),
                enriched.get("fund_name", ""),
            )
            summary["fund_code"] = code
            summary["fund_name"] = fund_name
            summary["pending_count"] = pending_for_fund

            # Today's estimation
            est = est_map.get(code, {})
            today_pct = est.get("est_pct")
            if today_pct is None:
                today_pct = est.get("published_pct")
            summary["today_est_pct"] = today_pct
            mv = summary.get("market_value")
            if today_pct is not None and mv:
                today_pnl = round(mv * today_pct / 100, 2)
                summary["today_est_pnl"] = today_pnl
                today_total_est_pnl += today_pnl
            else:
                summary["today_est_pnl"] = None

            # Related sectors (LLM-classified, DB-cached)
            sector_names = await classify_fund_sectors(
                code, fund_name, available_sectors, sector_repo
            )
            summary["sectors"] = [
                {"name": s, "change_pct": sectors_map[s]}
                for s in sector_names
                if s in sectors_map
            ]

            summaries.append(summary)

    return {
        "funds": summaries,
        "pending_count": total_pending,
        "today_total_est_pnl": round(today_total_est_pnl, 2) if summaries else None,
    }


# ── DCA plan endpoints ───────────────────────────────────────────────


dca_router = APIRouter(prefix="/api/dca-plans", tags=["dca-plans"])


@dca_router.post("")
async def create_dca_plan(
    request: DCAPlanRequest,
    user: dict = Depends(get_current_user),
    repo: DCAPlanRepository = Depends(get_dca_repo),
):
    # Validate frequency-specific fields
    if request.frequency == "monthly" and not request.day_of_month:
        raise HTTPException(status_code=400, detail="monthly 频率需提供 day_of_month")
    if request.frequency in ("weekly", "biweekly") and not request.day_of_week:
        raise HTTPException(status_code=400, detail=f"{request.frequency} 频率需提供 day_of_week")
    if request.frequency == "biweekly" and not request.anchor_date:
        raise HTTPException(status_code=400, detail="biweekly 频率需提供 anchor_date 起始日")

    enriched = await enrich_holding({"fund_code": request.fund_code})
    plan = {
        "user_id": user["user_id"],
        "fund_code": request.fund_code,
        "fund_name": enriched.get("fund_name", ""),
        "frequency": request.frequency,
        "amount": request.amount,
        "day_of_month": request.day_of_month,
        "day_of_week": request.day_of_week,
        "anchor_date": request.anchor_date,
        "status": "active",
        "last_executed": None,
    }
    return await repo.insert(plan)


@dca_router.get("")
async def list_dca_plans(
    user: dict = Depends(get_current_user),
    repo: DCAPlanRepository = Depends(get_dca_repo),
):
    from ..services.dca_scheduler import compute_next_execution

    plans = await repo.list_for_user(user["user_id"])
    for p in plans:
        next_exec = compute_next_execution(p)
        p["next_execution"] = next_exec.isoformat() if next_exec else None
    return {"plans": plans, "count": len(plans)}


@dca_router.patch("/{plan_id}/pause")
async def pause_dca_plan(
    plan_id: str,
    repo: DCAPlanRepository = Depends(get_dca_repo),
):
    await repo.update_status(plan_id, "paused")
    return {"status": "paused"}


@dca_router.patch("/{plan_id}/resume")
async def resume_dca_plan(
    plan_id: str,
    repo: DCAPlanRepository = Depends(get_dca_repo),
):
    await repo.update_status(plan_id, "active")
    return {"status": "active"}


@dca_router.delete("/{plan_id}")
async def delete_dca_plan(
    plan_id: str,
    user: dict = Depends(get_current_user),
    repo: DCAPlanRepository = Depends(get_dca_repo),
):
    deleted = await repo.delete(user["user_id"], plan_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="定投计划不存在")
    return {"deleted": True}
