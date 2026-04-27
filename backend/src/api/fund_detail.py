"""Fund detail API — aggregates AkShare data for one fund (NAV history, basic info, top holdings)."""

import asyncio
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException

from .dependencies.auth import get_current_user

logger = structlog.get_logger()
router = APIRouter(prefix="/api/funds", tags=["funds"])


def _run_sync(fn):
    return asyncio.get_event_loop().run_in_executor(None, fn)


@router.get("/{fund_code}")
async def get_fund_detail(
    fund_code: str,
    _: dict = Depends(get_current_user),
):
    if not fund_code.isdigit() or len(fund_code) != 6:
        raise HTTPException(status_code=400, detail="基金代码须为6位数字")

    try:
        import akshare as ak
    except ImportError:
        raise HTTPException(status_code=500, detail="akshare 未安装")

    result: dict[str, Any] = {"fund_code": fund_code}

    # Basic info
    try:
        df = await _run_sync(lambda: ak.fund_individual_basic_info_xq(symbol=fund_code))
        info: dict[str, str] = {}
        for _, row in df.iterrows():
            info[str(row["item"])] = str(row["value"])
        result["basic_info"] = info
        result["fund_name"] = info.get("基金名称", "")
    except Exception as e:
        logger.warning("basic info failed", code=fund_code, error=str(e))
        result["basic_info"] = {}
        result["fund_name"] = ""

    # NAV history (~1 year of trading days; frontend slices for week/month/year toggle)
    try:
        df = await _run_sync(lambda: ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势"))
        if not df.empty:
            tail = df.tail(250)
            result["nav_history"] = [
                {
                    "date": str(row["净值日期"]),
                    "nav": float(row["单位净值"]),
                    "change_pct": float(row["日增长率"]) if row["日增长率"] is not None else 0.0,
                }
                for _, row in tail.iterrows()
            ]
            latest = tail.iloc[-1]
            result["latest_nav"] = float(latest["单位净值"])
            result["latest_change_pct"] = float(latest["日增长率"]) if latest["日增长率"] is not None else 0.0
            result["latest_date"] = str(latest["净值日期"])
    except Exception as e:
        logger.warning("nav history failed", code=fund_code, error=str(e))
        result["nav_history"] = []

    # Top 10 holdings (latest year)
    try:
        from datetime import datetime
        year = str(datetime.now().year)
        df = await _run_sync(lambda: ak.fund_portfolio_hold_em(symbol=fund_code, date=year))
        if df.empty:
            df = await _run_sync(lambda: ak.fund_portfolio_hold_em(symbol=fund_code, date=str(int(year) - 1)))
        if not df.empty:
            quarters = df["季度"].unique()
            latest_q = quarters[0] if len(quarters) > 0 else None
            if latest_q:
                df_latest = df[df["季度"] == latest_q].head(10)
                result["top_holdings"] = [
                    {
                        "rank": int(row["序号"]),
                        "stock_code": str(row["股票代码"]),
                        "stock_name": str(row["股票名称"]),
                        "ratio_pct": float(row["占净值比例"]) if row["占净值比例"] is not None else 0.0,
                    }
                    for _, row in df_latest.iterrows()
                ]
                result["holdings_quarter"] = str(latest_q)
    except Exception as e:
        logger.warning("holdings failed", code=fund_code, error=str(e))
        result["top_holdings"] = []

    return result
