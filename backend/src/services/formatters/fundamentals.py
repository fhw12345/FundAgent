"""
Fundamentals formatting for Alpha Vantage responses.

Handles company overview, cash flow, and balance sheet formatting.
"""

from datetime import datetime
from typing import Any

from .base import (
    calculate_qoq_growth,
    extract_current_year_quarters,
    format_large_number,
    generate_metadata_header,
    get_quarter_label,
    safe_float,
)


class FundamentalsFormatter:
    """Formatter for company fundamentals data."""

    @staticmethod
    def format_company_overview(
        raw_data: dict[str, Any], symbol: str, invoked_at: str
    ) -> str:
        """
        Format company overview with comprehensive metrics.

        Args:
            raw_data: Raw Alpha Vantage OVERVIEW response
            symbol: Stock symbol
            invoked_at: ISO timestamp

        Returns:
            Rich markdown with company info and key metrics
        """
        header = generate_metadata_header(
            tool_name="Company Overview",
            symbol=symbol,
            invoked_at=invoked_at,
            data_source="OVERVIEW",
        )

        # Extract company info
        name = raw_data.get("Name", symbol)
        description = raw_data.get("Description", "N/A")
        industry = raw_data.get("Industry", "N/A")
        sector = raw_data.get("Sector", "N/A")
        exchange = raw_data.get("Exchange", "N/A")
        country = raw_data.get("Country", "N/A")

        # Extract key metrics
        market_cap = safe_float(raw_data.get("MarketCapitalization"))
        pe_ratio = safe_float(raw_data.get("PERatio"))
        eps = safe_float(raw_data.get("EPS"))
        profit_margin = safe_float(raw_data.get("ProfitMargin")) * 100
        revenue_ttm = safe_float(raw_data.get("RevenueTTM"))
        dividend_yield = safe_float(raw_data.get("DividendYield")) * 100
        beta = safe_float(raw_data.get("Beta"))
        percent_insiders = safe_float(raw_data.get("PercentInsiders"))
        percent_institutions = safe_float(raw_data.get("PercentInstitutions"))
        week_52_high = safe_float(raw_data.get("52WeekHigh"))
        week_52_low = safe_float(raw_data.get("52WeekLow"))

        # Build output
        output = [
            header,
            f"## Company Overview - {symbol}",
            f"*{name}*",
            "",
            "### Company Information",
            "",
            f"**Industry:** {industry} | **Sector:** {sector}",
            f"**Exchange:** {exchange} | **Country:** {country}",
            "",
            f"**Description:** {description}",
            "",
            "### Key Metrics",
            "",
            "| Metric | Value | Metric | Value |",
            "|--------|-------|--------|-------|",
        ]

        # Build metrics table (2 columns)
        metrics = []
        if market_cap > 0:
            metrics.append(
                (
                    f"Market Cap | {format_large_number(market_cap)}",
                    (
                        f"P/E Ratio | {pe_ratio:.2f}"
                        if pe_ratio > 0
                        else "P/E Ratio | N/A"
                    ),
                )
            )
        if eps != 0:
            metrics.append(
                (
                    f"EPS | ${eps:.2f}",
                    (
                        f"Profit Margin | {profit_margin:.2f}%"
                        if profit_margin > 0
                        else "Profit Margin | N/A"
                    ),
                )
            )
        if revenue_ttm > 0:
            metrics.append(
                (
                    f"Revenue (TTM) | {format_large_number(revenue_ttm)}",
                    (
                        f"Dividend Yield | {dividend_yield:.2f}%"
                        if dividend_yield > 0
                        else "Dividend Yield | N/A"
                    ),
                )
            )
        if beta != 0:
            metrics.append(
                (
                    f"Beta | {beta:.2f}",
                    (
                        f"% Insiders | {percent_insiders:.2f}%"
                        if percent_insiders > 0
                        else "% Insiders | N/A"
                    ),
                )
            )
        if percent_institutions > 0:
            metrics.append(
                (
                    f"% Institutions | {percent_institutions:.2f}%",
                    (
                        f"52W High | ${week_52_high:.2f}"
                        if week_52_high > 0
                        else "52W High | N/A"
                    ),
                )
            )
        if week_52_low > 0:
            metrics.append(("52W Low | $" + f"{week_52_low:.2f}", "- | -"))

        # Add metrics to table
        for left, right in metrics:
            output.append(f"| {left} | {right} |")

        return "\n".join(output)

    @staticmethod
    def format_cash_flow(raw_data: dict[str, Any], symbol: str, invoked_at: str) -> str:
        """
        Format cash flow statement with trend analysis.

        Shows latest annual + current year quarterly trends.

        Args:
            raw_data: Raw Alpha Vantage CASH_FLOW response
            symbol: Stock symbol
            invoked_at: ISO timestamp

        Returns:
            Rich markdown with cash flow trends
        """
        header = generate_metadata_header(
            tool_name="Cash Flow Analysis",
            symbol=symbol,
            invoked_at=invoked_at,
            data_source="CASH_FLOW",
        )

        annual_reports = raw_data.get("annualReports", [])
        quarterly_reports = raw_data.get("quarterlyReports", [])

        if not annual_reports:
            return (
                f"{header}\n## Cash Flow - {symbol}\n\n"
                f"No cash flow data available for {symbol}"
            )

        # Latest annual report
        latest_annual = annual_reports[0]
        fiscal_year = latest_annual.get("fiscalDateEnding", "N/A")

        operating_cf = safe_float(latest_annual.get("operatingCashflow"))
        capex = safe_float(latest_annual.get("capitalExpenditures"))
        free_cf = operating_cf - abs(capex) if operating_cf and capex else None
        dividend_payout = safe_float(latest_annual.get("dividendPayout"))

        output = [
            header,
            f"## Cash Flow - {symbol}",
            "",
            f"### Latest Annual Report (FY {fiscal_year[:4]})",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Operating Cash Flow | {format_large_number(operating_cf)} |",
            f"| Capital Expenditures | {format_large_number(abs(capex))} |",
            f"| Free Cash Flow | {format_large_number(free_cf)} |",
        ]

        if dividend_payout and dividend_payout > 0:
            output.append(
                f"| Dividend Payout | {format_large_number(dividend_payout)} |"
            )

        # Current year quarterly trend
        current_year = datetime.now().year
        current_year_quarters = extract_current_year_quarters(
            quarterly_reports, current_year
        )

        if current_year_quarters:
            output.extend(
                [
                    "",
                    f"### Current Year Quarterly Trend ({current_year})",
                    "",
                    "| Quarter | Operating CF | CapEx | Free CF | QoQ Growth |",
                    "|---------|-------------|-------|---------|------------|",
                ]
            )

            previous_fcf = None
            for q in current_year_quarters:
                q_date = q.get("fiscalDateEnding", "")
                q_label = get_quarter_label(q_date)

                q_operating = safe_float(q.get("operatingCashflow"))
                q_capex = safe_float(q.get("capitalExpenditures"))
                q_free_cf = (
                    q_operating - abs(q_capex) if q_operating and q_capex else None
                )

                qoq_growth = calculate_qoq_growth(q_free_cf, previous_fcf)

                output.append(
                    f"| {q_label} | {format_large_number(q_operating)} | "
                    f"{format_large_number(abs(q_capex))} | "
                    f"{format_large_number(q_free_cf)} | {qoq_growth} |"
                )

                previous_fcf = q_free_cf

            # Trend analysis
            if len(current_year_quarters) >= 2:
                latest_q = current_year_quarters[-1]
                prev_q = current_year_quarters[-2]

                latest_fcf = safe_float(latest_q.get("operatingCashflow")) - abs(
                    safe_float(latest_q.get("capitalExpenditures"))
                )
                prev_fcf = safe_float(prev_q.get("operatingCashflow")) - abs(
                    safe_float(prev_q.get("capitalExpenditures"))
                )

                growth = calculate_qoq_growth(latest_fcf, prev_fcf)

                output.extend(
                    [
                        "",
                        "### Trend Analysis",
                        f"* Free cash flow QoQ change: {growth}",
                    ]
                )

                if operating_cf > 0 and capex != 0:
                    capex_ratio = (abs(capex) / operating_cf) * 100
                    output.append(
                        f"* Capital efficiency: CapEx/Operating CF = {capex_ratio:.1f}%"
                    )

        return "\n".join(output)

    @staticmethod
    def format_balance_sheet(
        raw_data: dict[str, Any], symbol: str, invoked_at: str
    ) -> str:
        """
        Format balance sheet with trend analysis.

        Shows latest annual + current year quarterly trends.

        Args:
            raw_data: Raw Alpha Vantage BALANCE_SHEET response
            symbol: Stock symbol
            invoked_at: ISO timestamp

        Returns:
            Rich markdown with balance sheet trends
        """
        header = generate_metadata_header(
            tool_name="Balance Sheet Analysis",
            symbol=symbol,
            invoked_at=invoked_at,
            data_source="BALANCE_SHEET",
        )

        annual_reports = raw_data.get("annualReports", [])
        quarterly_reports = raw_data.get("quarterlyReports", [])

        if not annual_reports:
            return (
                f"{header}\n## Balance Sheet - {symbol}\n\n"
                f"No balance sheet data available for {symbol}"
            )

        # Latest annual report
        latest_annual = annual_reports[0]
        fiscal_year = latest_annual.get("fiscalDateEnding", "N/A")

        total_assets = safe_float(latest_annual.get("totalAssets"))
        total_liabilities = safe_float(latest_annual.get("totalLiabilities"))
        equity = safe_float(latest_annual.get("totalShareholderEquity"))
        current_assets = safe_float(latest_annual.get("currentAssets"))
        current_liabilities = safe_float(latest_annual.get("currentLiabilities"))
        cash = safe_float(latest_annual.get("cashAndCashEquivalentsAtCarryingValue"))

        output = [
            header,
            f"## Balance Sheet - {symbol}",
            "",
            f"### Latest Annual Report (FY {fiscal_year[:4]})",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Total Assets | {format_large_number(total_assets)} |",
            f"| Total Liabilities | {format_large_number(total_liabilities)} |",
            f"| Shareholder Equity | {format_large_number(equity)} |",
            f"| Current Assets | {format_large_number(current_assets)} |",
            f"| Current Liabilities | {format_large_number(current_liabilities)} |",
            f"| Cash & Equivalents | {format_large_number(cash)} |",
        ]

        # Financial ratios
        if current_assets > 0 and current_liabilities > 0:
            current_ratio = current_assets / current_liabilities
            output.extend(
                [
                    "",
                    "### Key Ratios",
                    f"* **Current Ratio:** {current_ratio:.2f} (liquidity measure)",
                ]
            )

        if total_assets > 0 and total_liabilities > 0:
            debt_to_assets = (total_liabilities / total_assets) * 100
            output.append(
                f"* **Debt-to-Assets:** {debt_to_assets:.1f}% (leverage measure)"
            )

        # Current year quarterly trend
        current_year = datetime.now().year
        current_year_quarters = extract_current_year_quarters(
            quarterly_reports, current_year
        )

        if current_year_quarters:
            output.extend(
                [
                    "",
                    f"### Current Year Quarterly Trend ({current_year})",
                    "",
                    "| Quarter | Total Assets | Total Liabilities | Equity | Current Ratio |",
                    "|---------|-------------|-------------------|--------|---------------|",
                ]
            )

            for q in current_year_quarters:
                q_date = q.get("fiscalDateEnding", "")
                q_label = get_quarter_label(q_date)

                q_assets = safe_float(q.get("totalAssets"))
                q_liabilities = safe_float(q.get("totalLiabilities"))
                q_equity = safe_float(q.get("totalShareholderEquity"))
                q_current_assets = safe_float(q.get("currentAssets"))
                q_current_liabilities = safe_float(q.get("currentLiabilities"))

                q_current_ratio = (
                    q_current_assets / q_current_liabilities
                    if q_current_liabilities > 0
                    else 0
                )

                output.append(
                    f"| {q_label} | {format_large_number(q_assets)} | "
                    f"{format_large_number(q_liabilities)} | "
                    f"{format_large_number(q_equity)} | "
                    f"{q_current_ratio:.2f} |"
                )

        return "\n".join(output)
