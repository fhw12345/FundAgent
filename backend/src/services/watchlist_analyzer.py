"""
Watchlist Analyzer Service.

Automated analysis scheduler that runs Fibonacci analysis
on watchlist symbols every 5 minutes.
"""

import asyncio
from datetime import datetime

import structlog
from motor.motor_asyncio import AsyncIOMotorCollection

from ..core.config import Settings
from ..core.financial_analysis import FibonacciAnalyzer
from ..database.redis import RedisCache
from ..database.repositories.chat_repository import ChatRepository
from ..database.repositories.message_repository import MessageRepository
from ..database.repositories.watchlist_repository import WatchlistRepository
from ..models.chat import ChatCreate
from ..models.message import MessageCreate, MessageMetadata
from .context_window_manager import ContextWindowManager

logger = structlog.get_logger()


class WatchlistAnalyzer:
    """Automated watchlist analysis service."""

    def __init__(
        self,
        watchlist_collection: AsyncIOMotorCollection,
        messages_collection: AsyncIOMotorCollection,
        chats_collection: AsyncIOMotorCollection,
        redis_cache: RedisCache,
        market_service,  # AlphaVantageMarketDataService for market data
        settings: Settings,  # Application settings for context management
        agent=None,  # LLM agent for analysis
        trading_service=None,  # Alpaca trading service for order placement
        order_repository=None,  # Repository for persisting orders to MongoDB
    ):
        """Initialize watchlist analyzer."""
        self.watchlist_repo = WatchlistRepository(watchlist_collection)
        self.message_repo = MessageRepository(messages_collection)
        self.chat_repo = ChatRepository(chats_collection)
        self.redis_cache = redis_cache
        self.market_service = market_service
        self.settings = settings
        self.agent = agent
        self.trading_service = trading_service
        self.order_repository = order_repository
        self.is_running = False
        self._task = None

        # Initialize context window manager for history management
        self.context_manager = ContextWindowManager(settings)

    async def _get_symbol_chat_id(self, symbol: str) -> str:
        """
        Get or create a dedicated chat for this symbol.

        Each symbol gets its own chat (e.g., "XIACY Analysis") where all
        analyses for that symbol are stored as messages.

        Args:
            symbol: Stock symbol (e.g., "XIACY", "MSFT")

        Returns:
            Chat ID for this symbol
        """
        # Try to find existing chat for this symbol
        # Search by title pattern: "{symbol} Analysis"
        chats = await self.chat_repo.list_by_user("portfolio_agent")
        for chat in chats:
            if chat.title and chat.title.startswith(f"{symbol} "):
                logger.info(
                    "Found existing chat for symbol",
                    symbol=symbol,
                    chat_id=chat.chat_id,
                )
                return chat.chat_id

        # Create new chat for this symbol
        chat_create = ChatCreate(title=f"{symbol} Analysis", user_id="portfolio_agent")
        chat = await self.chat_repo.create(chat_create)
        logger.info("Created new chat for symbol", symbol=symbol, chat_id=chat.chat_id)
        return chat.chat_id

    async def analyze_symbol(
        self, symbol: str, user_id: str = "default_user", analysis_id: str | None = None
    ) -> bool:
        """
        Run LLM agent analysis on a single symbol with MCP tools.

        Args:
            symbol: Stock symbol to analyze
            user_id: User ID for the analysis
            analysis_id: Optional analysis ID for grouping

        Returns:
            True if analysis succeeded, False otherwise
        """
        try:
            # Generate analysis_id if not provided (format: symbol_YYYYMMDD_HHMMSS)
            if analysis_id is None:
                from datetime import datetime

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                analysis_id = f"{symbol}_{timestamp}"

            logger.info(
                "Running agent-based analysis",
                symbol=symbol,
                user_id=user_id,
                analysis_id=analysis_id,
                has_agent=self.agent is not None,
            )

            # If no agent, fall back to basic Fibonacci
            if not self.agent:
                logger.warning(
                    "No agent available, falling back to basic Fibonacci analysis",
                    symbol=symbol,
                )
                return await self._fallback_fibonacci_analysis(symbol, analysis_id)

            # Use LLM agent for comprehensive analysis
            prompt = f"""Analyze the stock symbol {symbol} and provide:

1. Technical Analysis: Use Fibonacci retracement, trend analysis, and any other technical indicators
2. Fundamental Data: Use AlphaVantage MCP tools to get company fundamentals, earnings, news sentiment
3. Trading Decision: Based on the analysis, recommend one of:
   - BUY (if strong bullish signals)
   - SELL (if strong bearish signals)
   - HOLD (if neutral or unclear)
4. Position Size: If BUY or SELL, suggest a position size (percentage of portfolio, e.g., 5%, 10%)

Provide a concise analysis with clear reasoning for your trading decision.
Format your response as:
DECISION: [BUY/SELL/HOLD]
POSITION_SIZE: [percentage if BUY/SELL, or N/A if HOLD]
REASONING: [your analysis]
"""

            # Get symbol-specific chat ID (one chat per symbol) - BEFORE invoking agent
            chat_id = await self._get_symbol_chat_id(symbol)

            # Fetch historical messages for context management
            historical_messages = await self.message_repo.get_by_chat(chat_id)

            # Prepare conversation history for agent
            conversation_history = []

            if historical_messages:
                # Calculate total tokens
                total_tokens = self.context_manager.calculate_context_tokens(
                    historical_messages
                )

                # Check if compaction is needed (> 50% of context limit)
                model = getattr(self.settings, "default_llm_model", "qwen-plus")
                should_compact = self.context_manager.should_compact(
                    total_tokens, model=model
                )

                if should_compact:
                    logger.info(
                        "Context compaction triggered",
                        symbol=symbol,
                        total_tokens=total_tokens,
                        message_count=len(historical_messages),
                    )

                    # Extract HEAD, BODY, TAIL structure
                    head, body, tail = self.context_manager.extract_context_structure(
                        historical_messages
                    )

                    # Summarize BODY using LLM
                    summary_text = await self.context_manager.summarize_history(
                        body_messages=body,
                        symbol=symbol,
                        llm_service=self.agent,  # Use the agent's LLM for summarization
                    )

                    # Persist summary message to database
                    if summary_text and body:
                        summary_metadata = MessageMetadata(
                            symbol=symbol,
                            is_summary=True,
                            summarized_message_count=len(body),
                        )
                        summary_message_create = MessageCreate(
                            chat_id=chat_id,
                            role="assistant",
                            content=f"## 📋 Analysis History Summary\n\n{summary_text}",
                            source="llm",
                            metadata=summary_metadata,
                        )
                        await self.message_repo.create(summary_message_create)

                        # Delete old messages, keeping last N (tail_messages_keep)
                        keep_count = self.settings.tail_messages_keep
                        deleted_count = (
                            await self.message_repo.delete_old_messages_keep_recent(
                                chat_id=chat_id,
                                keep_count=keep_count,
                                exclude_summaries=True,
                            )
                        )

                        logger.info(
                            "Compaction persisted and old messages deleted",
                            symbol=symbol,
                            summarized_count=len(body),
                            deleted_count=deleted_count,
                            kept_count=keep_count,
                        )

                    # Reconstruct compacted context
                    compacted_messages = self.context_manager.reconstruct_context(
                        head=head, summary_text=summary_text, tail=tail
                    )

                    # Convert to conversation_history format
                    for msg in compacted_messages:
                        conversation_history.append(
                            {"role": msg.role, "content": msg.content}
                        )

                    logger.info(
                        "Context compacted successfully",
                        symbol=symbol,
                        original_count=len(historical_messages),
                        compacted_count=len(compacted_messages),
                        compression_ratio=round(
                            len(compacted_messages) / len(historical_messages), 3
                        ),
                    )
                else:
                    # No compaction needed - use full history
                    for msg in historical_messages:
                        conversation_history.append(
                            {"role": msg.role, "content": msg.content}
                        )

                    logger.info(
                        "Using full conversation history",
                        symbol=symbol,
                        total_tokens=total_tokens,
                        message_count=len(historical_messages),
                    )

            logger.info(
                "Invoking agent for analysis",
                symbol=symbol,
                conversation_history_length=len(conversation_history),
            )

            # Invoke agent with conversation history
            response = await self.agent.ainvoke(
                prompt, conversation_history=conversation_history
            )

            logger.info(
                "Agent analysis complete",
                symbol=symbol,
                response_length=len(str(response)),
            )

            # Parse agent response - extract final_answer from dict response
            if isinstance(response, dict) and "final_answer" in response:
                response_text = response["final_answer"]
            else:
                response_text = str(response)

            # Extract decision
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
                size_line = [
                    line
                    for line in response_text.split("\n")
                    if "POSITION_SIZE:" in line
                ][0]
                # Extract percentage (e.g., "5%" or "5") - match number followed by %
                import re

                match = re.search(r"(\d+)%", size_line)
                if match:
                    position_size = int(match.group(1))

            # Create analysis message
            message_content = f"## 🤖 AI Agent Analysis - {symbol}\n\n"
            message_content += f"**Decision:** {decision}\n"
            if position_size:
                message_content += f"**Position Size:** {position_size}%\n"
            message_content += f"**Analysis ID:** {analysis_id}\n\n"
            message_content += f"{response_text}\n"

            metadata = MessageMetadata(
                symbol=symbol,
                interval="1d",
                analysis_id=analysis_id,
                # Add decision metadata for order placement
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

            logger.info(
                "Agent analysis completed",
                symbol=symbol,
                decision=decision,
                position_size=position_size,
                analysis_id=analysis_id,
            )

            # Place order if decision is BUY or SELL
            if decision in ["BUY", "SELL"] and position_size and self.trading_service:
                try:
                    # For now, use a fixed quantity of 1 share
                    # TODO: Calculate quantity based on position_size percentage and portfolio value
                    quantity = 1

                    logger.info(
                        "Placing order via Alpaca",
                        symbol=symbol,
                        side=decision.lower(),
                        quantity=quantity,
                        analysis_id=analysis_id,
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

                    # Persist order to MongoDB for audit trail
                    if self.order_repository:
                        await self.order_repository.create(order)
                        logger.info(
                            "Order persisted to MongoDB", order_id=order.order_id
                        )
                    else:
                        logger.warning(
                            "Order repository not available - order not persisted to MongoDB"
                        )

                    logger.info(
                        "Order placed successfully",
                        symbol=symbol,
                        order_id=order.alpaca_order_id,
                        analysis_id=analysis_id,
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
                    # Don't fail the whole analysis if order placement fails

            return True

        except Exception as e:
            logger.error(
                "Agent analysis failed",
                symbol=symbol,
                error=str(e),
                error_type=type(e).__name__,
            )
            return False

    async def _fallback_fibonacci_analysis(self, symbol: str, analysis_id: str) -> bool:
        """Fallback to basic Fibonacci analysis if agent not available."""
        try:
            from datetime import datetime, timedelta

            analyzer = FibonacciAnalyzer(self.market_service)
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=180)

            result = await analyzer.analyze(
                symbol=symbol,
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
                timeframe="1d",
            )

            trend = (
                result.market_structure.trend_direction
                if result.market_structure
                else None
            )
            levels = (
                [level.price for level in result.fibonacci_levels[:5]]
                if result.fibonacci_levels
                else []
            )

            metadata = MessageMetadata(
                symbol=symbol,
                interval="1d",
                trend_direction=trend,
                key_levels=levels,
                analysis_id=analysis_id,
            )

            chat_id = await self._get_symbol_chat_id(symbol)

            message_content = f"## 📊 Fibonacci Analysis - {symbol}\n\n"
            message_content += f"**Trend:** {trend or 'Unknown'}\n"
            message_content += f"**Period:** {start_date} to {end_date}\n"
            message_content += f"**Confidence:** {result.confidence_score:.2%}\n"

            message_create = MessageCreate(
                chat_id=chat_id,
                role="assistant",
                content=message_content,
                source="llm",
                metadata=metadata,
            )
            await self.message_repo.create(message_create)

            logger.info(
                "Fallback Fibonacci analysis completed", symbol=symbol, trend=trend
            )
            return True

        except Exception as e:
            logger.error("Fallback analysis failed", symbol=symbol, error=str(e))
            return False

    async def run_analysis_cycle(self, force: bool = False):
        """
        Run one analysis cycle for all watchlist items.

        Args:
            force: If True, analyze all symbols regardless of last_analyzed_at.
                   If False, only analyze symbols not analyzed in last 5 minutes.
        """
        try:
            logger.info("Starting watchlist analysis cycle", force=force)

            if force:
                # Get ALL watchlist items (manual trigger)
                items = await self.watchlist_repo.get_by_user("default_user")
            else:
                # Get stale items (not analyzed in last 5 minutes)
                items = await self.watchlist_repo.get_stale_items(minutes=5)

            if not items:
                logger.debug("No symbols need analysis")
                return

            logger.info("Found symbols to analyze", count=len(items))

            # Analyze each symbol
            for item in items:
                try:
                    success = await self.analyze_symbol(item.symbol, item.user_id)

                    if not success:
                        logger.warning(
                            "Analysis returned failure",
                            symbol=item.symbol,
                            user_id=item.user_id,
                        )
                except Exception as e:
                    logger.error(
                        "Analysis failed with exception",
                        symbol=item.symbol,
                        user_id=item.user_id,
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                    success = False
                finally:
                    # ALWAYS update last_analyzed_at to prevent infinite retry loops
                    # Even on failure, we don't want to retry immediately
                    await self.watchlist_repo.update_last_analyzed(
                        watchlist_id=item.watchlist_id,
                        user_id=item.user_id,
                        timestamp=datetime.utcnow(),
                    )

                # Small delay between analyses to avoid rate limiting
                await asyncio.sleep(2)

            logger.info("Analysis cycle completed", analyzed=len(items))

        except Exception as e:
            logger.error(
                "Analysis cycle failed",
                error=str(e),
                error_type=type(e).__name__,
            )

    async def start(self):
        """Start the automated analysis scheduler (runs every 5 minutes)."""
        if self.is_running:
            logger.warning("Watchlist analyzer already running")
            return

        self.is_running = True
        logger.info("Starting watchlist analyzer (5-minute cycle)")

        while self.is_running:
            try:
                await self.run_analysis_cycle()

                # Wait 5 minutes until next cycle
                await asyncio.sleep(5 * 60)

            except asyncio.CancelledError:
                logger.info("Watchlist analyzer cancelled")
                break
            except Exception as e:
                logger.error(
                    "Watchlist analyzer error",
                    error=str(e),
                    error_type=type(e).__name__,
                )
                # Wait a bit before retrying on error
                await asyncio.sleep(30)

    async def stop(self):
        """Stop the automated analysis scheduler."""
        logger.info("Stopping watchlist analyzer")
        self.is_running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
