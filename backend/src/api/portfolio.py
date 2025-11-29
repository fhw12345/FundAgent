"""
Portfolio API endpoints for Alpaca paper trading integration.

All portfolio data comes from Alpaca API (single source of truth).
No manual holdings management - Alpaca handles all positions.
"""

from datetime import datetime, timedelta

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request

from ..database.mongodb import MongoDB
from ..database.repositories.portfolio_order_repository import PortfolioOrderRepository
from ..models.holding import Holding
from ..services.alpaca_trading_service import AlpacaTradingService
from ..services.chat_service import ChatService
from .dependencies.auth import get_current_user_id, get_mongodb, require_admin
from .dependencies.chat_deps import get_chat_service
from .dependencies.portfolio_deps import get_alpaca_trading_service
from .dependencies.rate_limit import (
    limiter,
)
from .schemas.portfolio_models import (
    AnalysisMarker,
    HoldingResponse,
    OrderMarker,
    PortfolioHistoryDataPoint,
    PortfolioHistoryResponse,
    PortfolioSummaryResponse,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("/holdings", response_model=list[HoldingResponse])
@limiter.limit("10/minute")  # Alpaca API call - restrictive limit
async def get_holdings(
    request: Request,
    user_id: str = Depends(get_current_user_id),  # JWT authentication required
    alpaca_trading: AlpacaTradingService | None = Depends(get_alpaca_trading_service),
) -> list[HoldingResponse]:
    """
    Get all positions from Alpaca account (single source of truth).

    Returns actual positions from Alpaca paper trading account.

    Args:
        user_id: Authenticated user ID
        alpaca_trading: Alpaca trading service

    Returns:
        List of current positions from Alpaca
    """
    if not alpaca_trading:
        raise HTTPException(
            status_code=503,
            detail="Alpaca credentials not configured. Cannot fetch positions.",
        )

    try:
        # Get positions from Alpaca (single source of truth)
        positions = await alpaca_trading.get_positions(user_id)

        # Convert PortfolioPosition to HoldingResponse format
        holdings = []
        for pos in positions:
            # Create a minimal Holding object for response
            holding = Holding(
                holding_id=f"alpaca_{pos.symbol}",  # Use symbol as ID
                user_id=user_id,
                symbol=pos.symbol,
                quantity=int(pos.quantity),
                avg_price=pos.avg_entry_price,
                cost_basis=pos.cost_basis,
                current_price=pos.current_price,
                market_value=pos.market_value,
                unrealized_pl=pos.unrealized_pl,
                unrealized_pl_pct=pos.unrealized_pl_pct,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                last_price_update=datetime.utcnow(),
            )
            holdings.append(HoldingResponse.from_holding(holding))

        logger.info(
            "Positions retrieved from Alpaca", user_id=user_id, count=len(holdings)
        )

        return holdings

    except Exception as e:
        logger.error(
            "Failed to fetch positions",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve portfolio positions. Please try again later.",
        )


@router.get("/summary", response_model=PortfolioSummaryResponse)
@limiter.limit("10/minute")  # Alpaca API call - restrictive limit
async def get_portfolio_summary(
    request: Request,
    user_id: str = Depends(get_current_user_id),  # JWT authentication required
    alpaca_trading: AlpacaTradingService | None = Depends(get_alpaca_trading_service),
) -> PortfolioSummaryResponse:
    """
    Get portfolio summary from Alpaca account.

    Returns actual account equity, cash, and P&L from Alpaca paper trading account.

    Args:
        user_id: Authenticated user ID
        alpaca_trading: Alpaca trading service

    Returns:
        Portfolio summary with account equity and P&L
    """
    if not alpaca_trading:
        raise HTTPException(
            status_code=503,
            detail="Alpaca credentials not configured. Cannot fetch account summary.",
        )

    try:
        # Get account summary from Alpaca
        account_summary = await alpaca_trading.get_account_summary(user_id)

        # Convert PortfolioSummary model to dict for PortfolioSummaryResponse
        summary_dict = {
            "holdings_count": account_summary.position_count,
            "total_cost_basis": account_summary.equity
            - account_summary.total_pl,  # Equity - P/L = initial
            "total_market_value": account_summary.equity,
            "total_unrealized_pl": account_summary.total_pl,
            "total_unrealized_pl_pct": account_summary.total_pl_pct,
        }

        logger.info(
            "Account summary retrieved from Alpaca",
            user_id=user_id,
            equity=account_summary.equity,
            total_pl=account_summary.total_pl,
            total_pl_pct=account_summary.total_pl_pct,
        )

        return PortfolioSummaryResponse(**summary_dict)

    except Exception as e:
        logger.error(
            "Failed to fetch account summary",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve portfolio summary. Please try again later.",
        )


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
        )


