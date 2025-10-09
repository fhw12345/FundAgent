"""
Dependencies for chat API endpoints.
"""

from fastapi import Depends

from ...agent.chat_agent import ChatAgent
from ...core.config import Settings, get_settings
from ...database.mongodb import MongoDB
from ...database.repositories.chat_repository import ChatRepository
from ...database.repositories.message_repository import MessageRepository
from ...services.chat_service import ChatService
from .auth import get_current_user_id, get_mongodb  # Import shared auth

# ===== MongoDB and Repository Dependencies =====


def get_chat_repository(mongodb: MongoDB = Depends(get_mongodb)) -> ChatRepository:
    """Get chat repository instance."""
    chats_collection = mongodb.get_collection("chats")
    return ChatRepository(chats_collection)


def get_message_repository(
    mongodb: MongoDB = Depends(get_mongodb),
) -> MessageRepository:
    """Get message repository instance."""
    messages_collection = mongodb.get_collection("messages")
    return MessageRepository(messages_collection)


# ===== Service Dependencies =====


def get_chat_service(
    chat_repo: ChatRepository = Depends(get_chat_repository),
    message_repo: MessageRepository = Depends(get_message_repository),
    settings: Settings = Depends(get_settings),
) -> ChatService:
    """Get chat service instance."""
    return ChatService(chat_repo, message_repo, settings)


def get_chat_agent(
    settings: Settings = Depends(get_settings),
) -> ChatAgent:
    """
    Get or create chat agent instance.

    Lightweight LLM wrapper, no session management needed.
    """
    return ChatAgent(settings=settings)


# Re-export get_current_user_id for backward compatibility
__all__ = ["get_current_user_id", "get_chat_service", "get_chat_agent"]
