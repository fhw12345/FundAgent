"""
Stock data fetching utilities.
DISABLED: Replaced by AlphaVantageMarketDataService.
"""

import pandas as pd
import structlog

logger = structlog.get_logger()


class StockDataFetcher:
    """Fetches and validates stock data.

    DEPRECATED: Use AlphaVantageMarketDataService instead.
    """

    @staticmethod
    async def fetch_stock_data(
        symbol: str, start_date: str, end_date: str
    ) -> pd.DataFrame | None:
        """
        Fetch stock data for the specified symbol and date range.

        Args:
            symbol: Stock symbol to fetch
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            DataFrame with OHLCV data or None if failed

        Raises:
            NotImplementedError: This method is deprecated. Use AlphaVantageMarketDataService.
        """
        raise NotImplementedError(
            "StockDataFetcher is deprecated. Use AlphaVantageMarketDataService instead."
        )

    @staticmethod
    def _clean_data(data: pd.DataFrame) -> pd.DataFrame:
        """Clean and validate stock data."""
        # Remove any rows with all NaN values
        data = data.dropna(how="all")

        # Forward fill any remaining NaN values
        data = data.fillna(method="ffill")

        # Ensure we have the required columns
        required_columns = ["Open", "High", "Low", "Close", "Volume"]
        for col in required_columns:
            if col not in data.columns:
                raise ValueError(f"Missing required column: {col}")

        return data

    @staticmethod
    def validate_data_quality(data: pd.DataFrame, min_days: int = 10) -> bool:
        """
        Validate that the data is sufficient for analysis.

        Args:
            data: Stock data DataFrame
            min_days: Minimum number of trading days required

        Returns:
            True if data quality is sufficient
        """
        if data.empty:
            return False

        if len(data) < min_days:
            logger.warning(
                "Insufficient data points", data_points=len(data), min_required=min_days
            )
            return False

        # Check for reasonable price ranges
        if (
            data["Close"].max() / data["Close"].min() > 100
        ):  # 100x price movement seems unreasonable
            logger.warning("Suspicious price range detected")
            return False

        return True
