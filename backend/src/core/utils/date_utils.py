"""
Date utility functions for financial data analysis.
Handles conversion between yfinance periods and absolute date ranges.
"""

from datetime import UTC, datetime, timedelta


def utcnow() -> datetime:
    """
    Return timezone-aware UTC datetime.

    Replaces deprecated datetime.utcnow() which is scheduled for removal in Python 3.14.
    See: https://docs.python.org/3/library/datetime.html#datetime.datetime.utcnow
    """
    return datetime.now(UTC)


def utcfromtimestamp(timestamp: float) -> datetime:
    """
    Return timezone-aware UTC datetime from POSIX timestamp.

    Replaces deprecated datetime.utcfromtimestamp() which is scheduled for removal.
    See: https://docs.python.org/3/library/datetime.html#datetime.datetime.utcfromtimestamp
    """
    return datetime.fromtimestamp(timestamp, UTC)


class DateUtils:
    """Utility class for date operations in financial analysis."""

    @staticmethod
    def period_to_date_range(
        period: str, reference_date: datetime | None = None
    ) -> tuple[str, str]:
        """
        Convert yfinance period string to start/end date range.

        Args:
            period: yfinance period string ('1d', '5d', '1mo', '6mo', '1y', etc.)
            reference_date: Reference date for calculation (defaults to today)

        Returns:
            Tuple of (start_date, end_date) as YYYY-MM-DD strings

        Raises:
            ValueError: If period format is invalid
        """
        if reference_date is None:
            reference_date = datetime.now()

        end_date = reference_date.date()

        # Map yfinance periods to timedelta
        period_map = {
            "1d": timedelta(days=1),
            "5d": timedelta(days=5),
            "1mo": timedelta(days=30),
            "3mo": timedelta(days=90),
            "6mo": timedelta(days=180),
            "1y": timedelta(days=365),
            "2y": timedelta(days=730),
            "5y": timedelta(days=1825),
            "10y": timedelta(days=3650),
            "ytd": DateUtils._get_ytd_delta(reference_date),
            "max": timedelta(days=7300),  # ~20 years
        }

        if period not in period_map:
            raise ValueError(
                f"Unsupported period: {period}. Supported periods: {list(period_map.keys())}"
            )

        delta = period_map[period]
        start_date = end_date - delta

        return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

    @staticmethod
    def _get_ytd_delta(reference_date: datetime) -> timedelta:
        """Calculate timedelta from year-to-date for given reference date."""
        year_start = datetime(reference_date.year, 1, 1).date()
        return reference_date.date() - year_start

    @staticmethod
    def validate_date_range(start_date: str, end_date: str) -> None:
        """
        Validate that date range is logical and in correct format.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Raises:
            ValueError: If date format is invalid or start_date >= end_date
        """
        # Strict format validation - must be exactly YYYY-MM-DD
        import re

        date_pattern = r"^\d{4}-\d{2}-\d{2}$"

        if not re.match(date_pattern, start_date):
            raise ValueError(f"Invalid date format. Expected YYYY-MM-DD: {start_date}")
        if not re.match(date_pattern, end_date):
            raise ValueError(f"Invalid date format. Expected YYYY-MM-DD: {end_date}")

        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError as e:
            raise ValueError(f"Invalid date format. Expected YYYY-MM-DD: {e}") from e

        if start >= end:
            raise ValueError(
                f"Start date ({start_date}) must be before end date ({end_date})"
            )
