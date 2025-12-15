"""
Chat CRUD endpoints for persistent chat management.

This module contains endpoints for creating, reading, updating, and deleting chats.
All operations require authentication and enforce ownership checks.
"""

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException

from ...core.exceptions import NotFoundError
from ...services.chat_service import ChatService
from ..dependencies.chat_deps import get_chat_service, get_current_user_id
from ..schemas.chat_models import (
    ChatDetailResponse,
    ChatListResponse,
    UpdateUIStateRequest,
)

logger = structlog.get_logger()

router = APIRouter()


# ===== Persistent Chat Management Endpoints =====


@router.post("/chats")
async def create_empty_chat(
    user_id: str = Depends(get_current_user_id),
    chat_service: ChatService = Depends(get_chat_service),
) -> dict[str, str]:
    """
    Create an empty chat for the user (triggered by symbol selection).

    **Authentication**: Requires Bearer token in Authorization header.

    **Response:**
    ```json
    {
      "chat_id": "chat_abc123"
    }
    ```
    """
    try:
        logger.info("Creating empty chat", user_id=user_id)
        chat = await chat_service.create_chat(user_id, title="New Chat")
        logger.info("Empty chat created", chat_id=chat.chat_id, user_id=user_id)
        return {"chat_id": chat.chat_id}
    except Exception as e:
        logger.error("Failed to create empty chat", user_id=user_id, error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to create chat: {str(e)}"
        ) from e


@router.get("/chats", response_model=ChatListResponse)
async def list_user_chats(
    page: int = 1,
    page_size: int = 20,
    include_archived: bool = False,
    user_id: str = Depends(get_current_user_id),
    chat_service: ChatService = Depends(get_chat_service),
) -> ChatListResponse:
    """
    List all chats for the authenticated user.

    **Authentication**: Requires Bearer token in Authorization header.

    **Query Parameters:**
    - page: Page number (1-indexed, default: 1)
    - page_size: Items per page (1-100, default: 20)
    - include_archived: Include archived chats (default: false)

    **Response:**
    ```json
    {
      "chats": [
        {
          "chat_id": "chat_abc123",
          "title": "AAPL Analysis",
          "last_message_preview": "Based on the Fibonacci levels...",
          "last_message_at": "2025-10-05T10:15:00Z",
          ...
        }
      ],
      "total": 42,
      "page": 1,
      "page_size": 20
    }
    ```
    """
    try:
        chats, total = await chat_service.list_user_chats(
            user_id=user_id,
            page=page,
            page_size=page_size,
            include_archived=include_archived,
        )

        logger.info(
            "Chats listed",
            user_id=user_id,
            count=len(chats),
            page=page,
        )

        return ChatListResponse(
            chats=chats,
            total=total,
            page=page,
            page_size=page_size,
        )

    except ValueError as e:
        logger.error("Validation error listing chats", error=str(e))
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("Failed to list chats", error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to list chats",
        ) from e


@router.get("/chats/{chat_id}", response_model=ChatDetailResponse)
async def get_chat_detail(
    chat_id: str,
    limit: int | None = None,
    offset: int = 0,
    user_id: str = Depends(get_current_user_id),
    chat_service: ChatService = Depends(get_chat_service),
) -> ChatDetailResponse:
    """
    Get chat with messages for state restoration.

    **Authentication**: Requires Bearer token in Authorization header.

    **Path Parameters:**
    - chat_id: Chat identifier

    **Query Parameters:**
    - limit: Optional limit on number of messages (default: 100)
    - offset: Number of messages to skip for pagination (default: 0)

    **Response:**
    ```json
    {
      "chat": {
        "chat_id": "chat_abc123",
        "title": "AAPL Analysis",
        "ui_state": {
          "current_symbol": "AAPL",
          "current_interval": "1d",
          "active_overlays": {
            "fibonacci": {"enabled": true}
          }
        },
        ...
      },
      "messages": [
        {
          "message_id": "msg_xyz789",
          "role": "user",
          "content": "What are the Fibonacci levels for AAPL?",
          "timestamp": "2025-10-05T10:00:00Z",
          ...
        }
      ]
    }
    ```
    """
    try:
        # Get chat with ownership verification
        chat = await chat_service.get_chat(chat_id, user_id)

        # Get messages with pagination
        messages = await chat_service.get_chat_messages(
            chat_id, user_id, limit=limit, offset=offset
        )

        logger.info(
            "Chat detail retrieved",
            chat_id=chat_id,
            user_id=user_id,
            message_count=len(messages),
        )

        return ChatDetailResponse(
            chat=chat,
            messages=messages,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get chat detail", chat_id=chat_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve chat",
        ) from e


@router.delete("/chats/{chat_id}", status_code=204)
async def delete_chat(
    chat_id: str,
    user_id: str = Depends(get_current_user_id),
    chat_service: ChatService = Depends(get_chat_service),
) -> None:
    """
    Delete a chat and all its messages.

    **Authentication**: Requires Bearer token in Authorization header.

    **Path Parameters:**
    - chat_id: Chat identifier

    **Response:** 204 No Content on success

    **Errors:**
    - 404: Chat not found or user doesn't own it
    - 500: Internal server error
    """
    try:
        deleted = await chat_service.delete_chat(chat_id, user_id)

        if not deleted:
            raise HTTPException(
                status_code=404,
                detail="Chat not found",
            )

        logger.info("Chat deleted via API", chat_id=chat_id, user_id=user_id)

        # Return 204 No Content (no response body)
        return None

    except NotFoundError as e:
        logger.error("Chat not found for deletion", chat_id=chat_id, error=str(e))
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error("Failed to delete chat", chat_id=chat_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to delete chat") from e


@router.patch("/chats/{chat_id}/ui-state")
async def update_chat_ui_state(
    chat_id: str,
    request: UpdateUIStateRequest,
    user_id: str = Depends(get_current_user_id),
    chat_service: ChatService = Depends(get_chat_service),
) -> Any:
    """
    Update chat UI state (debounced from frontend).

    **Authentication**: Requires Bearer token in Authorization header.

    **Path Parameters:**
    - chat_id: Chat identifier

    **Request Body:**
    ```json
    {
      "ui_state": {
        "current_symbol": "AAPL",
        "current_interval": "1d",
        "current_date_range": {"start": null, "end": null},
        "active_overlays": {
          "fibonacci": {"enabled": true, "levels": [0.236, 0.382, 0.618]}
        }
      }
    }
    ```

    **Response:** Updated chat object
    """
    try:
        updated_chat = await chat_service.update_ui_state(
            chat_id, user_id, request.ui_state
        )

        logger.info(
            "UI state updated",
            chat_id=chat_id,
            user_id=user_id,
            symbol=request.ui_state.current_symbol,
        )

        return updated_chat

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update UI state", chat_id=chat_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to update UI state",
        ) from e
