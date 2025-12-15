"""
Position and portfolio operations for Alpaca Trading Service.

Handles position tracking, account summary, and portfolio history.
"""

import asyncio
from datetime import datetime

import structlog
from alpaca.trading.requests import GetPortfolioHistoryRequest

from ...models.portfolio import PortfolioPosition, PortfolioSummary
from .base import AlpacaTradingServiceBase
from .helpers import alpaca_position_to_portfolio_position

logger = structlog.get_logger()


class PositionOperations(AlpacaTradingServiceBase):
    """Position tracking and portfolio summary operations."""

    async def get_account_summary(self, user_id: str) -> PortfolioSummary:
        """
        Get portfolio summary from Alpaca account.

        Fetches base_value from portfolio history to calculate accurate P&L.

        Args:
            user_id: Portfolio owner

        Returns:
            PortfolioSummary with account values and P&L

        Example:
            >>> summary = await service.get_account_summary("user_123")
            >>> print(summary.equity)
            106870.0
            >>> print(summary.total_pl)
            107.50
        """
        try:
            # Get account info from Alpaca
            account = self.client.get_account()

            # Get positions for position count
            positions = self.client.get_all_positions()

            # Get base_value from portfolio history (this is the actual starting balance)
            history_request = GetPortfolioHistoryRequest(
                period="all",
                timeframe="1D",
            )
            history = self.client.get_portfolio_history(history_request)
            base_value = history.base_value

            # Calculate P&L from actual base value
            equity = float(account.equity)
            total_pl = equity - base_value
            total_pl_pct = (total_pl / base_value * 100) if base_value > 0 else 0.0

            # Create summary
            summary = PortfolioSummary(
                user_id=user_id,
                equity=equity,
                cash=float(account.cash),
                buying_power=float(account.buying_power),
                total_pl=total_pl,
                total_pl_pct=total_pl_pct,
                day_pl=float(account.equity) - float(account.last_equity),
                day_pl_pct=(
                    (float(account.equity) - float(account.last_equity))
                    / float(account.last_equity)
                    * 100
                    if float(account.last_equity) > 0
                    else 0.0
                ),
                position_count=len(positions),
            )

            logger.info(
                "Account summary retrieved",
                user_id=user_id,
                equity=summary.equity,
                base_value=base_value,
                total_pl=summary.total_pl,
                total_pl_pct=summary.total_pl_pct,
                position_count=summary.position_count,
            )

            return summary

        except Exception as e:
            logger.error(
                "Failed to get account summary",
                user_id=user_id,
                error=str(e),
            )
            raise

    async def get_positions(self, user_id: str) -> list[PortfolioPosition]:
        """
        Get all current positions in portfolio.

        Args:
            user_id: Portfolio owner

        Returns:
            List of PortfolioPosition models

        Example:
            >>> positions = await service.get_positions("user_123")
            >>> for pos in positions:
            ...     print(f"{pos.symbol}: {pos.quantity} shares @ ${pos.current_price}")
            'AAPL: 25.0 shares @ $274.80'
        """
        try:
            # Get positions from Alpaca
            alpaca_positions = self.client.get_all_positions()

            positions = [
                alpaca_position_to_portfolio_position(pos, user_id)
                for pos in alpaca_positions
            ]

            logger.info(
                "Positions retrieved",
                user_id=user_id,
                position_count=len(positions),
            )

            return positions

        except Exception as e:
            logger.error(
                "Failed to get positions",
                user_id=user_id,
                error=str(e),
            )
            raise

    async def get_portfolio_history(
        self,
        period: str = "1M",
        timeframe: str = "1D",
    ) -> dict:
        """
        Get portfolio value history from Alpaca.

        Args:
            period: Time period ("1D", "1M", "1Y", "all")
            timeframe: Data granularity ("1Min", "5Min", "15Min", "1H", "1D")

        Returns:
            Dict with:
            - base_value: Starting portfolio value
            - timestamps: List of datetime strings
            - equity: List of portfolio values
            - profit_loss: List of P/L values
            - profit_loss_pct: List of P/L percentages

        Example:
            >>> history = await service.get_portfolio_history(period="1M", timeframe="1D")
            >>> print(history["base_value"])
            100000.0
            >>> print(history["equity"][-1])
            106870.0
        """
        try:
            request = GetPortfolioHistoryRequest(
                period=period,
                timeframe=timeframe,
                extended_hours=False,
            )

            # Run blocking Alpaca API call in thread executor to avoid blocking event loop
            history = await asyncio.to_thread(
                self.client.get_portfolio_history, request
            )

            logger.info(
                "Portfolio history retrieved",
                period=period,
                timeframe=timeframe,
                data_points=len(history.timestamp),
                base_value=history.base_value,
            )

            return {
                "base_value": history.base_value,
                "timestamps": [
                    datetime.fromtimestamp(ts).isoformat() for ts in history.timestamp
                ],
                "equity": list(history.equity) if history.equity else [],
                "profit_loss": list(history.profit_loss) if history.profit_loss else [],
                "profit_loss_pct": (
                    [pct * 100 for pct in history.profit_loss_pct]
                    if history.profit_loss_pct
                    else []
                ),
            }

        except Exception as e:
            logger.error(
                "Failed to get portfolio history",
                period=period,
                error=str(e),
            )
            raise
