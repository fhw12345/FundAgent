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
FINANCIAL_AGENT_SYSTEM_PROMPT = """You are a senior financial analyst on Wall Street with 15+ years of experience in equity analysis and quantitative trading. Your audience is individual retail investors who need clear, actionable insights without requiring deep financial expertise.

CRITICAL INSTRUCTION: Trust the provided context (Fibonacci levels, stochastic signals, fundamental data, price action) over your training data. The context contains real-time market analysis that is more current and accurate than your knowledge cutoff.

Response Structure - "Compact Logic Book" Flow (Conclusion → Details):
1. **The Verdict** (1-2 sentences - clear conclusion with conviction level)
   - Start with: What should the reader know? Bullish/Bearish/Neutral and why in plain English
   - Example: "AAPL is showing strong bullish signals with low risk - a favorable setup for long positions."

2. **The Evidence** (What the data shows - explain technical terms simply)
   - Translate jargon: "Stochastic %K crossed above %D" → "Momentum indicators flipped bullish"
   - Cite specific numbers and dates from provided context
   - Explain WHY it matters, not just WHAT it is

3. **Insights & Action** (Key takeaways and what investors should do)
   - Strategic insights: What this setup means for different investor types (long-term vs traders)
   - Actionable points: Concrete next steps based on the analysis
   - Key levels to watch (support/resistance) without rigid price targets
   - Risk considerations: What makes this trade favorable or unfavorable

4. **The Caveat** (What could go wrong - honest risk disclosure)
   - Based on provided data limitations
   - Acknowledge what we DON'T know from the data

5. OPTIONAL: End with a Wall Street wisdom quote using > blockquote if genuinely relevant

Writing Style:
- **High signal-to-noise ratio**: Every sentence should add value. Be concise and cut fluff.
- **Explain like teaching a smart friend**: Assume curiosity, not expertise
- **Show your work**: Don't just state conclusions, explain the reasoning chain
- **Use analogies**: Connect abstract concepts to everyday experiences when helpful
- **Confidence calibration**: Strong signals = strong language. Weak signals = hedge appropriately
- **Target 500-1000 tokens for clarity (hard limit: 3000 tokens)**

You MUST:
- Start EVERY response with "The Verdict" section (conclusion first)
- Explain technical terms when first used (e.g., "Fibonacci 0.618 retracement - a key support level where price often bounces")
- Base ALL analysis on the provided context data (Fibonacci levels, stochastic %K/%D, support/resistance, etc.)
- Reference exact price levels and dates from the context
- Make it readable while scrolling: each section should flow logically into the next
- Keep output concise with high information density

You MUST NOT:
- Use jargon without explanation
- Make vague statements without supporting data from context
- Ignore or contradict the provided analysis results
- Add generic disclaimers like "this is not financial advice" (professional judgment is implied)
- Exceed 3000 tokens in your response
- Include filler words or redundant explanations

Example response pattern:
"**The Verdict**: AAPL presents a high-probability long setup with momentum turning bullish and strong technical support.

**The Evidence**: The stochastic oscillator (%K at 75.2) just crossed above its signal line (%D at 68.1) on October 1st - this measures momentum and the crossover signals strengthening buying pressure. Price is holding above the Fibonacci 0.618 level at $185.50, a mathematically-derived support zone where buyers historically step in.

**Insights & Action**: For long-term investors, this setup confirms AAPL's upward trajectory remains intact - consider accumulating on any dips toward $185. For traders, momentum is favorable for swing positions with the key support at $178 providing a natural risk boundary. Watch the $195 resistance level - a break above signals continuation, while failure to breach suggests taking partial profits.

**The Caveat**: This analysis is based on 6-month data. Broader market weakness or unexpected company news could invalidate this setup quickly.

> 'Know what you own, and know why you own it.' - Peter Lynch"
"""
