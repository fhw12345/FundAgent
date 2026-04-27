"""Portfolio API — screenshot import, CRUD, daily analysis trigger."""

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..core.config import Settings, get_settings
from ..database.mongodb import MongoDB
from ..database.repositories.portfolio_repository import PortfolioRepository
from ..services.market_data import get_fund_estimation_map, get_sectors_today
from ..services.portfolio_service import (
    import_portfolio_from_screenshot,
    run_daily_analysis,
)
from ..services.portfolio_enrichment import enrich_holdings
from ..services.sector_classifier import classify_fund_sectors
from .dependencies.auth import get_current_user, get_mongodb

logger = structlog.get_logger()
router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


def get_portfolio_repo(mongodb: MongoDB = Depends(get_mongodb)) -> PortfolioRepository:
    return PortfolioRepository(mongodb.get_collection("portfolios"))


# ── Schemas ──────────────────────────────────────────────────────────


class HoldingItem(BaseModel):
    fund_code: str = Field(..., pattern=r"^\d{6}$", description="6位基金代码")
    fund_name: str = ""
    shares: float | None = None
    nav: float | None = None
    market_value: float | None = None
    return_pct: float | None = None


class ManualPortfolioRequest(BaseModel):
    holdings: list[HoldingItem]


class ScreenshotImportRequest(BaseModel):
    image_base64: str = Field(..., description="Base64 encoded screenshot image")


# ── Endpoints ────────────────────────────────────────────────────────


@router.get("")
async def get_portfolio(
    request: Request,
    user: dict = Depends(get_current_user),
    repo: PortfolioRepository = Depends(get_portfolio_repo),
):
    portfolio = await repo.get_portfolio(user["user_id"])
    if not portfolio:
        return {"holdings": [], "source": None, "updated_at": None, "today_total_est_pnl": None}
    portfolio.pop("_id", None)

    holdings = portfolio.get("holdings") or []
    if not holdings:
        portfolio["today_total_est_pnl"] = None
        return portfolio

    redis_cache = request.app.state.redis
    sector_repo = request.app.state.sector_repo
    est_map = await get_fund_estimation_map(redis_cache)
    sectors_map = await get_sectors_today(redis_cache)
    available_sectors = list(sectors_map.keys())

    today_total = 0.0
    has_any = False
    for h in holdings:
        code = h.get("fund_code")
        if not code:
            continue
        est = est_map.get(code, {})
        pct = est.get("est_pct")
        if pct is None:
            pct = est.get("published_pct")
        h["today_est_pct"] = pct
        mv = h.get("market_value")
        if pct is not None and mv:
            pnl = round(float(mv) * float(pct) / 100, 2)
            h["today_est_pnl"] = pnl
            today_total += pnl
            has_any = True
        else:
            h["today_est_pnl"] = None

        sector_names = await classify_fund_sectors(
            code, h.get("fund_name", ""), available_sectors, sector_repo
        )
        h["sectors"] = [
            {"name": s, "change_pct": sectors_map[s]}
            for s in sector_names
            if s in sectors_map
        ]

    portfolio["today_total_est_pnl"] = round(today_total, 2) if has_any else None
    return portfolio


@router.put("")
async def update_portfolio(
    request: ManualPortfolioRequest,
    user: dict = Depends(get_current_user),
    repo: PortfolioRepository = Depends(get_portfolio_repo),
):
    holdings = [h.model_dump() for h in request.holdings]
    enriched = await enrich_holdings(holdings)
    doc = await repo.upsert_portfolio(user["user_id"], enriched, source="manual")
    doc.pop("_id", None)
    return doc


@router.post("/import-screenshot")
async def import_from_screenshot(
    request: ScreenshotImportRequest,
    user: dict = Depends(get_current_user),
    repo: PortfolioRepository = Depends(get_portfolio_repo),
    settings: Settings = Depends(get_settings),
):
    try:
        holdings = await import_portfolio_from_screenshot(request.image_base64, settings)
    except Exception as e:
        logger.error("Screenshot import failed", error=str(e))
        raise HTTPException(status_code=422, detail=f"截图识别失败: {str(e)}") from e

    if not holdings:
        raise HTTPException(status_code=422, detail="未能从截图中识别出基金持仓")

    doc = await repo.upsert_portfolio(user["user_id"], holdings, source="screenshot")
    doc.pop("_id", None)
    return {"imported_count": len(holdings), "portfolio": doc}


@router.post("/daily-analysis")
async def trigger_daily_analysis(
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
    repo: PortfolioRepository = Depends(get_portfolio_repo),
    settings: Settings = Depends(get_settings),
):
    fund_codes = await repo.get_fund_codes(user["user_id"])
    if not fund_codes:
        raise HTTPException(status_code=400, detail="持仓为空，请先导入持仓")

    background_tasks.add_task(
        run_daily_analysis,
        user_id=user["user_id"],
        portfolio_repo=repo,
        settings=settings,
    )
    return {
        "status": "started",
        "fund_count": len(fund_codes),
        "fund_codes": fund_codes,
        "message": f"已开始分析 {len(fund_codes)} 只基金，请稍后查看结果",
    }
