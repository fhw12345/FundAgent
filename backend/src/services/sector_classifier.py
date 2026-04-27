"""LLM-based fund → sector classification with persistent DB cache.

Flow per fund:
  1. Check DB cache; hit → return cached list
  2. Miss → call LLM with the live Sina sector list as choices
  3. Parse JSON response; dedupe; persist to DB
"""

import json
import re
from typing import Any

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from ..agent.llm_client import get_chat_model
from ..database.repositories.fund_sector_repository import FundSectorRepository

logger = structlog.get_logger()

_SYSTEM = (
    "你是基金主题分类器。给定基金名称和可选的行业板块列表，"
    "选出 1-3 个最相关的板块名称（必须从给定列表中选）。"
    "如果基金属于宽基/全市场指数（如沪深300、中证500、上证50），返回空数组。"
    "只返回 JSON：{\"sectors\": [\"板块名1\", \"板块名2\"]}，无任何其他文本。"
)


def _extract_json(text: str) -> dict[str, Any] | None:
    """Pull a JSON object out of an LLM response (handles ```json blocks)."""
    if not text:
        return None
    # Try direct parse first
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    # Find first {...} block
    match = re.search(r"\{[^{}]*\"sectors\"[^{}]*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None


async def classify_fund_sectors(
    fund_code: str,
    fund_name: str,
    available_sectors: list[str],
    repo: FundSectorRepository,
) -> list[str]:
    """Returns sector names valid against the given available_sectors list."""
    if not fund_code or not fund_name:
        return []

    cached = await repo.get(fund_code)
    if cached is not None:
        return [s for s in cached if s in available_sectors]

    if not available_sectors:
        return []

    try:
        llm = get_chat_model(role="default", temperature=0.0, streaming=False)
        prompt = (
            f"基金名称: {fund_name}\n"
            f"可选板块: {', '.join(available_sectors)}\n"
            "请选出 1-3 个最相关的板块。"
        )
        response = await llm.ainvoke([
            SystemMessage(content=_SYSTEM),
            HumanMessage(content=prompt),
        ])
        text = str(getattr(response, "content", "") or "")
        parsed = _extract_json(text)
        sectors_raw = (parsed or {}).get("sectors", []) if isinstance(parsed, dict) else []
        if not isinstance(sectors_raw, list):
            sectors_raw = []
        # Filter to valid sectors only, dedupe preserving order
        seen: set[str] = set()
        result: list[str] = []
        for s in sectors_raw:
            if isinstance(s, str) and s in available_sectors and s not in seen:
                seen.add(s)
                result.append(s)
            if len(result) >= 3:
                break
    except Exception as e:
        logger.warning("LLM sector classify failed", code=fund_code, error=str(e))
        result = []

    await repo.upsert(fund_code, fund_name, result)
    logger.info("Fund sectors classified", code=fund_code, name=fund_name, sectors=result)
    return result
