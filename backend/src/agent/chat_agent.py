"""
Simple multi-turn chat agent for financial analysis.

v0.2.0: Basic chat with Qwen model
v0.3.0+: Will integrate with LangGraph for tool orchestration
v0.5.0: Simplified to direct LLM wrapper (removed SessionManager)
"""

from collections.abc import AsyncGenerator

import structlog

from ..core.config import Settings
from .llm_client import FINANCIAL_AGENT_SYSTEM_PROMPT, DashScopeClient, TokenUsage

logger = structlog.get_logger()


class ChatAgent:
    """
    Conversational agent for financial analysis.

    Lightweight wrapper around DashScopeClient for LLM streaming.
    Message history managed by MongoDB, not in-memory sessions.
    """

    def __init__(self, settings: Settings):
        """
        Initialize chat agent.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.system_prompt = FINANCIAL_AGENT_SYSTEM_PROMPT
        # Cache LLM clients by model to avoid recreation
        self._client_cache: dict[str, DashScopeClient] = {}

        logger.info("ChatAgent initialized")

    def _get_client(self, model: str) -> DashScopeClient:
        """Get or create LLM client for the specified model."""
        if model not in self._client_cache:
            self._client_cache[model] = DashScopeClient(self.settings, model=model)
            logger.info("Created new LLM client", model=model)
        return self._client_cache[model]

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        model: str = "qwen-plus",
        thinking_enabled: bool = False,
        max_tokens: int = 3000,
    ) -> AsyncGenerator[str, None]:
        """
        Stream LLM response for conversation history.

        Args:
            messages: Conversation history (without system prompt)
                     Format: [{"role": "user", "content": "..."}, ...]
            model: Model ID (qwen-plus, qwen3-max, deepseek-v3, deepseek-v3.2-exp)
            thinking_enabled: Enable thinking mode for supported models
            max_tokens: Maximum output tokens

        Yields:
            str: Response content chunks as they arrive
        """
        # Prepare messages with system prompt
        conversation_history = [
            {"role": "system", "content": self.system_prompt}
        ] + messages

        logger.info(
            "Streaming chat to LLM",
            model=model,
            thinking_enabled=thinking_enabled,
            max_tokens=max_tokens,
            message_count=len(messages),
            total_with_system=len(conversation_history),
        )

        # Get client for the specified model
        llm_client = self._get_client(model)

        # Stream LLM response
        async for chunk in llm_client.astream_chat(
            messages=conversation_history,
            temperature=0.7,
            max_tokens=max_tokens,
            thinking_enabled=thinking_enabled,
        ):
            yield chunk

        logger.info("Streaming chat completed", model=model)

    def get_last_token_usage(self, model: str = "qwen-plus") -> TokenUsage | None:
        """
        Get token usage from the last chat operation.

        Args:
            model: Model ID to get usage from

        Returns:
            TokenUsage if available, None otherwise
        """
        client = self._client_cache.get(model)
        if not client:
            return None
        return client.get_last_token_usage()
