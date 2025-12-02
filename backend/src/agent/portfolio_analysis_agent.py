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
from ..models.trading_decision import (
    SymbolAnalysisResult,
    TradingDecision,
)
from ..services.context_window_manager import ContextWindowManager
from ..services.credit_service import CreditService
from .langgraph_react_agent import FinancialAnalysisReActAgent
from .order_optimizer import OrderOptimizer

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

        # Order optimizer for Phase 2/3 (aggregation and execution)
        self.order_optimizer = OrderOptimizer(
            react_agent=react_agent,
            trading_service=trading_service,
            order_repo=self.order_repo,
            message_repo=self.message_repo,
        )

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
        Run portfolio analysis with Research → Decide → Execute flow.

        Phase 1: Independent symbol research (concurrent, pure analysis)
        Phase 2: Portfolio Agent makes holistic decisions for all symbols
        Phase 3: Execute orders (SELLs first for liquidity, then BUYs)

        Analyzes:
        1. Holdings (current positions)
        2. Watchlist symbols
        (Market movers removed - were informational only, not actionable)

        Args:
            user_id: User identifier
            dry_run: If True, don't write results to DB or execute orders

        Returns:
            Analysis result summary
        """
        logger.info("Analyzing user portfolio", user_id=user_id, dry_run=dry_run)

        result_summary = {
            "user_id": user_id,
            "portfolios_count": 0,
            "holdings_analyzed": 0,
            "watchlist_analyzed": 0,
            "total_symbols_analyzed": 0,
            "decisions_made": 0,
            "orders_executed": 0,
            "orders_failed": 0,
            "orders_skipped": 0,
            "errors": [],
        }

        # Collect all SymbolAnalysisResult for Phase 2 decision making
        all_analysis_results: list[SymbolAnalysisResult] = []

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
                logger.info(
                    "Trading service not available - skipping positions analysis"
                )

            # 2. Get user's watchlist
            watchlist_items = await self.watchlist_repo.get_by_user(user_id)
            logger.info(
                "Retrieved user watchlist",
                user_id=user_id,
                watchlist_count=len(watchlist_items),
            )

            # 3. Build portfolio context (used in Phase 2 for decisions)
            portfolio_context = None
            if self.trading_service:
                try:
                    account_summary = await self.trading_service.get_account_summary(
                        user_id
                    )
                    portfolio_context = {
                        "total_equity": float(account_summary.equity),
                        "buying_power": float(account_summary.buying_power),
                        "cash": float(account_summary.cash),
                        "positions": [
                            {
                                "symbol": pos.symbol,
                                "quantity": int(pos.quantity),
                                "market_value": float(pos.market_value),
                                "unrealized_pl_percent": float(pos.unrealized_pl_pct),
                            }
                            for pos in positions
                        ],
                    }
                    logger.info(
                        "Portfolio context built",
                        equity=portfolio_context["total_equity"],
                        buying_power=portfolio_context["buying_power"],
                        positions_count=len(portfolio_context["positions"]),
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to build portfolio context",
                        error=str(e),
                        error_type=type(e).__name__,
                    )

            # Track analyzed symbols to avoid duplicates (Holdings > Watchlist)
            analyzed_symbols: set[str] = set()

            # ================================================================
            # PHASE 1: Independent Symbol Research (NO portfolio context)
            # ================================================================

            # 4. Analyze holdings - BATCH PROCESSING
            if positions:
                if dry_run:
                    for position in positions:
                        logger.info(
                            "Dry run - would research holding",
                            symbol=position.symbol,
                        )
                        result_summary["holdings_analyzed"] += 1
                        analyzed_symbols.add(position.symbol)
                else:
                    holdings_tasks = [
                        self._analyze_symbol(
                            symbol=position.symbol,
                            user_id=user_id,
                            analysis_type="holding",
                        )
                        for position in positions
                    ]

                    batch_size = 5
                    for i in range(0, len(holdings_tasks), batch_size):
                        batch = holdings_tasks[i : i + batch_size]
                        results = await asyncio.gather(*batch, return_exceptions=True)

                        for idx, result in enumerate(results):
                            symbol = positions[i + idx].symbol
                            if isinstance(result, Exception):
                                logger.error(
                                    "Failed to research holding",
                                    symbol=symbol,
                                    error=str(result),
                                )
                                result_summary["errors"].append(
                                    {"type": "holding", "symbol": symbol}
                                )
                            elif result is not None:
                                all_analysis_results.append(result)
                                result_summary["holdings_analyzed"] += 1
                                analyzed_symbols.add(symbol)
                            else:
                                result_summary["errors"].append(
                                    {"type": "holding", "symbol": symbol}
                                )

            # 5. Analyze watchlist - BATCH PROCESSING (with deduplication)
            if watchlist_items:
                unique_watchlist_items = [
                    item
                    for item in watchlist_items
                    if item.symbol not in analyzed_symbols
                ]

                if len(unique_watchlist_items) < len(watchlist_items):
                    skipped_count = len(watchlist_items) - len(unique_watchlist_items)
                    logger.info(
                        "Skipping watchlist items already analyzed as holdings",
                        skipped_count=skipped_count,
                    )

                if dry_run:
                    for watchlist_item in unique_watchlist_items:
                        logger.info(
                            "Dry run - would research watchlist item",
                            symbol=watchlist_item.symbol,
                        )
                        result_summary["watchlist_analyzed"] += 1
                        analyzed_symbols.add(watchlist_item.symbol)
                else:
                    watchlist_tasks = [
                        self._analyze_symbol(
                            symbol=watchlist_item.symbol,
                            user_id=user_id,
                            analysis_type="watchlist",
                        )
                        for watchlist_item in unique_watchlist_items
                    ]

                    batch_size = 5
                    for i in range(0, len(watchlist_tasks), batch_size):
                        batch = watchlist_tasks[i : i + batch_size]
                        results = await asyncio.gather(*batch, return_exceptions=True)

                        for idx, result in enumerate(results):
                            watchlist_item = unique_watchlist_items[i + idx]
                            if isinstance(result, Exception):
                                logger.error(
                                    "Failed to research watchlist item",
                                    symbol=watchlist_item.symbol,
                                    error=str(result),
                                )
                                result_summary["errors"].append(
                                    {
                                        "type": "watchlist",
                                        "symbol": watchlist_item.symbol,
                                    }
                                )
                            elif result is not None:
                                all_analysis_results.append(result)
                                result_summary["watchlist_analyzed"] += 1
                                analyzed_symbols.add(watchlist_item.symbol)
                                await self.watchlist_repo.update_last_analyzed(
                                    watchlist_item.watchlist_id,
                                    user_id,
                                    datetime.utcnow(),
                                )
                            else:
                                result_summary["errors"].append(
                                    {
                                        "type": "watchlist",
                                        "symbol": watchlist_item.symbol,
                                    }
                                )

            # Calculate total
            result_summary["total_symbols_analyzed"] = (
                result_summary["holdings_analyzed"]
                + result_summary["watchlist_analyzed"]
            )

            logger.info(
                "Phase 1 complete: Symbol research finished",
                user_id=user_id,
                total_analyzed=result_summary["total_symbols_analyzed"],
                holdings=result_summary["holdings_analyzed"],
                watchlist=result_summary["watchlist_analyzed"],
                analysis_results_count=len(all_analysis_results),
            )

            # ================================================================
            # PHASE 2: Portfolio Agent Decision (single holistic call)
            # ================================================================
            if not dry_run and all_analysis_results and portfolio_context:
                logger.info(
                    "Phase 2: Portfolio Agent making holistic decisions",
                    symbols_count=len(all_analysis_results),
                )

                # Get decisions from Portfolio Agent
                trading_decisions = await self._make_portfolio_decisions(
                    symbol_analyses=all_analysis_results,
                    portfolio_context=portfolio_context,
                    user_id=user_id,
                )

                result_summary["decisions_made"] = len(trading_decisions)

                # ================================================================
                # PHASE 3: Order Execution (SELLs first for liquidity, then BUYs)
                # ================================================================
                if trading_decisions:
                    logger.info(
                        "Phase 3: Converting decisions to execution plan",
                        decisions_count=len(trading_decisions),
                    )

                    # Convert TradingDecisions to OrderExecutionPlan via optimizer
                    execution_plan = await self.order_optimizer.optimize_trading_decisions(
                        analysis_results=all_analysis_results,
                        portfolio_context=portfolio_context,
                        user_id=user_id,
                        trading_decisions=trading_decisions,  # Pass pre-made decisions
                    )

                    if execution_plan and execution_plan.orders:
                        logger.info(
                            "Phase 3: Executing orders",
                            orders_count=len(execution_plan.orders),
                            scaling_applied=execution_plan.scaling_applied,
                        )

                        execution_result = (
                            await self.order_optimizer.execute_order_plan(
                                plan=execution_plan,
                                user_id=user_id,
                                analysis_results=all_analysis_results,
                            )
                        )

                        result_summary["orders_executed"] = execution_result.get(
                            "executed", 0
                        )
                        result_summary["orders_failed"] = execution_result.get(
                            "failed", 0
                        )
                        result_summary["orders_skipped"] = execution_result.get(
                            "skipped", 0
                        )

                        logger.info(
                            "Phase 3 complete: Order execution finished",
                            executed=result_summary["orders_executed"],
                            failed=result_summary["orders_failed"],
                            skipped=result_summary["orders_skipped"],
                        )
                    else:
                        logger.info("Phase 3: No actionable orders after optimization")
                else:
                    logger.info("Phase 2: No trading decisions made")

            logger.info(
                "User portfolio analysis completed",
                user_id=user_id,
                total_analyzed=result_summary["total_symbols_analyzed"],
                holdings=result_summary["holdings_analyzed"],
                watchlist=result_summary["watchlist_analyzed"],
                decisions_made=result_summary["decisions_made"],
                orders_executed=result_summary["orders_executed"],
                errors=len(result_summary["errors"]),
            )

        except Exception as e:
            logger.error(
                "Portfolio analysis failed",
                user_id=user_id,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            result_summary["errors"].append({"type": "general", "error": str(e)})

        return result_summary

    async def _analyze_symbol(
        self,
        symbol: str,
        user_id: str,
        analysis_type: str,
    ) -> SymbolAnalysisResult | None:
        """
        Phase 1: Independent symbol research using ReAct agent with tools.

        Pure research without portfolio context or trading decisions.
        Decisions are made holistically in Phase 2 after all analyses complete.

        Args:
            symbol: Stock symbol to analyze
            user_id: User ID (use "portfolio_agent" for system analysis)
            analysis_type: Type of analysis (holding, watchlist)

        Returns:
            SymbolAnalysisResult with analysis text, or None if failed
        """
        try:
            # Generate analysis_id for tracking
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            analysis_id = f"{symbol}_{analysis_type}_{timestamp}"

            logger.info(
                "Phase 1: Starting symbol research",
                symbol=symbol,
                user_id=user_id,
                analysis_type=analysis_type,
                analysis_id=analysis_id,
            )

            # Get symbol-specific chat ID for context retrieval
            chat_id = await self._get_symbol_chat_id(symbol, user_id)

            # Fetch historical messages for context management (sliding window + summary)
            historical_messages = await self.message_repo.get_by_chat(chat_id)

            # Pure research prompt - NO portfolio context, NO trading decisions
            # Decisions will be made in Phase 2 with full portfolio visibility
            prompt = f"""# Symbol Research: {symbol}

