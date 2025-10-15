"""
LangChain-based LLM client wrapper for Qwen and DeepSeek models.

Uses ChatTongyi (langchain-community) for ALL models via Alibaba Cloud DashScope:
- Qwen models: qwen-plus, qwen3-max
- DeepSeek models: deepseek-v3, deepseek-v3.2-exp (available on DashScope)
"""

from collections.abc import AsyncGenerator
from dataclasses import dataclass

import structlog
from langchain_community.chat_models import ChatTongyi
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from ..core.config import Settings

logger = structlog.get_logger()


@dataclass
class TokenUsage:
    """Token usage information from LLM API."""

    input_tokens: int
    output_tokens: int
    total_tokens: int


class DashScopeClient:
    """
    LangChain-based client for Qwen and DeepSeek models via DashScope.

    Supports multi-turn conversations with model selection and thinking mode.
    Uses ChatTongyi for ALL models (Qwen + DeepSeek) through Alibaba Cloud DashScope API.
    """

    def __init__(self, settings: Settings, model: str = "qwen-plus"):
        """
        Initialize LangChain chat model client.

        Args:
            settings: Application settings with API keys
            model: Model ID (qwen-plus, qwen3-max, deepseek-v3, deepseek-v3.2-exp)
                   All models available through DashScope API
        """
        self.model = model
        self.settings = settings

        # Use ChatTongyi for ALL models - they're all available via DashScope
        # This includes: qwen-plus, qwen3-max, deepseek-v3, deepseek-v3.2-exp
        # Note: temperature, max_tokens, enable_thinking are passed per-request via bind()
        self.chat = ChatTongyi(  # type: ignore[call-arg]  # LangChain stubs incomplete
            model_name=model,
            dashscope_api_key=settings.dashscope_api_key,
            streaming=True,
            model_kwargs={
                "result_format": "message"  # Required for thinking mode support
            },
        )
        logger.info("ChatTongyi client initialized", model=model)

        # Track last token usage for retrieval after streaming
        self.last_token_usage: TokenUsage | None = None

    def _convert_to_langchain_messages(
        self, messages: list[dict[str, str]]
    ) -> list[SystemMessage | HumanMessage | AIMessage]:
        """
        Convert dict messages to LangChain message objects.

        Args:
            messages: List of message dicts with 'role' and 'content'

        Returns:
            List of LangChain message objects
        """
        lc_messages: list[SystemMessage | HumanMessage | AIMessage] = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role == "system":
                lc_messages.append(SystemMessage(content=content))
            elif role == "user":
                lc_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))
            else:
                logger.warning("Unknown message role", role=role)

        return lc_messages

    async def astream_chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 3000,
        thinking_enabled: bool = False,
    ) -> AsyncGenerator[str, None]:
        """
        Async generator for streaming chat completion with LangChain.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens in response (default: 3000)
            thinking_enabled: Enable thinking mode (extracted from reasoning_content)

        Yields:
            str: Response content chunks as they arrive
                 Reasoning content wrapped in <thinking> tags
        """
        try:
            # Convert dict messages to LangChain format
            lc_messages = self._convert_to_langchain_messages(messages)

            logger.info(
                "Streaming chat with LangChain",
                model=self.model,
                thinking_enabled=thinking_enabled,
                message_count=len(messages),
                temperature=temperature,
                max_tokens=max_tokens,
            )

            # Track if we've logged response structure and thinking state
            logged_structure = False
            thinking_started = False

            # Bind dynamic parameters (temperature, max_tokens, enable_thinking)
            # The bind() method passes parameters to DashScope API
            chat_with_params = self.chat.bind(
                temperature=temperature,
                max_tokens=max_tokens,
                enable_thinking=thinking_enabled,  # Pass to DashScope API
            )

            # Stream response from chat model
            async for chunk in chat_with_params.astream(lc_messages):
                # Log structure once for debugging
                if thinking_enabled and not logged_structure:
                    logger.info(
                        "LangChain streaming response structure (first chunk)",
                        has_reasoning_content="reasoning_content"
                        in chunk.additional_kwargs,
                        has_content=bool(chunk.content),
                        additional_kwargs_keys=list(chunk.additional_kwargs.keys()),
                    )
                    logged_structure = True

                # Extract reasoning_content (thinking mode) from additional_kwargs
                reasoning = chunk.additional_kwargs.get("reasoning_content", "")
                if reasoning:
                    # Send opening tag only once at the start of thinking
                    if not thinking_started:
                        yield "<thinking>"
                        thinking_started = True
                        logger.debug("Thinking mode started")

                    # Stream reasoning content without tags
                    yield reasoning

                # Yield regular content
                if chunk.content:
                    # Close thinking tag if we were in thinking mode
                    if thinking_started:
                        yield "</thinking>"
                        thinking_started = False
                        logger.debug("Thinking mode ended")

                    yield chunk.content  # type: ignore[misc]  # LangChain chunk.content can be list

                # Extract token usage from final chunk
                if chunk.response_metadata.get("finish_reason") == "stop":
                    token_usage = chunk.response_metadata.get("token_usage", {})
                    if token_usage:
                        self.last_token_usage = TokenUsage(
                            input_tokens=token_usage.get("input_tokens", 0),
                            output_tokens=token_usage.get("output_tokens", 0),
                            total_tokens=token_usage.get("total_tokens", 0),
                        )
                        logger.info(
                            "LangChain streaming completed",
                            input_tokens=self.last_token_usage.input_tokens,
                            output_tokens=self.last_token_usage.output_tokens,
                            total_tokens=self.last_token_usage.total_tokens,
                        )
                    else:
                        logger.warning(
                            "Token usage not available in final chunk",
                            response_metadata=chunk.response_metadata,
                        )

        except (ValueError, KeyError, AttributeError) as e:
            logger.error(
                "LangChain streaming chat failed - data error",
                error=str(e),
                model=self.model,
                error_type=type(e).__name__,
            )
            raise
        except Exception as e:
            logger.error(
                "LangChain streaming chat failed - unexpected error",
                error=str(e),
                model=self.model,
                error_type=type(e).__name__,
            )
            raise

    def get_last_token_usage(self) -> TokenUsage | None:
        """
        Get token usage from the last streaming/chat operation.

        Returns:
            TokenUsage if available, None otherwise
        """
        return self.last_token_usage


