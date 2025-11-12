"""
Stock fundamentals and analysis engine.
Provides comprehensive fundamental analysis including valuation metrics and company information.

NOTE: Temporarily disabled - requires migration from yfinance to alternative data source.
"""

from datetime import datetime

import structlog
# import yfinance as yf  # DISABLED: Removed yfinance dependency

from ...api.models import StockFundamentalsResponse

logger = structlog.get_logger()


class StockAnalyzer:
    """Stock fundamentals and analysis engine.

    NOTE: Currently disabled - requires alternative data source for fundamentals.
    """

    def __init__(self) -> None:
        self.ticker_data: None = None  # was: yf.Ticker | None
        self.symbol: str = ""

    async def get_fundamentals(self, symbol: str) -> StockFundamentalsResponse:
        """
        Get comprehensive stock fundamentals.

        Args:
            symbol: Stock symbol to analyze

        Returns:
            StockFundamentalsResponse with fundamental data
        """
        try:
            logger.info("Starting fundamentals analysis", symbol=symbol)

            self.symbol = symbol.upper()
            self.ticker_data = yf.Ticker(self.symbol)

            # Get basic info and price data
            info = self.ticker_data.info
            hist = self.ticker_data.history(period="5d")

            if hist.empty:
                raise ValueError(
                    f"'{symbol}' is not a valid stock symbol or the stock may be delisted. Please check the symbol and try again."
                )

            # Extract current price and changes
            current_price = float(hist["Close"].iloc[-1])
            if len(hist) >= 2:
                prev_close = float(hist["Close"].iloc[-2])
                price_change = current_price - prev_close
                price_change_percent = (price_change / prev_close) * 100
            else:
                price_change = 0.0
                price_change_percent = 0.0

            # Extract fundamental metrics with proper type conversion
            company_name = info.get("longName", symbol)

            # Safe numeric conversion functions
            def safe_float(value: float | None, default: float = 0.0) -> float:
                if value is None:
                    return default
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return default

            def safe_int(value: int | None, default: int = 0) -> int:
                if value is None:
                    return default
                try:
                    return int(
                        float(value)
                    )  # Convert via float first to handle string numbers
                except (ValueError, TypeError):
                    return default

            market_cap = safe_float(info.get("marketCap"), 0)
            volume = int(hist["Volume"].iloc[-1]) if not hist.empty else 0
            avg_volume = safe_int(info.get("averageVolume"), volume)

            # Valuation metrics - use None for missing data
            pe_ratio = (
                safe_float(info.get("trailingPE"))
                if info.get("trailingPE") is not None
                else None
            )
            pb_ratio = (
                safe_float(info.get("priceToBook"))
                if info.get("priceToBook") is not None
                else None
            )
            dividend_yield_raw = (
                safe_float(info.get("dividendYield"))
                if info.get("dividendYield") is not None
                else None
            )
            # yfinance returns dividendYield as decimal (0.025 for 2.5%), so convert to percentage
            # But handle edge cases where it might already be a percentage or invalid
            dividend_yield: float | None
            if dividend_yield_raw is not None and dividend_yield_raw > 0:
                # If value is > 1, assume it's already a percentage (yfinance inconsistency)
                if dividend_yield_raw > 1:
                    dividend_yield = dividend_yield_raw
                else:
                    dividend_yield = dividend_yield_raw * 100
                # Cap at reasonable max to reject bad data (max dividend yield typically < 20%)
                if dividend_yield > 25:
                    dividend_yield = None  # Reject unrealistic data
            else:
                dividend_yield = None

            # Risk metrics
            beta = (
                safe_float(info.get("beta")) if info.get("beta") is not None else None
            )

            # 52-week range
            fifty_two_week_high = safe_float(
                info.get("fiftyTwoWeekHigh"), current_price
            )
            fifty_two_week_low = safe_float(info.get("fiftyTwoWeekLow"), current_price)

            # Generate summary and insights
            fundamental_summary, key_metrics = self._generate_fundamental_insights(
                symbol,
                company_name,
                current_price,
                market_cap,
                pe_ratio,
                pb_ratio,
                dividend_yield,
                beta,
                fifty_two_week_high,
                fifty_two_week_low,
            )

            response = StockFundamentalsResponse(
                symbol=self.symbol,
                company_name=company_name,
                analysis_date=datetime.now().isoformat(),
                current_price=current_price,
                price_change=price_change,
                price_change_percent=price_change_percent,
                volume=volume,
                avg_volume=avg_volume,
                market_cap=market_cap,
                pe_ratio=pe_ratio,
                pb_ratio=pb_ratio,
                dividend_yield=dividend_yield,
                beta=beta,
                fifty_two_week_high=fifty_two_week_high,
                fifty_two_week_low=fifty_two_week_low,
                fundamental_summary=fundamental_summary,
                key_metrics=key_metrics,
            )

            logger.info("Fundamentals analysis completed", symbol=symbol)
            return response

        except Exception as e:
            logger.error("Fundamentals analysis failed", symbol=symbol, error=str(e))
            raise

    def _generate_fundamental_insights(
        self,
        symbol: str,
        company_name: str,
        current_price: float,
        market_cap: float,
        pe_ratio: float | None,
        pb_ratio: float | None,
        dividend_yield: float | None,
        beta: float | None,
        week_52_high: float,
        week_52_low: float,
    ) -> tuple[str, list[str]]:
        """Generate fundamental analysis insights."""

        # Calculate position in 52-week range
        price_range = week_52_high - week_52_low
        position_in_range = (
            ((current_price - week_52_low) / price_range * 100)
            if price_range > 0
            else 50
        )

        # Market cap classification
        if market_cap > 200_000_000_000:
            cap_class = "mega-cap"
        elif market_cap > 10_000_000_000:
            cap_class = "large-cap"
        elif market_cap > 2_000_000_000:
            cap_class = "mid-cap"
        elif market_cap > 300_000_000:
            cap_class = "small-cap"
        else:
            cap_class = "micro-cap"

        summary = (
            f"{symbol} is a {cap_class} stock trading at ${current_price:.2f}, "
            f"which is {position_in_range:.1f}% of its 52-week range. "
        )

        if market_cap > 0:
            summary += f"Market cap: ${market_cap/1e9:.1f}B. "

        key_metrics = [
            f"52-Week Range: ${week_52_low:.2f} - ${week_52_high:.2f}",
            f"Position in Range: {position_in_range:.1f}%",
            f"Market Cap Class: {cap_class.title()}",
        ]

        # Add valuation metrics if available
        if pe_ratio is not None and pe_ratio > 0:
            pe_interpretation = (
                "expensive"
                if pe_ratio > 25
                else "reasonable" if pe_ratio > 15 else "cheap"
            )
            key_metrics.append(f"P/E Ratio: {pe_ratio:.1f} ({pe_interpretation})")
            summary += (
                f"P/E ratio of {pe_ratio:.1f} suggests {pe_interpretation} valuation. "
            )

        if pb_ratio is not None and pb_ratio > 0:
            pb_interpretation = (
                "premium" if pb_ratio > 3 else "fair" if pb_ratio > 1 else "discount"
            )
            key_metrics.append(f"P/B Ratio: {pb_ratio:.1f} ({pb_interpretation})")

        if dividend_yield is not None and dividend_yield > 0:
            key_metrics.append(f"Dividend Yield: {dividend_yield:.1f}%")
            if dividend_yield > 4:
                summary += "High dividend yield suggests income focus. "

        if beta is not None:
            volatility = "high" if beta > 1.5 else "moderate" if beta > 0.5 else "low"
            key_metrics.append(f"Beta: {beta:.2f} ({volatility} volatility)")

        return summary, key_metrics
