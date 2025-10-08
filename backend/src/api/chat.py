"""
Chat API endpoint for conversational financial analysis.
Following Factor 11 & 12: Triggerable via API, Stateless Service.

This module contains persistent chat management endpoints using MongoDB.
Legacy session-based endpoints are in chat_legacy.py.
"""

import json

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from ..agent.chat_agent import ChatAgent
from ..core.exceptions import NotFoundError
from ..models.chat import ChatUpdate
from ..services.chat_service import ChatService
from .dependencies.chat_deps import (
    get_chat_agent,
    get_chat_service,
    get_current_user_id,
)
from .schemas.chat_models import (
    ChatDetailResponse,
    ChatListResponse,
    ChatRequest,
    UpdateUIStateRequest,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/api/chat", tags=["chat"])


# ===== Persistent Chat Management Endpoints =====


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

        # Get messages
        messages = await chat_service.get_chat_messages(chat_id, user_id, limit=limit)

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
):
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


@router.post("/stream-v2")
async def chat_stream_persistent(
    request: ChatRequest,
    user_id: str = Depends(get_current_user_id),
    chat_service: ChatService = Depends(get_chat_service),
    agent: ChatAgent = Depends(get_chat_agent),
) -> StreamingResponse:
    """
    Send a message and receive streaming response with MongoDB persistence.

    **Authentication**: Requires Bearer token in Authorization header.

    **Request:**
    ```json
    {
      "message": "What are the Fibonacci levels for AAPL?",
      "chat_id": "chat_abc123"  // Optional - omit to create new chat
    }
    ```

    **Response:** Stream of Server-Sent Events with incremental content
    """

    async def generate_stream_with_persistence():
        """Generate SSE stream and persist to MongoDB."""
        chat_id = None

        try:
            # Get or create chat
            if request.chat_id:
                # Verify ownership and get chat
                chat = await chat_service.get_chat(request.chat_id, user_id)
                chat_id = chat.chat_id
            else:
                # Create new chat with provided title or default
                chat_title = request.title if request.title else "New Chat"
                chat = await chat_service.create_chat(user_id, title=chat_title)
                chat_id = chat.chat_id
                logger.info(
                    "New persistent chat created",
                    chat_id=chat_id,
                    user_id=user_id,
                    title=chat_title,
                )

                # Send chat_id to client immediately
                chat_info = {"chat_id": chat_id, "type": "chat_created"}
                yield f"data: {json.dumps(chat_info)}\n\n"

            # Save message to MongoDB
            msg = await chat_service.add_message(
                chat_id=chat_id,
                user_id=user_id,
                role=request.role,
                content=request.message,
                source=request.source,
                metadata=request.metadata,  # Pass metadata for overlays
            )

            # Auto-update UI state from analysis metadata
            if request.metadata and hasattr(request.metadata, "raw_data"):
                raw_data = request.metadata.raw_data or {}
                symbol = raw_data.get("symbol")
                timeframe = raw_data.get("timeframe")
                start_date = raw_data.get("start_date")
                end_date = raw_data.get("end_date")

                if symbol or timeframe:
                    from ..models.chat import UIState

                    # Build active_overlays based on analysis source
                    active_overlays = {}
                    if request.source == "fibonacci":
                        active_overlays["fibonacci"] = {"enabled": True}
                    elif request.source == "stochastic":
                        active_overlays["stochastic"] = {"enabled": True}
                    elif request.source == "macro":
                        active_overlays["macro"] = {"enabled": True}
                    elif request.source == "fundamentals":
                        active_overlays["fundamentals"] = {"enabled": True}

                    ui_state = UIState(
                        current_symbol=symbol,
                        current_interval=timeframe or "1d",
                        current_date_range=(
                            {
                                "start": start_date,
                                "end": end_date,
                            }
                            if start_date and end_date
                            else {"start": None, "end": None}
                        ),
                        active_overlays=active_overlays,
                    )
                    await chat_service.update_ui_state(chat_id, user_id, ui_state)
                    logger.info(
                        "UI state auto-updated from metadata",
                        chat_id=chat_id,
                        symbol=symbol,
                        timeframe=timeframe,
                        overlays=list(active_overlays.keys()),
                    )

            # If source is analysis (not "user"), skip LLM (results already provided)
            if request.source in ("fibonacci", "stochastic", "macro", "fundamentals"):
                logger.info(
                    "Analysis results - skipping LLM",
                    chat_id=chat_id,
                    role=request.role,
                    source=request.source,
                )

                # Send completion event
                messages = await chat_service.get_chat_messages(chat_id, user_id)
                completion_data = {
                    "type": "done",
                    "chat_id": chat_id,
                    "message_count": len(messages),
                }
                yield f"data: {json.dumps(completion_data)}\n\n"

                logger.info(
                    "Analysis results saved without LLM call",
                    chat_id=chat_id,
                    message_count=len(messages),
                )
                return

            # Get conversation history from MongoDB
            messages = await chat_service.get_chat_messages(chat_id, user_id)

            # Create temporary session and populate with MongoDB history
            session = await agent.create_session(user_id=user_id)
            session_id = session.session_id

            # Populate session with existing messages (excluding the user message we just added)
            for msg in messages[:-1]:  # Exclude last message (the one we just added)
                session.add_message(msg.role, msg.content)

            # Update session in manager
            agent.session_manager.update_session(session)

            # Stream LLM response
            full_response = ""
            import asyncio

            async for chunk in agent.stream_chat(
                session_id=session_id, user_message=request.message
            ):
                full_response += chunk
                chunk_data = {"content": chunk, "type": "content"}
                yield f"data: {json.dumps(chunk_data)}\n\n"
                await asyncio.sleep(0)  # Flush buffer

            # Save assistant response to MongoDB
            await chat_service.add_message(
                chat_id=chat_id,
                user_id=user_id,
                role="assistant",
                content=full_response,
                source="llm",
            )

            # Generate title on first message (only if not provided)
            if await chat_service.should_generate_title(chat_id):
                title = await chat_service.generate_title_from_llm(
                    request.message, full_response
                )
                await chat_service.chat_repo.update(chat_id, ChatUpdate(title=title))
                logger.info("Chat title generated", chat_id=chat_id, title=title)

                # Send title to client
                title_data = {"title": title, "type": "title_generated"}
                yield f"data: {json.dumps(title_data)}\n\n"

            # Send completion event
            messages = await chat_service.get_chat_messages(chat_id, user_id)
            completion_data = {
                "type": "done",
                "chat_id": chat_id,
                "message_count": len(messages),
            }
            yield f"data: {json.dumps(completion_data)}\n\n"

            logger.info(
                "Streaming chat with persistence completed",
                chat_id=chat_id,
                message_count=len(messages),
            )

        except HTTPException as e:
            error_data = {"error": e.detail, "type": "error"}
            yield f"data: {json.dumps(error_data)}\n\n"
        except Exception as e:
            logger.error("Streaming chat with persistence failed", error=str(e))
            error_data = {
                "error": "Failed to process streaming chat. Please try again.",
                "type": "error",
            }
            yield f"data: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        generate_stream_with_persistence(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
