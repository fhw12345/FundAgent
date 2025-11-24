"""
Portfolio Analysis Agent - Autonomous portfolio analysis.

Runs periodically (CronJob) to analyze all active user portfolios.
"""

import asyncio
from datetime import datetime
from typing import Any

import structlog

from ..core.config import Settings
from ..database.mongodb import MongoDB
from ..database.redis import RedisCache
from ..database.repositories.chat_repository import ChatRepository
from ..database.repositories.message_repository import MessageRepository
from ..database.repositories.portfolio_order_repository import PortfolioOrderRepository
from ..database.repositories.transaction_repository import TransactionRepository
from ..database.repositories.user_repository import UserRepository
from ..database.repositories.watchlist_repository import WatchlistRepository
from ..models.chat import ChatCreate
from ..models.message import MessageCreate, MessageMetadata
from ..services.context_window_manager import ContextWindowManager
from ..services.credit_service import CreditService
from .langgraph_react_agent import FinancialAnalysisReActAgent

logger = structlog.get_logger()


class PortfolioAnalysisAgent:
    """
    Autonomous agent for portfolio analysis.

    Features:
    - Analyzes all active user portfolios
    - Uses ReAct agent with 120 tools (2 local + 118 MCP)
    - Stores analysis results in MongoDB
    - Handles errors gracefully
    """

    def __init__(
        self,
        mongodb: MongoDB,
        redis_cache: RedisCache,
        react_agent: FinancialAnalysisReActAgent,
        settings: Settings,
        market_service=None,  # AlphaVantageMarketDataService
        trading_service=None,  # AlpacaTradingService
        credit_service: CreditService | None = None,  # For usage tracking
    ):
        """
        Initialize portfolio analysis agent.

        Args:
            mongodb: MongoDB connection
            redis_cache: Redis cache connection
            react_agent: ReAct agent with MCP tools
            settings: Application settings
            market_service: Alpha Vantage market data service
            trading_service: Alpaca trading service for order placement
            credit_service: Credit service for usage tracking (optional)
        """
        self.mongodb = mongodb
        self.redis_cache = redis_cache
        self.react_agent = react_agent
        self.settings = settings
        self.market_service = market_service
        self.trading_service = trading_service
        self.credit_service = credit_service

        # Repositories
        self.user_repo = UserRepository(mongodb.get_collection("users"))
        self.watchlist_repo = WatchlistRepository(mongodb.get_collection("watchlist"))
        self.chat_repo = ChatRepository(mongodb.get_collection("chats"))
        self.message_repo = MessageRepository(mongodb.get_collection("messages"))
        self.order_repo = PortfolioOrderRepository(
            mongodb.get_collection("portfolio_orders")
        )
        self.transaction_repo = TransactionRepository(
            mongodb.get_collection("transactions")
        )

        # Context window manager for sliding window + summary
        self.context_manager = ContextWindowManager(settings)

    async def analyze_all_portfolios(self, dry_run: bool = False) -> dict[str, Any]:
        """
        Run analysis for all active user portfolios.

        Args:
            dry_run: If True, don't write results to DB

        Returns:
            Execution summary with metrics
        """
        run_id = f"run_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        started_at = datetime.utcnow()

        logger.info(
            "Portfolio analysis started",
            run_id=run_id,
            dry_run=dry_run,
        )

        # Get all active users with portfolios
        users_to_analyze = await self.user_repo.get_active_users_with_portfolios()

        results = {
            "run_id": run_id,
            "started_at": started_at.isoformat(),
            "dry_run": dry_run,
            "users_to_analyze": len(users_to_analyze),
            "users_analyzed": 0,
            "portfolios_analyzed": 0,
            "errors": [],
            "metrics": {},
        }

        if not users_to_analyze:
            logger.info("No users with portfolios to analyze", run_id=run_id)
            results["completed_at"] = datetime.utcnow().isoformat()
            return results

        # Analyze each user's portfolio
        for user in users_to_analyze:
            try:
                user_result = await self.analyze_user_portfolio(
                    user_id=user["user_id"],
                    dry_run=dry_run,
                )

                results["users_analyzed"] += 1
                results["portfolios_analyzed"] += user_result.get("portfolios_count", 0)

            except Exception as e:
                logger.error(
                    "Failed to analyze user portfolio",
                    run_id=run_id,
                    user_id=user.get("user_id"),
                    error=str(e),
                    error_type=type(e).__name__,
                    exc_info=True,
                )

                results["errors"].append(
                    {
                        "user_id": user.get("user_id"),
                        "error": str(e),
                        "error_type": type(e).__name__,
                    }
                )

        # Calculate metrics
        completed_at = datetime.utcnow()
        duration_seconds = (completed_at - started_at).total_seconds()

        results["completed_at"] = completed_at.isoformat()
        results["metrics"] = {
            "total_duration_seconds": duration_seconds,
            "avg_duration_per_user_seconds": (
                duration_seconds / results["users_analyzed"]
                if results["users_analyzed"] > 0
                else 0
            ),
        }

        # Store execution record in MongoDB
        if not dry_run:
            await self._store_execution_record(results)

        logger.info(
            "Portfolio analysis completed",
            run_id=run_id,
            users_analyzed=results["users_analyzed"],
            portfolios_analyzed=results["portfolios_analyzed"],
            errors_count=len(results["errors"]),
            duration_seconds=duration_seconds,
        )

        return results

    async def analyze_user_portfolio(
        self, user_id: str, dry_run: bool = False
    ) -> dict[str, Any]:
        """
        Run analysis for single user's portfolio.

        Analyzes:
        1. Holdings (buy/sell/hold recommendations)
        2. Watchlist symbols
        3. Top market movers (3 gainers, 3 losers, 3 most active)

        Args:
            user_id: User identifier
            dry_run: If True, don't write results to DB

        Returns:
            Analysis result summary
        """
        logger.info("Analyzing user portfolio", user_id=user_id, dry_run=dry_run)

        analysis_results = {
            "user_id": user_id,
            "portfolios_count": 0,
            "holdings_analyzed": 0,
            "watchlist_analyzed": 0,
            "market_movers_analyzed": 0,
            "total_symbols_analyzed": 0,
            "errors": [],
        }

        try:
            # 1. Get user's positions from Alpaca (single source of truth)
            positions = []
            if self.trading_service:
                try:
                    positions = await self.trading_service.get_positions(user_id)
                    logger.info(
                        "Retrieved Alpaca positions",
                        user_id=user_id,
                        positions_count=len(positions),
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to retrieve Alpaca positions - continuing without positions",
                        user_id=user_id,
                        error=str(e),
                    )
            else:
                logger.info("Trading service not available - skipping positions analysis")

            # 2. Get user's watchlist
            watchlist_items = await self.watchlist_repo.get_by_user(user_id)
            logger.info(
                "Retrieved user watchlist",
                user_id=user_id,
                watchlist_count=len(watchlist_items),
            )

            # 3. Get top market movers (top 3 each category)
            market_movers_symbols = []
            if self.market_service:
                try:
                    movers_data = await self.market_service.get_top_gainers_losers()
                    # Extract top 3 from each category
                    top_gainers = movers_data.get("top_gainers", [])[:3]
                    top_losers = movers_data.get("top_losers", [])[:3]
                    most_active = movers_data.get("most_actively_traded", [])[:3]

                    # Extract symbols from market movers
                    market_movers_symbols = (
                        [
                            item.get("ticker")
                            for item in top_gainers
                            if item.get("ticker")
                        ]
                        + [
                            item.get("ticker")
                            for item in top_losers
                            if item.get("ticker")
                        ]
                        + [
                            item.get("ticker")
                            for item in most_active
                            if item.get("ticker")
                        ]
                    )

                    logger.info(
                        "Retrieved market movers",
                        gainers=len(top_gainers),
                        losers=len(top_losers),
                        active=len(most_active),
                        total_symbols=len(market_movers_symbols),
                    )
                except Exception as e:
                    logger.error(
                        "Failed to get market movers",
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                    analysis_results["errors"].append(
                        {"type": "market_movers", "error": str(e)}
                    )

            # 4. Analyze positions (Alpaca holdings) - BATCH PROCESSING
            if positions:
                if dry_run:
                    for position in positions:
                        logger.info(
                            "Dry run - would analyze position",
                            symbol=position.symbol,
                            quantity=position.quantity,
                        )
                        analysis_results["holdings_analyzed"] += 1
                else:
                    # Batch process holdings (5 concurrent max to avoid rate limits)
                    holdings_tasks = [
                        self._analyze_symbol(
                            symbol=position.symbol,
                            user_id=user_id,
                            analysis_type="holding",
                            holding_quantity=int(position.quantity),
                        )
                        for position in positions
                    ]

                    # Process in batches of 5
                    batch_size = 5
                    for i in range(0, len(holdings_tasks), batch_size):
                        batch = holdings_tasks[i : i + batch_size]
                        results = await asyncio.gather(*batch, return_exceptions=True)

                        for idx, result in enumerate(results):
                            if isinstance(result, Exception):
                                symbol = positions[i + idx].symbol
                                logger.error(
                                    "Failed to analyze holding",
                                    symbol=symbol,
                                    error=str(result),
                                )
                                analysis_results["errors"].append(
                                    {"type": "holding", "symbol": symbol}
                                )
                            elif result:
                                analysis_results["holdings_analyzed"] += 1
                            else:
                                symbol = positions[i + idx].symbol
                                analysis_results["errors"].append(
                                    {"type": "holding", "symbol": symbol}
                                )

            # 5. Analyze watchlist items - BATCH PROCESSING
            if watchlist_items:
                if dry_run:
                    for watchlist_item in watchlist_items:
                        logger.info(
                            "Dry run - would analyze watchlist item",
                            symbol=watchlist_item.symbol,
                        )
                        analysis_results["watchlist_analyzed"] += 1
                else:
                    # Batch process watchlist (5 concurrent max)
                    watchlist_tasks = [
                        self._analyze_symbol(
                            symbol=watchlist_item.symbol,
                            user_id=user_id,
                            analysis_type="watchlist",
                        )
                        for watchlist_item in watchlist_items
                    ]

                    # Process in batches of 5
                    batch_size = 5
                    for i in range(0, len(watchlist_tasks), batch_size):
                        batch = watchlist_tasks[i : i + batch_size]
                        results = await asyncio.gather(*batch, return_exceptions=True)

                        for idx, result in enumerate(results):
                            watchlist_item = watchlist_items[i + idx]
                            if isinstance(result, Exception):
                                logger.error(
                                    "Failed to analyze watchlist item",
                                    symbol=watchlist_item.symbol,
                                    error=str(result),
                                )
                                analysis_results["errors"].append(
                                    {
                                        "type": "watchlist",
                                        "symbol": watchlist_item.symbol,
                                    }
                                )
                            elif result:
                                analysis_results["watchlist_analyzed"] += 1
                                # Update last_analyzed_at timestamp
                                await self.watchlist_repo.update_last_analyzed(
                                    watchlist_item.watchlist_id,
                                    user_id,
                                    datetime.utcnow(),
                                )
                            else:
                                analysis_results["errors"].append(
                                    {
                                        "type": "watchlist",
                                        "symbol": watchlist_item.symbol,
                                    }
                                )

            # 6. Analyze market movers - BATCH PROCESSING
            if market_movers_symbols:
                if dry_run:
                    for symbol in market_movers_symbols:
                        logger.info(
                            "Dry run - would analyze market mover", symbol=symbol
                        )
                        analysis_results["market_movers_analyzed"] += 1
                else:
                    # Batch process market movers (5 concurrent max)
                    movers_tasks = [
                        self._analyze_symbol(
                            symbol=symbol,
                            user_id=user_id,
                            analysis_type="market_mover",
                        )
                        for symbol in market_movers_symbols
                    ]

                    # Process in batches of 5
                    batch_size = 5
                    for i in range(0, len(movers_tasks), batch_size):
                        batch = movers_tasks[i : i + batch_size]
                        results = await asyncio.gather(*batch, return_exceptions=True)

                        for idx, result in enumerate(results):
                            symbol = market_movers_symbols[i + idx]
                            if isinstance(result, Exception):
                                logger.error(
                                    "Failed to analyze market mover",
                                    symbol=symbol,
                                    error=str(result),
                                )
                                analysis_results["errors"].append(
                                    {"type": "market_mover", "symbol": symbol}
                                )
                            elif result:
                                analysis_results["market_movers_analyzed"] += 1
                            else:
                                analysis_results["errors"].append(
                                    {"type": "market_mover", "symbol": symbol}
                                )

            # Calculate total
            analysis_results["total_symbols_analyzed"] = (
                analysis_results["holdings_analyzed"]
                + analysis_results["watchlist_analyzed"]
                + analysis_results["market_movers_analyzed"]
            )

            logger.info(
                "User portfolio analysis completed",
                user_id=user_id,
                total_analyzed=analysis_results["total_symbols_analyzed"],
                holdings=analysis_results["holdings_analyzed"],
                watchlist=analysis_results["watchlist_analyzed"],
                market_movers=analysis_results["market_movers_analyzed"],
                errors=len(analysis_results["errors"]),
            )

        except Exception as e:
            logger.error(
                "Portfolio analysis failed",
                user_id=user_id,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            analysis_results["errors"].append({"type": "general", "error": str(e)})

        return analysis_results

    async def _analyze_symbol(
        self,
        symbol: str,
        user_id: str,
        analysis_type: str,
        holding_quantity: int | None = None,
    ) -> bool:
        """
        Analyze a single symbol using the ReAct agent.

        Args:
            symbol: Stock symbol to analyze
            user_id: User ID (use "portfolio_agent" for system analysis)
            analysis_type: Type of analysis (holding, watchlist, market_mover)
            holding_quantity: Current holding quantity (for holdings only)

        Returns:
            True if analysis succeeded, False otherwise
        """
        try:
            # Generate analysis_id for tracking
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            analysis_id = f"{symbol}_{analysis_type}_{timestamp}"

            logger.info(
                "Analyzing symbol",
                symbol=symbol,
                user_id=user_id,
                analysis_type=analysis_type,
                analysis_id=analysis_id,
            )

            # Get symbol-specific chat ID BEFORE building prompt (needed for context retrieval)
            chat_id = await self._get_symbol_chat_id(symbol, user_id)

            # Fetch historical messages for context management (sliding window + summary)
            historical_messages = await self.message_repo.get_by_chat(chat_id)

            # Build prompt based on analysis type
            if analysis_type == "holding":
                prompt = f"""Analyze my current holding of {holding_quantity} shares of {symbol}. Provide:

1. Technical Analysis: Use Fibonacci retracement, trend analysis, and technical indicators
2. Fundamental Data: Company fundamentals, earnings, news sentiment
3. Trading Decision: Should I:
   - BUY more (if strong bullish signals)
   - SELL (if strong bearish signals or take profit)
   - HOLD (if neutral or long-term hold)
4. Position Size: If BUY/SELL, suggest percentage (e.g., 5%, 10%)

Provide clear reasoning for your trading decision.
Format:
DECISION: [BUY/SELL/HOLD]
POSITION_SIZE: [percentage if BUY/SELL, or N/A if HOLD]
REASONING: [your analysis]
"""
            elif analysis_type == "watchlist":
                prompt = f"""Analyze the watchlist symbol {symbol} for potential entry. Provide:

1. Technical Analysis: Fibonacci levels, trends, technical indicators
2. Fundamental Data: Company info, earnings, news sentiment
3. Trading Decision: Recommend one of:
   - BUY (if good entry point)
   - SELL (if already own, or avoid)
   - HOLD (if wait for better entry)
4. Position Size: If BUY, suggest percentage (e.g., 5%, 10%)

Format:
DECISION: [BUY/SELL/HOLD]
POSITION_SIZE: [percentage if BUY, or N/A]
REASONING: [your analysis]
"""
            else:  # market_mover
                prompt = f"""Analyze the market mover {symbol} (top gainer/loser/active today). Provide:

1. Why it's moving: News, earnings, market sentiment
2. Technical Analysis: Is the move sustainable?
3. Trading Decision: Recommend one of:
   - BUY (if momentum continues)
   - SELL (if reversal likely)
   - HOLD (if wait and see)
4. Position Size: If BUY/SELL, suggest percentage

Format:
DECISION: [BUY/SELL/HOLD]
POSITION_SIZE: [percentage if BUY/SELL, or N/A]
REASONING: [your analysis]
"""

            # Apply context window management (sliding window + summary)
            # This provides historical context automatically
            conversation_history = []
            if historical_messages:
                total_tokens = self.context_manager.calculate_context_tokens(historical_messages)
                model = getattr(self.settings, "dashscope_model", "qwen-plus")

                if self.context_manager.should_compact(total_tokens, model=model):
                    logger.info(
                        "Context compaction triggered",
                        symbol=symbol,
                        total_tokens=total_tokens,
                        message_count=len(historical_messages),
                    )

                    # Extract HEAD, BODY, TAIL
                    head, body, tail = self.context_manager.extract_context_structure(historical_messages)

                    # Summarize BODY
                    summary_text = await self.context_manager.summarize_history(
                        body_messages=body,
                        symbol=symbol,
                        llm_service=self.react_agent,
                    )

                    # Reconstruct compacted context
                    compacted_messages = self.context_manager.reconstruct_context(
                        head=head,
                        summary_text=summary_text,
                        tail=tail,
                    )

                    for msg in compacted_messages:
                        conversation_history.append({"role": msg.role, "content": msg.content})

                    logger.info(
                        "Context compacted successfully",
                        symbol=symbol,
                        original_tokens=total_tokens,
                        compacted_count=len(compacted_messages),
                    )
                else:
                    # Use full history (under threshold)
                    for msg in historical_messages:
                        conversation_history.append({"role": msg.role, "content": msg.content})

            # Add current prompt to conversation
            conversation_history.append({"role": "user", "content": prompt})

            # Create pending transaction for credit tracking (if enabled)
            transaction = None
            if self.credit_service:
                try:
                    transaction = await self.credit_service.create_pending_transaction(
                        user_id="portfolio_agent",
                        chat_id=chat_id if 'chat_id' in locals() else analysis_id,  # Use analysis_id temporarily
                        estimated_cost=10.0,  # Estimated cost for portfolio analysis
                        model=self.settings.dashscope_model,
                    )
                    logger.info(
                        "Created pending transaction for portfolio analysis",
                        transaction_id=transaction.transaction_id,
                        symbol=symbol,
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to create pending transaction - continuing without credit tracking",
                        error=str(e),
                        symbol=symbol,
                    )

            # Invoke agent with conversation history (sliding window + summary applied)
            logger.info(
                "Invoking agent for analysis",
                symbol=symbol,
                conversation_history_length=len(conversation_history),
            )
            response = await self.react_agent.ainvoke(prompt, conversation_history=conversation_history)

            # Parse response
            if isinstance(response, dict) and "final_answer" in response:
                response_text = response["final_answer"]
            else:
                response_text = str(response)

            # Extract token usage from response (LangGraph format)
            input_tokens = 0
            output_tokens = 0
            if isinstance(response, dict):
                usage = response.get("usage", {})
                input_tokens = usage.get("input_tokens", 0)
                output_tokens = usage.get("output_tokens", 0)
                logger.info(
                    "Token usage extracted",
                    symbol=symbol,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )

            # Extract decision and position size
            decision = "HOLD"
            position_size = None

            if "DECISION:" in response_text:
                decision_line = [
                    line for line in response_text.split("\n") if "DECISION:" in line
                ][0]
                if "BUY" in decision_line.upper():
                    decision = "BUY"
                elif "SELL" in decision_line.upper():
                    decision = "SELL"

            if "POSITION_SIZE:" in response_text:
                import re

                size_line = [
                    line
                    for line in response_text.split("\n")
                    if "POSITION_SIZE:" in line
                ][0]
                match = re.search(r"(\d+)%", size_line)
                if match:
                    position_size = int(match.group(1))

            # Create analysis message
            # Note: chat_id already retrieved earlier for context management
            emoji_map = {
                "holding": "💼",
                "watchlist": "👀",
                "market_mover": "📈",
            }
            emoji = emoji_map.get(analysis_type, "📊")

            message_content = f"## {emoji} Portfolio Agent Analysis - {symbol}\n\n"
            message_content += f"**Type:** {analysis_type.replace('_', ' ').title()}\n"
            message_content += f"**Decision:** {decision}\n"
            if position_size:
                message_content += f"**Position Size:** {position_size}%\n"
            if holding_quantity:
                message_content += f"**Current Holding:** {holding_quantity} shares\n"
            message_content += f"**Analysis ID:** {analysis_id}\n\n"
            message_content += f"{response_text}\n"

            metadata = MessageMetadata(
                symbol=symbol,
                interval="1d",
                analysis_id=analysis_id,
                trend_direction=(
                    decision.lower() if decision in ["BUY", "SELL"] else None
                ),
            )

            message_create = MessageCreate(
                chat_id=chat_id,
                role="assistant",
                content=message_content,
                source="llm",
                metadata=metadata,
            )
            message = await self.message_repo.create(message_create)

            # Complete transaction with actual token usage (if credit tracking enabled)
            if self.credit_service and transaction:
                try:
                    updated_transaction, updated_user = (
                        await self.credit_service.complete_transaction_with_deduction(
                            transaction_id=transaction.transaction_id,
                            message_id=message.message_id,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            model=self.settings.dashscope_model,
                            thinking_enabled=False,  # Portfolio agent doesn't use thinking mode
                        )
                    )

                    if updated_transaction and updated_user:
                        logger.info(
                            "Transaction completed for portfolio analysis",
                            transaction_id=updated_transaction.transaction_id,
                            actual_cost=updated_transaction.actual_cost,
                            remaining_credits=updated_user.credits,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                        )
                    else:
                        logger.warning(
                            "Failed to complete transaction for portfolio analysis",
                            transaction_id=transaction.transaction_id,
                        )
                except Exception as e:
                    logger.error(
                        "Error completing transaction",
                        error=str(e),
                        transaction_id=transaction.transaction_id,
                    )

            logger.info(
                "Symbol analysis completed",
                symbol=symbol,
                analysis_type=analysis_type,
                decision=decision,
                position_size=position_size,
            )

            # Place order if decision is BUY or SELL
            if decision in ["BUY", "SELL"] and position_size and self.trading_service:
                try:
                    # Calculate quantity based on position_size percentage and portfolio value
                    account_summary = await self.trading_service.get_account_summary(
                        user_id
                    )
                    portfolio_value = account_summary.equity

                    # Get current stock price
                    try:
                        quote = await self.market_service.get_quote(symbol)
                        stock_price = quote.get("price", 0)
                    except Exception:
                        # Fallback: use Alpaca's latest trade
                        latest_trade = self.trading_service.client.get_latest_trade(
                            symbol
                        )
                        stock_price = float(latest_trade.price)

                    # Calculate shares: (portfolio_value * position_size%) / stock_price
                    dollar_amount = portfolio_value * (position_size / 100)
                    quantity = int(dollar_amount / stock_price) if stock_price > 0 else 1

                    # Minimum 1 share, maximum 10% of portfolio
                    quantity = max(1, min(quantity, int(portfolio_value * 0.1 / stock_price)))

                    logger.info(
                        "Placing order via Alpaca",
                        symbol=symbol,
                        side=decision.lower(),
                        quantity=quantity,
                        position_size_pct=position_size,
                        dollar_amount=dollar_amount,
                        stock_price=stock_price,
                        analysis_type=analysis_type,
                    )

                    order = await self.trading_service.place_market_order(
                        symbol=symbol,
                        quantity=quantity,
                        side=decision.lower(),
                        analysis_id=analysis_id,
                        chat_id=chat_id,
                        user_id=user_id,
                        message_id=message.message_id if message else None,
                    )

                    # Persist order to MongoDB
                    await self.order_repo.create(order)

                    logger.info(
                        "Order placed and persisted",
                        symbol=symbol,
                        order_id=order.alpaca_order_id,
                    )

                    # Update message metadata with order_id
                    if message:
                        metadata.order_placed = True
                        metadata.order_id = order.alpaca_order_id
                        await self.message_repo.update_metadata(
                            message.message_id, metadata
                        )

                except Exception as e:
                    logger.error(
                        "Failed to place order",
                        symbol=symbol,
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                    # Don't fail analysis if order placement fails

            return True

        except Exception as e:
            logger.error(
                "Symbol analysis failed",
                symbol=symbol,
                analysis_type=analysis_type,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            return False

    async def _get_symbol_chat_id(self, symbol: str, user_id: str = "portfolio_agent") -> str:
        """
        Get or create a dedicated chat for this symbol.

        CRITICAL: Portfolio agent chats MUST be owned by "portfolio_agent" user, NOT individual users.

        This ensures:
        1. Chats appear in Portfolio Dashboard only (not personal chat)
        2. All users see the same portfolio analysis history
        3. No chat duplication across users
        4. Proper auth isolation between personal and portfolio chats

        Args:
            symbol: Stock symbol
            user_id: MUST be "portfolio_agent" (system user) - defaults to "portfolio_agent"

        Returns:
            Chat ID for this symbol
        """
        # Force portfolio_agent as owner (ignore passed user_id for safety)
        owner_id = "portfolio_agent"

        # Try to find existing chat for this symbol
        chats = await self.chat_repo.list_by_user(owner_id)
        for chat in chats:
            if chat.title and chat.title.startswith(f"{symbol} "):
                logger.info(
                    "Found existing chat for symbol",
                    symbol=symbol,
                    owner=owner_id,
                    chat_id=chat.chat_id,
                )
                return chat.chat_id

        # Create new chat for this symbol
        chat_create = ChatCreate(
            title=f"{symbol} Analysis",
            user_id=owner_id,
        )
        chat = await self.chat_repo.create(chat_create)
        logger.info(
            "Created new chat for symbol",
            symbol=symbol,
            owner=owner_id,
            chat_id=chat.chat_id,
        )
        return chat.chat_id

    async def _store_execution_record(self, execution_data: dict[str, Any]) -> None:
        """
        Store execution record in MongoDB.

        Args:
            execution_data: Execution result data
        """
        try:
            collection = self.mongodb.get_collection("portfolio_analysis_runs")
            await collection.insert_one(execution_data)

            logger.info(
                "Execution record stored",
                run_id=execution_data["run_id"],
            )

        except Exception as e:
            logger.error(
                "Failed to store execution record",
                run_id=execution_data.get("run_id"),
                error=str(e),
                error_type=type(e).__name__,
            )
            # Don't raise - execution succeeded even if record storage failed
