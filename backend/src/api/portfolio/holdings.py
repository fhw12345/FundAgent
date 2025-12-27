"""
Portfolio holdings and summary endpoints.

Provides:
- GET /holdings: Fetch current positions from Alpaca
- GET /summary: Get portfolio account summary
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request

from src.core.utils.date_utils import utcnow

from ...models.holding import Holding
from ...services.alpaca_trading_service import AlpacaTradingService
from ..dependencies.auth import get_current_user_id
from ..dependencies.portfolio_deps import get_alpaca_trading_service
from ..dependencies.rate_limit import limiter
from ..schemas.portfolio_models import (
    HoldingResponse,
    PortfolioSummaryResponse,
)

logger = structlog.get_logger()

router = APIRouter()


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
                created_at=utcnow(),
                updated_at=utcnow(),
                last_price_update=utcnow(),
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
        ) from e


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
        ) from e
