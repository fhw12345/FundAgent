"""Portfolio API — screenshot import, CRUD, daily analysis trigger."""

from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from ..core.config import Settings, get_settings
from ..core.exceptions import NotFoundError
from ..database.mongodb import MongoDB
from ..database.repositories.chat_repository import ChatRepository
from ..database.repositories.message_repository import MessageRepository
from ..database.repositories.portfolio_repository import PortfolioRepository
from ..services.chat_service import ChatService
from ..services.market_data import get_fund_estimation_map, get_sectors_today
from ..services.portfolio_enrichment import enrich_holdings
from ..services.portfolio_service import (
    import_portfolio_from_screenshot,
    run_daily_analysis,
)
from ..services.sector_classifier import classify_fund_sectors
from .dependencies.auth import get_current_user, get_mongodb

logger = structlog.get_logger()
router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

SHANGHAI = ZoneInfo("Asia/Shanghai")


def get_portfolio_repo(mongodb: MongoDB = Depends(get_mongodb)) -> PortfolioRepository:
    return PortfolioRepository(mongodb.get_collection("portfolios"))


def get_portfolio_chat_service(
    mongodb: MongoDB = Depends(get_mongodb),
    settings: Settings = Depends(get_settings),
) -> ChatService:
    chat_repo = ChatRepository(mongodb.get_collection("chats"))
    message_repo = MessageRepository(mongodb.get_collection("messages"))
    return ChatService(chat_repo, message_repo, settings)


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
        pct = est.get("published_pct")
        if pct is None:
            pct = est.get("est_pct")
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
    mongodb: MongoDB = Depends(get_mongodb),
):
    fund_codes = await repo.get_fund_codes(user["user_id"])
    if not fund_codes:
        raise HTTPException(status_code=400, detail="持仓为空，请先导入持仓")

    # FastAPI Depends does not run inside BackgroundTasks; build deps explicitly.
    chat_repo = ChatRepository(mongodb.get_collection("chats"))
    message_repo = MessageRepository(mongodb.get_collection("messages"))
    chat_service = ChatService(chat_repo, message_repo, settings)
    job_runs_collection = mongodb.get_collection("job_runs")

    background_tasks.add_task(
        run_daily_analysis,
        user_id=user["user_id"],
        portfolio_repo=repo,
        settings=settings,
        chat_service=chat_service,
        job_runs_collection=job_runs_collection,
    )
    return {
        "status": "started",
        "fund_count": len(fund_codes),
        "fund_codes": fund_codes,
        "message": f"已开始分析 {len(fund_codes)} 只基金，请稍后查看结果",
    }


# ── Chat history endpoints ──────────────────────────────────────────


def _ensure_aware(dt: datetime) -> datetime:
    """Treat naive timestamps as UTC (they are stored as utcnow())."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _serialize_message(msg: Any) -> dict[str, Any]:
    """Convert a Message model to the dict shape expected by the frontend."""
    md_obj = getattr(msg, "metadata", None)
    if md_obj is None:
        md: dict[str, Any] = {}
    elif hasattr(md_obj, "model_dump"):
        md = md_obj.model_dump(exclude_none=False)
    elif isinstance(md_obj, dict):
        md = dict(md_obj)
    else:
        md = {}

    ts = _ensure_aware(msg.timestamp)

    return {
        "message_id": msg.message_id,
        "chat_id": msg.chat_id,
        "role": msg.role,
        "content": msg.content,
        "source": getattr(msg, "source", None),
        "timestamp": ts.isoformat(),
        "metadata": md,
    }


@router.get("/chat-history")
async def get_chat_history(
    date: str | None = Query(None, description="YYYY-MM-DD in Asia/Shanghai (default: today)"),
    analysis_type: str | None = Query(None, description="Reserved; currently ignored"),
    user: dict = Depends(get_current_user),
    repo: PortfolioRepository = Depends(get_portfolio_repo),
    chat_service: ChatService = Depends(get_portfolio_chat_service),
):
    """List today's per-fund analysis chats with their messages."""
    # Parse date in Asia/Shanghai.
    if date:
        try:
            day = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid date: {date}") from e
    else:
        day = datetime.now(SHANGHAI).date()

    start_local = datetime.combine(day, time.min, tzinfo=SHANGHAI)
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)

    user_id = user["user_id"]
    fund_codes = await repo.get_fund_codes(user_id)

    out_chats: list[dict[str, Any]] = []
    for code in fund_codes:
        chat = await chat_service.find_chat_by_symbol(user_id, code)
        if not chat:
            continue

        all_messages = await chat_service.get_chat_messages(
            chat.chat_id, user_id, limit=500, offset=0
        )

        filtered = []
        for m in all_messages:
            ts = _ensure_aware(m.timestamp)
            if start_utc <= ts < end_utc:
                filtered.append(m)

        if not filtered:
            continue

        latest_ts = max(_ensure_aware(m.timestamp) for m in filtered)

        out_chats.append(
            {
                "chat_id": chat.chat_id,
                "symbol": chat.ui_state.current_symbol or code,
                "title": chat.title,
                "message_count": len(filtered),
                "messages": [_serialize_message(m) for m in filtered],
                "latest_timestamp": latest_ts.isoformat(),
            }
        )

    return {"chats": out_chats}


@router.get("/chats/{chat_id}")
async def get_portfolio_chat_detail(
    chat_id: str,
    user: dict = Depends(get_current_user),
    chat_service: ChatService = Depends(get_portfolio_chat_service),
):
    """Return chat + messages. 404 if not owned by current user (no leak)."""
    user_id = user["user_id"]
    try:
        chat = await chat_service.get_chat(chat_id, user_id)
        messages = await chat_service.get_chat_messages(chat_id, user_id, limit=500)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail="Chat not found") from e

    chat_dict = chat.model_dump()
    # Serialize datetimes as ISO strings.
    for k in ("created_at", "updated_at", "last_message_at"):
        v = chat_dict.get(k)
        if isinstance(v, datetime):
            chat_dict[k] = _ensure_aware(v).isoformat()

    return {
        "chat": chat_dict,
        "messages": [_serialize_message(m) for m in messages],
    }


@router.delete("/chats/{chat_id}", status_code=204)
async def delete_portfolio_chat(
    chat_id: str,
    user: dict = Depends(get_current_user),
    chat_service: ChatService = Depends(get_portfolio_chat_service),
):
    """Delete chat + cascade messages. 404 if not owned by current user."""
    user_id = user["user_id"]
    try:
        deleted = await chat_service.delete_chat(chat_id, user_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail="Chat not found") from e

    if not deleted:
        raise HTTPException(status_code=404, detail="Chat not found")

    return Response(status_code=204)
