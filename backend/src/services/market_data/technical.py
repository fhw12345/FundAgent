"""
Technical indicators for Alpha Vantage service.
"""

from typing import Any

import pandas as pd
import structlog

from .base import AlphaVantageBase

logger = structlog.get_logger()


class TechnicalMixin(AlphaVantageBase):
    """Methods for technical indicators (SMA, EMA, RSI, MACD, etc.)."""

    async def get_technical_indicator(
        self,
        symbol: str,
        function: str,
        interval: str,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """
        Get technical indicator data (unified method for all indicators).

        Supports: SMA, EMA, VWAP, MACD, STOCH, RSI, ADX, AROON, BBANDS, AD, OBV

        Args:
            symbol: Stock ticker symbol
            function: Technical indicator name (uppercase)
            interval: Time interval (1min, 5min, 15min, 30min, 60min, daily, weekly, monthly)
            **kwargs: Indicator-specific parameters:
                - time_period: Period for MA indicators (default: 10)
                - series_type: close, open, high, low (default: close)
                - fastperiod, slowperiod, signalperiod: For MACD
                - fastkperiod, slowkperiod, slowdperiod: For STOCH
                - nbdevup, nbdevdn, matype: For BBANDS

        Returns:
            DataFrame with date/timestamp index and indicator values
        """
        try:
            # Validate indicator
            supported = [
                "SMA",
                "EMA",
                "VWAP",
                "MACD",
                "STOCH",
                "RSI",
                "ADX",
                "AROON",
                "BBANDS",
                "AD",
                "OBV",
            ]
            function_upper = function.upper()

            if function_upper not in supported:
                raise ValueError(
                    f"Unsupported indicator: {function}. Use one of: {', '.join(supported)}"
                )

            # Build params with defaults
            params = {
                "function": function_upper,
                "symbol": symbol,
                "interval": interval,
                "apikey": self.api_key,
            }

            # Add optional parameters
            if "time_period" in kwargs:
                params["time_period"] = kwargs["time_period"]
            if "series_type" in kwargs:
                params["series_type"] = kwargs["series_type"]

            # MACD-specific params
            if function_upper == "MACD":
                params["fastperiod"] = kwargs.get("fastperiod", 12)
                params["slowperiod"] = kwargs.get("slowperiod", 26)
                params["signalperiod"] = kwargs.get("signalperiod", 9)

            # STOCH-specific params
            if function_upper == "STOCH":
                params["fastkperiod"] = kwargs.get("fastkperiod", 5)
                params["slowkperiod"] = kwargs.get("slowkperiod", 3)
                params["slowdperiod"] = kwargs.get("slowdperiod", 3)

            # BBANDS-specific params
            if function_upper == "BBANDS":
                params["nbdevup"] = kwargs.get("nbdevup", 2)
                params["nbdevdn"] = kwargs.get("nbdevdn", 2)

            response = await self.client.get(self.base_url, params=params)

            if response.status_code != 200:
                sanitized_text = self._sanitize_text(response.text)
                raise ValueError(
                    f"Alpha Vantage API error: {response.status_code} - {sanitized_text}"
                )

            data = response.json()

            # Find the technical indicator key in response
            tech_key = None
            for key in data.keys():
                if "Technical Analysis" in key or function_upper in key:
                    tech_key = key
                    break

            if not tech_key or not data[tech_key]:
                sanitized = self._sanitize_response(data)
                raise ValueError(
                    f"No {function} data for symbol: {symbol}. Response: {sanitized}"
                )

            time_series = data[tech_key]

            # Convert to DataFrame
            df_data = []
            for timestamp, values in time_series.items():
                row = {"timestamp": pd.to_datetime(timestamp)}
                # Add all indicator values (handles single and multi-column indicators)
                for val_key, val in values.items():
                    # Clean column name (remove numeric prefix like "1. ")
                    clean_key = (
                        val_key.split(". ", 1)[-1] if ". " in val_key else val_key
                    )
                    row[clean_key] = float(val)
                df_data.append(row)

            df = pd.DataFrame(df_data)
            df.set_index("timestamp", inplace=True)
            df.sort_index(inplace=True)

            # Localize intraday timestamps to ET
            if interval in ["1min", "5min", "15min", "30min", "60min"]:
                if df.index.tz is None:
                    df.index = df.index.tz_localize("America/New_York")

            logger.info(
                "Technical indicator fetched",
                symbol=symbol,
                function=function,
                interval=interval,
                data_points=len(df),
            )

            return df

        except Exception as e:
            logger.error(
                "Technical indicator fetch failed",
                symbol=symbol,
                function=function,
                interval=interval,
                error=str(e),
            )
            raise
