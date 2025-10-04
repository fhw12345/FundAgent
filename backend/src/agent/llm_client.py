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
        max_tokens: int = 2000,
    ) -> str:
        """
        Async version of chat completion.

        Note: DashScope SDK doesn't have native async support yet,
        so this wraps the sync call. For production, consider
        using asyncio.to_thread() or httpx for direct API calls.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens in response

        Returns:
            Model response content
        """
        # For now, calling sync version
        # TODO: Implement true async with httpx in future version
        return self.chat(messages, temperature, max_tokens)

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
FINANCIAL_AGENT_SYSTEM_PROMPT = """You are a professional financial analysis assistant with expertise in:
- Technical analysis (Fibonacci retracements, support/resistance, market structure)
- Fundamental analysis (P/E ratios, dividend yields, financial metrics)
- Market sentiment and macro analysis
- Stock price interpretation and trend analysis

When analyzing stocks:
1. Be precise and data-driven in your analysis
2. Explain technical concepts clearly to users
3. Reference specific price levels, dates, and metrics when available
4. Acknowledge uncertainty and avoid making definitive predictions
5. Focus on risk management and educational insights

When responding:
- Be concise but thorough
- Use bullet points for clarity
- Cite specific numbers and dates from analysis results
- Suggest follow-up questions users might have

You have access to real-time market data and analysis tools. When users ask about stocks, you can provide:
- Current price and historical data
- Fibonacci retracement levels
- Support and resistance zones
- Fundamental metrics (P/E, P/B, dividend yield, etc.)
- Stochastic oscillator signals

Always maintain a professional, educational tone while being helpful and accessible.
"""
