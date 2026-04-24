"""Portfolio API — screenshot import, CRUD, daily analysis trigger."""

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from ..core.config import Settings, get_settings
from ..database.mongodb import MongoDB
from ..database.repositories.portfolio_repository import PortfolioRepository
from ..services.portfolio_service import (
    import_portfolio_from_screenshot,
    run_daily_analysis,
)
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
    user: dict = Depends(get_current_user),
    repo: PortfolioRepository = Depends(get_portfolio_repo),
):
    portfolio = await repo.get_portfolio(user["user_id"])
    if not portfolio:
        return {"holdings": [], "source": None, "updated_at": None}
    portfolio.pop("_id", None)
    return portfolio


@router.put("")
async def update_portfolio(
    request: ManualPortfolioRequest,
    user: dict = Depends(get_current_user),
    repo: PortfolioRepository = Depends(get_portfolio_repo),
):
    holdings = [h.model_dump() for h in request.holdings]
    doc = await repo.upsert_portfolio(user["user_id"], holdings, source="manual")
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
