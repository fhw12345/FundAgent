"""
AkShare fund data tools for Chinese mutual fund (公募基金) analysis.

Provides LangChain tools for:
- Fund NAV history (净值走势)
- Fund overview/info (基金概况)
- Fund holdings (持仓)
- Fund rankings (排行)
- Fund search (搜索)
"""

from __future__ import annotations

from typing import Any

import structlog
from langchain_core.tools import tool

logger = structlog.get_logger()


def create_akshare_fund_tools() -> list[Any]:
    """Create all AkShare fund data tools."""
    return [
        fund_nav_history,
        fund_overview,
        fund_holdings,
        fund_ranking,
        fund_search,
        fund_nav_estimate,
    ]


@tool
async def fund_nav_history(
    fund_code: str,
    indicator: str = "单位净值走势",
) -> str:
    """查询基金净值历史走势。

    Args:
        fund_code: 基金代码，如 "110011"（易方达中小盘）
        indicator: 数据类型，可选：
            - "单位净值走势"（默认）
            - "累计净值走势"
            - "累计收益率走势"
            - "同类排名走势"

    Returns:
        最近30个交易日的净值数据表
    """
    import akshare as ak

    try:
        df = ak.fund_open_fund_info_em(symbol=fund_code, indicator=indicator)

        if df.empty:
            return f"基金 {fund_code} 无{indicator}数据"

        df_recent = df.tail(30)

        if indicator == "单位净值走势":
            lines = [f"基金 {fund_code} 近期单位净值走势（最近{len(df_recent)}个交易日）:"]
            lines.append("日期        | 单位净值 | 日增长率")
            lines.append("-----------|---------|--------")
            for _, row in df_recent.iterrows():
                lines.append(f"{row['净值日期']} | {row['单位净值']:.4f} | {row.get('日增长率', 'N/A')}%")
        elif indicator == "累计净值走势":
            lines = [f"基金 {fund_code} 累计净值走势:"]
            for _, row in df_recent.iterrows():
                lines.append(f"{row['净值日期']} | 累计净值: {row['累计净值']:.4f}")
        elif indicator == "累计收益率走势":
            lines = [f"基金 {fund_code} 累计收益率走势:"]
            for _, row in df_recent.iterrows():
                lines.append(f"{row['日期']} | 累计收益率: {row['累计收益率']:.2f}%")
        else:
            lines = [f"基金 {fund_code} {indicator}:"]
            for _, row in df_recent.iterrows():
                lines.append(" | ".join(str(v) for v in row.values))

        # Summary
        if indicator == "单位净值走势" and len(df_recent) > 1:
            latest = df_recent.iloc[-1]["单位净值"]
            earliest = df_recent.iloc[0]["单位净值"]
            change_pct = (latest - earliest) / earliest * 100
            lines.append(f"\n区间变动: {earliest:.4f} → {latest:.4f} ({change_pct:+.2f}%)")

        return "\n".join(lines)

    except Exception as e:
        logger.error("fund_nav_history failed", fund_code=fund_code, error=str(e))
        return f"查询基金 {fund_code} 净值失败: {e}"


@tool
async def fund_overview(fund_code: str) -> str:
    """查询基金基本信息概况（名称、类型、规模、基金经理、费率等）。

    Args:
        fund_code: 基金代码，如 "110011"

    Returns:
        基金概况信息
    """
    import akshare as ak

    try:
        df = ak.fund_individual_basic_info_xq(symbol=fund_code)

        if df.empty:
            return f"基金 {fund_code} 无概况数据"

        lines = [f"基金 {fund_code} 概况:"]
        for _, row in df.iterrows():
            lines.append(f"  {row['item']}: {row['value']}")

        return "\n".join(lines)

    except Exception as e:
        logger.error("fund_overview failed", fund_code=fund_code, error=str(e))
        return f"查询基金 {fund_code} 概况失败: {e}"


