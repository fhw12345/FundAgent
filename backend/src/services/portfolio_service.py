"""Portfolio service — screenshot import + daily analysis orchestrator."""

import json
import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import structlog
from motor.motor_asyncio import AsyncIOMotorCollection

from ..agent.llm_client import VisionClient
from ..core.config import Settings
from ..database.repositories.portfolio_repository import PortfolioRepository
from .chat_service import ChatService

logger = structlog.get_logger()

PORTFOLIO_VISION_PROMPT = """请分析这张基金持仓截图，提取每只基金的信息。

请以严格的JSON数组格式返回，每个元素包含：
- fund_code: 基金代码（6位数字字符串）
- fund_name: 基金名称
- shares: 持有份额（数字，没有则为null）
- nav: 最新净值（数字，没有则为null）
- market_value: 持仓市值（数字，没有则为null）
- return_pct: 持仓收益率（百分比数字，如5.23代表5.23%，没有则为null）

只返回JSON数组，不要其他文字。如果无法识别，返回空数组 []。"""


def _extract_json_array(text: str) -> list[dict[str, Any]]:
    """Extract JSON array from LLM response that may contain markdown fences."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*(\[.*?])\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)
    elif not text.startswith("["):
        bracket_start = text.find("[")
        bracket_end = text.rfind("]")
        if bracket_start != -1 and bracket_end != -1:
            text = text[bracket_start : bracket_end + 1]

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        logger.warning("Failed to parse vision response as JSON", text=text[:200])
    return []


async def import_portfolio_from_screenshot(
    image_base64: str,
    settings: Settings,
) -> list[dict[str, Any]]:
    vision = VisionClient(settings)
    raw = await vision.analyze_image(image_base64, PORTFOLIO_VISION_PROMPT)
    holdings = _extract_json_array(raw)
    valid = [h for h in holdings if h.get("fund_code") and re.match(r"^\d{6}$", str(h["fund_code"]))]
    logger.info("Screenshot import parsed", total=len(holdings), valid=len(valid))
    return valid


def _to_jsonable(obj: Any) -> Any:
    """Recursively coerce objects (datetime, Pydantic, etc.) into JSON-safe primitives."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_to_jsonable(v) for v in obj]
    if hasattr(obj, "model_dump"):
        try:
            return _to_jsonable(obj.model_dump())
        except Exception:
            pass
    if hasattr(obj, "__dict__"):
        try:
            return _to_jsonable(vars(obj))
        except Exception:
            pass
    return str(obj)


async def run_daily_analysis(
    user_id: str,
    portfolio_repo: PortfolioRepository,
    settings: Settings,
    chat_service: ChatService | None = None,
    job_runs_collection: AsyncIOMotorCollection | None = None,
    on_event: Any = None,
) -> dict[str, Any]:
    """Run analysis for all funds in user's portfolio.

    Persists each successful analysis as an assistant message in the
    symbol-per-chat conversation owned by ``user_id``. Tracks run metadata
    in ``job_runs`` when a collection is provided.
    """
    fund_codes = await portfolio_repo.get_fund_codes(user_id)
    if not fund_codes:
        return {"status": "empty", "message": "持仓为空，请先导入持仓"}

    # ── job_runs: start ──
    run_id: str | None = None
    if job_runs_collection is not None:
        run_id = str(uuid4())
        try:
            await job_runs_collection.insert_one(
                {
                    "run_id": run_id,
                    "job_type": "daily_analysis",
                    "user_id": user_id,
                    "started_at": datetime.now(timezone.utc),
                    "finished_at": None,
                    "status": "running",
                    "fund_codes": fund_codes,
                    "fund_results": {},
                }
            )
        except Exception as e:  # pragma: no cover - logging only
            logger.warning("job_runs start insert failed", error=str(e))

    from ..agent.deep_react_agent import DeepReActAgent
    from ..agent.tools.akshare_fund_tools import create_akshare_fund_tools

    tools = create_akshare_fund_tools()
    agent = DeepReActAgent(
        settings=settings,
        tools=tools,
        enable_debate=True,
        max_debate_rounds=1,
    )

    # Determine model id (best-effort) for metadata.
    role_models = getattr(settings, "role_models", None) or {}
    model_id = role_models.get("main_analyst") or role_models.get("default")

    results: dict[str, Any] = {}
    fund_results_status: dict[str, str] = {}

    for code in fund_codes:
        try:
            logger.info("Daily analysis starting", fund_code=code, user_id=user_id)
            result = await agent.analyze(
                symbol=code,
                user_id=user_id,
                on_event=on_event,
            )
            report = result.get("research_report", "") if isinstance(result, dict) else ""
            results[code] = {
                "status": "ok",
                "report": report[:2000] if report else "",
                "duration_ms": result.get("agent_duration_ms", 0) if isinstance(result, dict) else 0,
            }
            fund_results_status[code] = "ok"

            # Persist as assistant message in the symbol chat.
            if chat_service is not None:
                try:
                    chat = await chat_service.get_or_create_symbol_chat(
                        user_id=user_id, symbol=code
                    )
                    await chat_service.add_message(
                        chat_id=chat.chat_id,
                        user_id=user_id,
                        role="assistant",
                        source="llm",
                        content=report or "(无报告内容)",
                        metadata={
                            "symbol": code,
                            "model": model_id,
                            "raw_data": _to_jsonable(result),
                        },
                    )
                except Exception as persist_err:
                    logger.error(
                        "Failed to persist analysis message",
                        fund_code=code,
                        user_id=user_id,
                        error=str(persist_err),
                    )

        except Exception as e:
            logger.error("Daily analysis failed for fund", fund_code=code, error=str(e))
            results[code] = {"status": "error", "message": str(e)}
            fund_results_status[code] = "error"

            if chat_service is not None:
                try:
                    chat = await chat_service.get_or_create_symbol_chat(
                        user_id=user_id, symbol=code
                    )
                    await chat_service.add_message(
                        chat_id=chat.chat_id,
                        user_id=user_id,
                        role="assistant",
                        source="llm",
                        content=f"分析失败: {str(e)}",
                        metadata={
                            "symbol": code,
                            "model": model_id,
                            "raw_data": {"status": "error", "message": str(e)},
                        },
                    )
                except Exception as persist_err:
                    logger.error(
                        "Failed to persist error message",
                        fund_code=code,
                        user_id=user_id,
                        error=str(persist_err),
                    )

    # Determine overall status.
    statuses = set(fund_results_status.values())
    if not statuses or statuses == {"error"}:
        overall = "error"
    elif "error" in statuses:
        overall = "partial"
    else:
        overall = "ok"

    # ── job_runs: finish ──
    if job_runs_collection is not None and run_id:
        try:
            await job_runs_collection.update_one(
                {"run_id": run_id},
                {
                    "$set": {
                        "finished_at": datetime.now(timezone.utc),
                        "status": overall,
                        "fund_results": fund_results_status,
                    }
                },
            )
        except Exception as e:  # pragma: no cover - logging only
            logger.warning("job_runs finish update failed", error=str(e))

    return {
        "status": overall,
        "fund_count": len(fund_codes),
        "results": results,
    }