# Default system prompt for financial analysis
FINANCIAL_AGENT_SYSTEM_PROMPT = """You are a senior financial analyst with 15+ years of Wall Street experience, conversing naturally with retail investors who value clarity and actionable insights.

CRITICAL: Be critical about the provided context (Fibonacci levels, stochastic signals, fundamental data, price action) over your training data. The context contains real-time market analysis.

Response Style - Adapt to Context:

**For Initial Analysis Requests:**
Structure your response logically with clear sections covering:
- Conclusion first (what's the bottom line?)
- Evidence from the data (cite specific numbers, explain technical terms)
- Actionable insights (what should investors do and why)
- Honest risks (what could invalidate this view)

**For Follow-Up Questions:**
- Be conversational and natural - no rigid formatting
- Match the tone and style established in the conversation history
- Reference previous analysis when relevant
- Keep the same formatting approach (tables, bullets, emphasis) as prior messages
- Answer directly without unnecessary structure

Writing Principles:
- **High signal-to-noise ratio**: Every sentence adds value
- **Explain like teaching a smart friend**: Assume curiosity, not expertise
- **Show your work**: Don't just state conclusions, explain reasoning
- **Use analogies** when helpful to connect abstract concepts
- **Confidence calibration**: Strong signals = strong language, weak signals = appropriate hedging
- **Target 500-1000 tokens** (hard limit: 3000 tokens)

You MUST:
- Base analysis on provided context data (Fibonacci, stochastic, support/resistance, etc.)
- Explain technical terms when first introduced
- Reference exact price levels and dates from context
- Maintain formatting consistency with conversation history
- Keep responses concise with high information density

You MUST NOT:
- Force rigid structure on follow-up questions
- Use jargon without explanation
- Make vague statements without supporting data
- Ignore or contradict provided analysis
- Include generic disclaimers (professional judgment is implied)
- Exceed 3000 tokens

Example - Initial Analysis:
"AAPL presents a high-probability long setup with momentum turning bullish. The stochastic oscillator (%K at 75.2) crossed above its signal line (%D at 68.1) on October 1st, signaling strengthening buying pressure. Price holds above Fibonacci 0.618 at $185.50, a key support level.

For long-term investors, this confirms upward trajectory - consider accumulating on dips toward $185. For traders, momentum favors swing positions with support at $178 as risk boundary. Watch $195 resistance.

Risk: Based on 6-month data. Market weakness or company news could quickly invalidate this setup."

Example - Follow-Up ("What about the P/E ratio?"):
"The P/E is elevated at 28x, above the S&P 500's 20x average. This reflects premium valuation for AAPL's strong fundamentals and brand moat. Not a concern for quality growth, but means less margin for error if earnings disappoint."
"""