@tool
async def fund_holdings(
    fund_code: str,
    year: str = "2024",
) -> str:
    """查询基金股票持仓（前十大重仓股）。

    Args:
        fund_code: 基金代码，如 "110011"
        year: 年份，如 "2024"

    Returns:
        基金各季度前十大重仓股
    """
    import akshare as ak

    try:
        df = ak.fund_portfolio_hold_em(symbol=fund_code, date=year)

        if df.empty:
            return f"基金 {fund_code} 在 {year} 年无持仓数据"

        quarters = df["季度"].unique()
        latest_q = quarters[0] if len(quarters) > 0 else "N/A"

        df_latest = df[df["季度"] == latest_q].head(10)

        lines = [f"基金 {fund_code} 重仓股（{latest_q}）:"]
        lines.append("序号 | 股票代码 | 股票名称     | 占净值比例  | 持仓市值(万)")
        lines.append("----|---------|------------|-----------|----------")

        for _, row in df_latest.iterrows():
            market_val = row.get("持仓市值", 0)
            if isinstance(market_val, (int, float)) and market_val > 0:
                market_val_str = f"{market_val / 10000:.1f}"
            else:
                market_val_str = str(market_val)
            lines.append(
                f"{row['序号']:>3} | {row['股票代码']} | {row['股票名称']:<10} | "
                f"{row['占净值比例']}% | {market_val_str}"
            )

        if len(quarters) > 1:
            lines.append(f"\n可查季度: {', '.join(str(q) for q in quarters)}")

        return "\n".join(lines)

    except Exception as e:
        logger.error("fund_holdings failed", fund_code=fund_code, error=str(e))
        return f"查询基金 {fund_code} 持仓失败: {e}"


@tool
async def fund_ranking(
    fund_type: str = "全部",
) -> str:
    """查询基金业绩排行榜。

    Args:
        fund_type: 基金类型，可选：
            - "全部"（默认）
            - "股票型"
            - "混合型"
            - "债券型"
            - "指数型"
            - "QDII"
            - "FOF"

    Returns:
        该类型基金近期业绩排行（前20名）
    """
    import akshare as ak

    try:
        df = ak.fund_open_fund_rank_em(symbol=fund_type)

        if df.empty:
            return f"无 {fund_type} 基金排行数据"

        df_top = df.head(20)

        lines = [f"{fund_type}基金业绩排行（前20）:"]
        lines.append("代码   | 名称           | 近1月    | 近3月    | 近1年    | 今年来")
        lines.append("------|---------------|---------|---------|---------|--------")

        for _, row in df_top.iterrows():
            lines.append(
                f"{row['基金代码']} | {str(row['基金简称'])[:12]:<12} | "
                f"{row.get('近1月', 'N/A'):>6}% | {row.get('近3月', 'N/A'):>6}% | "
                f"{row.get('近1年', 'N/A'):>6}% | {row.get('今年来', 'N/A'):>6}%"
            )

        return "\n".join(lines)

    except Exception as e:
        logger.error("fund_ranking failed", fund_type=fund_type, error=str(e))
        return f"查询 {fund_type} 基金排行失败: {e}"


@tool
async def fund_search(keyword: str) -> str:
    """按关键词搜索基金（代码或名称）。

    Args:
        keyword: 搜索关键词，如 "易方达" 或 "110011" 或 "中小盘"

    Returns:
        匹配的基金列表（最多20条）
    """
    import akshare as ak

    try:
        df = ak.fund_name_em()

        if df.empty:
            return "无法获取基金列表"

        mask = (
            df["基金代码"].str.contains(keyword, na=False)
            | df["基金简称"].str.contains(keyword, na=False)
            | df["拼音缩写"].str.contains(keyword.upper(), na=False)
        )
        matches = df[mask].head(20)

        if matches.empty:
            return f"未找到匹配 '{keyword}' 的基金"

        lines = [f"搜索 '{keyword}' 找到 {len(matches)} 只基金:"]
        lines.append("代码   | 名称           | 类型")
        lines.append("------|---------------|------")

        for _, row in matches.iterrows():
            lines.append(
                f"{row['基金代码']} | {str(row['基金简称'])[:12]:<12} | {row.get('基金类型', 'N/A')}"
            )

        return "\n".join(lines)

    except Exception as e:
        logger.error("fund_search failed", keyword=keyword, error=str(e))
        return f"搜索基金 '{keyword}' 失败: {e}"


@tool
async def fund_nav_estimate(fund_type: str = "全部") -> str:
    """查询基金实时净值估算（盘中估值）。

    Args:
        fund_type: 基金类型过滤，可选 "全部"（默认）

    Returns:
        基金实时估值数据（前20条）
    """
    import akshare as ak

    try:
        df = ak.fund_value_estimation_em(symbol=fund_type)

        if df.empty:
            return "无实时估值数据"

        df_top = df.head(20)

        lines = ["基金实时净值估算（前20）:"]
        lines.append("代码   | 名称           | 估算值  | 估算增长率 | 单位净值")
        lines.append("------|---------------|--------|---------|--------")

        for _, row in df_top.iterrows():
            lines.append(
                f"{row['基金代码']} | {str(row['基金名称'])[:12]:<12} | "
                f"{row.get('估算值', 'N/A'):>6} | {row.get('估算增长率', 'N/A'):>7}% | "
                f"{row.get('单位净值', 'N/A'):>6}"
            )

        return "\n".join(lines)

    except Exception as e:
        logger.error("fund_nav_estimate failed", error=str(e))
        return f"查询基金估值失败: {e}"
