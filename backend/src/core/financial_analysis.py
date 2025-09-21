"""
Core financial analysis logic ported from the CLI tool.
Designed to be callable by both API endpoints and future LangChain agents.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import structlog

from ..api.models import (
    FibonacciAnalysisResponse, MacroSentimentResponse, StockFundamentalsResponse,
    FibonacciLevel, MarketStructure, PricePoint
)

logger = structlog.get_logger()


class FibonacciAnalyzer:
    """Fibonacci retracement analysis engine."""

    # Standard Fibonacci levels
    FIBONACCI_LEVELS = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
    KEY_LEVELS = [0.382, 0.5, 0.618]  # Most important levels
    GOLDEN_RATIO = 0.618
    PRESSURE_ZONE_TOLERANCE = 0.025  # ±2.5% around 61.8%

    def __init__(self):
        self.data: Optional[pd.DataFrame] = None
        self.symbol: str = ""
        self.start_date: Optional[str] = None
        self.end_date: Optional[str] = None

    async def analyze(self, symbol: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> FibonacciAnalysisResponse:
        """
        Perform complete Fibonacci analysis on a stock symbol.

        Args:
            symbol: Stock symbol to analyze
            start_date: Start date for analysis (YYYY-MM-DD format)
            end_date: End date for analysis (YYYY-MM-DD format)

        Returns:
            FibonacciAnalysisResponse with complete analysis
        """
        try:
            logger.info("Starting Fibonacci analysis", symbol=symbol, start_date=start_date, end_date=end_date)

            self.symbol = symbol.upper()
            self.start_date = start_date
            self.end_date = end_date

            # Fetch stock data
            stock_data = await self._fetch_stock_data()
            if stock_data is None or stock_data.empty:
                raise ValueError(f"'{symbol}' is not a valid stock symbol or the stock may be delisted. Please check the symbol and try again.")

            self.data = stock_data

            # Perform market structure analysis
            market_structure = self._analyze_market_structure()

            # Calculate Fibonacci levels
            fibonacci_levels = self._calculate_fibonacci_levels(market_structure)

            # Get current price and analysis metrics
            current_price = float(stock_data['Close'].iloc[-1])
            confidence_score = self._calculate_confidence_score(market_structure, fibonacci_levels)

            # Generate insights and summary
            analysis_summary, key_insights = self._generate_analysis_insights(
                market_structure, fibonacci_levels, current_price
            )

            # Calculate pressure zone around Golden Ratio
            pressure_zone = self._calculate_pressure_zone(fibonacci_levels)

            # Prepare raw data for debugging/agent use
            raw_data = {
                "data_points": len(stock_data),
                "date_range": {
                    "start": stock_data.index[0].strftime("%Y-%m-%d"),
                    "end": stock_data.index[-1].strftime("%Y-%m-%d")
                },
                "price_range": {
                    "high": float(stock_data['High'].max()),
                    "low": float(stock_data['Low'].min())
                },
                "volume_avg": float(stock_data['Volume'].mean()),
                "calculation_method": "swing_point_detection"
            }

            response = FibonacciAnalysisResponse(
                symbol=self.symbol,
                start_date=self.start_date,
                end_date=self.end_date,
                current_price=current_price,
                analysis_date=datetime.now().isoformat(),
                fibonacci_levels=fibonacci_levels,
                market_structure=market_structure,
                confidence_score=confidence_score,
                pressure_zone=pressure_zone,
                trend_strength=self._assess_trend_strength(market_structure),
                analysis_summary=analysis_summary,
                key_insights=key_insights,
                raw_data=raw_data
            )

            logger.info("Fibonacci analysis completed",
                       symbol=symbol,
                       confidence=confidence_score,
                       trend=market_structure.trend_direction)

            return response

        except Exception as e:
            logger.error("Fibonacci analysis failed", symbol=symbol, error=str(e))
            raise

    async def _fetch_stock_data(self) -> Optional[pd.DataFrame]:
        """Fetch stock data using yfinance."""
        try:
            ticker = yf.Ticker(self.symbol)

            # Use date range if provided, otherwise default to 6 months
            if self.start_date and self.end_date:
                data = ticker.history(start=self.start_date, end=self.end_date)
            else:
                # Default to 6 months if no dates provided
                data = ticker.history(period="6mo")

            if data.empty:
                return None

            # Clean data
            data = data.dropna()
            return data

        except Exception as e:
            logger.error("Failed to fetch stock data", symbol=self.symbol, error=str(e))
            raise

    def _analyze_market_structure(self) -> MarketStructure:
        """Analyze market structure to identify swing points and trend."""
        if self.data is None:
            raise ValueError("No data available for market structure analysis")

        # Find significant swing points
        swing_high, swing_low = self._find_swing_points()

        # Determine trend direction
        trend_direction = self._determine_trend_direction(swing_high, swing_low)

        # Assess structure quality
        structure_quality = self._assess_structure_quality(swing_high, swing_low)

        # Determine market phase
        current_price = float(self.data['Close'].iloc[-1])
        phase = self._determine_market_phase(current_price, swing_high, swing_low)

        return MarketStructure(
            trend_direction=trend_direction,
            swing_high=PricePoint(
                price=swing_high['price'],
                date=swing_high['date'].strftime("%Y-%m-%d")
            ),
            swing_low=PricePoint(
                price=swing_low['price'],
                date=swing_low['date'].strftime("%Y-%m-%d")
            ),
            structure_quality=structure_quality,
            phase=phase
        )

    def _find_swing_points(self) -> Tuple[Dict, Dict]:
        """Find significant swing high and low points."""
        high_prices = self.data['High']
        low_prices = self.data['Low']

        # Use rolling windows to find local extremes
        window = max(5, len(self.data) // 20)  # Adaptive window size

        # Find swing high (highest high in recent period)
        swing_high_idx = high_prices.rolling(window=window, center=True).max().idxmax()
        swing_high = {
            'price': float(high_prices[swing_high_idx]),
            'date': swing_high_idx
        }

        # Find swing low (lowest low in recent period)
        swing_low_idx = low_prices.rolling(window=window, center=True).min().idxmin()
        swing_low = {
            'price': float(low_prices[swing_low_idx]),
            'date': swing_low_idx
        }

        # Ensure we have a meaningful range
        if swing_high['price'] <= swing_low['price']:
            # Fallback to period high/low
            swing_high = {
                'price': float(high_prices.max()),
                'date': high_prices.idxmax()
            }
            swing_low = {
                'price': float(low_prices.min()),
                'date': low_prices.idxmin()
            }

        return swing_high, swing_low

    def _determine_trend_direction(self, swing_high: Dict, swing_low: Dict) -> str:
        """Determine overall trend direction."""
        # Simple trend analysis based on recent price action
        recent_data = self.data.tail(20)  # Last 20 periods

        if len(recent_data) < 10:
            return "sideways"

        start_price = float(recent_data['Close'].iloc[0])
        end_price = float(recent_data['Close'].iloc[-1])
        price_change_pct = (end_price - start_price) / start_price * 100

        if price_change_pct > 2:
            return "uptrend"
        elif price_change_pct < -2:
            return "downtrend"
        else:
            return "sideways"

    def _assess_structure_quality(self, swing_high: Dict, swing_low: Dict) -> str:
        """Assess the quality of market structure."""
        price_range = swing_high['price'] - swing_low['price']
        current_price = float(self.data['Close'].iloc[-1])

        # Quality based on range significance and data points
        range_pct = price_range / current_price * 100
        data_length = len(self.data)

        if range_pct > 15 and data_length > 100:
            return "high"
        elif range_pct > 8 and data_length > 50:
            return "medium"
        else:
            return "low"

    def _determine_market_phase(self, current_price: float, swing_high: Dict, swing_low: Dict) -> str:
        """Determine current market phase."""
        price_range = swing_high['price'] - swing_low['price']
        position_in_range = (current_price - swing_low['price']) / price_range

        if position_in_range > 0.8:
            return "Near swing high - potential resistance"
        elif position_in_range < 0.2:
            return "Near swing low - potential support"
        elif 0.35 <= position_in_range <= 0.65:
            return "Middle range - watch for direction"
        else:
            return "In retracement zone"

    def _calculate_fibonacci_levels(self, market_structure: MarketStructure) -> List[FibonacciLevel]:
        """Calculate Fibonacci retracement levels."""
        high_price = market_structure.swing_high.price
        low_price = market_structure.swing_low.price
        price_range = high_price - low_price

        fibonacci_levels = []

        for level in self.FIBONACCI_LEVELS:
            # Calculate price at this Fibonacci level
            if market_structure.trend_direction == "downtrend":
                # For downtrends, calculate from high down
                fib_price = high_price - (price_range * level)
            else:
                # For uptrends, calculate from low up
                fib_price = low_price + (price_range * level)

            fibonacci_levels.append(FibonacciLevel(
                level=level,
                price=fib_price,
                percentage=f"{level * 100:.1f}%",
                is_key_level=level in self.KEY_LEVELS
            ))

        return fibonacci_levels

    def _calculate_confidence_score(self, market_structure: MarketStructure, fibonacci_levels: List[FibonacciLevel]) -> float:
        """Calculate confidence score for the analysis."""
        score = 0.5  # Base score

        # Adjust based on structure quality
        if market_structure.structure_quality == "high":
            score += 0.3
        elif market_structure.structure_quality == "medium":
            score += 0.1

        # Adjust based on data length
        if len(self.data) > 100:
            score += 0.1

        # Adjust based on price range significance
        current_price = float(self.data['Close'].iloc[-1])
        price_range = market_structure.swing_high.price - market_structure.swing_low.price
        range_pct = price_range / current_price * 100

        if range_pct > 20:
            score += 0.1

        return min(score, 1.0)

    def _calculate_pressure_zone(self, fibonacci_levels: List[FibonacciLevel]) -> Optional[Dict[str, float]]:
        """Calculate pressure zone around the Golden Ratio level."""
        golden_ratio_level = None

        for level in fibonacci_levels:
            if abs(level.level - self.GOLDEN_RATIO) < 0.001:  # Find 61.8% level
                golden_ratio_level = level
                break

        if golden_ratio_level is None:
            return None

        price_tolerance = golden_ratio_level.price * self.PRESSURE_ZONE_TOLERANCE

        return {
            "center_price": golden_ratio_level.price,
            "upper_bound": golden_ratio_level.price + price_tolerance,
            "lower_bound": golden_ratio_level.price - price_tolerance,
            "tolerance_percent": self.PRESSURE_ZONE_TOLERANCE * 100
        }

    def _assess_trend_strength(self, market_structure: MarketStructure) -> str:
        """Assess the strength of the current trend."""
        if market_structure.structure_quality == "high":
            return "Strong"
        elif market_structure.structure_quality == "medium":
            return "Moderate"
        else:
            return "Weak"

    def _generate_analysis_insights(self, market_structure: MarketStructure, fibonacci_levels: List[FibonacciLevel], current_price: float) -> Tuple[str, List[str]]:
        """Generate human-readable analysis summary and key insights."""

        # Find current price position relative to Fibonacci levels
        current_position = self._find_current_fib_position(fibonacci_levels, current_price)

        # Generate summary
        summary = (
            f"{self.symbol} is currently in a {market_structure.trend_direction} with {market_structure.structure_quality} "
            f"quality market structure. The stock is trading {current_position} and shows "
            f"{self._assess_trend_strength(market_structure).lower()} trend characteristics."
        )

        # Generate key insights
        key_insights = [
            f"Market Structure: {market_structure.structure_quality.title()} quality {market_structure.trend_direction}",
            f"Current Phase: {market_structure.phase}",
            f"Price Position: {current_position}",
            f"Swing High: ${market_structure.swing_high.price:.2f} ({market_structure.swing_high.date})",
            f"Swing Low: ${market_structure.swing_low.price:.2f} ({market_structure.swing_low.date})"
        ]

        # Add pressure zone insight if applicable
        golden_ratio_level = next((level for level in fibonacci_levels if level.level == self.GOLDEN_RATIO), None)
        if golden_ratio_level:
            distance_to_golden = abs(current_price - golden_ratio_level.price) / current_price * 100
            if distance_to_golden < 5:  # Within 5% of golden ratio
                key_insights.append(f"⚠️ Near Golden Ratio (61.8%) at ${golden_ratio_level.price:.2f} - key decision point")

        return summary, key_insights

    def _find_current_fib_position(self, fibonacci_levels: List[FibonacciLevel], current_price: float) -> str:
        """Determine where current price sits relative to Fibonacci levels."""
        sorted_levels = sorted(fibonacci_levels, key=lambda x: x.price)

        for i, level in enumerate(sorted_levels):
            if current_price <= level.price:
                if i == 0:
                    return f"below the {level.percentage} level at ${level.price:.2f}"
                else:
                    prev_level = sorted_levels[i-1]
                    return f"between {prev_level.percentage} (${prev_level.price:.2f}) and {level.percentage} (${level.price:.2f})"

        return f"above the {sorted_levels[-1].percentage} level at ${sorted_levels[-1].price:.2f}"


class MacroAnalyzer:
    """Macro market sentiment analysis engine."""

    # Major market indices
    MAJOR_INDICES = {
        "SPY": "S&P 500",
        "QQQ": "NASDAQ-100",
        "DIA": "Dow Jones",
        "IWM": "Russell 2000"
    }

    # Sector ETFs
    SECTOR_ETFS = {
        "XLK": "Technology",
        "XLF": "Financials",
        "XLV": "Healthcare",
        "XLE": "Energy",
        "XLI": "Industrials",
        "XLP": "Consumer Staples",
        "XLY": "Consumer Discretionary",
        "XLU": "Utilities",
        "XLB": "Materials",
        "XLRE": "Real Estate"
    }

    async def analyze(self) -> MacroSentimentResponse:
        """Perform macro market sentiment analysis."""
        try:
            logger.info("Starting macro sentiment analysis")

            # Get VIX data
            vix_data = await self._get_vix_data()

            # Analyze major indices
            indices_performance = await self._analyze_major_indices()

            # Analyze sector rotation
            sector_performance = await self._analyze_sector_performance()

            # Calculate overall sentiment
            fear_greed_score = self._calculate_fear_greed_score(vix_data, indices_performance)
            market_sentiment = self._determine_market_sentiment(fear_greed_score)

            # Generate insights
            sentiment_summary, key_factors = self._generate_sentiment_insights(
                vix_data, market_sentiment, indices_performance, sector_performance
            )

            response = MacroSentimentResponse(
                analysis_date=datetime.now().isoformat(),
                vix_level=vix_data["current_level"],
                vix_interpretation=vix_data["interpretation"],
                fear_greed_score=fear_greed_score,
                major_indices=indices_performance,
                sector_performance=sector_performance,
                market_sentiment=market_sentiment,
                confidence_level=0.8,  # Fixed confidence for now
                sentiment_summary=sentiment_summary,
                market_outlook=self._generate_market_outlook(market_sentiment, vix_data),
                key_factors=key_factors
            )

            logger.info("Macro sentiment analysis completed", sentiment=market_sentiment, vix=vix_data["current_level"])
            return response

        except Exception as e:
            logger.error("Macro sentiment analysis failed", error=str(e))
            raise

    async def _get_vix_data(self) -> Dict[str, Any]:
        """Get VIX fear index data."""
        try:
            vix = yf.Ticker("^VIX")
            data = vix.history(period="5d")

            if data.empty:
                # Fallback values if VIX data unavailable
                return {
                    "current_level": 20.0,
                    "interpretation": "Moderate fear (estimated)"
                }

            current_vix = float(data['Close'].iloc[-1])

            # VIX interpretation
            if current_vix < 15:
                interpretation = "Low fear - Complacent market"
            elif current_vix < 20:
                interpretation = "Moderate fear - Normal market"
            elif current_vix < 30:
                interpretation = "Elevated fear - Cautious market"
            else:
                interpretation = "High fear - Stressed market"

            return {
                "current_level": current_vix,
                "interpretation": interpretation
            }

        except Exception as e:
            logger.warning("Failed to fetch VIX data", error=str(e))
            return {
                "current_level": 20.0,
                "interpretation": "Moderate fear (estimated)"
            }

    async def _analyze_major_indices(self) -> Dict[str, float]:
        """Analyze performance of major market indices."""
        performance = {}

        for symbol, name in self.MAJOR_INDICES.items():
            try:
                ticker = yf.Ticker(symbol)
                data = ticker.history(period="5d")

                if not data.empty and len(data) >= 2:
                    current_price = float(data['Close'].iloc[-1])
                    prev_price = float(data['Close'].iloc[-2])
                    change_pct = (current_price - prev_price) / prev_price * 100
                    performance[name] = round(change_pct, 2)
                else:
                    performance[name] = 0.0

            except Exception as e:
                logger.warning(f"Failed to fetch data for {symbol}", error=str(e))
                performance[name] = 0.0

        return performance

    async def _analyze_sector_performance(self) -> Dict[str, float]:
        """Analyze sector rotation through ETF performance."""
        performance = {}

        for symbol, sector in self.SECTOR_ETFS.items():
            try:
                ticker = yf.Ticker(symbol)
                data = ticker.history(period="5d")

                if not data.empty and len(data) >= 2:
                    current_price = float(data['Close'].iloc[-1])
                    prev_price = float(data['Close'].iloc[-2])
                    change_pct = (current_price - prev_price) / prev_price * 100
                    performance[sector] = round(change_pct, 2)
                else:
                    performance[sector] = 0.0

            except Exception as e:
                logger.warning(f"Failed to fetch data for {symbol}", error=str(e))
                performance[sector] = 0.0

        return performance

    def _calculate_fear_greed_score(self, vix_data: Dict, indices_performance: Dict[str, float]) -> int:
        """Calculate fear/greed score (0-100)."""
        score = 50  # Neutral starting point

        # VIX component (40% weight)
        vix_level = vix_data["current_level"]
        if vix_level < 15:
            score += 20  # Low VIX = Greed
        elif vix_level > 30:
            score -= 20  # High VIX = Fear
        elif vix_level > 25:
            score -= 10

        # Market performance component (60% weight)
        avg_performance = sum(indices_performance.values()) / len(indices_performance)
        if avg_performance > 1:
            score += 30
        elif avg_performance > 0.5:
            score += 15
        elif avg_performance < -1:
            score -= 30
        elif avg_performance < -0.5:
            score -= 15

        return max(0, min(100, score))

    def _determine_market_sentiment(self, fear_greed_score: int) -> str:
        """Determine overall market sentiment from fear/greed score."""
        if fear_greed_score <= 30:
            return "fearful"
        elif fear_greed_score >= 70:
            return "greedy"
        else:
            return "neutral"

    def _generate_sentiment_insights(self, vix_data: Dict, sentiment: str, indices: Dict, sectors: Dict) -> Tuple[str, List[str]]:
        """Generate sentiment summary and key factors."""

        summary = (
            f"Market sentiment is currently {sentiment} with VIX at {vix_data['current_level']:.1f}. "
            f"{vix_data['interpretation']}. "
        )

        # Add market performance context
        avg_index_performance = sum(indices.values()) / len(indices)
        if avg_index_performance > 0:
            summary += f"Major indices are up an average of {avg_index_performance:.1f}%."
        else:
            summary += f"Major indices are down an average of {abs(avg_index_performance):.1f}%."

        # Key factors
        key_factors = [
            f"VIX Level: {vix_data['current_level']:.1f} ({vix_data['interpretation']})"
        ]

        # Best and worst performing indices
        if indices:
            best_index = max(indices.items(), key=lambda x: x[1])
            worst_index = min(indices.items(), key=lambda x: x[1])
            key_factors.extend([
                f"Best Index: {best_index[0]} (+{best_index[1]:.1f}%)",
                f"Worst Index: {worst_index[0]} ({worst_index[1]:+.1f}%)"
            ])

        # Best and worst performing sectors
        if sectors:
            best_sector = max(sectors.items(), key=lambda x: x[1])
            worst_sector = min(sectors.items(), key=lambda x: x[1])
            key_factors.extend([
                f"Leading Sector: {best_sector[0]} (+{best_sector[1]:.1f}%)",
                f"Lagging Sector: {worst_sector[0]} ({worst_sector[1]:+.1f}%)"
            ])

        return summary, key_factors

    def _generate_market_outlook(self, sentiment: str, vix_data: Dict) -> str:
        """Generate short-term market outlook."""
        if sentiment == "fearful":
            if vix_data["current_level"] > 30:
                return "High volatility expected. Look for oversold bounce opportunities."
            else:
                return "Cautious sentiment prevails. Defensive positioning recommended."
        elif sentiment == "greedy":
            return "Bullish sentiment strong but watch for overextension. Consider profit-taking."
        else:
            return "Neutral sentiment. Market direction unclear - wait for clearer signals."


class StockAnalyzer:
    """Stock fundamentals and company information analyzer."""

    async def analyze(self, symbol: str) -> StockFundamentalsResponse:
        """Analyze stock fundamentals and company information."""
        try:
            logger.info("Starting stock fundamentals analysis", symbol=symbol)

            symbol = symbol.upper()
            ticker = yf.Ticker(symbol)

            # Get stock info and recent data
            info = ticker.info
            hist_data = ticker.history(period="2d")

            if hist_data.empty:
                raise ValueError(f"No data available for symbol {symbol}")

            # Current price data
            current_price = float(hist_data['Close'].iloc[-1])
            prev_price = float(hist_data['Close'].iloc[-2]) if len(hist_data) >= 2 else current_price
            price_change = current_price - prev_price
            price_change_percent = (price_change / prev_price * 100) if prev_price != 0 else 0

            # Extract fundamental data with safe defaults
            company_name = info.get('longName', symbol)
            volume = int(hist_data['Volume'].iloc[-1])
            avg_volume = info.get('averageVolume', volume)
            market_cap = info.get('marketCap', 0)

            # Valuation metrics (may not be available for all stocks)
            pe_ratio = info.get('trailingPE')
            pb_ratio = info.get('priceToBook')
            dividend_yield = info.get('dividendYield')
            if dividend_yield:
                dividend_yield = dividend_yield * 100  # Convert to percentage

            # Risk metrics
            beta = info.get('beta')
            fifty_two_week_high = info.get('fiftyTwoWeekHigh', current_price)
            fifty_two_week_low = info.get('fiftyTwoWeekLow', current_price)

            # Generate analysis summary
            fundamental_summary, key_metrics = self._generate_fundamental_insights(
                symbol, current_price, market_cap, pe_ratio, pb_ratio,
                dividend_yield, beta, fifty_two_week_high, fifty_two_week_low
            )

            response = StockFundamentalsResponse(
                symbol=symbol,
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
                key_metrics=key_metrics
            )

            logger.info("Stock fundamentals analysis completed", symbol=symbol)
            return response

        except Exception as e:
            logger.error("Stock fundamentals analysis failed", symbol=symbol, error=str(e))
            raise

    def _generate_fundamental_insights(self, symbol: str, current_price: float, market_cap: float,
                                     pe_ratio: Optional[float], pb_ratio: Optional[float],
                                     dividend_yield: Optional[float], beta: Optional[float],
                                     week_52_high: float, week_52_low: float) -> Tuple[str, List[str]]:
        """Generate fundamental analysis insights."""

        # Position within 52-week range
        price_range = week_52_high - week_52_low
        position_in_range = ((current_price - week_52_low) / price_range * 100) if price_range > 0 else 50

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
            f"Market Cap Class: {cap_class.title()}"
        ]

        # Add valuation metrics if available
        if pe_ratio is not None and pe_ratio > 0:
            pe_interpretation = "expensive" if pe_ratio > 25 else "reasonable" if pe_ratio > 15 else "cheap"
            key_metrics.append(f"P/E Ratio: {pe_ratio:.1f} ({pe_interpretation})")
            summary += f"P/E ratio of {pe_ratio:.1f} suggests {pe_interpretation} valuation. "

        if pb_ratio is not None and pb_ratio > 0:
            pb_interpretation = "premium" if pb_ratio > 3 else "fair" if pb_ratio > 1 else "discount"
            key_metrics.append(f"P/B Ratio: {pb_ratio:.1f} ({pb_interpretation})")

        if dividend_yield is not None and dividend_yield > 0:
            key_metrics.append(f"Dividend Yield: {dividend_yield:.1f}%")
            if dividend_yield > 4:
                summary += "High dividend yield suggests income focus. "

        if beta is not None:
            volatility = "high" if beta > 1.5 else "moderate" if beta > 0.5 else "low"
            key_metrics.append(f"Beta: {beta:.2f} ({volatility} volatility)")

        return summary, key_metrics


class MacroAnalyzer:
    """Macro market sentiment analyzer."""

    def __init__(self):
        self.vix_data: Optional[pd.DataFrame] = None
        self.indices_data: Dict[str, pd.DataFrame] = {}
        self.sectors_data: Dict[str, pd.DataFrame] = {}

    async def analyze(self, include_sectors: bool = True, include_indices: bool = True) -> MacroSentimentResponse:
        """
        Analyze macro market sentiment.

        Args:
            include_sectors: Include sector rotation analysis
            include_indices: Include major indices analysis

        Returns:
            MacroSentimentResponse with complete sentiment analysis
        """
        try:
            logger.info("Starting macro sentiment analysis")

            # Get VIX data for fear/greed analysis
            vix_level, vix_interpretation, fear_greed_score = await self._analyze_vix()

            # Get major indices performance
            major_indices = {}
            if include_indices:
                major_indices = await self._analyze_major_indices()

            # Get sector performance
            sector_performance = {}
            if include_sectors:
                sector_performance = await self._analyze_sector_performance()

            # Overall sentiment assessment
            market_sentiment = self._assess_overall_sentiment(fear_greed_score, major_indices)
            confidence_level = self._calculate_confidence(vix_level, major_indices, sector_performance)

            # Generate insights
            sentiment_summary, market_outlook, key_factors = self._generate_macro_insights(
                vix_level, vix_interpretation, major_indices, sector_performance
            )

            response = MacroSentimentResponse(
                analysis_date=datetime.now().isoformat(),
                vix_level=vix_level,
                vix_interpretation=vix_interpretation,
                fear_greed_score=fear_greed_score,
                major_indices=major_indices,
                sector_performance=sector_performance,
                market_sentiment=market_sentiment,
                confidence_level=confidence_level,
                sentiment_summary=sentiment_summary,
                market_outlook=market_outlook,
                key_factors=key_factors
            )

            logger.info("Macro sentiment analysis completed", sentiment=market_sentiment)
            return response

        except Exception as e:
            logger.error("Macro sentiment analysis failed", error=str(e))
            raise

    async def _analyze_vix(self) -> Tuple[float, str, int]:
        """Analyze VIX for fear/greed sentiment."""
        try:
            vix_ticker = yf.Ticker("^VIX")
            vix_data = vix_ticker.history(period="5d")

            if vix_data.empty:
                # Fallback values if VIX data unavailable
                return 20.0, "neutral", 50

            current_vix = float(vix_data['Close'].iloc[-1])

            # VIX interpretation
            if current_vix > 30:
                interpretation = "fearful"
                fear_greed_score = max(0, 50 - int((current_vix - 30) * 2))
            elif current_vix < 15:
                interpretation = "greedy"
                fear_greed_score = min(100, 50 + int((15 - current_vix) * 3))
            else:
                interpretation = "neutral"
                fear_greed_score = 50

            return current_vix, interpretation, fear_greed_score

        except Exception as e:
            logger.warning("Failed to fetch VIX data", error=str(e))
            return 20.0, "neutral", 50

    async def _analyze_major_indices(self) -> Dict[str, float]:
        """Analyze major market indices performance."""
        indices = {
            "S&P 500": "^GSPC",
            "NASDAQ": "^IXIC",
            "DOW": "^DJI",
            "Russell 2000": "^RUT"
        }

        performance = {}
        for name, symbol in indices.items():
            try:
                ticker = yf.Ticker(symbol)
                data = ticker.history(period="5d")

                if not data.empty and len(data) >= 2:
                    change = ((data['Close'].iloc[-1] - data['Close'].iloc[-2]) / data['Close'].iloc[-2]) * 100
                    performance[name] = float(change)
                else:
                    performance[name] = 0.0

            except Exception as e:
                logger.warning(f"Failed to fetch {name} data", error=str(e))
                performance[name] = 0.0

        return performance

    async def _analyze_sector_performance(self) -> Dict[str, float]:
        """Analyze sector ETF performance."""
        sectors = {
            "Technology": "XLK",
            "Healthcare": "XLV",
            "Financial": "XLF",
            "Energy": "XLE",
            "Consumer Discretionary": "XLY",
            "Industrials": "XLI",
            "Communication": "XLC",
            "Consumer Staples": "XLP",
            "Utilities": "XLU",
            "Real Estate": "XLRE"
        }

        performance = {}
        for name, symbol in sectors.items():
            try:
                ticker = yf.Ticker(symbol)
                data = ticker.history(period="5d")

                if not data.empty and len(data) >= 2:
                    change = ((data['Close'].iloc[-1] - data['Close'].iloc[-2]) / data['Close'].iloc[-2]) * 100
                    performance[name] = float(change)
                else:
                    performance[name] = 0.0

            except Exception as e:
                logger.warning(f"Failed to fetch {name} sector data", error=str(e))
                performance[name] = 0.0

        return performance

    def _assess_overall_sentiment(self, fear_greed_score: int, major_indices: Dict[str, float]) -> str:
        """Assess overall market sentiment."""
        # Weight fear/greed score and market performance
        if major_indices:
            avg_performance = sum(major_indices.values()) / len(major_indices)
            if avg_performance > 1.0 and fear_greed_score > 60:
                return "greedy"
            elif avg_performance < -1.0 and fear_greed_score < 40:
                return "fearful"
            else:
                return "neutral"
        else:
            # Fallback to VIX-only assessment
            if fear_greed_score > 60:
                return "greedy"
            elif fear_greed_score < 40:
                return "fearful"
            else:
                return "neutral"

    def _calculate_confidence(self, vix_level: float, major_indices: Dict[str, float],
                             sector_performance: Dict[str, float]) -> float:
        """Calculate confidence in sentiment analysis."""
        data_quality = 0.7  # Base confidence

        # Boost confidence if we have good data coverage
        if major_indices and len(major_indices) > 3:
            data_quality += 0.1
        if sector_performance and len(sector_performance) > 5:
            data_quality += 0.1

        # Reduce confidence for extreme VIX readings (potential data issues)
        if vix_level > 50 or vix_level < 10:
            data_quality -= 0.2

        return min(1.0, max(0.0, data_quality))

    def _generate_macro_insights(self, vix_level: float, vix_interpretation: str,
                                major_indices: Dict[str, float],
                                sector_performance: Dict[str, float]) -> Tuple[str, str, List[str]]:
        """Generate human-readable macro insights."""

        # Sentiment summary
        sentiment_summary = f"Market sentiment is currently {vix_interpretation} with VIX at {vix_level:.1f}. "

        if major_indices:
            avg_performance = sum(major_indices.values()) / len(major_indices)
            if avg_performance > 0:
                sentiment_summary += f"Major indices are up an average of {avg_performance:.1f}% today."
            else:
                sentiment_summary += f"Major indices are down an average of {abs(avg_performance):.1f}% today."

        # Market outlook
        if vix_level > 25:
            outlook = "Elevated volatility suggests caution is warranted in the near term."
        elif vix_level < 15:
            outlook = "Low volatility environment may indicate complacency or strong confidence."
        else:
            outlook = "Moderate volatility suggests balanced market conditions."

        # Key factors
        key_factors = [
            f"VIX at {vix_level:.1f} indicates {vix_interpretation} sentiment",
        ]

        if major_indices:
            best_index = max(major_indices.items(), key=lambda x: x[1])
            worst_index = min(major_indices.items(), key=lambda x: x[1])
            key_factors.extend([
                f"Best performing index: {best_index[0]} ({best_index[1]:+.1f}%)",
                f"Worst performing index: {worst_index[0]} ({worst_index[1]:+.1f}%)"
            ])

        if sector_performance:
            sector_items = list(sector_performance.items())
            if sector_items:
                best_sector = max(sector_items, key=lambda x: x[1])
                key_factors.append(f"Leading sector: {best_sector[0]} ({best_sector[1]:+.1f}%)")

        return sentiment_summary, outlook, key_factors


class StockAnalyzer:
    """Stock fundamentals and analysis engine."""

    def __init__(self):
        self.ticker_data: Optional[yf.Ticker] = None
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
                raise ValueError(f"'{symbol}' is not a valid stock symbol or the stock may be delisted. Please check the symbol and try again.")

            # Extract current price and changes
            current_price = float(hist['Close'].iloc[-1])
            if len(hist) >= 2:
                prev_close = float(hist['Close'].iloc[-2])
                price_change = current_price - prev_close
                price_change_percent = (price_change / prev_close) * 100
            else:
                price_change = 0.0
                price_change_percent = 0.0

            # Extract fundamental metrics with proper type conversion
            company_name = info.get('longName', symbol)

            # Safe numeric conversion function
            def safe_float(value, default=0.0):
                if value is None:
                    return default
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return default

            def safe_int(value, default=0):
                if value is None:
                    return default
                try:
                    return int(float(value))  # Convert via float first to handle string numbers
                except (ValueError, TypeError):
                    return default

            market_cap = safe_float(info.get('marketCap'), 0)
            volume = int(hist['Volume'].iloc[-1]) if not hist.empty else 0
            avg_volume = safe_int(info.get('averageVolume'), volume)

            # Valuation metrics - use None for missing data
            pe_ratio = safe_float(info.get('trailingPE')) if info.get('trailingPE') is not None else None
            pb_ratio = safe_float(info.get('priceToBook')) if info.get('priceToBook') is not None else None
            dividend_yield_raw = safe_float(info.get('dividendYield')) if info.get('dividendYield') is not None else None
            dividend_yield = (dividend_yield_raw * 100) if dividend_yield_raw and dividend_yield_raw > 0 else None

            # Risk metrics
            beta = safe_float(info.get('beta')) if info.get('beta') is not None else None

            # 52-week range
            fifty_two_week_high = safe_float(info.get('fiftyTwoWeekHigh'), current_price)
            fifty_two_week_low = safe_float(info.get('fiftyTwoWeekLow'), current_price)

            # Generate summary and insights
            fundamental_summary, key_metrics = self._generate_fundamental_insights(
                symbol, company_name, current_price, market_cap, pe_ratio, pb_ratio,
                dividend_yield, beta, fifty_two_week_high, fifty_two_week_low
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
                key_metrics=key_metrics
            )

            logger.info("Fundamentals analysis completed", symbol=symbol)
            return response

        except Exception as e:
            logger.error("Fundamentals analysis failed", symbol=symbol, error=str(e))
            raise

    def _generate_fundamental_insights(self, symbol: str, company_name: str, current_price: float,
                                     market_cap: float, pe_ratio: Optional[float],
                                     pb_ratio: Optional[float], dividend_yield: Optional[float],
                                     beta: Optional[float], week_52_high: float,
                                     week_52_low: float) -> Tuple[str, List[str]]:
        """Generate fundamental analysis insights."""

        # Calculate position in 52-week range
        price_range = week_52_high - week_52_low
        position_in_range = ((current_price - week_52_low) / price_range * 100) if price_range > 0 else 50

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
            f"Market Cap Class: {cap_class.title()}"
        ]

        # Add valuation metrics if available
        if pe_ratio is not None and pe_ratio > 0:
            pe_interpretation = "expensive" if pe_ratio > 25 else "reasonable" if pe_ratio > 15 else "cheap"
            key_metrics.append(f"P/E Ratio: {pe_ratio:.1f} ({pe_interpretation})")
            summary += f"P/E ratio of {pe_ratio:.1f} suggests {pe_interpretation} valuation. "

        if pb_ratio is not None and pb_ratio > 0:
            pb_interpretation = "premium" if pb_ratio > 3 else "fair" if pb_ratio > 1 else "discount"
            key_metrics.append(f"P/B Ratio: {pb_ratio:.1f} ({pb_interpretation})")

        if dividend_yield is not None and dividend_yield > 0:
            key_metrics.append(f"Dividend Yield: {dividend_yield:.1f}%")
            if dividend_yield > 4:
                summary += "High dividend yield suggests income focus. "

        if beta is not None:
            volatility = "high" if beta > 1.5 else "moderate" if beta > 0.5 else "low"
            key_metrics.append(f"Beta: {beta:.2f} ({volatility} volatility)")

        return summary, key_metrics