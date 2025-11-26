"""
Alpha Vantage Response Formatter.

Provides unified, rich markdown formatting for all Alpha Vantage API responses.
Ensures consistent output across agent tools, button tools, and copilot.

Key Features:
- Metadata headers (tool name, symbol, invocation time, data source)
- Latest annual + current year quarterly trends
- Trend analysis insights (QoQ growth, ratios)
- Safe number formatting with M/B suffixes
"""

from datetime import datetime
from typing import Any


class AlphaVantageResponseFormatter:
    """Centralized formatter for Alpha Vantage API responses."""

    @staticmethod
    def _safe_float(value: str | None, default: float = 0.0) -> float:
        """
        Safely convert string to float.

        Args:
            value: String value to convert
            default: Default value if conversion fails

        Returns:
            Float value or default
        """
        if not value or value == "None":
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _format_large_number(value: float | None) -> str:
        """
        Format large numbers with M/B suffixes.

        Args:
            value: Number to format

        Returns:
            Formatted string (e.g., "1.5B", "250.3M")
        """
        if value is None or value == 0:
            return "N/A"

        abs_value = abs(value)
        if abs_value >= 1e9:
            return f"${value/1e9:.2f}B"
        elif abs_value >= 1e6:
            return f"${value/1e6:.1f}M"
        elif abs_value >= 1e3:
            return f"${value/1e3:.1f}K"
        else:
            return f"${value:.2f}"

    @staticmethod
    def _calculate_qoq_growth(current: float | None, previous: float | None) -> str:
        """
        Calculate quarter-over-quarter growth percentage.

        Args:
            current: Current quarter value
            previous: Previous quarter value

        Returns:
            Formatted growth string (e.g., "+5.2%", "-2.1%")
        """
        if current is None or previous is None or previous == 0:
            return "N/A"

        growth = ((current - previous) / previous) * 100
        sign = "+" if growth >= 0 else ""
        return f"{sign}{growth:.1f}%"

    @staticmethod
    def _generate_metadata_header(
        tool_name: str, symbol: str | None, invoked_at: str, data_source: str
    ) -> str:
        """
        Generate metadata header for tool output.

        Args:
            tool_name: Name of the tool (e.g., "Cash Flow Analysis")
            symbol: Stock symbol (optional)
            invoked_at: ISO timestamp of invocation
            data_source: API endpoint name

        Returns:
            Formatted metadata header
        """
        lines = [
            "---",
            f"**Tool:** {tool_name}",
        ]

        if symbol:
            lines.append(f"**Symbol:** {symbol}")

        lines.extend(
            [
                f"**Invoked:** {invoked_at}",
                f"**Data Source:** Alpha Vantage {data_source} API",
                "---",
                "",
            ]
        )

        return "\n".join(lines)

    @staticmethod
    def _extract_current_year_quarters(
        quarterly_reports: list[dict[str, Any]], current_year: int | None = None
    ) -> list[dict[str, Any]]:
        """
        Extract quarters from the current year.

        Args:
            quarterly_reports: List of quarterly reports from Alpha Vantage
            current_year: Year to filter (defaults to current year)

        Returns:
            List of quarters from current year, sorted chronologically
        """
        if current_year is None:
            current_year = datetime.now().year

        current_year_quarters = [
            q
            for q in quarterly_reports
            if q.get("fiscalDateEnding", "").startswith(str(current_year))
        ]

        # Sort by fiscal date (chronological order)
        current_year_quarters.sort(key=lambda x: x.get("fiscalDateEnding", ""))

        return current_year_quarters

    def format_company_overview(
        self, raw_data: dict[str, Any], symbol: str, invoked_at: str
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
        header = self._generate_metadata_header(
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
        market_cap = self._safe_float(raw_data.get("MarketCapitalization"))
        pe_ratio = self._safe_float(raw_data.get("PERatio"))
        eps = self._safe_float(raw_data.get("EPS"))
        profit_margin = self._safe_float(raw_data.get("ProfitMargin")) * 100
        revenue_ttm = self._safe_float(raw_data.get("RevenueTTM"))
        dividend_yield = self._safe_float(raw_data.get("DividendYield")) * 100
        beta = self._safe_float(raw_data.get("Beta"))
        percent_insiders = self._safe_float(raw_data.get("PercentInsiders"))
        percent_institutions = self._safe_float(raw_data.get("PercentInstitutions"))
        week_52_high = self._safe_float(raw_data.get("52WeekHigh"))
        week_52_low = self._safe_float(raw_data.get("52WeekLow"))

        # Build output
        output = [
            header,
            f"## 🏢 Company Overview - {symbol}",
            f"*{name}*",
            "",
            "### 📋 Company Information",
            "",
            f"**Industry:** {industry} | **Sector:** {sector}",
            f"**Exchange:** {exchange} | **Country:** {country}",
            "",
            f"**Description:** {description}",
            "",
            "### 📊 Key Metrics",
            "",
            "| Metric | Value | Metric | Value |",
            "|--------|-------|--------|-------|",
        ]

        # Build metrics table (2 columns)
        metrics = []
        if market_cap > 0:
            metrics.append(
                (
                    f"Market Cap | {self._format_large_number(market_cap)}",
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
                    f"Revenue (TTM) | {self._format_large_number(revenue_ttm)}",
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

    def format_cash_flow(
        self, raw_data: dict[str, Any], symbol: str, invoked_at: str
    ) -> str:
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
        header = self._generate_metadata_header(
            tool_name="Cash Flow Analysis",
            symbol=symbol,
            invoked_at=invoked_at,
            data_source="CASH_FLOW",
        )

        annual_reports = raw_data.get("annualReports", [])
        quarterly_reports = raw_data.get("quarterlyReports", [])

        if not annual_reports:
            return f"{header}\n## 💵 Cash Flow - {symbol}\n\nNo cash flow data available for {symbol}"

        # Latest annual report
        latest_annual = annual_reports[0]
        fiscal_year = latest_annual.get("fiscalDateEnding", "N/A")

        operating_cf = self._safe_float(latest_annual.get("operatingCashflow"))
        capex = self._safe_float(latest_annual.get("capitalExpenditures"))
        free_cf = operating_cf - abs(capex) if operating_cf and capex else None
        dividend_payout = self._safe_float(latest_annual.get("dividendPayout"))

        output = [
            header,
            f"## 💵 Cash Flow - {symbol}",
            "",
            f"### 📊 Latest Annual Report (FY {fiscal_year[:4]})",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Operating Cash Flow | {self._format_large_number(operating_cf)} |",
            f"| Capital Expenditures | {self._format_large_number(abs(capex))} |",
            f"| Free Cash Flow | {self._format_large_number(free_cf)} |",
        ]

        if dividend_payout and dividend_payout > 0:
            output.append(
                f"| Dividend Payout | {self._format_large_number(dividend_payout)} |"
            )

        # Current year quarterly trend
        current_year = datetime.now().year
        current_year_quarters = self._extract_current_year_quarters(
            quarterly_reports, current_year
        )

        if current_year_quarters:
            output.extend(
                [
                    "",
                    f"### 📈 Current Year Quarterly Trend ({current_year})",
                    "",
                    "| Quarter | Operating CF | CapEx | Free CF | QoQ Growth |",
                    "|---------|-------------|-------|---------|------------|",
                ]
            )

            previous_fcf = None
            for q in current_year_quarters:
                q_date = q.get("fiscalDateEnding", "")
                q_label = f"Q{(int(q_date[5:7]) - 1) // 3 + 1} {q_date[:4]}"

                q_operating = self._safe_float(q.get("operatingCashflow"))
                q_capex = self._safe_float(q.get("capitalExpenditures"))
                q_free_cf = (
                    q_operating - abs(q_capex) if q_operating and q_capex else None
                )

                qoq_growth = self._calculate_qoq_growth(q_free_cf, previous_fcf)

                output.append(
                    f"| {q_label} | {self._format_large_number(q_operating)} | "
                    f"{self._format_large_number(abs(q_capex))} | "
                    f"{self._format_large_number(q_free_cf)} | {qoq_growth} |"
                )

                previous_fcf = q_free_cf

            # Trend analysis
            if len(current_year_quarters) >= 2:
                latest_q = current_year_quarters[-1]
                prev_q = current_year_quarters[-2]

                latest_fcf = self._safe_float(latest_q.get("operatingCashflow")) - abs(
                    self._safe_float(latest_q.get("capitalExpenditures"))
                )
                prev_fcf = self._safe_float(prev_q.get("operatingCashflow")) - abs(
                    self._safe_float(prev_q.get("capitalExpenditures"))
                )

                growth = self._calculate_qoq_growth(latest_fcf, prev_fcf)

                output.extend(
                    [
                        "",
                        "### 💡 Trend Analysis",
                        f"• Free cash flow QoQ change: {growth}",
                    ]
                )

                if operating_cf > 0 and capex != 0:
                    capex_ratio = (abs(capex) / operating_cf) * 100
                    output.append(
                        f"• Capital efficiency: CapEx/Operating CF = {capex_ratio:.1f}%"
                    )

        return "\n".join(output)

    def format_balance_sheet(
        self, raw_data: dict[str, Any], symbol: str, invoked_at: str
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
        header = self._generate_metadata_header(
            tool_name="Balance Sheet Analysis",
            symbol=symbol,
            invoked_at=invoked_at,
            data_source="BALANCE_SHEET",
        )

        annual_reports = raw_data.get("annualReports", [])
        quarterly_reports = raw_data.get("quarterlyReports", [])

        if not annual_reports:
            return f"{header}\n## 📋 Balance Sheet - {symbol}\n\nNo balance sheet data available for {symbol}"

        # Latest annual report
        latest_annual = annual_reports[0]
        fiscal_year = latest_annual.get("fiscalDateEnding", "N/A")

        total_assets = self._safe_float(latest_annual.get("totalAssets"))
        total_liabilities = self._safe_float(latest_annual.get("totalLiabilities"))
        equity = self._safe_float(latest_annual.get("totalShareholderEquity"))
        current_assets = self._safe_float(latest_annual.get("currentAssets"))
        current_liabilities = self._safe_float(latest_annual.get("currentLiabilities"))
        cash = self._safe_float(
            latest_annual.get("cashAndCashEquivalentsAtCarryingValue")
        )

        output = [
            header,
            f"## 📋 Balance Sheet - {symbol}",
            "",
            f"### 📊 Latest Annual Report (FY {fiscal_year[:4]})",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Total Assets | {self._format_large_number(total_assets)} |",
            f"| Total Liabilities | {self._format_large_number(total_liabilities)} |",
            f"| Shareholder Equity | {self._format_large_number(equity)} |",
            f"| Current Assets | {self._format_large_number(current_assets)} |",
            f"| Current Liabilities | {self._format_large_number(current_liabilities)} |",
            f"| Cash & Equivalents | {self._format_large_number(cash)} |",
        ]

        # Financial ratios
        if current_assets > 0 and current_liabilities > 0:
            current_ratio = current_assets / current_liabilities
            output.extend(
                [
                    "",
                    "### 📐 Key Ratios",
                    f"• **Current Ratio:** {current_ratio:.2f} (liquidity measure)",
                ]
            )

        if total_assets > 0 and total_liabilities > 0:
            debt_to_assets = (total_liabilities / total_assets) * 100
            output.append(
                f"• **Debt-to-Assets:** {debt_to_assets:.1f}% (leverage measure)"
            )

        # Current year quarterly trend
        current_year = datetime.now().year
        current_year_quarters = self._extract_current_year_quarters(
            quarterly_reports, current_year
        )

        if current_year_quarters:
            output.extend(
                [
                    "",
                    f"### 📈 Current Year Quarterly Trend ({current_year})",
                    "",
                    "| Quarter | Total Assets | Total Liabilities | Equity | Current Ratio |",
                    "|---------|-------------|-------------------|--------|---------------|",
                ]
            )

            for q in current_year_quarters:
                q_date = q.get("fiscalDateEnding", "")
                q_label = f"Q{(int(q_date[5:7]) - 1) // 3 + 1} {q_date[:4]}"

                q_assets = self._safe_float(q.get("totalAssets"))
                q_liabilities = self._safe_float(q.get("totalLiabilities"))
                q_equity = self._safe_float(q.get("totalShareholderEquity"))
                q_current_assets = self._safe_float(q.get("currentAssets"))
                q_current_liabilities = self._safe_float(q.get("currentLiabilities"))

                q_current_ratio = (
                    q_current_assets / q_current_liabilities
                    if q_current_liabilities > 0
                    else 0
                )

                output.append(
                    f"| {q_label} | {self._format_large_number(q_assets)} | "
                    f"{self._format_large_number(q_liabilities)} | "
                    f"{self._format_large_number(q_equity)} | "
                    f"{q_current_ratio:.2f} |"
                )

        return "\n".join(output)

    def format_news_sentiment(
        self, raw_data: dict[str, Any], symbol: str, invoked_at: str
    ) -> str:
        """
        Format news sentiment with positive/negative articles.

        Args:
            raw_data: Raw Alpha Vantage NEWS_SENTIMENT response
            symbol: Stock symbol
            invoked_at: ISO timestamp

        Returns:
            Rich markdown with sentiment analysis
        """
        header = self._generate_metadata_header(
            tool_name="News Sentiment Analysis",
            symbol=symbol,
            invoked_at=invoked_at,
            data_source="NEWS_SENTIMENT",
        )

        feed = raw_data.get("feed", [])

        if not feed:
            return f"{header}\n## 📰 News Sentiment - {symbol}\n\nNo news articles available for {symbol}"

        # Filter by sentiment
        positive_news = [
            item for item in feed if item.get("overall_sentiment_score", 0) > 0.15
        ]
        negative_news = [
            item for item in feed if item.get("overall_sentiment_score", 0) < -0.15
        ]

        # Sort and limit
        positive_news = sorted(
            positive_news,
            key=lambda x: x.get("overall_sentiment_score", 0),
            reverse=True,
        )[:3]
        negative_news = sorted(
            negative_news, key=lambda x: x.get("overall_sentiment_score", 0)
        )[:3]

        output = [
            header,
            f"## 📰 News Sentiment - {symbol}",
            "",
            "### 📝 Overall Summary",
            f"Found {len(positive_news)} strongly positive and {len(negative_news)} strongly negative articles",
            "",
        ]

        if positive_news:
            output.extend(["### ✅ Positive News", ""])
            for article in positive_news:
                score = article.get("overall_sentiment_score", 0)
                title = article.get("title", "")
                source = article.get("source", "Unknown")
                url = article.get("url", "#")
                summary = article.get("summary", "")
                time_published = article.get("time_published", "")

                # Format publication time if available
                time_str = ""
                if time_published:
                    # Alpha Vantage returns YYYYMMDDTHHMMSS format
                    try:
                        from datetime import datetime

                        dt = datetime.strptime(time_published, "%Y%m%dT%H%M%S")
                        time_str = f" • {dt.strftime('%b %d, %Y')}"
                    except (ValueError, TypeError):
                        pass

                # Title as clickable link with icon to indicate clickability
                output.extend([f"🔗 **[{title}]({url})**"])

                # Add source, sentiment, and time on one line
                output.append(
                    f"*{source}{time_str} • Sentiment: {score:+.2f} (Bullish)*"
                )

                # Add summary if available (expandable)
                if summary:
                    output.extend(
                        [
                            "",
                            "<details>",
                            "<summary><strong>📄 Read summary</strong></summary>",
                            "",
                            summary,
                            "",
                            "</details>",
                            "",
                        ]
                    )
                else:
                    # Add spacing if no summary
                    output.append("")

        if negative_news:
            output.extend(["### ❌ Negative News", ""])
            for article in negative_news:
                score = article.get("overall_sentiment_score", 0)
                title = article.get("title", "")
                source = article.get("source", "Unknown")
                url = article.get("url", "#")
                summary = article.get("summary", "")
                time_published = article.get("time_published", "")

                # Format publication time if available
                time_str = ""
                if time_published:
                    # Alpha Vantage returns YYYYMMDDTHHMMSS format
                    try:
                        from datetime import datetime

                        dt = datetime.strptime(time_published, "%Y%m%dT%H%M%S")
                        time_str = f" • {dt.strftime('%b %d, %Y')}"
                    except (ValueError, TypeError):
                        pass

                # Title as clickable link with icon to indicate clickability
                output.extend([f"🔗 **[{title}]({url})**"])

                # Add source, sentiment, and time on one line
                output.append(
                    f"*{source}{time_str} • Sentiment: {score:+.2f} (Bearish)*"
                )

                # Add summary if available (expandable)
                if summary:
                    output.extend(
                        [
                            "",
                            "<details>",
                            "<summary><strong>📄 Read summary</strong></summary>",
                            "",
                            summary,
                            "",
                            "</details>",
                            "",
                        ]
                    )
                else:
                    # Add spacing if no summary
                    output.append("")

        if not positive_news and not negative_news:
            output.append(
                "No strongly positive or negative articles found (sentiment threshold: ±0.15)"
            )

        return "\n".join(output)

    def format_market_movers(self, raw_data: dict[str, Any], invoked_at: str) -> str:
        """
        Format market movers (gainers, losers, most active).

        Args:
            raw_data: Raw Alpha Vantage TOP_GAINERS_LOSERS response
            invoked_at: ISO timestamp

        Returns:
            Rich markdown with market movers
        """
        header = self._generate_metadata_header(
            tool_name="Market Movers",
            symbol=None,
            invoked_at=invoked_at,
            data_source="TOP_GAINERS_LOSERS",
        )

        gainers = raw_data.get("top_gainers", [])[:5]
        losers = raw_data.get("top_losers", [])[:5]
        active = raw_data.get("most_actively_traded", [])[:5]

        output = [
            header,
            "## 📊 Today's Market Movers",
            "",
        ]

        if gainers:
            output.extend(
                [
                    "### 📈 Top Gainers",
                    "",
                    "| Ticker | Price | Change | Volume |",
                    "|--------|-------|--------|--------|",
                ]
            )

            for stock in gainers:
                ticker = stock.get("ticker", "N/A")
                price = float(stock.get("price", 0))
                change_pct = stock.get("change_percentage", "N/A")
                volume = int(stock.get("volume", 0))

                output.append(
                    f"| {ticker} | ${price:.2f} | {change_pct} | {volume/1e6:.1f}M |"
                )

            output.append("")

        if losers:
            output.extend(
                [
                    "### 📉 Top Losers",
                    "",
                    "| Ticker | Price | Change | Volume |",
                    "|--------|-------|--------|--------|",
                ]
            )

            for stock in losers:
                ticker = stock.get("ticker", "N/A")
                price = float(stock.get("price", 0))
                change_pct = stock.get("change_percentage", "N/A")
                volume = int(stock.get("volume", 0))

                output.append(
                    f"| {ticker} | ${price:.2f} | {change_pct} | {volume/1e6:.1f}M |"
                )

            output.append("")

        if active:
            output.extend(
                [
                    "### 🔥 Most Active",
                    "",
                    "| Ticker | Price | Change | Volume |",
                    "|--------|-------|--------|--------|",
                ]
            )

            for stock in active:
                ticker = stock.get("ticker", "N/A")
                price = float(stock.get("price", 0))
                change_pct = stock.get("change_percentage", "N/A")
                volume = int(stock.get("volume", 0))

                output.append(
                    f"| {ticker} | ${price:.2f} | {change_pct} | {volume/1e6:.1f}M |"
                )

        return "\n".join(output)

    def format_insider_transactions(
        self,
        raw_data: dict[str, Any],
        symbol: str,
        invoked_at: str,
    ) -> str:
        """
        Format insider transactions for LLM consumption.

        Groups by acquisition vs disposal, shows recent activity trends.

        Args:
            raw_data: Dict with 'data' list of transaction records
            symbol: Stock symbol
            invoked_at: Timestamp when tool was invoked

        Returns:
            Compressed markdown summary of insider activity
        """
        output = [
            f"# 👔 Insider Transactions: {symbol}",
            f"*Data Source: Alpha Vantage | Invoked: {invoked_at}*",
            "",
        ]

        transactions = raw_data.get("data", [])

        if not transactions:
            output.append("**No insider transaction data available**")
            return "\n".join(output)

        # Group by acquisition vs disposal
        acquisitions = [
            t for t in transactions if t.get("acquisition_or_disposal") == "A"
        ]
        disposals = [t for t in transactions if t.get("acquisition_or_disposal") == "D"]

        # Calculate totals
        total_acquired_shares = sum(
            self._safe_float(t.get("shares", "0")) for t in acquisitions
        )
        total_disposed_shares = sum(
            self._safe_float(t.get("shares", "0")) for t in disposals
        )

        output.extend(
            [
                "## Recent Activity Summary",
                "",
                f"- **Acquisitions**: {len(acquisitions)} transactions ({total_acquired_shares:,.0f} shares)",
                f"- **Disposals**: {len(disposals)} transactions ({total_disposed_shares:,.0f} shares)",
                "",
            ]
        )

        # Trend analysis
        net_shares = total_acquired_shares - total_disposed_shares
        if net_shares > 0:
            trend = f"↑ **Bullish** (Net buying: {net_shares:,.0f} shares)"
        elif net_shares < 0:
            trend = f"↓ **Bearish** (Net selling: {abs(net_shares):,.0f} shares)"
        else:
            trend = "→ **Neutral** (No net change)"

        output.extend([f"**Insider Sentiment**: {trend}", ""])

        # Top acquisitions
        if acquisitions:
            output.extend(
                [
                    "### Top Acquisitions",
                    "",
                    "| Date | Executive | Shares | Price |",
                    "|------|-----------|--------|-------|",
                ]
            )

            for t in acquisitions[:5]:
                date = t.get("transaction_date", "N/A")
                exec_name = t.get("executive", "N/A")
                shares = self._safe_float(t.get("shares", "0"))
                price = self._safe_float(t.get("share_price", "0"))

                output.append(
                    f"| {date} | {exec_name[:25]} | {shares:,.0f} | ${price:.2f} |"
                )

            output.append("")

        # Top disposals
        if disposals:
            output.extend(
                [
                    "### Top Disposals",
                    "",
                    "| Date | Executive | Shares | Price |",
                    "|------|-----------|--------|-------|",
                ]
            )

            for t in disposals[:5]:
                date = t.get("transaction_date", "N/A")
                exec_name = t.get("executive", "N/A")
                shares = self._safe_float(t.get("shares", "0"))
                price = self._safe_float(t.get("share_price", "0"))

                output.append(
                    f"| {date} | {exec_name[:25]} | {shares:,.0f} | ${price:.2f} |"
                )

            output.append("")

        return "\n".join(output)

    def format_etf_profile(
        self,
        raw_data: dict[str, Any],
        symbol: str,
        invoked_at: str,
    ) -> str:
        """
        Format ETF profile with top holdings and sector allocation.

        Args:
            raw_data: Dict with ETF profile data
            symbol: ETF ticker symbol
            invoked_at: Timestamp when tool was invoked

        Returns:
            Formatted ETF profile markdown
        """
        output = [
            f"# 📦 ETF Profile: {symbol}",
            f"*Data Source: Alpha Vantage | Invoked: {invoked_at}*",
            "",
        ]

        # Overview
        net_assets = raw_data.get("net_assets", "N/A")
        expense_ratio = raw_data.get("net_expense_ratio", "N/A")
        dividend_yield = raw_data.get("dividend_yield", "N/A")
        leveraged = raw_data.get("leveraged", "NO")

        # Format net assets
        if net_assets != "N/A":
            net_assets_num = self._safe_float(net_assets)
            net_assets_formatted = self._format_large_number(net_assets_num)
        else:
            net_assets_formatted = "N/A"

        output.extend(
            [
                "## Overview",
                "",
                f"- **Net Assets**: ${net_assets_formatted}",
                f"- **Expense Ratio**: {expense_ratio}",
                f"- **Dividend Yield**: {dividend_yield}",
                f"- **Leveraged**: {leveraged}",
                "",
            ]
        )

        # Top holdings
        holdings = raw_data.get("holdings", [])
        if holdings:
            output.extend(
                [
                    f"## Top {min(10, len(holdings))} Holdings",
                    "",
                    "| Symbol | Description | Weight |",
                    "|--------|-------------|--------|",
                ]
            )

            for holding in holdings[:10]:
                symbol_h = holding.get("symbol", "N/A")
                desc = holding.get("description", "N/A")
                weight = holding.get("weight", "0")
                weight_pct = self._safe_float(weight) * 100

                output.append(f"| {symbol_h} | {desc[:30]} | {weight_pct:.2f}% |")

            output.append("")

        # Sector allocation
        sectors = raw_data.get("sectors", [])
        if sectors:
            output.extend(
                [
                    "## Sector Allocation",
                    "",
                    "| Sector | Weight |",
                    "|--------|--------|",
                ]
            )

            for sector in sectors:
                sector_name = sector.get("sector", "N/A")
                weight = sector.get("weight", "0")
                weight_pct = self._safe_float(weight) * 100

                output.append(f"| {sector_name} | {weight_pct:.2f}% |")

            output.append("")

        return "\n".join(output)

    def format_commodity_price(
        self,
        df: Any,  # pd.DataFrame
        commodity: str,
        interval: str,
        invoked_at: str,
    ) -> str:
        """
        Format commodity price data with trend analysis.

        Args:
            df: DataFrame with date index and value column
            commodity: Commodity name (e.g., "COPPER")
            interval: Price interval
            invoked_at: Timestamp when tool was invoked

        Returns:
            Formatted commodity price markdown with trends
        """

        output = [
            f"# 🔶 {commodity.title()} Prices ({interval.title()})",
            f"*Data Source: Alpha Vantage | Invoked: {invoked_at}*",
            "",
        ]

        if df.empty:
            output.append("**No price data available**")
            return "\n".join(output)

        # Current price (most recent)
        current_price = float(df.iloc[-1]["value"])

        output.extend(
            [
                f"## Current Price: ${current_price:,.2f}",
                "",
            ]
        )

        # Calculate trends (if enough data)
        if len(df) >= 12:
            price_1m_ago = (
                float(df.iloc[-2]["value"]) if len(df) >= 2 else current_price
            )
            price_3m_ago = (
                float(df.iloc[-4]["value"]) if len(df) >= 4 else current_price
            )
            price_12m_ago = (
                float(df.iloc[-13]["value"]) if len(df) >= 13 else current_price
            )

            change_1m = ((current_price - price_1m_ago) / price_1m_ago) * 100
            change_3m = ((current_price - price_3m_ago) / price_3m_ago) * 100
            change_12m = ((current_price - price_12m_ago) / price_12m_ago) * 100

            output.extend(
                [
                    "## Trend Analysis",
                    "",
                    f"- **1-Period Change**: {change_1m:+.1f}% (${price_1m_ago:,.2f} → ${current_price:,.2f})",
                    f"- **3-Period Change**: {change_3m:+.1f}% (${price_3m_ago:,.2f} → ${current_price:,.2f})",
                    f"- **12-Period Change**: {change_12m:+.1f}% (${price_12m_ago:,.2f} → ${current_price:,.2f})",
                    "",
                ]
            )

            # Overall trend
            if change_12m > 10:
                trend = "↑ **Strong Bullish** (Rising demand)"
            elif change_12m > 0:
                trend = "↗ **Bullish** (Moderate growth)"
            elif change_12m > -10:
                trend = "↘ **Bearish** (Slight decline)"
            else:
                trend = "↓ **Strong Bearish** (Falling demand)"

            output.extend([f"**Overall Trend**: {trend}", ""])

        # Recent price history (last 12 periods)
        output.extend(
            [
                "## Price History (Recent)",
                "",
                "| Date | Price | Change |",
                "|------|-------|--------|",
            ]
        )

        recent_df = df.tail(12)
        for i, (date, row) in enumerate(recent_df.iterrows()):
            price = float(row["value"])
            if i > 0:
                prev_price = float(recent_df.iloc[i - 1]["value"])
                change_pct = ((price - prev_price) / prev_price) * 100
                change_str = f"{change_pct:+.1f}%"
            else:
                change_str = "-"

            output.append(f"| {date.date()} | ${price:,.2f} | {change_str} |")

        output.append("")

        return "\n".join(output)

    def format_technical_indicator(
        self,
        df: Any,  # pd.DataFrame
        symbol: str,
        function: str,
        interval: str,
        invoked_at: str,
    ) -> str:
        """
        Format technical indicator with current value and signal.

        Args:
            df: DataFrame with indicator values
            symbol: Stock symbol
            function: Indicator name (RSI, MACD, etc.)
            interval: Time interval
            invoked_at: Timestamp when tool was invoked

        Returns:
            Formatted technical indicator markdown
        """
        output = [
            f"# 📉 {function}: {symbol}",
            f"*{interval.title()} | Data Source: Alpha Vantage | Invoked: {invoked_at}*",
            "",
        ]

        if df.empty:
            output.append("**No indicator data available**")
            return "\n".join(output)

        # Current value (most recent)
        last_row = df.iloc[-1]

        # Format current value based on indicator type
        if len(df.columns) == 1:
            # Single-value indicators (SMA, EMA, RSI, etc.)
            col_name = df.columns[0]
            current_value = float(last_row[col_name])

            output.extend(
                [
                    f"## Current {function}: {current_value:.2f}",
                    "",
                ]
            )

            # Add signal interpretation for specific indicators
            if function == "RSI":
                if current_value > 70:
                    signal = "🔴 **Overbought** (Potential reversal down)"
                elif current_value < 30:
                    signal = "🟢 **Oversold** (Potential reversal up)"
                else:
                    signal = "🟡 **Neutral** (Range-bound)"

                output.extend([f"**Signal**: {signal}", ""])

        else:
            # Multi-value indicators (MACD, STOCH, BBANDS, etc.)
            output.extend(["## Current Values", ""])

            for col in df.columns:
                value = float(last_row[col])
                output.append(f"- **{col}**: {value:.2f}")

            output.append("")

            # MACD-specific signal
            if function == "MACD" and "MACD" in df.columns:
                macd_val = float(last_row.get("MACD", 0))
                signal_val = float(last_row.get("MACD_Signal", 0))

                if macd_val > signal_val:
                    signal = "🟢 **Bullish** (MACD above signal)"
                else:
                    signal = "🔴 **Bearish** (MACD below signal)"

                output.extend([f"**Signal**: {signal}", ""])

        # Recent values table (last 10 periods)
        output.extend(
            [
                "## Recent Values",
                "",
            ]
        )

        # Build table header
        header = "| Date |"
        separator = "|------|"
        for col in df.columns:
            header += f" {col} |"
            separator += "--------|"

        output.extend([header, separator])

        # Add last 10 rows
        recent_df = df.tail(10)
        for date, row in recent_df.iterrows():
            row_str = f"| {date.date() if hasattr(date, 'date') else date} |"
            for col in df.columns:
                value = float(row[col])
                row_str += f" {value:.2f} |"
            output.append(row_str)

        output.append("")

        return "\n".join(output)