@router.get("/chat-history")
@limiter.limit("60/minute")  # Standard read operation
async def get_portfolio_chat_history(
    request: Request,
    symbol: str | None = None,  # Optional symbol filter (e.g., "AAPL")
    start_date: str | None = None,  # Optional start date (YYYY-MM-DD)
    end_date: str | None = None,  # Optional end date (YYYY-MM-DD)
    date: str | None = None,  # Legacy: single date filter (YYYY-MM-DD) - deprecated
    user_id: str = Depends(get_current_user_id),  # ✅ JWT authentication required
    mongodb: MongoDB = Depends(get_mongodb),
) -> dict:
    """
    Get portfolio agent's chat history grouped by symbol.

    **Authentication**: Requires Bearer token in Authorization header.

    Each symbol has its own chat (e.g., "XIACY Analysis") where all
    analyses for that symbol are stored as messages.

    **Enhanced Filtering**:
    - Filter by specific symbol: `?symbol=AAPL`
    - Filter by date range: `?start_date=2025-01-01&end_date=2025-03-15`
    - Filter by symbol AND date: `?symbol=AAPL&start_date=2025-01-01`

    Args:
        symbol: Optional symbol filter (returns only chats for this symbol)
        start_date: Optional start date (YYYY-MM-DD). Filters messages >= this date
        end_date: Optional end date (YYYY-MM-DD). Filters messages <= this date
        date: Legacy single date filter (YYYY-MM-DD) - use start_date/end_date instead
        user_id: Authenticated user ID (auto-injected via JWT)

    Returns:
        Dictionary with symbol as keys, chat info with messages as values.
        Messages within each chat are sorted chronologically (oldest first).
        Chats are sorted by most recent message timestamp (newest first).
    """
    # Auth verification happens automatically via get_current_user_id
    # Portfolio data is shared (all authenticated users see same analysis)
    # But only authenticated users can access it
    try:
        from datetime import datetime

        chats_collection = mongodb.get_collection("chats")
        messages_collection = mongodb.get_collection("messages")

        # Parse date filters
        date_start = None
        date_end = None

        # Handle legacy single date filter (convert to date range)
        if date and not start_date and not end_date:
            start_date = date
            # Single date = same day range
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d")
                date_end = date_obj.replace(hour=23, minute=59, second=59)
            except ValueError:
                logger.warning("Invalid date format provided", date=date)
                raise HTTPException(
                    status_code=400, detail="Invalid date format. Use YYYY-MM-DD."
                )

        # Parse start_date
        if start_date:
            try:
                date_start = datetime.strptime(start_date, "%Y-%m-%d").replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
            except ValueError:
                logger.warning("Invalid start_date format", start_date=start_date)
                raise HTTPException(
                    status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD."
                )

        # Parse end_date
        if end_date:
            try:
                date_end = datetime.strptime(end_date, "%Y-%m-%d").replace(
                    hour=23, minute=59, second=59, microsecond=999999
                )
            except ValueError:
                logger.warning("Invalid end_date format", end_date=end_date)
                raise HTTPException(
                    status_code=400, detail="Invalid end_date format. Use YYYY-MM-DD."
                )

        # Get all chats for portfolio_agent user
        chat_query = {"user_id": "portfolio_agent"}

        # Apply symbol filter if provided (filter by title pattern)
        if symbol:
            # Match chats where title starts with symbol (e.g., "AAPL Analysis")
            chat_query["title"] = {"$regex": f"^{symbol}\\s", "$options": "i"}

        portfolio_chats = await chats_collection.find(chat_query).to_list(length=None)

        if not portfolio_chats:
            logger.info(
                "No portfolio agent chats found",
                symbol_filter=symbol,
                date_filter=start_date or end_date,
            )
            return {"chats": []}

        logger.info(
            "Found portfolio agent chats",
            count=len(portfolio_chats),
            symbol_filter=symbol,
            start_date=start_date,
            end_date=end_date,
        )

        # Build result: one entry per chat (symbol)
        result_chats = []

        for chat in portfolio_chats:
            chat_id = chat["chat_id"]
            title = chat.get("title", "Unknown")

            # Extract symbol from title (format: "{symbol} Analysis")
            symbol = title.split(" ")[0] if " " in title else title

            # Build message query
            message_query = {"chat_id": chat_id}
            if date_start and date_end:
                # Filter messages by date range
                message_query["timestamp"] = {"$gte": date_start, "$lt": date_end}
            elif date_start:
                # Filter messages from start date onwards
                message_query["timestamp"] = {"$gte": date_start}
            elif date_end:
                # Filter messages up to end date
                message_query["timestamp"] = {"$lt": date_end}

            # Get messages for this chat (filtered by date if specified)
            # Sort newest first (most recent analysis at top)
            messages = (
                await messages_collection.find(message_query)
                .sort("timestamp", -1)
                .to_list(length=None)
            )  # Sort newest first

            # Skip chats with no messages in the date range
            if date and not messages:
                continue

            # Clean messages
            for msg in messages:
                msg.pop("_id", None)

            # Get most recent message timestamp for sorting (first message since sorted newest first)
            latest_timestamp = (
                messages[0].get("timestamp", datetime.min) if messages else datetime.min
            )

            result_chats.append(
                {
                    "chat_id": chat_id,
                    "symbol": symbol,
                    "title": title,
                    "message_count": len(messages),
                    "messages": messages,
                    "latest_timestamp": (
                        latest_timestamp.isoformat()
                        if isinstance(latest_timestamp, datetime)
                        else str(latest_timestamp)
                    ),
                }
            )

        # Sort chats by most recent message (newest first)
        result_chats.sort(key=lambda c: c.get("latest_timestamp", ""), reverse=True)

        logger.info(
            "Portfolio chat history retrieved",
            chats_count=len(result_chats),
            total_messages=sum(c["message_count"] for c in result_chats),
            date_filter=date,
            filtered=bool(date),
        )

        return {"chats": result_chats}

    except Exception as e:
        logger.error(
            "Failed to fetch portfolio chat history",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve portfolio chat history. Please try again later.",
        )


