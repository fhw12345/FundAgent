"""Eastmoney crawler tools — supplementary fund data for agent use."""

from __future__ import annotations

import structlog
from langchain_core.tools import tool

logger = structlog.get_logger()


@tool
async def fund_manager_info(fund_code: str) -> str:
    """查询基金经理信息（姓名、任职日期、任职回报）。适用于评估基金经理能力。

    Args:
        fund_code: 6位基金代码，如 "110011"
    """
    from ...services.eastmoney_crawler import get_fund_manager_info

    data = await get_fund_manager_info(fund_code)
    if "error" in data:
        return f"查询失败: {data['error']}"

    parts = [f"基金代码: {fund_code}"]
    if data.get("manager_name"):
        parts.append(f"基金经理: {data['manager_name']}")
    if data.get("start_date"):
        parts.append(f"任职日期: {data['start_date']}")
    if data.get("tenure_return_pct") is not None:
        parts.append(f"任职回报: {data['tenure_return_pct']}%")
    return "\n".join(parts) if len(parts) > 1 else "未找到基金经理信息"


@tool
async def fund_fee_info(fund_code: str) -> str:
    """查询基金费率信息（管理费、托管费）。适用于评估基金成本。

    Args:
        fund_code: 6位基金代码，如 "110011"
    """
    from ...services.eastmoney_crawler import get_fund_fees

    data = await get_fund_fees(fund_code)
    if "error" in data:
        return f"查询失败: {data['error']}"

    parts = [f"基金代码: {fund_code}"]
    if data.get("management_fee_pct") is not None:
        parts.append(f"管理费率: {data['management_fee_pct']}%/年")
    if data.get("custody_fee_pct") is not None:
        parts.append(f"托管费率: {data['custody_fee_pct']}%/年")
    return "\n".join(parts) if len(parts) > 1 else "未找到费率信息"


def create_eastmoney_tools() -> list:
    return [fund_manager_info, fund_fee_info]