Conduct comprehensive technical and fundamental research for {symbol}.

## Research Requirements

1. **Technical Analysis**
   - Fibonacci retracement levels and trend analysis
   - Support and resistance levels
   - Momentum indicators (RSI, MACD, Stochastic)
   - Recent price action and volume patterns

2. **Fundamental Analysis**
   - Company overview and business model
   - Financial health (revenue, earnings, cash flow)
   - News sentiment and recent developments
   - Industry trends and competitive position

3. **Value Assessment**
   - Current valuation metrics (P/E, P/B, etc.)
   - Growth prospects and catalysts
   - Risk factors and concerns
   - Short-term vs long-term outlook

**IMPORTANT**: Provide factual research and analysis only.
Do NOT make buy/sell/hold recommendations - decisions will be made separately
by the Portfolio Agent after reviewing all symbol analyses together.

LANGUAGE REQUIREMENT:
Respond in Simplified Chinese (简体中文).
Technical terms can include English in parentheses for clarity.
"""

            # Apply context window management (sliding window + summary)
            conversation_history = []
            if historical_messages:
                total_tokens = self.context_manager.calculate_context_tokens(
                    historical_messages
                )
                model = getattr(self.settings, "dashscope_model", "qwen-plus")

                if self.context_manager.should_compact(total_tokens, model=model):
                    logger.info(
                        "Context compaction triggered",
                        symbol=symbol,
                        total_tokens=total_tokens,
                        message_count=len(historical_messages),
                    )

                    head, body, tail = self.context_manager.extract_context_structure(
                        historical_messages
                    )
                    summary_text = await self.context_manager.summarize_history(
                        body_messages=body,
                        symbol=symbol,
                        llm_service=self.react_agent,
                    )
                    compacted_messages = self.context_manager.reconstruct_context(
                        head=head,
                        summary_text=summary_text,
                        tail=tail,
                    )

                    for msg in compacted_messages:
                        conversation_history.append(
                            {"role": msg.role, "content": msg.content}
                        )

                    logger.info(
                        "Context compacted successfully",
                        symbol=symbol,
                        original_tokens=total_tokens,
                        compacted_count=len(compacted_messages),
                    )
                else:
                    # Use full history (under threshold)
                    for msg in historical_messages:
                        conversation_history.append(
                            {"role": msg.role, "content": msg.content}
                        )

            # NOTE: Do NOT add prompt to conversation_history here!
            # ainvoke() will add it with language instruction - adding here causes duplicate

            # Create pending transaction for credit tracking (if enabled)
            transaction = None
            if self.credit_service:
                try:
                    transaction = await self.credit_service.create_pending_transaction(
                        user_id="portfolio_agent",
                        chat_id=chat_id,
                        estimated_cost=10.0,
                        model=self.settings.dashscope_model,
                    )
                    logger.info(
                        "Created pending transaction",
                        transaction_id=transaction.transaction_id,
                        symbol=symbol,
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to create pending transaction",
                        error=str(e),
                        symbol=symbol,
                    )

            # Invoke ReAct agent for research (tools enabled)
            logger.info(
                "Invoking agent for symbol research",
                symbol=symbol,
                conversation_history_length=len(conversation_history),
            )
            response = await self.react_agent.ainvoke(
                prompt, conversation_history=conversation_history
            )

            # Parse response
            if isinstance(response, dict) and "final_answer" in response:
                response_text = response["final_answer"]
            else:
                response_text = str(response)

            # Extract token usage
            input_tokens = 0
            output_tokens = 0
            if isinstance(response, dict):
                usage = response.get("usage", {})
                input_tokens = usage.get("input_tokens", 0)
                output_tokens = usage.get("output_tokens", 0)

            # Create analysis message (pure research, no decision)
            emoji_map = {"holding": "💼", "watchlist": "👀"}
            emoji = emoji_map.get(analysis_type, "📊")

            message_content = f"## {emoji} Symbol Research - {symbol}\n\n"
            message_content += f"**Type:** {analysis_type.replace('_', ' ').title()}\n"
            message_content += f"**Analysis ID:** {analysis_id}\n\n"
            message_content += f"{response_text}\n"

            metadata = MessageMetadata(
                symbol=symbol,
                interval="1d",
                analysis_id=analysis_id,
            )

            message_create = MessageCreate(
                chat_id=chat_id,
                role="assistant",
                content=message_content,
                source="llm",
                metadata=metadata,
            )
            message = await self.message_repo.create(message_create)

            # Complete transaction with actual token usage
            if self.credit_service and transaction:
                try:
                    await self.credit_service.complete_transaction_with_deduction(
                        transaction_id=transaction.transaction_id,
                        message_id=message.message_id,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        model=self.settings.dashscope_model,
                        thinking_enabled=False,
                    )
                except Exception as e:
                    logger.error(
                        "Error completing transaction",
                        error=str(e),
                        transaction_id=transaction.transaction_id,
                    )

            logger.info(
                "Phase 1: Symbol research completed",
                symbol=symbol,
                analysis_type=analysis_type,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

            # Return research result (no decision - that comes in Phase 2)
            return SymbolAnalysisResult(
                symbol=symbol,
                analysis_type=analysis_type,
                analysis_text=response_text,
                analysis_id=analysis_id,
                chat_id=chat_id,
                message_id=message.message_id if message else None,
            )

        except Exception as e:
            logger.error(
                "Symbol research failed",
                symbol=symbol,
                analysis_type=analysis_type,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            return None

    async def _make_portfolio_decisions(
        self,
        symbol_analyses: list[SymbolAnalysisResult],
        portfolio_context: dict[str, Any],
        user_id: str,
    ) -> list[TradingDecision]:
        """
        Phase 2: Make all trading decisions in a single holistic call.

        After all symbol research completes, the Portfolio Agent reviews
        everything together and makes decisions for all symbols at once.

        Args:
            symbol_analyses: List of SymbolAnalysisResult from Phase 1
            portfolio_context: Portfolio state (equity, buying_power, positions)
            user_id: User ID for tracking

        Returns:
            List of TradingDecision for all analyzed symbols
        """
        if not symbol_analyses:
            logger.info("No symbol analyses to process for decisions")
            return []

        logger.info(
            "Phase 2: Making portfolio decisions",
            symbols_count=len(symbol_analyses),
            user_id=user_id,
        )

        # Build portfolio state summary
        total_equity = portfolio_context.get("total_equity", 0)
        buying_power = portfolio_context.get("buying_power", 0)
        cash = portfolio_context.get("cash", 0)
        positions = portfolio_context.get("positions", [])

        # Format positions table
        positions_table = "| Symbol | Shares | Market Value | P/L % |\n"
        positions_table += "|--------|--------|--------------|-------|\n"
        if positions:
            for pos in positions:
                positions_table += f"| {pos['symbol']} | {pos['quantity']} | ${pos['market_value']:,.2f} | {pos['unrealized_pl_percent']:.2f}% |\n"
        else:
            positions_table += "| (No positions) | - | - | - |\n"

        # Format all symbol analyses
        analyses_section = ""
        for result in symbol_analyses:
            analyses_section += (
                f"\n### {result.symbol} ({result.analysis_type.title()})\n"
            )
            analyses_section += f"{result.analysis_text}\n"
            analyses_section += "---\n"

        # Build the holistic decision prompt
        decision_prompt = f"""# Portfolio Trading Decisions