@router.get("/chats/{chat_id}")
@limiter.limit("60/minute")  # Standard read operation
async def get_portfolio_chat_detail(
    request: Request,
    chat_id: str,
    limit: int | None = None,
    user_id: str = Depends(get_current_user_id),  # ✅ JWT authentication required
    chat_service: ChatService = Depends(get_chat_service),
) -> dict:
    """
    Get portfolio agent chat detail with messages.

    **Authentication**: Requires Bearer token in Authorization header.

    Fetches portfolio_agent chats (owned by system user "portfolio_agent").
    Portfolio data is shared across all authenticated users.

    Args:
        chat_id: Chat identifier
        limit: Optional message limit (default: 100)
        user_id: Authenticated user ID (auto-injected via JWT)

    Returns:
        Chat detail with messages
    """
    # Auth verification happens automatically via get_current_user_id
    # Portfolio chats are owned by "portfolio_agent" (system user)
    # All authenticated users can view them (shared data)
    try:
        # Get chat without ownership verification (portfolio_agent chats)
        chat = await chat_service.get_chat(chat_id, user_id="portfolio_agent")

        # Get messages
        messages = await chat_service.get_chat_messages(
            chat_id, user_id="portfolio_agent", limit=limit
        )

        logger.info(
            "Portfolio chat detail retrieved",
            chat_id=chat_id,
            message_count=len(messages),
        )

        return {
            "chat": chat,
            "messages": messages,
        }

    except Exception as e:
        logger.error(
            "Failed to get portfolio chat detail",
            chat_id=chat_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve portfolio chat. Please try again later.",
        )


