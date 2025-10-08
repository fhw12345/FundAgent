"""
Alibaba Cloud Qwen LLM client wrapper.
Using DashScope SDK for qwen-vl-30b-a3b-thinking model.
"""

import dashscope
import structlog
from dashscope import Generation

from ..core.config import Settings

logger = structlog.get_logger()


class QwenClient:
    """
    Client for Alibaba Cloud Qwen VL model.

    Supports multi-turn conversations with financial analysis context.
    """

    def __init__(self, settings: Settings):
        """
        Initialize Qwen client.

        Args:
            settings: Application settings with DASHSCOPE_API_KEY
        """
        self.api_key = settings.dashscope_api_key
        # Using Qwen text model (VL models require different endpoint)
        self.model = "qwen-plus"  # High-performance text model

        # Set API key and base URL for DashScope
        dashscope.api_key = self.api_key
        # Use China region (Alibaba Cloud Bailian)
        dashscope.base_http_api_url = "https://dashscope.aliyuncs.com/api/v1"

        logger.info("QwenClient initialized", model=self.model)

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """
        Send chat completion request to Qwen model.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens in response

        Returns:
            Model response content

        Raises:
            Exception: If API call fails
        """
        try:
            response = Generation.call(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                result_format="message",  # Return in message format
            )

            if response.status_code == 200:
                content = response.output.choices[0].message.content
                logger.info(
                    "Qwen chat completed",
                    tokens_used=response.usage.total_tokens,
                    message_count=len(messages),
                )
                return content
            else:
                error_msg = f"Qwen API error: {response.code} - {response.message}"
                logger.error("Qwen API failed", error=error_msg)
                raise Exception(error_msg)

        except Exception as e:
            logger.error("Qwen chat failed", error=str(e))
            raise

    async def achat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 3000,
    ) -> str:
        """
        Async version of chat completion.

        Note: DashScope SDK doesn't have native async support yet,
        so this wraps the sync call. For production, consider
        using asyncio.to_thread() or httpx for direct API calls.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens in response (default: 3000)

        Returns:
            Model response content
        """
        # For now, calling sync version
        # TODO: Implement true async with httpx in future version
        return self.chat(messages, temperature, max_tokens)

    def stream_chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 3000,
    ):
        """
        Stream chat completion response chunk by chunk.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens in response (default: 3000)

        Yields:
            str: Response content chunks as they arrive

        Raises:
            Exception: If API call fails
        """
        try:
            responses = Generation.call(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                result_format="message",
                stream=True,  # Enable streaming
                incremental_output=True,  # Get incremental chunks
            )

            total_tokens = 0
            for response in responses:
                if response.status_code == 200:
                    # Extract incremental content from this chunk
                    chunk_content = response.output.choices[0].message.content
                    if chunk_content:
                        yield chunk_content

                    # Track token usage from final response
                    finish_reason = response.output.choices[0].get("finish_reason")
                    if finish_reason == "stop" and hasattr(response, "usage"):
                        total_tokens = response.usage.total_tokens
                else:
                    error_msg = f"Qwen API error: {response.code} - {response.message}"
                    logger.error("Qwen streaming failed", error=error_msg)
                    raise Exception(error_msg)

            logger.info(
                "Qwen streaming completed",
                tokens_used=total_tokens,
                message_count=len(messages),
            )

        except Exception as e:
            logger.error("Qwen streaming chat failed", error=str(e))
            raise

    async def astream_chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 3000,
    ):
        """
        Async generator for streaming chat completion.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens in response (default: 3000)

        Yields:
            str: Response content chunks as they arrive
        """
        # DashScope SDK uses sync generators, so we yield from the sync version
        # In production, consider implementing with httpx for true async
        for chunk in self.stream_chat(messages, temperature, max_tokens):
            yield chunk

    def chat_with_system_prompt(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> str:
        """
        Chat with a system prompt and optional history.

        Args:
            user_message: Current user message
            system_prompt: System instructions for the model
            conversation_history: Previous messages (without system prompt)

        Returns:
            Model response
        """
        messages = [{"role": "system", "content": system_prompt}]

        if conversation_history:
            messages.extend(conversation_history)

        messages.append({"role": "user", "content": user_message})

        return self.chat(messages)


# Default system prompt for financial analysis
FINANCIAL_AGENT_SYSTEM_PROMPT = """You are a senior financial analyst with 15+ years of Wall Street experience, conversing naturally with retail investors who value clarity and actionable insights.

CRITICAL: Trust the provided context (Fibonacci levels, stochastic signals, fundamental data, price action) over your training data. The context contains real-time market analysis.

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
- Force rigid structure ("The Verdict", "The Evidence") on follow-up questions
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