You are a Portfolio Manager. Review ALL the symbol research below and make trading decisions
considering the overall portfolio optimization, diversification, and risk management.

## Current Portfolio State

**Account Summary:**
- Total Equity: ${total_equity:,.2f}
- Buying Power: ${buying_power:,.2f}
- Cash: ${cash:,.2f}

**Current Holdings:**
{positions_table}

## Symbol Research Results
{analyses_section}

## Decision Rules

For EACH analyzed symbol, decide ONE action:

- **BUY**: Add new position or increase existing
  - position_size_percent = % of BUYING POWER to spend
  - Example: 10% means spend 10% of ${buying_power:,.2f} = ${buying_power * 0.1:,.2f}

- **SELL**: Reduce or exit position (MUST be a current holding)
  - position_size_percent = % of CURRENT HOLDING to sell
  - Example: 50% of 100 shares = sell 50 shares
  - SELLs execute FIRST to gain liquidity for BUYs

- **HOLD**: No action needed
  - position_size_percent should be null

## Important Considerations

1. **Liquidity First**: SELL orders execute before BUYs to free up buying power
2. **Diversification**: Avoid over-concentration in any single position
3. **Risk Management**: Consider correlation between positions
4. **Position Sizing**: Use confidence level to scale position sizes
5. **Holdings vs Watchlist**: Holdings can be SELL/HOLD; Watchlist can be BUY/HOLD

Provide a decision for EVERY symbol in the research above.
Include short reasoning (1-2 sentences) for each decision.
"""

        try:
            # Import the schema here to avoid circular imports
            from ..models.trading_decision import PortfolioDecisionList

            # Single structured call for all decisions
            decision_result = await self.react_agent.ainvoke_structured(
                prompt=decision_prompt,
                schema=PortfolioDecisionList,
                context=None,  # Context is embedded in prompt
            )

            logger.info(
                "Phase 2: Portfolio decisions completed",
                decisions_count=len(decision_result.decisions),
                assessment_preview=decision_result.portfolio_assessment[:100],
            )

            return decision_result.decisions

        except Exception as e:
            logger.error(
                "Phase 2: Failed to make portfolio decisions",
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            # Return empty list on failure - no orders will be executed
            return []

    async def _get_symbol_chat_id(
        self, symbol: str, user_id: str = "portfolio_agent"
    ) -> str:
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