@router.delete("/chats/{chat_id}", status_code=204)
@limiter.limit("30/minute")  # Write operation - admin only
async def delete_portfolio_chat(
    request: Request,
    chat_id: str,
    _: None = Depends(require_admin),  # Admin only
    chat_service: ChatService = Depends(get_chat_service),
) -> None:
    """
    Delete a portfolio agent chat and all its messages.

    **Admin only** - Requires admin privileges to delete portfolio analysis chats.

    Args:
        chat_id: Chat identifier

    Returns:
        204 No Content on success

    Raises:
        HTTPException: 403 if not admin, 404 if chat not found
    """
    try:
        # Delete chat with portfolio_agent as owner
        deleted = await chat_service.delete_chat(chat_id, user_id="portfolio_agent")

        if not deleted:
            logger.warning(
                "Portfolio chat not found for deletion",
                chat_id=chat_id,
            )
            raise HTTPException(
                status_code=404,
                detail="Portfolio chat not found",
            )

        logger.info(
            "Portfolio chat deleted",
            chat_id=chat_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to delete portfolio chat",
            chat_id=chat_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail="Unable to delete portfolio chat. Please try again later.",
        )


@router.get("/orders")
@limiter.limit("10/minute")  # Alpaca API call - restrictive limit
async def get_portfolio_orders(
    request: Request,
    limit: int = 50,
    status: str | None = None,  # "open", "closed", "all"
    user_id: str = Depends(get_current_user_id),  # ✅ JWT authentication required
    trading_service: AlpacaTradingService = Depends(get_alpaca_trading_service),
) -> dict:
    """
    Get portfolio orders from Alpaca.

    **Authentication**: Requires Bearer token in Authorization header.

    Shows actual BUY/SELL orders placed by the portfolio analysis agent.
    All authenticated users see the same orders (shared paper trading account).

    Args:
        limit: Maximum number of orders to return (default: 50)
        status: Filter by status - "open", "closed", or "all" (default: "all")
        user_id: Authenticated user ID (auto-injected via JWT)

    Returns:
        List of orders with execution details
    """
    try:
        # Get orders from Alpaca
        from alpaca.trading.enums import QueryOrderStatus
        from alpaca.trading.requests import GetOrdersRequest

        # Map status parameter to Alpaca enum
        status_filter = None
        if status == "open":
            status_filter = QueryOrderStatus.OPEN
        elif status == "closed":
            status_filter = QueryOrderStatus.CLOSED
        else:
            status_filter = QueryOrderStatus.ALL

        request = GetOrdersRequest(
            status=status_filter,
            limit=limit,
        )

        alpaca_orders = trading_service.client.get_orders(filter=request)

        # Transform to our format
        orders = []
        for alpaca_order in alpaca_orders:
            # Clean enum strings (remove "orderside." prefix, etc.)
            side = str(alpaca_order.side).lower().replace("orderside.", "")
            order_type = str(alpaca_order.type).lower().replace("ordertype.", "")
            status = str(alpaca_order.status).lower().replace("orderstatus.", "")

            orders.append(
                {
                    "order_id": str(alpaca_order.id),
                    "symbol": alpaca_order.symbol,
                    "side": side,
                    "quantity": float(alpaca_order.qty),
                    "order_type": order_type,
                    "status": status,
                    "filled_qty": float(alpaca_order.filled_qty or 0),
                    "filled_avg_price": (
                        float(alpaca_order.filled_avg_price)
                        if alpaca_order.filled_avg_price
                        else None
                    ),
                    "submitted_at": (
                        alpaca_order.submitted_at.isoformat()
                        if alpaca_order.submitted_at
                        else None
                    ),
                    "filled_at": (
                        alpaca_order.filled_at.isoformat()
                        if alpaca_order.filled_at
                        else None
                    ),
                    "analysis_id": alpaca_order.client_order_id,  # Our analysis ID
                }
            )

        logger.info(
            "Portfolio orders retrieved",
            order_count=len(orders),
            status_filter=status,
        )

        return {
            "orders": orders,
            "total": len(orders),
        }

    except Exception as e:
        logger.error(
            "Failed to retrieve portfolio orders",
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve order history. Please try again later.",
        )


