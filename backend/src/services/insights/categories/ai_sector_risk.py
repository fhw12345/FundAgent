"""AI Sector Risk category implementation.

This category measures AI sector bubble risk using 6 quantitative
indicators from Alpha Vantage data. The composite index provides
an overall risk assessment for AI-related investments.

Metrics:
1. AI Price Anomaly - Z-score of AI stocks vs 200 SMA
2. News Sentiment - Normalized sentiment from NEWS_SENTIMENT
3. Smart Money Flow - Smart Money Index (Last Hour - First Hour returns)
4. IPO Heat - IPO count in 90-day window
5. Yield Curve - 10Y-2Y spread analysis
6. Fed Expectations - 2Y yield slope

Interpretation Zones:
- 0-25: Low risk / Accumulation zone (Green)
- 25-50: Normal bull market (Blue)
- 50-75: Elevated / Caution (Yellow)
- 75-100: High risk / Euphoria (Red)
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
import structlog

from ..base import InsightCategoryBase
from ..models import InsightMetric, MetricExplanation, MetricStatus, ThresholdConfig
from ..registry import register_category

logger = structlog.get_logger()

# ETF used for dynamic AI basket (Global X Artificial Intelligence & Technology ETF)
AI_ETF_SYMBOL = "AIQ"

# Fallback symbols if ETF fetch fails
AI_BASKET_FALLBACK = ["NVDA", "MSFT", "AMD", "PLTR", "GOOGL", "META"]

# Number of top holdings to use from ETF
AI_BASKET_TOP_N = 10

# Cache key for ETF-derived basket
AI_BASKET_CACHE_KEY = "insights:ai_basket_symbols"
AI_BASKET_CACHE_TTL = 86400  # 24 hours (ETF holdings change infrequently)


@register_category
class AISectorRiskCategory(InsightCategoryBase):
    """AI Sector Risk assessment category.

    Measures bubble risk in the AI sector using 6 quantitative
    indicators with weighted composite scoring.
    """

    CATEGORY_ID = "ai_sector_risk"
    CATEGORY_NAME = "AI Sector Risk"
    CATEGORY_ICON = "🎯"
    CATEGORY_DESCRIPTION = (
        "Measures bubble risk in the AI sector using price anomalies, "
        "sentiment, smart money flow, IPO activity, and yield curve signals. "
        "Higher scores indicate elevated euphoria and potential correction risk."
    )

    # Cache for 30 minutes (metrics change slowly)
    CACHE_TTL_SECONDS = 1800

    def get_metric_definitions(self) -> list[dict[str, Any]]:
        """Return metric definitions for AI Sector Risk."""
        return [
            {
                "id": "ai_price_anomaly",
                "name": "AI Price Anomaly",
                "weight": 0.20,
                "data_sources": ["TIME_SERIES_DAILY"],
                "description": "Z-score of AI stocks vs 200-day SMA",
            },
            {
                "id": "news_sentiment",
                "name": "News Sentiment",
                "weight": 0.20,
                "data_sources": ["NEWS_SENTIMENT"],
                "description": "Normalized AI news sentiment (-0.35 to +0.35 → 0-100)",
            },
            {
                "id": "smart_money_flow",
                "name": "Smart Money Flow",
                "weight": 0.20,
                "data_sources": ["TIME_SERIES_INTRADAY"],
                "description": "Smart Money Index: Last hour return minus first hour return",
            },
            {
                "id": "ipo_heat",
                "name": "IPO Heat",
                "weight": 0.10,
                "data_sources": ["IPO_CALENDAR"],
                "description": "Count of tech IPOs in next 90 days",
            },
            {
                "id": "yield_curve",
                "name": "Yield Curve",
                "weight": 0.15,
                "data_sources": ["TREASURY_YIELD"],
                "description": "10Y-2Y spread (loose money indicator)",
            },
            {
                "id": "fed_expectations",
                "name": "Fed Expectations",
                "weight": 0.15,
                "data_sources": ["TREASURY_YIELD"],
                "description": "2Y yield slope over 20 days",
            },
        ]

    def get_composite_weights(self) -> dict[str, float]:
        """Return weights for composite score calculation."""
        return {
            "ai_price_anomaly": 0.20,
            "news_sentiment": 0.20,
            "smart_money_flow": 0.20,
            "ipo_heat": 0.10,
            "yield_curve": 0.15,
            "fed_expectations": 0.15,
        }

    async def _get_ai_basket_symbols(self) -> tuple[list[str], str]:
        """Get AI basket symbols dynamically from AIQ ETF holdings.

        Fetches top holdings from the Global X AI & Technology ETF (AIQ)
        and filters for valid US-traded symbols. Results are cached for
        24 hours since ETF holdings change infrequently.

        Returns:
            Tuple of (symbols list, source description)
        """
        # Check cache first
        if self.redis_cache:
            cached = await self.redis_cache.get(AI_BASKET_CACHE_KEY)
            if cached and isinstance(cached, list):
                logger.info(
                    "AI basket cache HIT",
                    symbols=cached,
                    source="cache",
                )
                return cached, f"AIQ ETF top {len(cached)} holdings (cached)"

        # Fetch from ETF if market service available
        if self.market_service:
            try:
                etf_data = await self.market_service.get_etf_profile(AI_ETF_SYMBOL)
                holdings = etf_data.get("holdings", [])

                # Filter for valid US symbols (exclude "n/a" and non-US)
                valid_symbols = []
                for holding in holdings:
                    symbol = holding.get("symbol", "")
                    weight = float(holding.get("weight", 0))

                    # Skip invalid symbols and very small positions
                    if symbol and symbol != "n/a" and weight >= 0.01:
                        valid_symbols.append(symbol)

                    # Stop when we have enough
                    if len(valid_symbols) >= AI_BASKET_TOP_N:
                        break

                if valid_symbols:
                    # Cache the result
                    if self.redis_cache:
                        await self.redis_cache.set(
                            AI_BASKET_CACHE_KEY,
                            valid_symbols,
                            ttl_seconds=AI_BASKET_CACHE_TTL,
                        )

                    logger.info(
                        "AI basket fetched from ETF",
                        etf=AI_ETF_SYMBOL,
                        symbols=valid_symbols,
                        total_holdings=len(holdings),
                    )
                    return valid_symbols, f"AIQ ETF top {len(valid_symbols)} holdings"

            except Exception as e:
                logger.warning(
                    "ETF basket fetch failed, using fallback",
                    etf=AI_ETF_SYMBOL,
                    error=str(e),
                )

        # Fallback to static symbols
        logger.info(
            "Using fallback AI basket",
            symbols=AI_BASKET_FALLBACK,
            reason="ETF fetch unavailable",
        )
        return AI_BASKET_FALLBACK, "Static fallback basket"

    async def calculate_metrics(self) -> list[InsightMetric]:
        """Calculate all 6 AI Sector Risk metrics.

        This method orchestrates the calculation of all metrics,
        handling partial failures gracefully. The AI basket is fetched
        once and reused across all metrics that need it.
        """
        logger.info("Calculating AI Sector Risk metrics")

        # Fetch AI basket once for all metrics that need it
        ai_symbols, basket_source = await self._get_ai_basket_symbols()
        ai_basket = (ai_symbols, basket_source)

        metrics = []

        # Calculate each metric with error handling
        # Metrics that use AI basket receive it as parameter
        metric_calculators: list[tuple[str, Any]] = [
            ("ai_price_anomaly", lambda: self._calculate_ai_price_anomaly(ai_basket)),
            ("news_sentiment", self._calculate_news_sentiment),  # Uses topics=technology
            ("smart_money_flow", lambda: self._calculate_smart_money_flow(ai_basket)),
            ("ipo_heat", self._calculate_ipo_heat),
            ("yield_curve", self._calculate_yield_curve),
            ("fed_expectations", self._calculate_fed_expectations),
        ]

        for metric_id, calculator in metric_calculators:
            try:
                metric = await calculator()
                metrics.append(metric)
            except Exception as e:
                logger.error(
                    "Metric calculation failed",
                    metric_id=metric_id,
                    error=str(e),
                )
                # Add placeholder metric for failed calculation
                metrics.append(self._create_error_metric(metric_id))

        logger.info(
            "AI Sector Risk metrics calculated",
            metric_count=len(metrics),
            successful=len([m for m in metrics if m.score >= 0]),
        )

        return metrics

    async def _calculate_ai_price_anomaly(
        self, ai_basket: tuple[list[str], str]
    ) -> InsightMetric:
        """Calculate AI Price Anomaly metric using real market data.

        Z-score of AI basket (dynamically sourced from AIQ ETF) vs 200-day SMA.
        Higher Z-score = higher risk of correction.

        Args:
            ai_basket: Tuple of (symbols list, source description) from AIQ ETF
        """
        if not self.market_service:
            return self._create_placeholder_metric(
                "ai_price_anomaly",
                "AI Price Anomaly",
                65.0,
                "Market service not available",
            )

        # Use pre-fetched AI basket
        ai_symbols, basket_source = ai_basket

        z_scores = []
        symbol_data = {}

        for symbol in ai_symbols:
            try:
                # Get daily bars (need 200+ days for SMA calculation)
                df = await self.market_service.get_daily_bars(
                    symbol=symbol,
                    outputsize="full",
                )

                if df is not None and len(df) >= 200:
                    # Calculate 200-day SMA and Z-score
                    close_prices = df["Close"].values
                    current_price = close_prices[-1]
                    sma_200 = np.mean(close_prices[-200:])
                    std_200 = np.std(close_prices[-200:])

                    if std_200 > 0:
                        z_score = (current_price - sma_200) / std_200
                        z_scores.append(z_score)
                        symbol_data[symbol] = {
                            "current": round(current_price, 2),
                            "sma_200": round(sma_200, 2),
                            "z_score": round(z_score, 2),
                        }

            except Exception as e:
                logger.warning(
                    "Failed to get data for symbol",
                    symbol=symbol,
                    error=str(e),
                )

        # Calculate average Z-score and normalize to 0-100
        if z_scores:
            avg_z_score = np.mean(z_scores)
            # Z-score of -2 to +3 maps to 0-100
            score = self.normalize_score(avg_z_score, -2.0, 3.0)
        else:
            score = 50.0
            avg_z_score = 0.0

        status = ThresholdConfig().get_status(score)

        return InsightMetric(
            id="ai_price_anomaly",
            name="AI Price Anomaly",
            score=score,
            status=status,
            explanation=MetricExplanation(
                summary=f"AI stocks are trading {avg_z_score:.1f} standard deviations from average.",
                detail=(
                    f"The AI basket ({', '.join(ai_symbols[:5])}"
                    f"{', ...' if len(ai_symbols) > 5 else ''}) is trading "
                    f"{avg_z_score:.2f} standard deviations {'above' if avg_z_score > 0 else 'below'} "
                    "the 200-day moving average. "
                    f"{'Elevated positioning suggests caution.' if score > 60 else 'Normal range.'}"
                ),
                methodology=(
                    f"Dynamically sources AI stocks from {AI_ETF_SYMBOL} ETF holdings. "
                    "Calculates the Z-score of the equal-weighted AI basket price "
                    "relative to its 200-day simple moving average. Higher Z-scores "
                    "indicate prices extended above historical norms."
                ),
                formula="Z = (P - SMA200) / σ200",
                historical_context=(
                    "Z-scores above 2.0 have historically preceded significant corrections. "
                    f"Current average Z-score: {avg_z_score:.2f}"
                ),
                actionable_insight=(
                    "Consider trimming AI positions if score exceeds 75. "
                    if score > 60
                    else "Current level is within normal range."
                ),
            ),
            data_sources=["TIME_SERIES_DAILY", "ETF_PROFILE"],
            last_updated=datetime.now(UTC),
            raw_data={
                "symbols": ai_symbols,
                "basket_source": basket_source,
                "avg_z_score": round(avg_z_score, 3),
                "symbol_data": symbol_data,
            },
        )

    async def _calculate_news_sentiment(self) -> InsightMetric:
        """Calculate News Sentiment metric using Alpha Vantage NEWS_SENTIMENT.

        Uses topics=technology for broad tech/AI sector sentiment coverage.
        Single API call for efficiency.
        """
        if not self.market_service:
            return self._create_placeholder_metric(
                "news_sentiment",
                "News Sentiment",
                58.0,
                "Market service not available",
            )

        try:
            # Use topics=technology for broad AI/tech sector sentiment
            # This is ONE API call instead of 10 individual ticker calls
            news_data = await self.market_service.get_news_sentiment(
                topics="technology",
                limit=50,
            )

            articles = news_data.get("feed", [])
            if not articles:
                return self._create_placeholder_metric(
                    "news_sentiment",
                    "News Sentiment",
                    50.0,
                    "No technology news articles found",
                )

            # Calculate average sentiment from all articles
            sentiments = [
                float(a["overall_sentiment_score"])
                for a in articles
                if "overall_sentiment_score" in a
            ]

            if not sentiments:
                return self._create_placeholder_metric(
                    "news_sentiment",
                    "News Sentiment",
                    50.0,
                    "No sentiment scores in articles",
                )

            avg_sentiment = float(np.mean(sentiments))
            # Sentiment ranges from -0.35 (bearish) to +0.35 (bullish)
            # Normalize to 0-100 where higher = more euphoric (bullish)
            score = self.normalize_score(avg_sentiment, -0.35, 0.35)

            status = ThresholdConfig().get_status(score)

            return InsightMetric(
                id="news_sentiment",
                name="News Sentiment",
                score=score,
                status=status,
                explanation=MetricExplanation(
                    summary=f"Tech sector news sentiment is {'positive' if avg_sentiment > 0 else 'negative'} ({avg_sentiment:.3f}).",
                    detail=(
                        f"Analyzed {len(articles)} technology sector articles. "
                        f"Average sentiment: {avg_sentiment:.3f}. "
                        f"{'Elevated optimism may signal bubble risk.' if score > 65 else 'Sentiment within normal range.'}"
                    ),
                    methodology=(
                        "Aggregates sentiment from NEWS_SENTIMENT API using topics=technology "
                        "for broad tech/AI sector coverage. Single API call for efficiency. "
                        "Normalizes the -0.35 to +0.35 range to 0-100."
                    ),
                    formula="Score = ((avg_sentiment + 0.35) / 0.70) × 100",
                    historical_context=(
                        "Peak euphoria readings (80+) were seen during ChatGPT launch. "
                        f"Current reading: {score:.1f}"
                    ),
                    actionable_insight=(
                        "Watch for scores above 70 which historically precede pullbacks."
                        if score < 70
                        else "High sentiment suggests caution."
                    ),
                ),
                data_sources=["NEWS_SENTIMENT"],
                last_updated=datetime.now(UTC),
                raw_data={
                    "avg_sentiment": round(avg_sentiment, 4),
                    "article_count": len(articles),
                    "topic": "technology",
                },
            )

        except Exception as e:
            logger.error("News sentiment calculation failed", error=str(e))
            return self._create_placeholder_metric(
                "news_sentiment",
                "News Sentiment",
                50.0,
                f"Error: {str(e)}",
            )

    async def _calculate_smart_money_flow(
        self, ai_basket: tuple[list[str], str]
    ) -> InsightMetric:
        """Calculate Smart Money Flow using Smart Money Index (SMI) logic.

        Smart Money Index (SMI) measures the divergence between "dumb money"
        (first hour trading, driven by emotion/news) and "smart money"
        (last hour trading, driven by institutional positioning).

        Formula: SMI = Last Hour Return - First Hour Return
        - Positive SMI: Smart money buying into close (Bullish)
        - Negative SMI: Smart money selling into close (Bearish)

        Args:
            ai_basket: Tuple of (symbols list, source description) from AIQ ETF
        """
        if not self.market_service:
            return self._create_placeholder_metric(
                "smart_money_flow",
                "Smart Money Flow",
                52.0,
                "Market service not available",
            )

        try:
            # Use pre-fetched AI basket
            ai_symbols, _ = ai_basket
            symbols_to_analyze = ai_symbols[:3]  # Analyze top 3 holdings
            smi_values = []

            for symbol in symbols_to_analyze:
                # Get intraday bars (60min to isolate first/last hour)
                # We need enough data to cover the current/last trading session
                df = await self.market_service.get_intraday_bars(
                    symbol=symbol,
                    interval="60min",
                    outputsize="compact",  # Latest 100 points
                )

                if df is not None and not df.empty:
                    # Group by date to get daily sessions
                    # df index is timezone aware (America/New_York)
                    last_date = df.index[-1].date()
                    todays_bars = df[df.index.date == last_date]

                    if len(todays_bars) >= 2:
                        # First hour bar (9:30 - 10:30)
                        first_hour = todays_bars.iloc[0]
                        # Last hour bar (15:30 - 16:00/16:30)
                        last_hour = todays_bars.iloc[-1]

                        # Calculate returns
                        # (Close - Open) / Open
                        first_hour_return = (
                            (first_hour["Close"] - first_hour["Open"])
                            / first_hour["Open"]
                        ) * 100

                        last_hour_return = (
                            (last_hour["Close"] - last_hour["Open"]) / last_hour["Open"]
                        ) * 100

                        # SMI = Last Hour - First Hour
                        # If Last Hour (Smart) > First Hour (Dumb) -> Positive SMI (Bullish)
                        smi = last_hour_return - first_hour_return
                        smi_values.append(smi)

            if smi_values:
                avg_smi = float(np.mean(smi_values))
                # SMI typically ranges from -2% to +2%
                # Map to 0-100 score where higher is more bullish (smart money buying)
                # But risk metric is "High Risk", so we invert:
                # High SMI (Bullish) = Low Risk Score
                # Low SMI (Bearish/Distribution) = High Risk Score

                # Normalization:
                # SMI = +1.0% -> Score 25 (Low Risk)
                # SMI = 0.0% -> Score 50 (Neutral)
                # SMI = -1.0% -> Score 75 (High Risk)
                score = self.normalize_score(-avg_smi, -1.0, 1.0)
            else:
                avg_smi = 0.0
                score = 50.0

            status = ThresholdConfig().get_status(score)

            return InsightMetric(
                id="smart_money_flow",
                name="Smart Money Flow",
                score=score,
                status=status,
                explanation=MetricExplanation(
                    summary=f"Smart Money Index is {avg_smi:+.2f}% (Last Hour vs First Hour).",
                    detail=(
                        f"Average SMI: {avg_smi:+.2f}%. "
                        f"{'Smart money is buying into the close (bullish).' if avg_smi > 0 else 'Smart money is selling into the close (bearish).'}"
                    ),
                    methodology=(
                        "Calculates Smart Money Index (SMI) = Last Hour Return - First Hour Return. "
                        "Positive SMI indicates institutional accumulation (smart money) vs retail reaction (dumb money). "
                        "Inverted for risk scoring: Negative SMI = High Risk."
                    ),
                    formula="Score = 50 + ((-SMI) / 1.0) × 25",
                    historical_context=(
                        "Smart money distribution often precedes trend reversals. "
                        f"Current SMI: {avg_smi:+.2f}%"
                    ),
                    actionable_insight=(
                        "Institutional distribution detected - caution warranted."
                        if avg_smi < -0.5
                        else "Smart money accumulation supports the trend."
                    ),
                ),
                data_sources=["TIME_SERIES_INTRADAY"],
                last_updated=datetime.now(UTC),
                raw_data={
                    "avg_smi": round(avg_smi, 3),
                    "symbols_analyzed": symbols_to_analyze,
                },
            )

        except Exception as e:
            logger.error("Smart money flow calculation failed", error=str(e))
            return self._create_placeholder_metric(
                "smart_money_flow",
                "Smart Money Flow",
                50.0,
                f"Error: {str(e)}",
            )

    async def _calculate_ipo_heat(self) -> InsightMetric:
        """Calculate IPO Heat using IPO_CALENDAR endpoint."""
        if not self.market_service:
            return self._create_placeholder_metric(
                "ipo_heat",
                "IPO Heat",
                35.0,
                "Market service not available",
            )

        try:
            ipos = await self.market_service.get_ipo_calendar()

            # Filter for IPOs in next 90 days
            cutoff_date = datetime.now(UTC) + timedelta(days=90)
            upcoming_ipos = []

            for ipo in ipos:
                ipo_date_str = ipo.get("ipoDate", "")
                if ipo_date_str:
                    try:
                        ipo_date = datetime.strptime(ipo_date_str, "%Y-%m-%d")
                        ipo_date = ipo_date.replace(tzinfo=UTC)
                        if ipo_date <= cutoff_date:
                            upcoming_ipos.append(ipo)
                    except ValueError:
                        pass

            ipo_count = len(upcoming_ipos)

            # 0-5 IPOs = cool, 20+ = overheated
            score = self.normalize_score(ipo_count, 0, 25)
            status = ThresholdConfig().get_status(score)

            return InsightMetric(
                id="ipo_heat",
                name="IPO Heat",
                score=score,
                status=status,
                explanation=MetricExplanation(
                    summary=f"{ipo_count} IPOs scheduled in next 90 days.",
                    detail=(
                        f"There are {ipo_count} IPOs scheduled in the next 90 days. "
                        f"{'High IPO activity suggests companies rushing to market.' if ipo_count > 15 else 'Normal IPO activity.'}"
                    ),
                    methodology=(
                        "Counts scheduled IPOs from IPO_CALENDAR endpoint. "
                        "Normalizes based on historical ranges: <5 = cold, >20 = overheated."
                    ),
                    formula="Score = min(100, (IPO_count / 25) × 100)",
                    historical_context=(
                        "Peak readings (80+) occurred in late 2021 with 25+ IPOs per quarter. "
                        f"Current count: {ipo_count}"
                    ),
                    actionable_insight=(
                        "Normal IPO activity suggests healthy market conditions."
                        if ipo_count < 15
                        else "Elevated IPO activity may signal late-cycle behavior."
                    ),
                ),
                data_sources=["IPO_CALENDAR"],
                last_updated=datetime.now(UTC),
                raw_data={
                    "ipo_count_90d": ipo_count,
                    "total_ipos": len(ipos),
                },
            )

        except Exception as e:
            logger.error("IPO heat calculation failed", error=str(e))
            return self._create_placeholder_metric(
                "ipo_heat",
                "IPO Heat",
                35.0,
                f"Error: {str(e)}",
            )

    async def _calculate_yield_curve(self) -> InsightMetric:
        """Calculate Yield Curve metric using TREASURY_YIELD endpoint."""
        if not self.market_service:
            return self._create_placeholder_metric(
                "yield_curve",
                "Yield Curve",
                70.0,
                "Market service not available",
            )

        try:
            # Get 10Y and 2Y yields
            yield_10y_df = await self.market_service.get_treasury_yield(
                maturity="10year",
                interval="daily",
            )
            yield_2y_df = await self.market_service.get_treasury_yield(
                maturity="2year",
                interval="daily",
            )

            if yield_10y_df.empty or yield_2y_df.empty:
                return self._create_placeholder_metric(
                    "yield_curve",
                    "Yield Curve",
                    50.0,
                    "Treasury yield data unavailable",
                )

            # Get most recent values
            yield_10y = yield_10y_df["value"].iloc[-1]
            yield_2y = yield_2y_df["value"].iloc[-1]
            spread = yield_10y - yield_2y

            # Spread range: -1% (inverted) to +2% (steep)
            # Inverted = 0 (deflationary), Steep = 100 (risk-on)
            score = self.normalize_score(spread, -1.0, 2.0)
            status = ThresholdConfig().get_status(score)

            return InsightMetric(
                id="yield_curve",
                name="Yield Curve",
                score=score,
                status=status,
                explanation=MetricExplanation(
                    summary=f"10Y-2Y spread is {spread:.2f}% ({'steep' if spread > 0.5 else 'flat' if spread > -0.2 else 'inverted'}).",
                    detail=(
                        f"10-year yield: {yield_10y:.2f}%, 2-year yield: {yield_2y:.2f}%. "
                        f"Spread: {spread:.2f}%. "
                        f"{'Steep curve supports risk assets but can fuel bubbles.' if spread > 0.5 else 'Flat/inverted curve signals caution.'}"
                    ),
                    methodology=(
                        "Calculates the 10-year minus 2-year Treasury yield spread. "
                        "Normalizes based on historical range: inverted = 0, +1.5% = 100."
                    ),
                    formula="Score = max(0, (spread + 1.0) / 3.0 × 100)",
                    historical_context=(
                        "The curve inverted in 2022-2023 before steepening. "
                        f"Current spread: {spread:.2f}%"
                    ),
                    actionable_insight=(
                        "Steep yield curve indicates loose monetary conditions."
                        if spread > 0.5
                        else "Flat or inverted curve suggests defensive positioning."
                    ),
                ),
                data_sources=["TREASURY_YIELD"],
                last_updated=datetime.now(UTC),
                raw_data={
                    "yield_10y": round(yield_10y, 3),
                    "yield_2y": round(yield_2y, 3),
                    "spread": round(spread, 3),
                },
            )

        except Exception as e:
            logger.error("Yield curve calculation failed", error=str(e))
            return self._create_placeholder_metric(
                "yield_curve",
                "Yield Curve",
                50.0,
                f"Error: {str(e)}",
            )

    async def _calculate_fed_expectations(self) -> InsightMetric:
        """Calculate Fed Expectations using 2Y yield slope."""
        if not self.market_service:
            return self._create_placeholder_metric(
                "fed_expectations",
                "Fed Expectations",
                62.0,
                "Market service not available",
            )

        try:
            # Get 2Y yield history
            yield_2y_df = await self.market_service.get_treasury_yield(
                maturity="2year",
                interval="daily",
            )

            if yield_2y_df.empty or len(yield_2y_df) < 20:
                return self._create_placeholder_metric(
                    "fed_expectations",
                    "Fed Expectations",
                    50.0,
                    "Insufficient yield data",
                )

            # Calculate 20-day change
            current_yield = yield_2y_df["value"].iloc[-1]
            yield_20d_ago = (
                yield_2y_df["value"].iloc[-20]
                if len(yield_2y_df) >= 20
                else yield_2y_df["value"].iloc[0]
            )
            change_20d = current_yield - yield_20d_ago

            # Falling yields = rate cut expectations = risk-on
            # Change from -0.5% (dovish) to +0.5% (hawkish) maps to 0-100
            # Invert: falling yields (negative change) = higher score
            score = self.normalize_score(-change_20d, -0.5, 0.5)
            status = ThresholdConfig().get_status(score)

            return InsightMetric(
                id="fed_expectations",
                name="Fed Expectations",
                score=score,
                status=status,
                explanation=MetricExplanation(
                    summary=f"2Y yield changed {change_20d:+.2f}% over 20 days.",
                    detail=(
                        f"2-year yield: {current_yield:.2f}% (was {yield_20d_ago:.2f}% 20 days ago). "
                        f"{'Falling yields suggest rate cut expectations, supporting risk assets.' if change_20d < 0 else 'Rising yields indicate hawkish expectations.'}"
                    ),
                    methodology=(
                        "Measures the 20-day change in the 2-year Treasury yield. "
                        "Declining yields indicate dovish expectations, rising yields hawkish."
                    ),
                    formula="Score = 50 + (Δ2Y_20d / -0.5) × 50",
                    historical_context=(
                        "Sharp yield declines preceded major rallies in 2023. "
                        f"Current 20-day change: {change_20d:+.2f}%"
                    ),
                    actionable_insight=(
                        "Dovish expectations are priced in - supports risk assets."
                        if change_20d < -0.1
                        else "Neutral or hawkish expectations."
                    ),
                ),
                data_sources=["TREASURY_YIELD"],
                last_updated=datetime.now(UTC),
                raw_data={
                    "yield_2y_current": round(current_yield, 3),
                    "yield_2y_20d_ago": round(yield_20d_ago, 3),
                    "change_20d": round(change_20d, 3),
                },
            )

        except Exception as e:
            logger.error("Fed expectations calculation failed", error=str(e))
            return self._create_placeholder_metric(
                "fed_expectations",
                "Fed Expectations",
                50.0,
                f"Error: {str(e)}",
            )

    def _create_placeholder_metric(
        self,
        metric_id: str,
        name: str,
        score: float,
        reason: str,
    ) -> InsightMetric:
        """Create a placeholder metric with a default score."""
        status = ThresholdConfig().get_status(score)

        return InsightMetric(
            id=metric_id,
            name=name,
            score=score,
            status=status,
            explanation=MetricExplanation(
                summary=f"Using estimated value. {reason}",
                detail=(
                    f"Real-time calculation unavailable. Using estimated score of {score:.1f}. "
                    f"Reason: {reason}"
                ),
                methodology="Placeholder - real calculation pending.",
                historical_context="Historical data unavailable.",
                actionable_insight="Wait for real-time data for accurate insights.",
            ),
            data_sources=[],
            last_updated=datetime.now(UTC),
            raw_data={"placeholder": True, "reason": reason},
        )

    def _create_error_metric(self, metric_id: str) -> InsightMetric:
        """Create placeholder metric when calculation fails."""
        metric_defs = {d["id"]: d for d in self.get_metric_definitions()}
        metric_def = metric_defs.get(
            metric_id, {"name": metric_id.replace("_", " ").title()}
        )

        return InsightMetric(
            id=metric_id,
            name=metric_def.get("name", metric_id),
            score=-1,  # Sentinel value for error
            status=MetricStatus.NORMAL,
            explanation=MetricExplanation(
                summary="Data temporarily unavailable.",
                detail=(
                    "Unable to calculate this metric due to data availability issues. "
                    "Please try refreshing in a few minutes."
                ),
                methodology="Unable to retrieve calculation methodology.",
                historical_context="Historical data unavailable.",
                actionable_insight="No actionable insight available at this time.",
            ),
            data_sources=metric_def.get("data_sources", []),
            last_updated=datetime.now(UTC),
            raw_data={"error": True, "metric_id": metric_id},
        )

    def _generate_composite_interpretation(
        self,
        score: float,
        status: MetricStatus,
    ) -> str:
        """Generate AI-specific composite interpretation."""
        if status == MetricStatus.LOW:
            return (
                f"AI Sector Risk Index: {score:.1f}/100 (Low Risk). "
                "Fear and pessimism dominate. Historically a good accumulation zone. "
                "Consider building positions in quality AI names."
            )
        elif status == MetricStatus.NORMAL:
            return (
                f"AI Sector Risk Index: {score:.1f}/100 (Normal). "
                "The AI sector is in a healthy bull market phase. "
                "Standard position sizing appropriate."
            )
        elif status == MetricStatus.ELEVATED:
            return (
                f"AI Sector Risk Index: {score:.1f}/100 (Elevated). "
                "Caution warranted. Late-cycle dynamics may be emerging. "
                "Consider trimming positions and tightening stops."
            )
        else:  # HIGH
            return (
                f"AI Sector Risk Index: {score:.1f}/100 (High Risk). "
                "Euphoria indicators are flashing. Historical parallels suggest "
                "elevated correction risk. Defensive positioning recommended."
            )
