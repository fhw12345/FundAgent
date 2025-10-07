"""
Dependencies for chat API endpoints.
"""

from fastapi import Depends, Header, HTTPException, status

from ...agent.chat_agent import ChatAgent
from ...agent.session_manager import SessionManager, get_session_manager
from ...core.config import Settings, get_settings
from ...database.mongodb import MongoDB
from ...database.repositories.chat_repository import ChatRepository
from ...database.repositories.message_repository import MessageRepository
from ...database.repositories.user_repository import UserRepository
from ...services.auth_service import AuthService
from ...services.chat_service import ChatService

# ===== MongoDB and Repository Dependencies =====


def get_mongodb() -> MongoDB:
    """Get MongoDB instance from app state."""
    from ...main import app

    return app.state.mongodb


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


def get_user_repository(mongodb: MongoDB = Depends(get_mongodb)) -> UserRepository:
    """Get user repository instance."""
    users_collection = mongodb.get_collection("users")
    return UserRepository(users_collection)


# ===== Service Dependencies =====


def get_auth_service_for_chat(
    user_repo: UserRepository = Depends(get_user_repository),
) -> AuthService:
    """Get auth service for token verification."""
    return AuthService(user_repo, redis_cache=None)


def get_chat_service(
    chat_repo: ChatRepository = Depends(get_chat_repository),
    message_repo: MessageRepository = Depends(get_message_repository),
    settings: Settings = Depends(get_settings),
) -> ChatService:
    """Get chat service instance."""
    return ChatService(chat_repo, message_repo, settings)


def get_chat_agent(
    settings: Settings = Depends(get_settings),
    session_manager: SessionManager = Depends(get_session_manager),
) -> ChatAgent:
    """
    Get or create chat agent instance.

    In production, this would be a singleton managed at app startup.
    """
    return ChatAgent(settings=settings, session_manager=session_manager)


# ===== Authentication Dependencies =====


async def get_current_user_id(
    authorization: str | None = Header(None),
    auth_service: AuthService = Depends(get_auth_service_for_chat),
) -> str:
    """
    Extract and verify user_id from JWT token in Authorization header.

    Args:
        authorization: Authorization header (Bearer token)
        auth_service: Auth service for token verification

    Returns:
        User ID from token

    Raises:
        HTTPException: If token is missing, invalid, or expired
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract token from "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Expected: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]

    # Verify token and extract user_id
    user_id = auth_service.verify_token(token)

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user_id
