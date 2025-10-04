"""
Chat API endpoint for conversational financial analysis.
Following Factor 11 & 12: Triggerable via API, Stateless Service.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..agent.chat_agent import ChatAgent
from ..agent.session_manager import SessionManager, get_session_manager
from ..core.config import Settings, get_settings

logger = structlog.get_logger()

router = APIRouter(prefix="/api/chat", tags=["chat"])


# Request/Response Models
class ChatRequest(BaseModel):
    """Chat request from user."""

    message: str = Field(
        ..., min_length=1, max_length=10000, description="User message"
    )
    session_id: str | None = Field(
        None, description="Session ID for continuing conversation"
    )


class ChatResponse(BaseModel):
    """Chat response to user."""

    response: str = Field(..., description="Assistant's response")
    session_id: str = Field(..., description="Session ID for this conversation")
    message_count: int = Field(..., description="Total messages in conversation")


# Dependency for chat agent
def get_chat_agent(
    settings: Settings = Depends(get_settings),
    session_manager: SessionManager = Depends(get_session_manager),
) -> ChatAgent:
    """
    Get or create chat agent instance.

    In production, this would be a singleton managed at app startup.
    """
    return ChatAgent(settings=settings, session_manager=session_manager)


@router.post("/sessions", response_model=dict)
async def create_session(
    agent: ChatAgent = Depends(get_chat_agent),
) -> dict:
    """
    Create a new chat session without sending a message.

    This is useful when you want to initialize a session before
    sending algorithm results or analysis data.

    **Response:**
    ```json
    {
      "session_id": "a1b2c3d4-...",
      "created_at": "2025-10-04T09:00:00Z"
    }
    ```
    """
    session = await agent.create_session()

    logger.info(
        "🆕 Empty session created",
        session_id=session.session_id,
    )

    return {
        "session_id": session.session_id,
        "created_at": session.created_at.isoformat(),
    }


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    agent: ChatAgent = Depends(get_chat_agent),
) -> ChatResponse:
    """
    Send a message and receive response from financial analysis agent.

    **Multi-turn conversation:**
    - First request: Omit session_id, receive new session_id in response
    - Follow-up requests: Include session_id to continue conversation

    **Example:**
    ```json
    {
      "message": "What are the Fibonacci levels for AAPL?",
      "session_id": "a1b2c3d4-..."
    }
    ```

    **Response:**
    ```json
    {
      "response": "I'll analyze the Fibonacci levels for AAPL...",
      "session_id": "a1b2c3d4-...",
      "message_count": 2
    }
    ```
    """
    try:
        # Create new session or retrieve existing
        if request.session_id:
            session = agent.get_session(request.session_id)
            if session is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Session {request.session_id} not found or expired. Please start a new conversation.",
                )
            session_id = request.session_id
        else:
            # Create new session
            session = await agent.create_session()
            session_id = session.session_id
            logger.info("New chat session created", session_id=session_id)

        # Process message
        response_text = await agent.chat(
            session_id=session_id, user_message=request.message
        )

        # Get updated session for message count
        updated_session = agent.get_session(session_id)
        message_count = len(updated_session.messages) if updated_session else 0

        logger.info(
            "Chat request completed",
            session_id=session_id,
            message_count=message_count,
        )

        return ChatResponse(
            response=response_text,
            session_id=session_id,
            message_count=message_count,
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.error("Validation error", error=str(e))
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("Chat request failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to process chat request. Please try again.",
        ) from e


@router.get("/sessions/{session_id}", response_model=dict)
async def get_session_info(
    session_id: str,
    agent: ChatAgent = Depends(get_chat_agent),
) -> dict:
    """
    Get information about a chat session.

    Returns session metadata and message count.
    """
    session = agent.get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=404,
            detail=f"Session {session_id} not found or expired",
        )

    return {
        "session_id": session.session_id,
        "message_count": len(session.messages),
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
        "current_symbol": session.current_symbol,
    }


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    session_manager: SessionManager = Depends(get_session_manager),
) -> dict:
    """
    Delete a chat session.

    Returns success status.
    """
    deleted = session_manager.delete_session(session_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Session {session_id} not found",
        )

    logger.info("Session deleted", session_id=session_id)
    return {"status": "success", "session_id": session_id}


class AddContextRequest(BaseModel):
    """Request to add context (algorithm results) to session."""

    content: str = Field(
        ..., min_length=1, description="Content to add as assistant message"
    )
    session_id: str = Field(..., description="Session ID")


@router.post("/sessions/{session_id}/context")
async def add_context_to_session(
    session_id: str,
    request: AddContextRequest,
    session_manager: SessionManager = Depends(get_session_manager),
) -> dict:
    """
    Add context (algorithm results) to session for LLM to see.

    This endpoint allows the frontend to inject algorithm results
    into the conversation history so the LLM can reference them.

    **Example:**
    ```json
    {
      "content": "## Fibonacci Analysis - AAPL\n...",
      "session_id": "a1b2c3d4-..."
    }
    ```
    """
    logger.info(
        "📥 Context sync request received",
        session_id=session_id,
        content_preview=(
            request.content[:100] + "..."
            if len(request.content) > 100
            else request.content
        ),
        content_length=len(request.content),
    )

    session = session_manager.get_session(session_id)
    if session is None:
        logger.error(
            "❌ Session not found for context sync",
            session_id=session_id,
        )
        raise HTTPException(
            status_code=404,
            detail=f"Session {session_id} not found or expired",
        )

    message_count_before = len(session.messages)

    # Add content as assistant message
    session.add_message("assistant", request.content)
    session_manager.update_session(session)

    message_count_after = len(session.messages)

    logger.info(
        "✅ Context added to session",
        session_id=session_id,
        content_length=len(request.content),
        message_count_before=message_count_before,
        message_count_after=message_count_after,
    )

    return {
        "status": "success",
        "session_id": session_id,
        "message_count": len(session.messages),
    }
