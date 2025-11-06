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

from datetime import datetime
from typing import TYPE_CHECKING, Any

import structlog

# Patch DashScope error handling BEFORE importing ChatTongyi
from ..core.utils.dashscope_fix import patch_tongyi_check_response
patch_tongyi_check_response()

from langchain_community.chat_models import ChatTongyi
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from ..core.analysis.fibonacci.analyzer import FibonacciAnalyzer
from ..core.utils import extract_token_usage_from_messages
from ..core.analysis.stochastic_analyzer import StochasticAnalyzer
from ..core.config import Settings
from ..core.data.ticker_data_service import TickerDataService
from ..services.tool_cache_wrapper import ToolCacheWrapper
from .llm_client import FINANCIAL_AGENT_SYSTEM_PROMPT

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
        tool_cache_wrapper: ToolCacheWrapper | None = None,
    ):
        """
        Initialize ReAct agent with SDK and MCP tools.

        Args:
            settings: Application settings with API keys
            ticker_data_service: Service for fetching ticker data
            tool_cache_wrapper: Optional wrapper for tool caching + tracking
        """
        self.settings = settings
        self.ticker_data_service = ticker_data_service
        self.tool_cache_wrapper = tool_cache_wrapper

        # Initialize Langfuse client globally (SDK v3 pattern)
        # Only enable if credentials are configured and library is available
        self.langfuse_enabled = False
        if (
            LANGFUSE_AVAILABLE
            and settings.langfuse_public_key
            and settings.langfuse_secret_key
        ):
            try:
                Langfuse(
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

        # Initialize analysis tools
        self.fibonacci_analyzer = FibonacciAnalyzer()
        self.stochastic_analyzer = StochasticAnalyzer(ticker_data_service)

        # Initialize LLM with centralized configuration
        self.llm = ChatTongyi(
            model_name=settings.default_llm_model,
            dashscope_api_key=settings.dashscope_api_key,
            temperature=settings.default_llm_temperature,
            model_kwargs={"result_format": "message"},
            request_timeout=30,
        )

        # Create compressed local tools
        self.tools = [
            self._create_fibonacci_tool(),
            self._create_stochastic_tool(),
        ]

        # Initialize MCP client for Alpha Vantage tools (118 tools)
        self.mcp_client = None
        if settings.alpha_vantage_api_key:
            try:
                self.mcp_client = self._initialize_mcp_client()
                logger.info("MCP client initialized", server="alphavantage")
            except Exception as e:
                logger.warning(
                    "Failed to initialize MCP client - continuing with local tools only",
                    error=str(e),
                    error_type=type(e).__name__,
                )
        else:
            logger.info("Alpha Vantage API key not configured - MCP tools disabled")

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
            local_tools=2,
            mcp_enabled=self.mcp_client is not None,
            total_tools=len(self.tools),
        )

    def _initialize_mcp_client(self) -> MultiServerMCPClient:
        """
        Initialize MCP client for Alpha Vantage tools.

        Returns:
            Configured MultiServerMCPClient with Alpha Vantage server
        """
        # Alpha Vantage MCP server URL
        mcp_url = f"https://mcp.alphavantage.co/mcp?apikey={self.settings.alpha_vantage_api_key}"

        # Initialize MCP client with Alpha Vantage server
        # Note: Parameter is 'connections' not 'servers' in langchain-mcp-adapters
        client = MultiServerMCPClient(
            connections={
                "alphavantage": {
                    "transport": "streamable_http",
                    "url": mcp_url,
                }
            }
        )

        logger.info(
            "MCP client created",
            server="alphavantage",
            transport="streamable_http",
        )

        return client

    async def initialize_mcp_tools(self) -> None:
        """
        Load MCP tools asynchronously and add to agent.

        This method should be called during application startup (after __init__).
        It loads 118 tools from Alpha Vantage MCP server and recreates the
        agent with the full tool set (2 local + 118 MCP = 120 total).
        """
        if not self.mcp_client:
            logger.info("MCP client not configured - skipping MCP tool initialization")
            return

        try:
            # Get tools from MCP client
            mcp_tools = await self.mcp_client.get_tools()

            # Add MCP tools to existing tools
            self.tools.extend(mcp_tools)

            # Recreate agent with full tool set
            self.agent = create_react_agent(
                self.llm,
                self.tools,
                checkpointer=self.checkpointer,
                prompt=FINANCIAL_AGENT_SYSTEM_PROMPT,
            )

            logger.info(
                "MCP tools initialized successfully",
                local_tools=2,
                mcp_tools=len(mcp_tools),
                total_tools=len(self.tools),
                mcp_server="alphavantage",
            )

        except Exception as e:
            logger.error(
                "Failed to initialize MCP tools - continuing with local tools only",
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
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
Key Levels: {', '.join(key_levels) if key_levels else 'N/A'}
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

        Returns:
            Agent response with messages and final answer
        """
        # Generate trace ID and thread ID
        trace_id = f"trace_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        thread_id = f"thread_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        logger.info(
            "ReAct agent invocation started",
            trace_id=trace_id,
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

        # Add current user message
        messages.append(HumanMessage(content=user_message))

        # Get Langfuse callback handler if enabled
        langfuse_handler = self._get_langfuse_handler()

        # Invoke agent with config
        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": 50,  # Allow up to 50 tool calls for complex analyses (default: 25)
        }

        # Add callbacks if Langfuse is configured
        if langfuse_handler:
            config["callbacks"] = [langfuse_handler]
            logger.info("Langfuse tracing enabled for this invocation")

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
            # Run ReAct loop (auto-loop handles tool calling)
            result = await self.agent.ainvoke({"messages": messages}, config=config)

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
            total_input_tokens, total_output_tokens, _ = extract_token_usage_from_messages(
                result["messages"]
            )

            logger.info(
                "ReAct agent invocation completed",
                trace_id=trace_id,
                total_messages=len(result["messages"]),
                tool_executions=len(tool_messages),
                final_answer_length=len(final_answer),
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
            )

            return {
                "trace_id": trace_id,
                "messages": result["messages"],
                "final_answer": final_answer,
                "tool_executions": len(tool_messages),
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "total_tokens": total_input_tokens + total_output_tokens,
            }

        except Exception as e:
            # Get full traceback for debugging
            import traceback
            tb_str = traceback.format_exc()

            logger.error(
                "ReAct agent invocation failed",
                trace_id=trace_id,
                error=str(e),
                error_type=type(e).__name__,
                traceback=tb_str,
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
            }
