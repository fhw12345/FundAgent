"""
Dependencies for chat API endpoints.
"""

from fastapi import Depends

from ...agent.chat_agent import ChatAgent
from ...agent.langgraph_react_agent import FinancialAnalysisReActAgent
from ...core.config import Settings, get_settings
from ...core.data.ticker_data_service import TickerDataService
from ...database.mongodb import MongoDB
from ...database.redis import RedisCache
from ...database.repositories.chat_repository import ChatRepository
from ...database.repositories.message_repository import MessageRepository
from ...services.chat_service import ChatService
from .auth import get_current_user_id, get_mongodb  # Import shared auth

# ===== Agent Singleton (Per-Worker Process) =====
# Agent is expensive to initialize (300-500ms for LangGraph compilation)
# Cache it as module-level singleton to avoid re-compilation on every request

_react_agent_singleton: FinancialAnalysisReActAgent | None = None

# ===== MongoDB and Repository Dependencies =====


def get_redis() -> RedisCache:
    """Get RedisCache instance from app state."""
    from ...main import app

    redis_cache: RedisCache = app.state.redis
    return redis_cache


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


def get_ticker_data_service(
    redis_cache: RedisCache = Depends(get_redis),
) -> TickerDataService:
    """Get ticker data service instance."""
    return TickerDataService(redis_cache=redis_cache)


def get_react_agent(
    settings: Settings = Depends(get_settings),
    ticker_service: TickerDataService = Depends(get_ticker_data_service),
) -> FinancialAnalysisReActAgent:
    """
    Get SDK ReAct agent with flexible auto-planning (singleton per worker).

    This agent uses LangGraph's create_react_agent SDK for:
    - Autonomous tool chaining (LLM decides sequence)
    - Compressed tool results (2-3 lines vs 20KB dicts)
    - Built-in message history via MemorySaver
    - 60% less code than custom state machine

    Key difference from get_financial_analysis_agent:
    - LLM-driven routing (vs hardcoded conditional_router)
    - Can chain multiple tools per invocation
    - Auto-loop handles ReAct pattern

    Performance: Using singleton pattern to avoid agent compilation overhead.
    """
    global _react_agent_singleton

    if _react_agent_singleton is None:
        _react_agent_singleton = FinancialAnalysisReActAgent(
            settings=settings,
            ticker_data_service=ticker_service,
        )

    return _react_agent_singleton


# Re-export get_current_user_id for backward compatibility
__all__ = [
    "get_current_user_id",
    "get_chat_service",
    "get_chat_agent",
    "get_react_agent",
]