@router.get("/transactions")
@limiter.limit("60/minute")  # Database read - standard limit
async def get_portfolio_transactions(
    request: Request,
    limit: int = 10,
    offset: int = 0,
    status: str | None = None,  # "success", "failed", or None for all
    user_id: str = Depends(get_current_user_id),  # JWT authentication required
    mongodb: MongoDB = Depends(get_mongodb),
) -> dict:
    """
    Get portfolio transactions from MongoDB (includes failed orders).

    **Authentication**: Requires Bearer token in Authorization header.

    Unlike /orders (Alpaca API), this endpoint returns transactions from our
    database which includes both successful and failed orders with error messages.

    Args:
        limit: Maximum number of transactions to return (default: 10)
        offset: Number of transactions to skip for pagination (default: 0)
        status: Filter by status - "success" (filled/new), "failed", or None for all
        user_id: Authenticated user ID (auto-injected via JWT)

    Returns:
        List of transactions with execution details and error messages for failures
    """
    try:
        orders_collection = mongodb.get_collection("portfolio_orders")
        order_repo = PortfolioOrderRepository(orders_collection)

        # Build query based on status filter
        query: dict = {}

        if status == "success":
            # Success = filled, new, partially_filled, accepted (anything that went to Alpaca)
            # Note: Status may include "OrderStatus." prefix from Alpaca SDK enum
            query["status"] = {
                "$in": [
                    "filled",
                    "new",
                    "partially_filled",
                    "accepted",
                    "pending_new",
                    "OrderStatus.FILLED",
                    "OrderStatus.NEW",
                    "OrderStatus.PARTIALLY_FILLED",
                    "OrderStatus.ACCEPTED",
                    "OrderStatus.PENDING_NEW",
                ]
            }
        elif status == "failed":
            # Failed = orders that failed before reaching Alpaca
            query["status"] = "failed"
        # else: no filter, return all

        # Get total count for pagination
        total_count = await orders_collection.count_documents(query)

        # Query with pagination
        cursor = (
            orders_collection.find(query)
            .sort("created_at", -1)
            .skip(offset)
            .limit(limit)
        )

        transactions = []
        async for order_dict in cursor:
            order_dict.pop("_id", None)
            transactions.append(
                {
                    "order_id": order_dict.get("order_id"),
                    "alpaca_order_id": order_dict.get("alpaca_order_id"),
                    "symbol": order_dict.get("symbol"),
                    "side": order_dict.get("side"),
                    "quantity": order_dict.get("quantity"),
                    "order_type": order_dict.get("order_type"),
                    "status": order_dict.get("status"),
                    "filled_qty": order_dict.get("filled_qty", 0),
                    "filled_avg_price": order_dict.get("filled_avg_price"),
                    "error_message": order_dict.get("error_message"),  # For failed orders
                    "analysis_id": order_dict.get("analysis_id"),
                    "created_at": (
                        order_dict["created_at"].isoformat()
                        if order_dict.get("created_at")
                        else None
                    ),
                    "filled_at": (
                        order_dict["filled_at"].isoformat()
                        if order_dict.get("filled_at")
                        else None
                    ),
                }
            )

        logger.info(
            "Portfolio transactions retrieved",
            transaction_count=len(transactions),
            total_count=total_count,
            status_filter=status,
            offset=offset,
            limit=limit,
        )

        return {
            "transactions": transactions,
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(transactions) < total_count,
        }

    except Exception as e:
        logger.error(
            "Failed to retrieve portfolio transactions",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve transaction history. Please try again later.",
        )
