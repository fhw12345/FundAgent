"""
Data types for the Data Manager Layer.

These models define the structure of data returned by the DML,
ensuring consistent interfaces across all data consumers.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class MetricStatus(str, Enum):
    """Status levels for insight metrics."""

    LOW = "low"
    NORMAL = "normal"
    ELEVATED = "elevated"
    HIGH = "high"


class Granularity(str, Enum):
    """Time granularity for OHLCV data."""

    MIN_1 = "1min"
    MIN_5 = "5min"
    MIN_15 = "15min"
    MIN_30 = "30min"
    MIN_60 = "60min"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

    @property
    def is_intraday(self) -> bool:
        """Returns True for granularities that should NOT be cached."""
        return self in (Granularity.MIN_1, Granularity.MIN_5, Granularity.MIN_15)

    @property
    def ttl_seconds(self) -> int:
        """Returns the TTL in seconds for this granularity."""
        ttl_map = {
            Granularity.MIN_1: 0,  # No cache
            Granularity.MIN_5: 0,  # No cache
            Granularity.MIN_15: 0,  # No cache
            Granularity.MIN_30: 300,  # 5 minutes
            Granularity.MIN_60: 900,  # 15 minutes
            Granularity.DAILY: 3600,  # 1 hour
            Granularity.WEEKLY: 7200,  # 2 hours
            Granularity.MONTHLY: 14400,  # 4 hours
        }
        return ttl_map.get(self, 3600)


@dataclass
class OHLCVData:
    """OHLCV bar data for a single time period."""

    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "date": self.date.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OHLCVData":
        """Create from dictionary."""
        return cls(
            date=datetime.fromisoformat(data["date"]),
            open=float(data["open"]),
            high=float(data["high"]),
            low=float(data["low"]),
            close=float(data["close"]),
            volume=int(data["volume"]),
        )


@dataclass
class TreasuryData:
    """Treasury yield data for a single date."""

    date: datetime
    yield_value: float
    maturity: str  # "2y", "10y", etc.

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "date": self.date.isoformat(),
            "yield_value": self.yield_value,
            "maturity": self.maturity,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TreasuryData":
        """Create from dictionary."""
        return cls(
            date=datetime.fromisoformat(data["date"]),
            yield_value=float(data["yield_value"]),
            maturity=data["maturity"],
        )


@dataclass
class NewsData:
    """News sentiment data for a single article/aggregation."""

    date: datetime
    sentiment_score: float  # -1.0 to 1.0
    ticker_relevance: float  # 0.0 to 1.0
    title: str = ""
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "date": self.date.isoformat(),
            "sentiment_score": self.sentiment_score,
            "ticker_relevance": self.ticker_relevance,
            "title": self.title,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NewsData":
        """Create from dictionary."""
        return cls(
            date=datetime.fromisoformat(data["date"]),
            sentiment_score=float(data["sentiment_score"]),
            ticker_relevance=float(data["ticker_relevance"]),
            title=data.get("title", ""),
            source=data.get("source", ""),
        )


@dataclass
class IPOData:
    """IPO calendar entry."""

    date: datetime
    name: str
    exchange: str
    price_range_low: float | None = None
    price_range_high: float | None = None
    shares_offered: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "date": self.date.isoformat(),
            "name": self.name,
            "exchange": self.exchange,
            "price_range_low": self.price_range_low,
            "price_range_high": self.price_range_high,
            "shares_offered": self.shares_offered,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IPOData":
        """Create from dictionary."""
        return cls(
            date=datetime.fromisoformat(data["date"]),
            name=data["name"],
            exchange=data["exchange"],
            price_range_low=data.get("price_range_low"),
            price_range_high=data.get("price_range_high"),
            shares_offered=data.get("shares_offered"),
        )


@dataclass
class TrendPoint:
    """Single data point in a trend series."""

    date: datetime
    score: float
    status: MetricStatus

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "date": self.date.isoformat(),
            "score": self.score,
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TrendPoint":
        """Create from dictionary."""
        return cls(
            date=datetime.fromisoformat(data["date"]),
            score=float(data["score"]),
            status=MetricStatus(data["status"]),
        )


@dataclass
class SharedDataContext:
    """
    Container for pre-fetched shared data.

    Used by the prefetch pattern to eliminate duplicate API calls
    when multiple metrics need the same data source.
    """

    ohlcv: dict[str, list[OHLCVData]] = field(default_factory=dict)
    treasury: dict[str, list[TreasuryData]] = field(default_factory=dict)
    news: dict[str, list[NewsData]] = field(default_factory=dict)
    ipo: list[IPOData] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)

    def get_ohlcv(self, symbol: str) -> list[OHLCVData] | None:
        """Get OHLCV data for a symbol, or None if not fetched."""
        return self.ohlcv.get(symbol.upper())

    def get_treasury(self, maturity: str) -> list[TreasuryData] | None:
        """Get treasury data for a maturity, or None if not fetched."""
        return self.treasury.get(maturity.lower())

    def has_errors(self) -> bool:
        """Check if any fetch errors occurred."""
        return len(self.errors) > 0


class DataFetchError(Exception):
    """Exception raised when data fetch fails."""

    def __init__(self, message: str, source: str | None = None):
        self.message = message
        self.source = source
        super().__init__(f"{source}: {message}" if source else message)
