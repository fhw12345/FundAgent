"""
Options data methods for Alpha Vantage service.

Provides access to HISTORICAL_OPTIONS endpoint for options chain data.
"""

from typing import Any

import structlog

from .base import AlphaVantageBase

logger = structlog.get_logger()


class OptionsMixin(AlphaVantageBase):
    """Methods for options chain data from Alpha Vantage."""

    async def get_historical_options(
        self, symbol: str, date: str | None = None
    ) -> dict[str, Any]:
        """
        Get historical options chain from Alpha Vantage HISTORICAL_OPTIONS.

        This endpoint returns the options chain for the previous trading day
        (or a specific historical date). Each option contract includes:
        - Strike price and expiration date
        - Last price, bid, ask
        - Volume and open interest
        - Greeks (delta, gamma, theta, vega)
        - Implied volatility

        Args:
            symbol: Stock symbol (e.g., "NVDA")
            date: Optional date in YYYY-MM-DD format (defaults to previous trading day)

        Returns:
            Dict with 'data' array containing option contracts:
            {
                "data": [
                    {
                        "contractID": "NVDA250117C00100000",
                        "symbol": "NVDA",
                        "expiration": "2025-01-17",
                        "strike": "100.00",
                        "type": "call",
                        "last": "88.50",
                        "bid": "88.30",
                        "ask": "88.70",
                        "volume": "1234",
                        "open_interest": "5678",
                        "implied_volatility": "0.45",
                        "delta": "0.95",
                        "gamma": "0.002",
                        "theta": "-0.05",
                        "vega": "0.10"
                    },
                    ...
                ]
            }

        Raises:
            ValueError: If API returns an error
        """
        try:
            params: dict[str, str] = {
                "function": "HISTORICAL_OPTIONS",
                "symbol": symbol.upper(),
                "apikey": self.api_key,
            }
            if date:
                params["date"] = date

            response = await self.client.get(self.base_url, params=params)

            if response.status_code != 200:
                sanitized_text = self._sanitize_text(response.text)
                raise ValueError(
                    f"Alpha Vantage API error: {response.status_code} - {sanitized_text}"
                )

            data: dict[str, Any] = response.json()

            # Check for error response
            if "Error Message" in data:
                error_msg = self._sanitize_text(str(data["Error Message"]))
                logger.warning("options_api_error", symbol=symbol, error=error_msg)
                return {"data": []}

            if "Information" in data:
                info_msg = self._sanitize_text(str(data["Information"]))
                logger.warning("options_api_info", symbol=symbol, info=info_msg)
                return {"data": []}

            contract_count = len(data.get("data", []))
            logger.info(
                "Options chain fetched",
                symbol=symbol,
                date=date or "previous_trading_day",
                contracts=contract_count,
            )

            return data

        except Exception as e:
            logger.error("Options fetch failed", symbol=symbol, error=str(e))
            raise
