"""
Simple multi-turn chat agent for financial analysis.

v0.2.0: Basic chat with Qwen model
v0.3.0+: Will integrate with LangGraph for tool orchestration
v0.5.0: Simplified to direct LLM wrapper (removed SessionManager)
"""

from collections.abc import AsyncGenerator

import structlog

from ..core.config import Settings
from .llm_client import FINANCIAL_AGENT_SYSTEM_PROMPT, QwenClient

logger = structlog.get_logger()


class ChatAgent:
    """
    Conversational agent for financial analysis.

    Lightweight wrapper around QwenClient for LLM streaming.
    Message history managed by MongoDB, not in-memory sessions.
    """

    def __init__(self, settings: Settings):
        """
        Initialize chat agent.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.llm_client = QwenClient(settings)
        self.system_prompt = FINANCIAL_AGENT_SYSTEM_PROMPT

        logger.info("ChatAgent initialized")

    async def stream_chat(
        self, messages: list[dict[str, str]]
    ) -> AsyncGenerator[str, None]:
        """
        Stream LLM response for conversation history.

        Args:
            messages: Conversation history (without system prompt)
                     Format: [{"role": "user", "content": "..."}, ...]

        Yields:
            str: Response content chunks as they arrive
        """
        # Prepare messages with system prompt
        conversation_history = [
            {"role": "system", "content": self.system_prompt}
        ] + messages

        logger.info(
            "Streaming chat to LLM",
            message_count=len(messages),
            total_with_system=len(conversation_history),
        )

        # Stream LLM response
        async for chunk in self.llm_client.astream_chat(
            messages=conversation_history,
            temperature=0.7,
            max_tokens=3000,
        ):
            yield chunk

        logger.info("Streaming chat completed")
