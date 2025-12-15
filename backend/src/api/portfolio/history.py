"""
Portfolio history endpoint.

Provides:
- GET /history: Portfolio value history with analysis/order markers
"""

from datetime import datetime, timedelta

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request

from ...database.mongodb import MongoDB
from ...services.alpaca_trading_service import AlpacaTradingService
from ..dependencies.auth import get_current_user_id, get_mongodb
from ..dependencies.portfolio_deps import get_alpaca_trading_service
from ..dependencies.rate_limit import limiter
from ..schemas.portfolio_models import (
    AnalysisMarker,
    OrderMarker,
    PortfolioHistoryDataPoint,
    PortfolioHistoryResponse,
)

logger = structlog.get_logger()

router = APIRouter()


@router.get("/history", response_model=PortfolioHistoryResponse)
@limiter.limit("10/minute")  # Alpaca API call - restrictive limit
async def get_portfolio_history(
    request: Request,
    period: str = "1D",
    symbol: str | None = None,  # Optional: filter analysis markers by symbol
    user_id: str = Depends(get_current_user_id),  # JWT authentication required
    alpaca_trading: AlpacaTradingService | None = Depends(get_alpaca_trading_service),
    mongodb: MongoDB = Depends(get_mongodb),
) -> PortfolioHistoryResponse:
    """
    Get portfolio value history from Alpaca with analysis markers.

    Args:
        period: Time period (1D, 1M, 1Y, All)
        symbol: Optional symbol to filter analysis markers
        user_id: Authenticated user ID
        alpaca_trading: Alpaca trading service
        mongodb: MongoDB instance

    Returns:
        Time series data with account equity history and analysis markers
    """
    if not alpaca_trading:
        raise HTTPException(
            status_code=503,
            detail="Alpaca credentials not configured. Cannot fetch portfolio history.",
        )

    try:
        # Map frontend period to Alpaca period format
        alpaca_period = period
        if period == "All":
            alpaca_period = "all"
        elif period == "1Y":
            alpaca_period = "1A"  # Alpaca uses "A" for annual, not "Y"

        # Map period to appropriate timeframe
        if period == "1D":
            timeframe = "5Min"  # Intraday granularity
        elif period in ["1M", "1Y", "All", "all"]:
            timeframe = "1D"  # Daily granularity
        else:
            timeframe = "1D"

        # Get portfolio history from Alpaca
        history_data = await alpaca_trading.get_portfolio_history(
            period=alpaca_period,
            timeframe=timeframe,
        )

        # Convert to response format
        data_points = [
            PortfolioHistoryDataPoint(
                timestamp=datetime.fromisoformat(ts), value=equity
            )
            for ts, equity in zip(
                history_data["timestamps"], history_data["equity"], strict=False
            )
        ]

        # Get current equity (last value)
        current_value = history_data["equity"][-1] if history_data["equity"] else 0.0

        # Get time range for filtering markers
        # Use a wider range to include recent analyses even outside trading hours
        if data_points:
            # Extend range to include analyses from past 7 days
            start_time = data_points[0].timestamp - timedelta(days=7)
            end_time = datetime.utcnow()  # Include future analyses up to now
        else:
            start_time = datetime.utcnow() - timedelta(days=7)
            end_time = datetime.utcnow()

        # NO LONGER SHOWING ANALYSIS MARKERS ON CHART
        # Analysis markers are now shown in sidebar chat history
        # Only order execution markers will be shown
        markers: list[AnalysisMarker] = []

        # Skip analysis marker processing (commented out for reference)
        # messages_collection = mongodb.get_collection("messages")
        # message_repo = MessageRepository(messages_collection)
        # analysis_messages = await message_repo.get_analysis_messages(...)

        # Future: Could add analysis markers back via API parameter if needed
        # Disabled - analysis markers removed from chart (now shown in sidebar)
        # The code below is kept for reference but not executed
        pass

        # Fetch order markers from portfolio_orders collection
        orders_collection = mongodb.get_collection("portfolio_orders")

        # Build order query (filter by symbol and time range)
        order_query = {
            "user_id": user_id,
            "created_at": {"$gte": start_time, "$lte": end_time},
        }
        if symbol:
            order_query["symbol"] = symbol

        # Query orders sorted by creation time descending
        orders_cursor = (
            orders_collection.find(order_query).sort("created_at", -1).limit(100)
        )

        # Convert to OrderMarker format
        order_markers: list[OrderMarker] = []
        async for order_dict in orders_cursor:
            order_markers.append(
                OrderMarker(
                    timestamp=order_dict["created_at"],
                    symbol=order_dict["symbol"],
                    side=order_dict["side"],
                    quantity=order_dict["quantity"],
                    status=order_dict["status"],
                    filled_avg_price=order_dict.get("filled_avg_price"),
                    order_id=order_dict["order_id"],
                )
            )

        logger.info(
            "Portfolio history fetched from Alpaca",
            user_id=user_id,
            period=period,
            data_points=len(data_points),
            analysis_markers=len(markers),
            order_markers=len(order_markers),
            current_value=current_value,
            base_value=history_data["base_value"],
        )

        return PortfolioHistoryResponse(
            data_points=data_points,
            markers=markers,
            order_markers=order_markers,
            current_value=current_value,
            period=period,
        )

    except Exception as e:
        logger.error(
            "Failed to fetch portfolio history",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve portfolio history. Please try again later.",
        ) from e
