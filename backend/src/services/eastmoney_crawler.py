"""天天基金 (eastmoney) polite crawler for supplementary fund data.

Rate-limited, with proper User-Agent and delays. Used as a fallback
when AkShare doesn't cover certain data points.
"""

import asyncio
import re
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://fund.eastmoney.com/",
}

_REQUEST_DELAY = 1.5


async def _fetch(url: str, timeout: float = 10.0) -> str:
    await asyncio.sleep(_REQUEST_DELAY)
    async with httpx.AsyncClient(headers=_HEADERS, timeout=timeout, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.text


async def get_fund_detail(fund_code: str) -> dict[str, Any]:
    """Get fund detail page data from eastmoney."""
    url = f"https://fund.eastmoney.com/{fund_code}.html"
    try:
        html = await _fetch(url)
        result: dict[str, Any] = {"fund_code": fund_code}

        name_match = re.search(r'<div class="fundDetail-tit"><div[^>]*>(.*?)<', html)
        if name_match:
            result["fund_name"] = name_match.group(1).strip()

        nav_match = re.search(r'<span class="dataItem02">\s*<span class="ui-font-large ui-num">([\d.]+)</span>', html)
        if nav_match:
            result["nav"] = float(nav_match.group(1))

        growth_match = re.search(r'<span class="ui-font-middle ui-num">([-\d.]+)%</span>', html)
        if growth_match:
            result["daily_return_pct"] = float(growth_match.group(1))

        logger.info("Fetched fund detail from eastmoney", fund_code=fund_code)
        return result
    except Exception as e:
        logger.error("Failed to fetch fund detail", fund_code=fund_code, error=str(e))
        return {"fund_code": fund_code, "error": str(e)}


async def get_fund_manager_info(fund_code: str) -> dict[str, Any]:
    """Get fund manager information."""
    url = f"https://fundf10.eastmoney.com/jjjl_{fund_code}.html"
    try:
        html = await _fetch(url)
        result: dict[str, Any] = {"fund_code": fund_code}

        manager_match = re.search(r'<a href="/manager/\d+\.html">(.*?)</a>', html)
        if manager_match:
            result["manager_name"] = manager_match.group(1).strip()

        tenure_match = re.search(r'任职日期.*?(\d{4}-\d{2}-\d{2})', html, re.DOTALL)
        if tenure_match:
            result["start_date"] = tenure_match.group(1)

        return_match = re.search(r'任职回报.*?([-\d.]+)%', html, re.DOTALL)
        if return_match:
            result["tenure_return_pct"] = float(return_match.group(1))

        logger.info("Fetched manager info from eastmoney", fund_code=fund_code)
        return result
    except Exception as e:
        logger.error("Failed to fetch manager info", fund_code=fund_code, error=str(e))
        return {"fund_code": fund_code, "error": str(e)}


async def get_fund_fees(fund_code: str) -> dict[str, Any]:
    """Get fund fee structure."""
    url = f"https://fundf10.eastmoney.com/jjfl_{fund_code}.html"
    try:
        html = await _fetch(url)
        result: dict[str, Any] = {"fund_code": fund_code}

        mgmt_match = re.search(r'管理费率.*?([\d.]+)%', html, re.DOTALL)
        if mgmt_match:
            result["management_fee_pct"] = float(mgmt_match.group(1))

        custody_match = re.search(r'托管费率.*?([\d.]+)%', html, re.DOTALL)
        if custody_match:
            result["custody_fee_pct"] = float(custody_match.group(1))

        logger.info("Fetched fund fees from eastmoney", fund_code=fund_code)
        return result
    except Exception as e:
        logger.error("Failed to fetch fund fees", fund_code=fund_code, error=str(e))
        return {"fund_code": fund_code, "error": str(e)}
