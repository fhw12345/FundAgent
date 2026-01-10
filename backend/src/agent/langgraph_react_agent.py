"""
LangGraph ReAct Agent with SDK Auto-Loop and Tool Compression.

This module implements a flexible ReAct agent using LangGraph's create_react_agent
SDK for autonomous tool chaining without rigid routing logic.

Key Features:
- Auto-loop: LLM dynamically decides tool sequence
- Tool compression: Results limited to 2-3 lines for context efficiency
- Message history: MemorySaver checkpointer for conversation continuity
- Langfuse integration: Automatic tracing via callback handler

Architecture:
    SDK ReAct Approach (this file):
        User Query → ReAct Loop (auto) → Final Answer
                     ├─ LLM reasons
                     ├─ Calls tool(s)
                     ├─ Observes results
                     └─ Decides: More tools OR Final answer

Key Benefits:
- LLM-driven routing (autonomous tool selection)
- Automatic tool chaining based on context
- Built-in message history management (MemorySaver)
- Compressed tool results (99.5% token reduction)
- Minimal code footprint (~300 lines)

Design Philosophy:
- Flexibility over control (LLM decides tool sequence)
- Message-based state (simpler than custom TypedDict)
- Trust the SDK (leverage LangGraph's built-in patterns)
"""

import asyncio
import random
import time
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

import structlog

# Patch DashScope error handling BEFORE importing ChatTongyi
from ..core.utils.dashscope_fix import patch_tongyi_check_response

patch_tongyi_check_response()

from langchain_community.chat_models import ChatTongyi
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from ..core.analysis.fibonacci.analyzer import FibonacciAnalyzer
from ..core.analysis.stochastic_analyzer import StochasticAnalyzer
from ..core.config import Settings
from ..core.data.ticker_data_service import TickerDataService
from ..core.localization import (
    DEFAULT_LANGUAGE,
    SupportedLanguage,
    get_brief_language_instruction,
)
from ..core.utils import extract_token_usage_from_messages
from ..services.alphavantage_response_formatter import AlphaVantageResponseFormatter
from ..services.data_manager import DataManager
from ..services.insights import InsightsCategoryRegistry
from ..services.insights.snapshot_service import InsightsSnapshotService
from ..services.market_data import FREDService
from ..services.tool_cache_wrapper import ToolCacheWrapper
from .llm_client import FINANCIAL_AGENT_SYSTEM_PROMPT
from .tools.alpha_vantage_tools import create_alpha_vantage_tools
from .tools.insights_tools import create_insights_tools
from .tools.pcr_tools import create_pcr_tools

logger = structlog.get_logger()

# Conditional import for Langfuse (skip in CI/tests)
if TYPE_CHECKING:
    from langfuse.langchain import CallbackHandler

try:
    from langfuse import Langfuse
    from langfuse.langchain import CallbackHandler as LangfuseCallbackHandler

    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    LangfuseCallbackHandler = None
    Langfuse = None
    logger.warning("Langfuse not available - observability disabled")


