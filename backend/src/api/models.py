"""
Pydantic models for Financial Analysis API responses.
Designed to be easily consumable by both frontend and future LangChain agents.
"""

from datetime import datetime
from typing import Optional, Dict, List, Any, Literal
from pydantic import BaseModel, Field


# Base models for common structures
class PricePoint(BaseModel):
    """Price point with date and value."""
    price: float = Field(..., description="Price value")
    date: str = Field(..., description="Date in YYYY-MM-DD format")


class FibonacciLevel(BaseModel):
    """Fibonacci retracement level."""
    level: float = Field(..., ge=0, description="Fibonacci ratio (e.g., 0.618)")
    price: float = Field(..., description="Price at this level")
    percentage: str = Field(..., description="Percentage string (e.g., '61.8%')")
    is_key_level: bool = Field(default=False, description="Whether this is a key level (38.2%, 50%, 61.8%)")


class MarketStructure(BaseModel):
    """Market structure analysis results."""
    trend_direction: Literal["uptrend", "downtrend", "sideways"] = Field(..., description="Overall trend direction")
    swing_high: PricePoint = Field(..., description="Most recent significant swing high")
    swing_low: PricePoint = Field(..., description="Most recent significant swing low")
    structure_quality: Literal["high", "medium", "low"] = Field(..., description="Quality of market structure")
    phase: str = Field(..., description="Current market phase description")


# Main analysis response models
class FibonacciAnalysisResponse(BaseModel):
    """Complete Fibonacci analysis response."""
    symbol: str = Field(..., description="Stock symbol analyzed")
    start_date: Optional[str] = Field(None, description="Analysis start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="Analysis end date (YYYY-MM-DD)")
    timeframe: str = Field(..., description="Analysis timeframe (1d, 1w, 1M)")
    current_price: float = Field(..., description="Current stock price")
    analysis_date: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="Analysis date in ISO format")

    # Core Fibonacci data
    fibonacci_levels: List[FibonacciLevel] = Field(..., description="All Fibonacci retracement levels")
    market_structure: MarketStructure = Field(..., description="Market structure analysis")

    # Analysis insights
    confidence_score: float = Field(..., ge=0, le=1, description="Analysis confidence (0-1)")
    pressure_zone: Optional[Dict[str, float]] = Field(None, description="Key pressure zone around 61.8%")
    trend_strength: str = Field(..., description="Trend strength assessment")

    # Educational context
    analysis_summary: str = Field(..., description="Human-readable analysis summary")
    key_insights: List[str] = Field(..., description="List of key insights from the analysis")

    # Metadata for agent use
    raw_data: Dict[str, Any] = Field(..., description="Raw calculation data for debugging")


class MacroSentimentResponse(BaseModel):
    """Macro market sentiment analysis response."""
    analysis_date: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="Analysis date in ISO format")

    # VIX analysis
    vix_level: float = Field(..., description="Current VIX level")
    vix_interpretation: str = Field(..., description="VIX interpretation (fearful/neutral/greedy)")
    fear_greed_score: int = Field(..., ge=0, le=100, description="Fear/Greed score (0=extreme fear, 100=extreme greed)")

    # Market indices
    major_indices: Dict[str, float] = Field(..., description="Major market index performance")
    sector_performance: Dict[str, float] = Field(..., description="Sector ETF performance")

    # Overall assessment
    market_sentiment: Literal["fearful", "neutral", "greedy"] = Field(..., description="Overall market sentiment")
    confidence_level: float = Field(..., ge=0, le=1, description="Sentiment analysis confidence")
    sentiment_summary: str = Field(..., description="Human-readable sentiment summary")

    # Recommendations
    market_outlook: str = Field(..., description="Short-term market outlook")
    key_factors: List[str] = Field(..., description="Key factors influencing sentiment")


class StockFundamentalsResponse(BaseModel):
    """Stock fundamentals and company information."""
    symbol: str = Field(..., description="Stock symbol")
    company_name: str = Field(..., description="Company name")
    analysis_date: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="Analysis date in ISO format")

    # Price data
    current_price: float = Field(..., description="Current stock price")
    price_change: float = Field(..., description="Price change from previous day")
    price_change_percent: float = Field(..., description="Price change percentage")

    # Volume and market data
    volume: int = Field(..., description="Current volume")
    avg_volume: int = Field(..., description="Average volume")
    market_cap: float = Field(..., description="Market capitalization")

    # Valuation metrics
    pe_ratio: Optional[float] = Field(None, description="Price-to-earnings ratio")
    pb_ratio: Optional[float] = Field(None, description="Price-to-book ratio")
    dividend_yield: Optional[float] = Field(None, ge=0, le=25, description="Dividend yield percentage. We cap at 25% to reject unrealistic data.")

    # Financial health
    beta: Optional[float] = Field(None, description="Stock beta (volatility vs market)")
    fifty_two_week_high: float = Field(..., description="52-week high price")
    fifty_two_week_low: float = Field(..., description="52-week low price")

    # Summary
    fundamental_summary: str = Field(..., description="Summary of fundamental analysis")
    key_metrics: List[str] = Field(..., description="Key fundamental metrics highlighted")


