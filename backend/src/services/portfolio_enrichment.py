"""Auto-enrich fund holdings with name + nav from AkShare."""

import asyncio
from typing import Any

import structlog

logger = structlog.get_logger()


async def enrich_holding(holding: dict[str, Any]) -> dict[str, Any]:
    """Fill fund_name + nav for a holding by code, then derive shares/market_value.

    Inputs the user provides: fund_code, market_value, return_pct (optional).
    Auto-fetched: fund_name (from xueqiu basic info), nav (latest from eastmoney).
    Derived: shares = market_value / nav (when both available).
    """
    code = holding.get("fund_code")
    if not code:
        return holding

    enriched = dict(holding)

    if not enriched.get("fund_name") or not enriched.get("nav"):
        try:
            import akshare as ak

            loop = asyncio.get_event_loop()

            if not enriched.get("fund_name"):
                try:
                    df_basic = await loop.run_in_executor(
                        None, lambda: ak.fund_individual_basic_info_xq(symbol=code)
                    )
                    if not df_basic.empty:
                        for _, row in df_basic.iterrows():
                            if row["item"] == "基金名称":
                                enriched["fund_name"] = str(row["value"])
                                break
                except Exception as e:
                    logger.warning("fetch fund_name failed", code=code, error=str(e))

            if not enriched.get("nav"):
                try:
                    df_nav = await loop.run_in_executor(
                        None,
                        lambda: ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势"),
                    )
                    if not df_nav.empty:
                        latest = df_nav.iloc[-1]
                        nav_val = latest.get("单位净值")
                        if nav_val is not None:
                            enriched["nav"] = float(nav_val)
                except Exception as e:
                    logger.warning("fetch nav failed", code=code, error=str(e))

        except ImportError:
            logger.warning("akshare not installed — skipping enrichment")

    mv = enriched.get("market_value")
    nav = enriched.get("nav")
    if mv is not None and nav and nav > 0 and not enriched.get("shares"):
        enriched["shares"] = round(float(mv) / float(nav), 2)

    return enriched


async def enrich_holdings(holdings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return await asyncio.gather(*(enrich_holding(h) for h in holdings))
