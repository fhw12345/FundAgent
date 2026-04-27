"""Cost basis & PnL calculator from transaction history.

Uses moving weighted-average cost (most common for funds).
"""

from typing import Any


def calc_fund_summary(transactions: list[dict[str, Any]], current_nav: float | None = None) -> dict[str, Any]:
    """Compute summary for one fund from its sorted transactions (oldest → newest).

    Returns dict with:
        total_shares: 当前持有份额
        total_cost: 累计成本 (买入 - 卖出回收 - 转换出回收)
        avg_cost: 加权平均成本价（每份）
        realized_pnl: 已实现盈亏（卖出实际收回 - 卖出对应成本）
        unrealized_pnl: 未实现盈亏（按 current_nav 估算）
        market_value: 当前市值
        total_return_pct: 总收益率
    """
    total_shares = 0.0
    total_cost = 0.0
    realized_pnl = 0.0

    for tx in transactions:
        tx_type = tx.get("tx_type")
        shares = float(tx.get("shares") or 0)
        amount = float(tx.get("amount") or 0)
        fee = float(tx.get("fee") or 0)

        if tx_type in ("buy", "convert", "dividend_invest"):
            total_shares += shares
            total_cost += amount + fee
        elif tx_type == "sell":
            sell_shares = abs(shares)
            if total_shares > 0:
                avg = total_cost / total_shares
                cost_of_sold = avg * sell_shares
                realized_pnl += (amount - fee) - cost_of_sold
                total_cost -= cost_of_sold
            total_shares -= sell_shares
            if total_shares < 0.0001:
                total_shares = 0.0
                total_cost = 0.0

    avg_cost = (total_cost / total_shares) if total_shares > 0 else 0.0

    summary = {
        "total_shares": round(total_shares, 4),
        "total_cost": round(total_cost, 2),
        "avg_cost": round(avg_cost, 4),
        "realized_pnl": round(realized_pnl, 2),
    }

    if current_nav and total_shares > 0:
        market_value = total_shares * current_nav
        unrealized_pnl = market_value - total_cost
        total_return_pct = ((unrealized_pnl + realized_pnl) / (total_cost + max(realized_pnl, 0)) * 100) if total_cost > 0 else 0.0
        summary.update({
            "current_nav": current_nav,
            "market_value": round(market_value, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "total_return_pct": round(total_return_pct, 2),
        })

    return summary


def aggregate_holdings(transactions_by_fund: dict[str, list[dict[str, Any]]], navs: dict[str, float]) -> list[dict[str, Any]]:
    """Aggregate transactions per fund into holding rows."""
    holdings = []
    for fund_code, txs in transactions_by_fund.items():
        if not txs:
            continue
        fund_name = next((t.get("fund_name", "") for t in txs if t.get("fund_name")), "")
        nav = navs.get(fund_code)
        summary = calc_fund_summary(txs, current_nav=nav)
        if summary["total_shares"] <= 0:
            continue
        holdings.append({
            "fund_code": fund_code,
            "fund_name": fund_name,
            "shares": summary["total_shares"],
            "nav": summary.get("current_nav"),
            "market_value": summary.get("market_value"),
            "avg_cost": summary["avg_cost"],
            "total_cost": summary["total_cost"],
            "unrealized_pnl": summary.get("unrealized_pnl"),
            "realized_pnl": summary["realized_pnl"],
            "return_pct": summary.get("total_return_pct"),
        })
    return holdings