class ChartGenerationResponse(BaseModel):
    """Chart generation response."""
    symbol: str = Field(..., description="Stock symbol for the chart")
    chart_type: str = Field(..., description="Type of chart generated")
    chart_url: Optional[str] = Field(None, description="URL to the generated chart image")
    chart_data: Dict[str, Any] = Field(..., description="Chart data for frontend rendering")
    generation_date: str = Field(..., description="Chart generation date")
    success: bool = Field(..., description="Whether chart generation was successful")
    error_message: Optional[str] = Field(None, description="Error message if generation failed")


class StochasticLevel(BaseModel):
    """Stochastic oscillator level reading."""
    timestamp: str = Field(..., description="Timestamp for this reading")
    k_percent: float = Field(..., ge=0, le=100, description="%K line value")
    d_percent: float = Field(..., ge=0, le=100, description="%D line value")
    signal: Literal["overbought", "oversold", "neutral"] = Field(..., description="Signal interpretation")


class StochasticAnalysisResponse(BaseModel):
    """Complete stochastic oscillator analysis response."""
    symbol: str = Field(..., description="Stock symbol analyzed")
    start_date: Optional[str] = Field(None, description="Analysis start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="Analysis end date (YYYY-MM-DD)")
    timeframe: str = Field(..., description="Analysis timeframe (1h, 1d, 1w, 1M)")
    current_price: float = Field(..., description="Current stock price")
    analysis_date: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="Analysis date in ISO format")

    # Stochastic parameters
    k_period: int = Field(..., description="K% period used")
    d_period: int = Field(..., description="D% period used")

    # Current readings
    current_k: float = Field(..., ge=0, le=100, description="Current %K value")
    current_d: float = Field(..., ge=0, le=100, description="Current %D value")
    current_signal: Literal["overbought", "oversold", "neutral"] = Field(..., description="Current signal interpretation")

    # Analysis results
    stochastic_levels: List[StochasticLevel] = Field(..., description="Historical stochastic levels")
    signal_changes: List[Dict[str, Any]] = Field(..., description="Signal change events (crossovers)")

    # Insights
    analysis_summary: str = Field(..., description="Human-readable analysis summary")
    key_insights: List[str] = Field(..., description="List of key insights from the analysis")

    # Metadata for debugging and advanced features
    raw_data: Dict[str, Any] = Field(..., description="Raw calculation data for debugging")


# Request models
class FibonacciAnalysisRequest(BaseModel):
    """Request model for Fibonacci analysis."""
    symbol: str = Field(..., description="Stock symbol to analyze", example="AAPL")
    start_date: Optional[str] = Field(default=None, description="Start date (YYYY-MM-DD)", example="2024-01-01")
    end_date: Optional[str] = Field(default=None, description="End date (YYYY-MM-DD)", example="2024-12-31")
    timeframe: Literal["1h", "1d", "1w", "1M"] = Field(default="1d", description="Analysis timeframe (1h, 1d, 1w, 1M)", example="1d")
    include_chart: bool = Field(default=True, description="Whether to generate a chart")


class MacroAnalysisRequest(BaseModel):
    """Request model for macro analysis."""
    include_sectors: bool = Field(default=True, description="Include sector rotation analysis")
    include_indices: bool = Field(default=True, description="Include major indices analysis")


class StockFundamentalsRequest(BaseModel):
    """Request model for stock fundamentals."""
    symbol: str = Field(..., min_length=1, pattern=r"^\S+$", description="Stock symbol to analyze", example="AAPL")


class ChartRequest(BaseModel):
    """Request model for chart generation."""
    symbol: str = Field(..., description="Stock symbol for chart", example="AAPL")
    start_date: Optional[str] = Field(default=None, description="Start date (YYYY-MM-DD)", example="2024-01-01")
    end_date: Optional[str] = Field(default=None, description="End date (YYYY-MM-DD)", example="2024-12-31")
    chart_type: Literal["price", "fibonacci", "volume"] = Field(default="fibonacci", description="Type of chart to generate")
    include_indicators: bool = Field(default=True, description="Include technical indicators")


class StochasticAnalysisRequest(BaseModel):
    """Request model for stochastic oscillator analysis."""
    symbol: str = Field(..., min_length=1, pattern=r"^\S+$", description="Stock symbol to analyze", example="AAPL")
    start_date: Optional[str] = Field(default=None, description="Start date (YYYY-MM-DD)", example="2024-01-01")
    end_date: Optional[str] = Field(default=None, description="End date (YYYY-MM-DD)", example="2024-12-31")
    timeframe: Literal["1h", "1d", "1w", "1M"] = Field(default="1d", description="Analysis timeframe (1h, 1d, 1w, 1M)", example="1d")
    k_period: int = Field(default=14, ge=5, le=50, description="K% period for stochastic calculation", example=14)
    d_period: int = Field(default=3, ge=2, le=20, description="D% period for signal line smoothing", example=3)


# Error response model
class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str = Field(..., description="Error message")
    error_code: str = Field(..., description="Error code for programmatic handling")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: str = Field(..., description="Error timestamp")