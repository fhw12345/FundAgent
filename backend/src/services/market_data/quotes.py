"""
Stock quotes and symbol search methods for Alpha Vantage service.
"""

from typing import Any

import pandas as pd
import structlog

from .base import AlphaVantageBase

logger = structlog.get_logger()


class QuotesMixin(AlphaVantageBase):
    """Methods for stock quotes, symbol search, and market status."""

    async def search_symbols(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """
        Search for stock symbols using Alpha Vantage SYMBOL_SEARCH.

        Args:
            query: Search query (symbol or company name)
            limit: Maximum number of results

        Returns:
            List of search results with symbol, name, type, region, currency
        """
        try:
            response = await self.client.get(
                self.base_url,
                params={
                    "function": "SYMBOL_SEARCH",
                    "keywords": query,
                    "apikey": self.api_key,
                },
            )

            if response.status_code != 200:
                sanitized_text = self._sanitize_text(response.text)
                raise ValueError(
                    f"Alpha Vantage API error: {response.status_code} - {sanitized_text}"
                )

            data = response.json()

            if "bestMatches" not in data:
                # Sanitize response to avoid logging API keys
                sanitized = self._sanitize_response(data)
                logger.warning("No matches found", query=query, response=sanitized)
                return []

            matches = data["bestMatches"][:limit]

            # Format results to match API contract
            results = []
            for match in matches:
                match_score = float(match.get("9. matchScore", "0.0"))
                results.append(
                    {
                        "symbol": match.get("1. symbol", ""),
                        "name": match.get("2. name", ""),
                        "type": match.get("3. type", ""),
                        "exchange": match.get(
                            "4. region", ""
                        ),  # Use region as exchange
                        "match_type": "exact_symbol" if match_score >= 0.9 else "fuzzy",
                        "confidence": match_score,
                    }
                )

            logger.info(
                "Symbol search completed",
                query=query,
                results_count=len(results),
            )

            return results

        except Exception as e:
            logger.error("Symbol search failed", query=query, error=str(e))
            raise

    async def get_quote(self, symbol: str) -> dict[str, Any]:
        """
        Get real-time quote using Alpha Vantage GLOBAL_QUOTE.

        Args:
            symbol: Stock symbol

        Returns:
            Dict with price, volume, change, etc.
        """
        try:
            # GLOBAL_QUOTE with entitlement=delayed returns previous day's close during market hours
            # It will show today's close only after market closes
            response = await self.client.get(
                self.base_url,
                params={
                    "function": "GLOBAL_QUOTE",
                    "symbol": symbol,
                    "entitlement": "delayed",
                    "apikey": self.api_key,
                },
            )

            if response.status_code != 200:
                sanitized_text = self._sanitize_text(response.text)
                raise ValueError(
                    f"Alpha Vantage API error: {response.status_code} - {sanitized_text}"
                )

            data = response.json()

            # Handle both standard and delayed response formats
            # Standard: "Global Quote"
            # Delayed: "Global Quote - DATA DELAYED BY 15 MINUTES"
            quote_key = None
            for key in data.keys():
                if key.startswith("Global Quote"):
                    quote_key = key
                    break

            if not quote_key or not data[quote_key]:
                raise ValueError(f"No quote data for symbol: {symbol}")

            quote = data[quote_key]

            logger.info(
                "Quote API response parsed",
                symbol=symbol,
                quote_key=quote_key,
            )

            result = {
                "symbol": quote.get("01. symbol", symbol),
                "price": float(quote.get("05. price", 0)),
                "volume": int(quote.get("06. volume", 0)),
                "latest_trading_day": quote.get("07. latest trading day", ""),
                "previous_close": float(quote.get("08. previous close", 0)),
                "change": float(quote.get("09. change", 0)),
                "change_percent": quote.get("10. change percent", "0%").rstrip("%"),
                "open": float(quote.get("02. open", 0)),
                "high": float(quote.get("03. high", 0)),
                "low": float(quote.get("04. low", 0)),
            }

            logger.info(
                "Quote fetched",
                symbol=symbol,
                price=result["price"],
            )

            return result

        except Exception as e:
            logger.error("Quote fetch failed", symbol=symbol, error=str(e))
            raise

    async def get_market_status(self, region: str = "United States") -> dict[str, Any]:
        """
        Get global market open/close status from Alpha Vantage MARKET_STATUS API.

        Supports multiple regions for extensibility (US, Hong Kong, China, etc.).

        Args:
            region: Market region to query. Supported values:
                - "United States" (default)
                - "Hong Kong"
                - "Mainland China"
                - "Japan"
                - "United Kingdom"
                - "Germany"
                - And more...

        Returns:
            Dict with market status info:
                - region: Market region name
                - current_status: "open" or "closed"
                - local_open: Local market open time (HH:MM)
                - local_close: Local market close time (HH:MM)
                - primary_exchanges: Exchange names
                - notes: Additional notes (e.g., lunch breaks)
                - local_time: Current local time for that market
                - utc_time: Current UTC time
        """
        # Region to timezone mapping for computing local time
        region_timezones = {
            "United States": "America/New_York",
            "Hong Kong": "Asia/Hong_Kong",
            "Mainland China": "Asia/Shanghai",
            "Japan": "Asia/Tokyo",
            "United Kingdom": "Europe/London",
            "Germany": "Europe/Berlin",
            "France": "Europe/Paris",
            "Canada": "America/Toronto",
            "India": "Asia/Kolkata",
            "Brazil": "America/Sao_Paulo",
            "Mexico": "America/Mexico_City",
            "South Africa": "Africa/Johannesburg",
            "Spain": "Europe/Madrid",
            "Portugal": "Europe/Lisbon",
        }

        try:
            response = await self.client.get(
                self.base_url,
                params={
                    "function": "MARKET_STATUS",
                    "apikey": self.api_key,
                },
            )

            if response.status_code != 200:
                sanitized_text = self._sanitize_text(response.text)
                raise ValueError(
                    f"Alpha Vantage API error: {response.status_code} - {sanitized_text}"
                )

            data = response.json()
            markets = data.get("markets", [])

            # Find the requested region
            market_info = None
            for market in markets:
                if (
                    market.get("region") == region
                    and market.get("market_type") == "Equity"
                ):
                    market_info = market
                    break

            if not market_info:
                raise ValueError(f"Market region not found: {region}")

            # Get current times
            utc_now = pd.Timestamp.now(tz="UTC")
            timezone = region_timezones.get(region, "UTC")
            local_now = utc_now.tz_convert(timezone)

            result = {
                "region": region,
                "current_status": market_info.get("current_status", "unknown"),
                "local_open": market_info.get("local_open", ""),
                "local_close": market_info.get("local_close", ""),
                "primary_exchanges": market_info.get("primary_exchanges", ""),
                "notes": market_info.get("notes", ""),
                "local_time": local_now.strftime("%Y-%m-%d %H:%M %Z"),
                "utc_time": utc_now.strftime("%Y-%m-%d %H:%M UTC"),
            }

            logger.info(
                "Market status fetched",
                region=region,
                status=result["current_status"],
            )

            return result

        except Exception as e:
            logger.error("Market status fetch failed", region=region, error=str(e))
            raise