# ================================
# FinancialAnalysisReActAgent (SDK-Based)
# ================================
class FinancialAnalysisReActAgent:
    """
    LangGraph SDK-based ReAct agent for financial analysis.

    Uses create_react_agent for flexible, LLM-driven tool orchestration
    without explicit routing logic.
    """

    def __init__(
        self,
        settings: Settings,
        ticker_data_service: TickerDataService,
        market_service,  # AlphaVantageMarketDataService for market data
        tool_cache_wrapper: ToolCacheWrapper | None = None,
        redis_cache=None,  # RedisCache for insights caching
        snapshot_service: (
            InsightsSnapshotService | None
        ) = None,  # Story 2.5: Cache-first insights
    ):
        """
        Initialize ReAct agent with SDK and MCP tools.

        Args:
            settings: Application settings with API keys
            ticker_data_service: Service for fetching ticker data
            market_service: Hybrid market data service for stock data
            tool_cache_wrapper: Optional wrapper for tool caching + tracking
            redis_cache: Optional Redis cache for insights caching (30min TTL)
            snapshot_service: Optional InsightsSnapshotService for cache-first reads (Story 2.5)
        """
        self.settings = settings
        self.market_service = market_service
        self.ticker_data_service = ticker_data_service
        self.tool_cache_wrapper = tool_cache_wrapper
        self.redis_cache = redis_cache

        # Initialize Langfuse client globally (SDK v3 pattern)
        # Only enable if credentials are configured and library is available
        self.langfuse_enabled = False
        self.langfuse_client = None  # Store client for custom span creation (Story 1.4)
        if (
            LANGFUSE_AVAILABLE
            and settings.langfuse_public_key
            and settings.langfuse_secret_key
        ):
            try:
                self.langfuse_client = Langfuse(
                    public_key=settings.langfuse_public_key,
                    secret_key=settings.langfuse_secret_key,
                    host=settings.langfuse_host,
                )
                self.langfuse_enabled = True
                logger.info(
                    "Langfuse SDK v3 initialized",
                    langfuse_host=settings.langfuse_host,
                )
            except Exception as e:
                logger.warning(
                    "Failed to initialize Langfuse - continuing without observability",
                    error=str(e),
                )

        # Initialize analysis tools (both use AlphaVantage for reliable data)
        self.fibonacci_analyzer = FibonacciAnalyzer(market_service)
        self.stochastic_analyzer = StochasticAnalyzer(market_service)

        # Initialize LLM with centralized configuration
        self.llm = ChatTongyi(
            model_name=settings.default_llm_model,
            dashscope_api_key=settings.dashscope_api_key,
            temperature=settings.default_llm_temperature,
            model_kwargs={"result_format": "message"},
            request_timeout=30,
        )

        # Create compressed local tools (Fibonacci + Stochastic)
        base_tools = [
            self._create_fibonacci_tool(),
            self._create_stochastic_tool(),
        ]
        self.tools = base_tools.copy()

        # Create formatter for Alpha Vantage responses
        alpha_vantage_formatter = AlphaVantageResponseFormatter()

        # Add Alpha Vantage tools (search, overview, news, financials, movers)
        alpha_vantage_tools = create_alpha_vantage_tools(
            market_service, alpha_vantage_formatter
        )
        self.tools.extend(alpha_vantage_tools)

        # Add Market Insights tools (category analysis, metrics)
        # Cache TTL: 30 minutes for full category data, 24 hours for AI basket symbols
        # Create FRED service for liquidity metrics
        fred_service = None
        if settings.fred_api_key:
            fred_service = FREDService(api_key=settings.fred_api_key)

        insights_registry = InsightsCategoryRegistry(
            settings=settings,
            redis_cache=self.redis_cache,  # Enable caching for 30min TTL
            market_service=market_service,
            fred_service=fred_service,
        )
        # Story 2.5: Pass snapshot_service for cache-first reads and trend queries
        insights_tools = create_insights_tools(
            insights_registry,
            snapshot_service=snapshot_service,
        )
        self.tools.extend(insights_tools)

        # Add Put/Call Ratio tools (Story 2.8: Reusable PCR service)
        # Uses DataManager for cached per-symbol PCR calculations
        pcr_tools = []
        if self.redis_cache:
            data_manager = DataManager(
                redis_cache=self.redis_cache,
                alpha_vantage_service=market_service,
            )
            pcr_tools = create_pcr_tools(data_manager)
            self.tools.extend(pcr_tools)

        # Track tool counts for logging
        base_tool_count = len(base_tools)
        alpha_vantage_tool_count = len(alpha_vantage_tools)
        insights_tool_count = len(insights_tools)
        pcr_tool_count = len(pcr_tools)

        # Create ReAct agent with memory and custom system prompt
        self.checkpointer = MemorySaver()
        self.agent = create_react_agent(
            self.llm,
            self.tools,
            checkpointer=self.checkpointer,
            prompt=FINANCIAL_AGENT_SYSTEM_PROMPT,
        )

        logger.info(
            "FinancialAnalysisReActAgent initialized",
            agent_type="langgraph_sdk",
            base_tools=base_tool_count,
            alpha_vantage_tools=alpha_vantage_tool_count,
            insights_tools=insights_tool_count,
            pcr_tools=pcr_tool_count,
            total_local_tools=len(self.tools),
        )

    def _create_fibonacci_tool(self) -> Any:
        """
        Create compressed Fibonacci analysis tool.

        Returns tool that outputs 2-3 line summary instead of full result dict.
        """
        analyzer = self.fibonacci_analyzer

        @tool
        async def fibonacci_analysis_tool(
            symbol: str,
            timeframe: str = "1d",
            start_date: str | None = None,
            end_date: str | None = None,
        ) -> str:
            """
            Analyze stock using Fibonacci retracement levels.

            Detects swing points, calculates Fibonacci pressure zones (0.382, 0.5, 0.618),
            and provides trend analysis with golden ratio zones.

            Args:
                symbol: Stock ticker symbol (e.g., "AAPL", "TSLA")
                timeframe: Time interval - "1h", "1d", "1w", "1M" (default: "1d")
                start_date: Start date in YYYY-MM-DD format (optional)
                end_date: End date in YYYY-MM-DD format (optional)

            Returns:
                Compressed 2-3 line Fibonacci analysis summary
            """
            try:
                result = await analyzer.analyze(
                    symbol=symbol,
                    timeframe=timeframe,
                    start_date=start_date,
                    end_date=end_date,
                )

                # Compress to 2-3 lines
                key_levels = [
                    f"{lv.percentage} (${lv.price:.2f})"
                    for lv in result.fibonacci_levels[:3]
                    if lv.is_key_level
                ]

                return f"""Fibonacci Analysis: {symbol} @ ${result.current_price:.2f}
Key Levels: {", ".join(key_levels) if key_levels else "N/A"}
Trend Strength: {result.trend_strength}, Confidence: {result.confidence_score * 100:.0f}%"""

            except Exception as e:
                logger.error("Fibonacci tool failed", symbol=symbol, error=str(e))
                return f"Fibonacci analysis error for {symbol}: {str(e)}"

        return fibonacci_analysis_tool

    def _create_stochastic_tool(self) -> Any:
        """
        Create compressed Stochastic analysis tool.

        Returns tool that outputs 2-3 line summary instead of full result dict.
        """
        analyzer = self.stochastic_analyzer

        @tool
        async def stochastic_analysis_tool(
            symbol: str,
            timeframe: str = "1d",
            k_period: int = 14,
            d_period: int = 3,
            start_date: str | None = None,
            end_date: str | None = None,
        ) -> str:
            """
            Analyze stock using Stochastic Oscillator.

            Identifies overbought/oversold conditions, bullish/bearish crossovers,
            and divergence patterns using %K and %D lines.

            Args:
                symbol: Stock ticker symbol (e.g., "AAPL", "TSLA")
                timeframe: Time interval - "1h", "1d", "1w", "1M" (default: "1d")
                k_period: Period for %K calculation (default: 14)
                d_period: Period for %D calculation (default: 3)
                start_date: Start date in YYYY-MM-DD format (optional)
                end_date: End date in YYYY-MM-DD format (optional)

            Returns:
                Compressed 2-3 line Stochastic analysis summary
            """
            try:
                result = await analyzer.analyze(
                    symbol=symbol,
                    timeframe=timeframe,
                    k_period=k_period,
                    d_period=d_period,
                    start_date=start_date,
                    end_date=end_date,
                )

                return f"""Stochastic Analysis: {symbol} @ ${result.current_price:.2f}
Oscillator: %K={result.current_k:.1f}, %D={result.current_d:.1f}, Signal: {result.current_signal.upper()}
Summary: {result.analysis_summary}"""

            except Exception as e:
                logger.error("Stochastic tool failed", symbol=symbol, error=str(e))
                return f"Stochastic analysis error for {symbol}: {str(e)}"

        return stochastic_analysis_tool

    def _get_langfuse_handler(self) -> "CallbackHandler | None":
        """
        Create Langfuse callback handler if configured.

        SDK v3.x pattern: CallbackHandler() with no args (uses global client).

        Returns:
            CallbackHandler instance if Langfuse is enabled, None otherwise
        """
        if not self.langfuse_enabled or not LANGFUSE_AVAILABLE:
            return None

        try:
            return LangfuseCallbackHandler()
        except Exception as e:
            logger.warning(
                "Failed to create Langfuse callback handler",
                error=str(e),
            )
            return None

    async def ainvoke(
        self,
        user_message: str,
        conversation_history: list[dict[str, str]] | None = None,
        debug: bool = False,
        additional_callbacks: list | None = None,
        language: SupportedLanguage = DEFAULT_LANGUAGE,
    ) -> dict[str, Any]:
        """
        Invoke ReAct agent with user message and conversation history.

        The agent will autonomously:
        1. Reason about the query
        2. Decide which tools to call (if any)
        3. Execute tools sequentially
        4. Observe results and decide: more tools OR final answer
        5. Synthesize final response

        Args:
            user_message: User's query
            conversation_history: Previous messages (optional, for new threads)
            debug: If True, log full LLM prompt for debugging
            additional_callbacks: Optional list of additional callbacks (e.g., ToolExecutionCallback)
            language: Response language ("zh-CN" or "en")

        Returns:
            Agent response with messages and final answer
        """
        # Generate trace ID and thread ID with UUID for guaranteed uniqueness
        # UUID suffix prevents collisions in concurrent execution (e.g., parallel market mover analysis)
        trace_id = f"trace_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        thread_id = (
            f"thread_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        )

        # ===== LANGFUSE LATENCY TRACKING (Story 1.4) =====
        # Track agent invocation latency with custom trace
        langfuse_trace = None
        agent_start_time = time.perf_counter()
        if self.langfuse_enabled and self.langfuse_client:
            try:
                langfuse_trace = self.langfuse_client.trace(
                    id=trace_id,
                    name="react_agent_invocation",
                    input={"user_message": user_message[:500]},  # Truncate for storage
                    metadata={
                        "thread_id": thread_id,
                        "language": language,
                        "history_length": (
                            len(conversation_history) if conversation_history else 0
                        ),
                    },
                )
            except Exception as e:
                logger.warning(
                    "Failed to create Langfuse trace for latency tracking",
                    error=str(e),
                )

        logger.info(
            "ReAct agent invocation started",
            trace_id=trace_id,
            thread_id=thread_id,
            user_message_preview=user_message[:100],
        )

        # Prepare messages
        messages = []

        # Add conversation history if provided
        if conversation_history:
            for msg in conversation_history:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    # Include assistant messages (both LLM and tool outputs)
                    messages.append(AIMessage(content=msg["content"]))

        # Add language instruction to user message
        language_instruction = get_brief_language_instruction(language)
        user_message_with_language = f"{user_message}\n\n{language_instruction}"

        # Add current user message with language instruction
        messages.append(HumanMessage(content=user_message_with_language))

        # Get Langfuse callback handler if enabled
        langfuse_handler = self._get_langfuse_handler()

        # Invoke agent with config
        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": 50,  # Allow up to 50 tool calls for complex analyses (default: 25)
        }

        # Build callbacks list
        callbacks = []
        if additional_callbacks:
            callbacks.extend(additional_callbacks)
        if langfuse_handler:
            callbacks.append(langfuse_handler)

        # Add callbacks to config if any are configured
        if callbacks:
            config["callbacks"] = callbacks
            logger.info(
                "Callbacks configured for agent invocation",
                callback_count=len(callbacks),
                has_langfuse=langfuse_handler is not None,
                has_additional=bool(additional_callbacks),
            )

        # Debug logging: Show full prompt sent to LLM
        if debug:
            logger.info(
                "🔍 DEBUG: Full LLM Prompt",
                trace_id=trace_id,
                message_count=len(messages),
                full_messages=[
                    {
                        "type": msg.__class__.__name__,
                        "content": msg.content,
                    }
                    for msg in messages
                ],
            )

        try:
            # ===== RETRY CONFIGURATION (Story 1.4: Retry Logic Optimization) =====
            # Exponential backoff with jitter for DashScope API (SSL errors, timeouts)
            max_retries = 3
            base_delay = 2.0  # seconds
            max_delay = 30.0  # seconds
            jitter_factor = 0.25  # Add 0-25% random jitter to prevent thundering herd

            # Retryable error keywords (network and transient errors)
            retryable_keywords = [
                "ssl",
                "certificate",
                "connection",
                "timeout",
                "max retries",
                "eof occurred",
                "rate limit",
                "service unavailable",
                "bad gateway",
                "gateway timeout",
            ]

            last_exception = None
            for attempt in range(max_retries):
                try:
                    # Run ReAct loop (auto-loop handles tool calling)
                    result = await self.agent.ainvoke(
                        {"messages": messages}, config=config
                    )
                    # Success - break out of retry loop
                    if attempt > 0:
                        logger.info(
                            "ReAct agent retry succeeded",
                            trace_id=trace_id,
                            attempt=attempt + 1,
                            recovery_after_retries=attempt,
                        )
                    break
                except Exception as e:
                    last_exception = e
                    # Check if this is a retryable error
                    error_str = str(e).lower()
                    is_retryable = any(
                        keyword in error_str for keyword in retryable_keywords
                    )

                    if not is_retryable or attempt == max_retries - 1:
                        # Non-retryable error or last attempt - raise immediately
                        logger.error(
                            "ReAct agent invocation failed (non-retryable or max retries exhausted)",
                            trace_id=trace_id,
                            attempt=attempt + 1,
                            max_retries=max_retries,
                            error=str(e),
                            error_type=type(e).__name__,
                            is_retryable=is_retryable,
                            total_attempts=attempt + 1,
                        )
                        raise

                    # Calculate exponential backoff with jitter (Story 1.4)
                    # Jitter prevents thundering herd problem when many requests retry simultaneously
                    base_wait = min(base_delay * (2**attempt), max_delay)
                    jitter = random.uniform(0, jitter_factor * base_wait)
                    delay = base_wait + jitter

                    logger.warning(
                        "ReAct agent retry scheduled",
                        trace_id=trace_id,
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        remaining_attempts=max_retries - attempt - 1,
                        error=str(e),
                        error_type=type(e).__name__,
                        retry_delay_seconds=round(delay, 2),
                        base_delay=base_wait,
                        jitter_applied=round(jitter, 2),
                    )

                    # Wait before retrying
                    await asyncio.sleep(delay)

            # If we exhausted all retries, raise the last exception
            if last_exception:
                raise last_exception

            # Extract final answer (last message)
            final_message = result["messages"][-1]
            final_answer = (
                final_message.content if hasattr(final_message, "content") else ""
            )

            # Count tool executions
            tool_messages = [
                msg
                for msg in result["messages"]
                if msg.__class__.__name__ == "ToolMessage"
            ]

            # Extract token usage from all AI messages
            total_input_tokens, total_output_tokens, _ = (
                extract_token_usage_from_messages(result["messages"])
            )

            # Calculate agent execution duration (Story 1.4)
            agent_duration_ms = int((time.perf_counter() - agent_start_time) * 1000)

            logger.info(
                "ReAct agent invocation completed",
                trace_id=trace_id,
                total_messages=len(result["messages"]),
                tool_executions=len(tool_messages),
                final_answer_length=len(final_answer),
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                agent_duration_ms=agent_duration_ms,
            )

            # ===== LANGFUSE LATENCY SPAN UPDATE (Story 1.4) =====
            # Add latency metrics to Langfuse trace
            if langfuse_trace:
                try:
                    langfuse_trace.update(
                        output={"final_answer_length": len(final_answer)},
                        metadata={
                            "duration_ms": agent_duration_ms,
                            "tool_executions": len(tool_messages),
                            "input_tokens": total_input_tokens,
                            "output_tokens": total_output_tokens,
                            "total_tokens": total_input_tokens + total_output_tokens,
                            "status": "success",
                        },
                    )
                    # Flush to ensure data is sent
                    if self.langfuse_client:
                        self.langfuse_client.flush()
                except Exception as e:
                    logger.warning(
                        "Failed to update Langfuse trace with latency metrics",
                        error=str(e),
                    )

            return {
                "trace_id": trace_id,
                "messages": result["messages"],
                "final_answer": final_answer,
                "tool_executions": len(tool_messages),
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "total_tokens": total_input_tokens + total_output_tokens,
                "agent_duration_ms": agent_duration_ms,  # Story 1.4: Include latency
            }

        except Exception as e:
            # Get full traceback for debugging
            import traceback

            tb_str = traceback.format_exc()

            # Calculate agent execution duration even on error
            agent_duration_ms = int((time.perf_counter() - agent_start_time) * 1000)

            logger.error(
                "ReAct agent invocation failed",
                trace_id=trace_id,
                error=str(e),
                error_type=type(e).__name__,
                traceback=tb_str,
                agent_duration_ms=agent_duration_ms,
            )

            # ===== LANGFUSE ERROR TRACKING (Story 1.4) =====
            if langfuse_trace:
                try:
                    langfuse_trace.update(
                        output={"error": str(e)},
                        metadata={
                            "duration_ms": agent_duration_ms,
                            "status": "error",
                            "error_type": type(e).__name__,
                        },
                    )
                    if self.langfuse_client:
                        self.langfuse_client.flush()
                except Exception as trace_error:
                    logger.warning(
                        "Failed to update Langfuse trace with error",
                        error=str(trace_error),
                    )

            return {
                "trace_id": trace_id,
                "messages": messages,
                "final_answer": f"Agent execution failed: {str(e)}",
                "error": str(e),
                "tool_executions": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "agent_duration_ms": agent_duration_ms,  # Story 1.4: Include latency
            }

    async def ainvoke_structured(
        self,
        prompt: str,
        schema: type,
        context: str | None = None,
    ):
        """
        Invoke LLM with structured output using with_structured_output().

        This method uses the LLM directly (not the ReAct agent) to extract
        structured data from text. Useful for extracting trading decisions
        from analysis text.

        Args:
            prompt: The prompt/question to ask the LLM
            schema: Pydantic model class for structured output
            context: Optional context text (e.g., analysis results)

        Returns:
            Instance of the schema Pydantic model

        Raises:
            Exception: If LLM fails to produce valid structured output
        """
        logger.info(
            "Structured output invocation started",
            schema=schema.__name__,
            prompt_preview=prompt[:100],
            has_context=context is not None,
        )

        try:
            # Create structured LLM
            structured_llm = self.llm.with_structured_output(schema)

            # Build full message
            full_prompt = prompt
            if context:
                full_prompt = f"{context}\n\n---\n\n{prompt}"

            # ===== RETRY CONFIGURATION (Story 1.4: Retry Logic Optimization) =====
            # Same pattern as ainvoke - exponential backoff with jitter
            max_retries = 3
            base_delay = 2.0
            max_delay = 30.0
            jitter_factor = 0.25

            retryable_keywords = [
                "ssl",
                "certificate",
                "connection",
                "timeout",
                "max retries",
                "eof occurred",
                "rate limit",
                "service unavailable",
            ]

            last_exception = None
            for attempt in range(max_retries):
                try:
                    result = await structured_llm.ainvoke(full_prompt)
                    if attempt > 0:
                        logger.info(
                            "Structured output retry succeeded",
                            schema=schema.__name__,
                            attempt=attempt + 1,
                            recovery_after_retries=attempt,
                        )
                    break
                except Exception as e:
                    last_exception = e
                    error_str = str(e).lower()
                    is_retryable = any(
                        keyword in error_str for keyword in retryable_keywords
                    )

                    if not is_retryable or attempt == max_retries - 1:
                        logger.error(
                            "Structured output invocation failed (non-retryable or max retries exhausted)",
                            schema=schema.__name__,
                            attempt=attempt + 1,
                            max_retries=max_retries,
                            error=str(e),
                            error_type=type(e).__name__,
                            is_retryable=is_retryable,
                        )
                        raise

                    # Calculate exponential backoff with jitter (Story 1.4)
                    base_wait = min(base_delay * (2**attempt), max_delay)
                    jitter = random.uniform(0, jitter_factor * base_wait)
                    delay = base_wait + jitter

                    logger.warning(
                        "Structured output retry scheduled",
                        schema=schema.__name__,
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        remaining_attempts=max_retries - attempt - 1,
                        error=str(e),
                        error_type=type(e).__name__,
                        retry_delay_seconds=round(delay, 2),
                    )
                    await asyncio.sleep(delay)

            if last_exception and not result:
                raise last_exception

            logger.info(
                "Structured output invocation completed",
                schema=schema.__name__,
                result_type=type(result).__name__,
            )

            return result

        except Exception as e:
            logger.error(
                "Structured output invocation failed",
                schema=schema.__name__,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise
