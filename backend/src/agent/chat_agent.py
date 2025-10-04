"""
Simple multi-turn chat agent for financial analysis.

v0.2.0: Basic chat with Qwen model
v0.3.0+: Will integrate with LangGraph for tool orchestration
"""

import structlog

from ..core.config import Settings
from .llm_client import FINANCIAL_AGENT_SYSTEM_PROMPT, QwenClient
from .session_manager import SessionManager
from .state import ChatSession

logger = structlog.get_logger()


class ChatAgent:
    """
    Conversational agent for financial analysis.

    Manages multi-turn conversations with context awareness.
    Future versions will integrate analysis tools via LangGraph.
    """

    def __init__(self, settings: Settings, session_manager: SessionManager):
        """
        Initialize chat agent.

        Args:
            settings: Application settings
            session_manager: Session manager instance
        """
        self.settings = settings
        self.session_manager = session_manager
        self.llm_client = QwenClient(settings)
        self.system_prompt = FINANCIAL_AGENT_SYSTEM_PROMPT

        logger.info("ChatAgent initialized")

    async def chat(self, session_id: str, user_message: str) -> str:
        """
        Process a user message and generate response.

        Args:
            session_id: Chat session identifier
            user_message: User's message

        Returns:
            Assistant's response

        Raises:
            ValueError: If session not found
        """
        # Get or create session
        session = self.session_manager.get_session(session_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found or expired")

        # Add user message to session
        session.add_message("user", user_message)

        logger.info(
            "Processing chat message",
            session_id=session_id,
            message_count=len(session.messages),
        )

        try:
            # Prepare conversation history for LLM
            conversation_history = self._prepare_conversation_history(session)

            # Get LLM response
            response = await self.llm_client.achat(
                messages=conversation_history,
                temperature=0.7,
                max_tokens=2000,
            )

            # Add assistant response to session
            session.add_message("assistant", response)

            # Update session in manager
            self.session_manager.update_session(session)

            logger.info(
                "Chat message processed",
                session_id=session_id,
                response_length=len(response),
            )

            return response

        except Exception as e:
            error_msg = f"Failed to process chat message: {str(e)}"
            logger.error("Chat processing failed", session_id=session_id, error=str(e))

            # Add error message to session for context
            session.add_message(
                "system",
                f"Error occurred: {error_msg}",
            )
            self.session_manager.update_session(session)

            raise

    def _prepare_conversation_history(
        self, session: ChatSession
    ) -> list[dict[str, str]]:
        """
        Prepare conversation history for LLM API call.

        Includes system prompt and recent message history.

        Args:
            session: Chat session

        Returns:
            List of message dicts for LLM API
        """
        messages = [{"role": "system", "content": self.system_prompt}]

        # Get recent conversation history (last 10 messages)
        # This prevents context window overflow and maintains relevance
        recent_messages = session.get_conversation_history(limit=10)

        logger.info(
            "📝 Preparing conversation history for LLM",
            session_id=session.session_id,
            total_messages_in_session=len(session.messages),
            messages_sent_to_llm=len(recent_messages),
        )

        for idx, msg in enumerate(recent_messages):
            # Only include user and assistant messages (skip system messages)
            if msg.role in ("user", "assistant"):
                content_preview = (
                    msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                )
                logger.info(
                    f"  [{idx+1}] {msg.role}: {content_preview}",
                    role=msg.role,
                    content_length=len(msg.content),
                )
                messages.append({"role": msg.role, "content": msg.content})

        logger.info(
            "✅ Conversation history prepared",
            session_id=session.session_id,
            final_message_count=len(messages),
        )

        return messages

    async def create_session(self, user_id: str | None = None) -> ChatSession:
        """
        Create a new chat session.

        Args:
            user_id: Optional user identifier

        Returns:
            New ChatSession
        """
        session = self.session_manager.create_session(user_id=user_id)
        logger.info("New chat session created", session_id=session.session_id)
        return session

    def get_session(self, session_id: str) -> ChatSession | None:
        """
        Retrieve an existing session.

        Args:
            session_id: Session identifier

        Returns:
            ChatSession if found, None otherwise
        """
        return self.session_manager.get_session(session_id)
