"""Dependencies for chat API endpoints."""

from typing import Any

from fastapi import Depends

from ...agent.chat_agent import ChatAgent
from ...agent.langgraph_react_agent import FinancialAnalysisReActAgent
from ...core.config import Settings, get_settings
from ...database.mongodb import MongoDB
from ...database.redis import RedisCache
from ...database.repositories.chat_repository import ChatRepository
from ...database.repositories.message_repository import MessageRepository
from ...services.chat_service import ChatService
from ...services.context_window_manager import ContextWindowManager
from .auth import get_current_user_id, get_mongodb

_react_agent_singleton: FinancialAnalysisReActAgent | None = None
_deep_agent_singleton = None


def get_redis() -> RedisCache:
    from ...main import app
    return app.state.redis


def get_chat_repository(mongodb: MongoDB = Depends(get_mongodb)) -> ChatRepository:
    return ChatRepository(mongodb.get_collection("chats"))


def get_message_repository(mongodb: MongoDB = Depends(get_mongodb)) -> MessageRepository:
    return MessageRepository(mongodb.get_collection("messages"))


def get_chat_service(
    chat_repo: ChatRepository = Depends(get_chat_repository),
    message_repo: MessageRepository = Depends(get_message_repository),
    settings: Settings = Depends(get_settings),
) -> ChatService:
    return ChatService(chat_repo, message_repo, settings)


def get_context_manager(settings: Settings = Depends(get_settings)) -> ContextWindowManager:
    return ContextWindowManager(settings)


def get_chat_agent(settings: Settings = Depends(get_settings)) -> ChatAgent:
    return ChatAgent(settings=settings)


def get_react_agent(
    settings: Settings = Depends(get_settings),
    redis_cache: RedisCache = Depends(get_redis),
) -> FinancialAnalysisReActAgent:
    global _react_agent_singleton
    from ...main import app

    if hasattr(app.state, "react_agent"):
        return app.state.react_agent

    if _react_agent_singleton is None:
        import structlog
        logger = structlog.get_logger()
        logger.warning("Creating fallback agent without app state")
        _react_agent_singleton = FinancialAnalysisReActAgent(
            settings=settings,
            redis_cache=redis_cache,
        )

    return _react_agent_singleton


def get_deep_agent(
    settings: Settings = Depends(get_settings),
    react_agent: FinancialAnalysisReActAgent = Depends(get_react_agent),
) -> Any:
    global _deep_agent_singleton

    if _deep_agent_singleton is not None:
        return _deep_agent_singleton

    import structlog
    from ...agent.deep_agent_adapter import DeepAgentAdapter
    from ...agent.deep_react_agent import DeepReActAgent

    tools = react_agent.tools if hasattr(react_agent, "tools") else []

    deep_agent = DeepReActAgent(
        settings=settings,
        tools=tools,
        enable_debate=True,
    )

    _deep_agent_singleton = DeepAgentAdapter(deep_agent)
    return _deep_agent_singleton


__all__ = [
    "get_current_user_id",
    "get_chat_service",
    "get_chat_agent",
    "get_react_agent",
    "get_deep_agent",
    "get_context_manager",
    "get_message_repository",
]
