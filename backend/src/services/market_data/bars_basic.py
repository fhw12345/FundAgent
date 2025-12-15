"""
Basic price bars methods (intraday, daily, weekly, monthly).
"""

import pandas as pd
import structlog

from .base import AlphaVantageBase

logger = structlog.get_logger()


class BarsBasicMixin(AlphaVantageBase):
    """Methods for fetching basic price bars (intraday, daily, weekly, monthly)."""

    async def get_intraday_bars(
        self,
        symbol: str,
        interval: str = "1min",
        outputsize: str = "compact",
    ) -> pd.DataFrame:
        """
        Get intraday bars with extended hours using TIME_SERIES_INTRADAY.

        Args:
            symbol: Stock symbol
            interval: 1min, 5min, 15min, 30min, 60min
            outputsize: compact (latest 100 points) or full (full-length)

        Returns:
            DataFrame with Open, High, Low, Close, Volume columns
        """
        try:
            response = await self.client.get(
                self.base_url,
                params={
                    "function": "TIME_SERIES_INTRADAY",
                    "symbol": symbol,
                    "interval": interval,
                    "outputsize": outputsize,
                    "extended_hours": "true",  # Include pre/post market
                    "entitlement": "delayed",  # 15-minute delayed data (premium)
                    "apikey": self.api_key,
                },
            )

            if response.status_code != 200:
                sanitized_text = self._sanitize_text(response.text)
                raise ValueError(
                    f"Alpha Vantage API error: {response.status_code} - {sanitized_text}"
                )

            data = response.json()

            # Find the time series key
            ts_key = f"Time Series ({interval})"
            if ts_key not in data:
                raise ValueError(f"No intraday data for symbol: {symbol}")

            time_series = data[ts_key]

            # Convert to DataFrame
            df_data = []
            for timestamp, values in time_series.items():
                df_data.append(
                    {
                        "timestamp": pd.to_datetime(timestamp),
                        "Open": float(values["1. open"]),
                        "High": float(values["2. high"]),
                        "Low": float(values["3. low"]),
                        "Close": float(values["4. close"]),
                        "Volume": int(values["5. volume"]),
                    }
                )

            df = pd.DataFrame(df_data)
            df.set_index("timestamp", inplace=True)
            df.sort_index(inplace=True)  # Ensure chronological order

            # Alpha Vantage returns intraday timestamps in US Eastern Time
            # Localize naive timestamps to ET for proper session detection
            if not df.empty and df.index.tz is None:
                df.index = df.index.tz_localize("America/New_York")

            logger.info(
                "Intraday bars fetched",
                symbol=symbol,
                interval=interval,
                bars_count=len(df),
            )

            return df

        except Exception as e:
            logger.error(
                "Intraday bars fetch failed",
                symbol=symbol,
                interval=interval,
                error=str(e),
            )
            raise

    async def get_daily_bars(
        self,
        symbol: str,
        outputsize: str = "compact",
    ) -> pd.DataFrame:
        """
        Get daily bars using TIME_SERIES_DAILY_ADJUSTED (split-adjusted prices).

        Args:
            symbol: Stock symbol
            outputsize: compact (latest 100 days) or full (20+ years)

        Returns:
            DataFrame with Open, High, Low, Close, Volume columns (split-adjusted)
        """
        try:
            response = await self.client.get(
                self.base_url,
                params={
                    "function": "TIME_SERIES_DAILY_ADJUSTED",
                    "symbol": symbol,
                    "outputsize": outputsize,
                    "apikey": self.api_key,
                },
            )

            if response.status_code != 200:
                sanitized_text = self._sanitize_text(response.text)
                raise ValueError(
                    f"Alpha Vantage API error: {response.status_code} - {sanitized_text}"
                )

            data = response.json()

            # DAILY_ADJUSTED returns data with different key name
            key = "Time Series (Daily)"
            if key not in data:
                raise ValueError(
                    f"No daily data for symbol: {symbol}. Keys: {list(data.keys())}"
                )

            time_series = data[key]

            # Convert to DataFrame
            # DAILY_ADJUSTED provides: adjusted close (field 5), dividend (7), split coeff (8)
            df_data = []
            for date, values in time_series.items():
                df_data.append(
                    {
                        "date": pd.to_datetime(date),
                        "Open": float(values["1. open"]),
                        "High": float(values["2. high"]),
                        "Low": float(values["3. low"]),
                        "Close": float(
                            values["5. adjusted close"]
                        ),  # Use adjusted close
                        "Volume": int(
                            values["6. volume"]
                        ),  # Volume is field 6 in DAILY_ADJUSTED
                    }
                )

            df = pd.DataFrame(df_data)
            df.set_index("date", inplace=True)
            df.sort_index(inplace=True)

            logger.info(
                "Daily bars fetched (split-adjusted)",
                symbol=symbol,
                bars_count=len(df),
            )

            return df

        except Exception as e:
            logger.error(
                "Daily bars fetch failed",
                symbol=symbol,
                error=str(e),
            )
            raise

    async def get_weekly_bars(
        self,
        symbol: str,
        outputsize: str = "compact",
    ) -> pd.DataFrame:
        """
        Get weekly bars using TIME_SERIES_WEEKLY.

        Args:
            symbol: Stock symbol
            outputsize: compact (latest 100 weeks) or full (20+ years)

        Returns:
            DataFrame with Open, High, Low, Close, Volume columns
        """
        try:
            response = await self.client.get(
                self.base_url,
                params={
                    "function": "TIME_SERIES_WEEKLY",
                    "symbol": symbol,
                    "apikey": self.api_key,
                },
            )

            if response.status_code != 200:
                sanitized_text = self._sanitize_text(response.text)
                raise ValueError(
                    f"Alpha Vantage API error: {response.status_code} - {sanitized_text}"
                )

            data = response.json()

            if "Weekly Time Series" not in data:
                raise ValueError(f"No weekly data for symbol: {symbol}")

            time_series = data["Weekly Time Series"]

            # Convert to DataFrame
            df_data = []
            for date, values in time_series.items():
                df_data.append(
                    {
                        "date": pd.to_datetime(date),
                        "Open": float(values["1. open"]),
                        "High": float(values["2. high"]),
                        "Low": float(values["3. low"]),
                        "Close": float(values["4. close"]),
                        "Volume": int(values["5. volume"]),
                    }
                )

            df = pd.DataFrame(df_data)
            df.set_index("date", inplace=True)
            df.sort_index(inplace=True)

            logger.info(
                "Weekly bars fetched",
                symbol=symbol,
                bars_count=len(df),
            )

            return df

        except Exception as e:
            logger.error(
                "Weekly bars fetch failed",
                symbol=symbol,
                error=str(e),
            )
            raise

    async def get_monthly_bars(
        self,
        symbol: str,
        outputsize: str = "compact",
    ) -> pd.DataFrame:
        """
        Get monthly bars using TIME_SERIES_MONTHLY.

        Args:
            symbol: Stock symbol
            outputsize: compact (latest 100 months) or full (20+ years)

        Returns:
            DataFrame with Open, High, Low, Close, Volume columns
        """
        try:
            response = await self.client.get(
                self.base_url,
                params={
                    "function": "TIME_SERIES_MONTHLY",
                    "symbol": symbol,
                    "apikey": self.api_key,
                },
            )

            if response.status_code != 200:
                sanitized_text = self._sanitize_text(response.text)
                raise ValueError(
                    f"Alpha Vantage API error: {response.status_code} - {sanitized_text}"
                )

            data = response.json()

            if "Monthly Time Series" not in data:
                raise ValueError(f"No monthly data for symbol: {symbol}")

            time_series = data["Monthly Time Series"]

            # Convert to DataFrame
            df_data = []
            for date, values in time_series.items():
                df_data.append(
                    {
                        "date": pd.to_datetime(date),
                        "Open": float(values["1. open"]),
                        "High": float(values["2. high"]),
                        "Low": float(values["3. low"]),
                        "Close": float(values["4. close"]),
                        "Volume": int(values["5. volume"]),
                    }
                )

            df = pd.DataFrame(df_data)
            df.set_index("date", inplace=True)
            df.sort_index(inplace=True)

            logger.info(
                "Monthly bars fetched",
                symbol=symbol,
                bars_count=len(df),
            )

            return df

        except Exception as e:
            logger.error(
                "Monthly bars fetch failed",
                symbol=symbol,
                error=str(e),
            )
            raise
