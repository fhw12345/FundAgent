"""
FRED API integration for liquidity metrics.

Provides access to Federal Reserve Economic Data (FRED) for market liquidity
indicators that are not available through Alpha Vantage:
- SOFR (Secured Overnight Financing Rate)
- EFFR (Effective Federal Funds Rate)
- RRP Balance (Fed Reverse Repo Operations)

These metrics are used by the AI Sector Risk category to assess actual market
liquidity conditions, which is critical for bubble risk assessment.

Theory: "When capital is abundant, asset prices easily rise and bubbles can form.
When capital is tight, even with high market sentiment, bubbles cannot easily form."
"""

from datetime import UTC, datetime, timedelta

import httpx
import pandas as pd
import structlog

logger = structlog.get_logger()

FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

# Cache TTL for FRED data (1 hour - daily data doesn't change frequently)
FRED_CACHE_TTL_SECONDS = 3600


class FREDService:
    """
    FRED (Federal Reserve Economic Data) API client.

    Provides access to liquidity-related economic indicators:
    - SOFR: Secured Overnight Financing Rate
    - EFFR: Effective Federal Funds Rate
    - RRPONTSYD: Overnight Reverse Repurchase Agreements (RRP balance)

    All methods return pandas DataFrames with date index and value column.
    Values with "." (missing data marker) are filtered out.
    """

    def __init__(self, api_key: str, client: httpx.AsyncClient | None = None):
        """
        Initialize FRED service.

        Args:
            api_key: FRED API key (free registration at https://fred.stlouisfed.org)
            client: Optional httpx AsyncClient for connection pooling
        """
        self.api_key = api_key
        self._client = client
        self._owns_client = client is None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self) -> None:
        """Close HTTP client if we own it."""
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def get_series(
        self,
        series_id: str,
        days: int = 60,
    ) -> pd.DataFrame:
        """
        Fetch FRED time series data.

        Args:
            series_id: FRED series identifier (e.g., "SOFR", "EFFR", "RRPONTSYD")
            days: Number of days of history to fetch (default: 60)

        Returns:
            DataFrame with date index and value column.
            Empty DataFrame if API call fails.

        Raises:
            ValueError: If API returns error response
        """
        client = await self._get_client()

        # Calculate date range
        end_date = datetime.now(UTC).strftime("%Y-%m-%d")
        start_date = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d")

        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "observation_start": start_date,
            "observation_end": end_date,
            "sort_order": "asc",  # Oldest first for proper DataFrame ordering
        }

        try:
            response = await client.get(FRED_BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()

            if "observations" not in data:
                logger.warning(
                    "No observations in FRED response",
                    series_id=series_id,
                    response_keys=list(data.keys()),
                )
                return pd.DataFrame(columns=["value"])

            # Parse observations, filtering out missing values (".")
            observations = data["observations"]
            df_data = []
            for obs in observations:
                value = obs.get("value", ".")
                if value != ".":
                    try:
                        df_data.append(
                            {
                                "date": pd.to_datetime(obs["date"]),
                                "value": float(value),
                            }
                        )
                    except (ValueError, TypeError):
                        # Skip invalid values
                        continue

            if not df_data:
                logger.warning(
                    "No valid data points in FRED response",
                    series_id=series_id,
                    total_observations=len(observations),
                )
                return pd.DataFrame(columns=["value"])

            df = pd.DataFrame(df_data)
            df.set_index("date", inplace=True)
            df.sort_index(inplace=True)

            logger.info(
                "FRED data fetched",
                series_id=series_id,
                data_points=len(df),
                date_range=f"{df.index[0]} to {df.index[-1]}",
            )

            return df

        except httpx.HTTPStatusError as e:
            logger.error(
                "FRED API HTTP error",
                series_id=series_id,
                status_code=e.response.status_code,
                error=str(e),
            )
            raise ValueError(f"FRED API error: {e.response.status_code}") from e
        except httpx.RequestError as e:
            logger.error(
                "FRED API request error",
                series_id=series_id,
                error=str(e),
            )
            raise ValueError(f"FRED API request failed: {e}") from e
        except Exception as e:
            logger.error(
                "Unexpected error fetching FRED data",
                series_id=series_id,
                error=str(e),
            )
            raise

    async def get_sofr(self, days: int = 60) -> pd.DataFrame:
        """
        Get Secured Overnight Financing Rate (SOFR).

        SOFR is a broad measure of the cost of borrowing cash overnight
        collateralized by Treasury securities. It's the benchmark rate
        for overnight funding in US markets.

        Args:
            days: Number of days of history (default: 60)

        Returns:
            DataFrame with date index and value (rate in percent) column
        """
        return await self.get_series("SOFR", days)

    async def get_effr(self, days: int = 60) -> pd.DataFrame:
        """
        Get Effective Federal Funds Rate (EFFR).

        EFFR is the interest rate at which depository institutions lend
        reserve balances to other depository institutions overnight.
        This is the Fed's primary policy rate target.

        Args:
            days: Number of days of history (default: 60)

        Returns:
            DataFrame with date index and value (rate in percent) column
        """
        return await self.get_series("EFFR", days)

    async def get_rrp_balance(self, days: int = 60) -> pd.DataFrame:
        """
        Get Fed Reverse Repo (RRP) balance.

        The RRP facility allows eligible counterparties to deposit excess
        cash with the Fed overnight. High RRP balance indicates abundant
        liquidity in the financial system seeking safe parking.

        Series: RRPONTSYD (Overnight Reverse Repurchase Agreements:
        Treasury Securities Sold by the Federal Reserve)

        Args:
            days: Number of days of history (default: 60)

        Returns:
            DataFrame with date index and value (balance in billions USD) column

        Historical Context:
        - Peak: ~$2,500B (Dec 2022) - extreme liquidity
        - Current (Dec 2025): ~$10-20B - near zero
        - Low (<$300B) historically coincides with market stress
        """
        return await self.get_series("RRPONTSYD", days)


# Export for module
__all__ = ["FREDService", "FRED_CACHE_TTL_SECONDS"]
