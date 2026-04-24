"""Portfolio service — screenshot import + daily analysis orchestrator."""

import base64
import json
import re
from typing import Any

import structlog

from ..agent.llm_client import VisionClient
from ..core.config import Settings
from ..database.repositories.portfolio_repository import PortfolioRepository

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


async def run_daily_analysis(
    user_id: str,
    portfolio_repo: PortfolioRepository,
    settings: Settings,
    on_event=None,
) -> dict[str, Any]:
    """Run analysis for all funds in user's portfolio.

    Returns a dict with per-fund summaries from the deep agent.
    """
    fund_codes = await portfolio_repo.get_fund_codes(user_id)
    if not fund_codes:
        return {"status": "empty", "message": "持仓为空，请先导入持仓"}

    from ..agent.deep_react_agent import DeepReActAgent
    from ..agent.tools.akshare_fund_tools import create_akshare_fund_tools

    tools = create_akshare_fund_tools()
    agent = DeepReActAgent(
        settings=settings,
        tools=tools,
        enable_debate=True,
        max_debate_rounds=1,
    )

    results: dict[str, Any] = {}
    for code in fund_codes:
        try:
            logger.info("Daily analysis starting", fund_code=code, user_id=user_id)
            result = await agent.analyze(
                symbol=code,
                user_id=user_id,
                on_event=on_event,
            )
            results[code] = {
                "status": "ok",
                "report": result.get("research_report", "")[:2000],
                "duration_ms": result.get("agent_duration_ms", 0),
            }
        except Exception as e:
            logger.error("Daily analysis failed for fund", fund_code=code, error=str(e))
            results[code] = {"status": "error", "message": str(e)}

    return {"status": "ok", "fund_count": len(fund_codes), "results": results}
