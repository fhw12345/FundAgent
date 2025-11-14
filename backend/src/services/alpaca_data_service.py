"""
Alpaca Data Service for historical and real-time market data.

Replaces yfinance with Alpaca's FREE paper trading data API.

Benefits over yfinance:
1. FREE pre/post-market data (yfinance requires premium)
2. Real-time quotes (no 15-minute delay)
3. Extended hours support
4. Consistent with trading service (same provider)
"""

from datetime import datetime, timedelta

import pandas as pd
import structlog
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestQuoteRequest
from alpaca.data.timeframe import TimeFrame

from ..core.config import Settings
from ..core.utils import map_frontend_to_alpaca

logger = structlog.get_logger()


class AlpacaDataService:
    """
    Alpaca Data API integration for historical OHLCV data.

    Free tier: Paper trading includes full market data access.
    """

    def __init__(self, settings: Settings):
        """
        Initialize Alpaca data client.

        Args:
            settings: Application settings with Alpaca credentials
        """
        self.settings = settings

        # Initialize Alpaca data client
        self.client = StockHistoricalDataClient(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
        )

        logger.info("AlpacaDataService initialized", paper_trading=True)

    async def get_bars(
        self,
        symbol: str,
        interval: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """
        Get historical OHLCV bars for symbol.

        Args:
            symbol: Stock symbol (e.g., "AAPL")
            interval: Data interval ("1m", "1h", "1d", "1w")
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            DataFrame with OHLCV data (columns: Open, High, Low, Close, Volume)
            Index: DatetimeIndex

        Example:
            >>> df = await service.get_bars("AAPL", "1d", "2025-01-01", "2025-11-01")
            >>> print(df.head())
                                Open      High       Low     Close      Volume
            2025-01-02 00:00:00  271.50  274.80  270.10  274.20  67844982
        """
        try:
            # Convert interval to Alpaca TimeFrame
            timeframe = self._map_interval_to_timeframe(interval)

            # Convert dates to datetime
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")

            # Add one day to end_date (Alpaca excludes end date)
            end_dt = end_dt + timedelta(days=1)

            logger.info(
                "Fetching bars from Alpaca",
                symbol=symbol,
                interval=interval,
                timeframe=str(timeframe),
                start=start_date,
                end=end_date,
            )

            # Create request
            request = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=timeframe,
                start=start_dt,
                end=end_dt,
            )

            # Fetch bars
            bars_response = self.client.get_stock_bars(request)

            # Convert to DataFrame
            # Type guard: bars_response should have .data attribute
            if not hasattr(bars_response, "data"):
                logger.error(
                    "Unexpected response format from Alpaca",
                    response_type=type(bars_response),
                )
                return pd.DataFrame()

            if symbol not in bars_response.data or not bars_response.data[symbol]:
                logger.warning(
                    "No data returned from Alpaca",
                    symbol=symbol,
                    interval=interval,
                    start=start_date,
                    end=end_date,
                )
                return pd.DataFrame()

            bars = bars_response.data[symbol]

            # Convert bars to DataFrame
            data = {
                "Open": [bar.open for bar in bars],
                "High": [bar.high for bar in bars],
                "Low": [bar.low for bar in bars],
                "Close": [bar.close for bar in bars],
                "Volume": [bar.volume for bar in bars],
            }

            df = pd.DataFrame(
                data,
                index=pd.DatetimeIndex([bar.timestamp for bar in bars]),
            )

            logger.info(
                "Successfully fetched from Alpaca",
                symbol=symbol,
                rows=len(df),
                columns=list(df.columns),
            )

            return df

        except Exception as e:
            logger.error(
                "Error fetching from Alpaca",
                symbol=symbol,
                interval=interval,
                error=str(e),
                exc_info=True,
            )
            return pd.DataFrame()

    async def get_latest_price(self, symbol: str) -> float | None:
        """
        Get latest/current price for symbol using Alpaca's latest quote.

        Args:
            symbol: Stock symbol (e.g., "AAPL")

        Returns:
            Latest price as float, or None if unavailable

        Example:
            >>> price = await service.get_latest_price("AAPL")
            >>> print(price)  # 274.20
        """
        try:
            logger.info("Fetching latest quote from Alpaca", symbol=symbol)

            # Create request for latest quote
            request = StockLatestQuoteRequest(symbol_or_symbols=symbol)

            # Fetch latest quote
            quote_response = self.client.get_stock_latest_quote(request)

            # Handle both dict and object responses
            if isinstance(quote_response, dict):
                # Response is a dict
                if symbol not in quote_response or not quote_response[symbol]:
                    logger.warning("No quote data for symbol", symbol=symbol)
                    return None
                quote = quote_response[symbol]
            elif hasattr(quote_response, "data"):
                # Response has .data attribute
                if symbol not in quote_response.data or not quote_response.data[symbol]:
                    logger.warning("No quote data for symbol", symbol=symbol)
                    return None
                quote = quote_response.data[symbol]
            else:
                logger.error(
                    "Unexpected quote response format from Alpaca",
                    response_type=type(quote_response),
                )
                return None

            # Use ask_price (current selling price) as the "current price"
            # Fall back to bid_price if ask not available
            price = quote.ask_price if quote.ask_price > 0 else quote.bid_price

            if price and price > 0:
                logger.info(
                    "Got latest price from Alpaca",
                    symbol=symbol,
                    price=price,
                    ask=quote.ask_price,
                    bid=quote.bid_price,
                )
                return float(price)
            else:
                logger.warning(
                    "Invalid price from Alpaca quote",
                    symbol=symbol,
                    ask=quote.ask_price,
                    bid=quote.bid_price,
                )
                return None

        except Exception as e:
            logger.error(
                "Error fetching latest price from Alpaca",
                symbol=symbol,
                error=str(e),
                exc_info=True,
            )
            return None

    def _map_interval_to_timeframe(self, interval: str) -> TimeFrame:
        """
        Map frontend interval to Alpaca TimeFrame.

        Args:
            interval: Frontend interval ("1m", "1h", "1d", "1w", "1M")

        Returns:
            Alpaca TimeFrame object

        Examples:
            >>> timeframe = service._map_interval_to_timeframe("1m")
            >>> print(timeframe)  # TimeFrame(1, TimeFrameUnit.Minute)

            >>> timeframe = service._map_interval_to_timeframe("1d")
            >>> print(timeframe)  # TimeFrame(1, TimeFrameUnit.Day)
        """
        # Simple mapping using utility function
        return map_frontend_to_alpaca(interval)
