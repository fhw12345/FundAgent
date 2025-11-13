"""
Chat API endpoint for conversational financial analysis.
Following Factor 11 & 12: Triggerable via API, Stateless Service.

This module contains persistent chat management endpoints using MongoDB.
Legacy session-based endpoints are in chat_legacy.py.
"""

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse

from ..agent.chat_agent import ChatAgent
from ..agent.langgraph_react_agent import FinancialAnalysisReActAgent
from ..core.exceptions import NotFoundError
from ..core.utils import extract_token_usage_from_agent_result
from ..models.chat import ChatUpdate
from ..services.chat_service import ChatService
from ..services.credit_service import CreditService
from .dependencies.chat_deps import (
    get_chat_agent,
    get_chat_service,
    get_current_user_id,
    get_react_agent,
)
from .dependencies.credit_deps import get_credit_service
from .schemas.chat_models import (
    ChatDetailResponse,
    ChatListResponse,
    ChatRequest,
    UpdateUIStateRequest,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/api/chat", tags=["chat"])


# ===== Helper Functions =====


async def get_or_create_chat(
    request: ChatRequest,
    user_id: str,
    chat_service: ChatService,
) -> tuple[str, dict[str, Any] | None]:
    """
    Get existing chat or create new one for streaming endpoints.

    Args:
        request: Chat request with optional chat_id
        user_id: Current user ID
        chat_service: Chat service instance

    Returns:
        Tuple of (chat_id, chat_created_event_dict)
        chat_created_event_dict is None if using existing chat,
        or a dict with chat_id and type='chat_created' if new chat was created
    """
    if request.chat_id:
        chat = await chat_service.get_chat(request.chat_id, user_id)
        return chat.chat_id, None
    else:
        chat_title = request.title if request.title else "New Chat"
        chat = await chat_service.create_chat(user_id, title=chat_title)
        return chat.chat_id, {"chat_id": chat.chat_id, "type": "chat_created"}


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


# ===== Unified Versioned Streaming Endpoint =====


@router.post("/stream")
async def chat_stream_unified(
    request: ChatRequest,
    user_id: str = Depends(get_current_user_id),
    chat_service: ChatService = Depends(get_chat_service),
    simple_agent: ChatAgent = Depends(get_chat_agent),
    react_agent: FinancialAnalysisReActAgent = Depends(get_react_agent),
    credit_service: CreditService = Depends(get_credit_service),
    x_debug: str | None = Header(None, alias="X-Debug"),
) -> StreamingResponse:
    """
    Unified streaming endpoint with version selection.

    **Authentication**: Requires Bearer token in Authorization header.

    **Agent Versions:**
    - **v2** (default): Simple ChatAgent - Basic LLM wrapper for general chat
    - **v3**: SDK ReAct Agent - Autonomous tool chaining for financial analysis

    **Request:**
    ```json
    {
      "message": "Analyze AAPL with Fibonacci",
      "chat_id": "chat_abc123",      // Optional
      "agent_version": "v3",          // Optional: "v2" or "v3" (default: v3)
      "model": "qwen-plus",           // Optional LLM model
      "thinking_enabled": false       // Optional thinking mode
    }
    ```

    **Response:** Server-Sent Events stream

    **Example:**
    ```bash
    # Use v3 (SDK ReAct Agent with tools)
    curl -X POST https://klinematrix.com/api/chat/stream \\
      -H "Authorization: Bearer $TOKEN" \\
      -d '{"message": "Analyze AAPL", "agent_version": "v3"}'

    # Use v2 (simple chat)
    curl -X POST https://klinematrix.com/api/chat/stream \\
      -H "Authorization: Bearer $TOKEN" \\
      -d '{"message": "Hello", "agent_version": "v2"}'
    ```
    """
    logger.info(
        "Unified stream request",
        agent_version=request.agent_version,
        user_id=user_id,
        chat_id=request.chat_id,
    )

    # Route to appropriate agent based on version
    if request.agent_version == "v2":
        # Use simple ChatAgent (basic LLM wrapper)
        return await _stream_with_simple_agent(
            request, user_id, chat_service, simple_agent, credit_service
        )
    elif request.agent_version == "v3":
        # Use SDK ReAct Agent (tool chaining)
        debug_enabled: bool = bool(x_debug and x_debug.lower() in ("true", "1", "yes"))
        return await _stream_with_react_agent(
            request, user_id, chat_service, react_agent, credit_service, debug_enabled
        )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid agent_version: {request.agent_version}. Must be 'v2' or 'v3'",
        )


async def _stream_with_simple_agent(
    request: ChatRequest,
    user_id: str,
    chat_service: ChatService,
    agent: ChatAgent,
    credit_service: CreditService,
) -> StreamingResponse:
    """Stream using simple ChatAgent (v2) with proper credit integration."""

    async def generate_stream() -> AsyncGenerator[str, None]:
        chat_id = None
        transaction = None

        try:
            # Create or get chat
            chat_id, chat_created_event = await get_or_create_chat(request, user_id, chat_service)
            if chat_created_event:
                yield f"data: {json.dumps(chat_created_event)}\n\n"

            # Save user message
            await chat_service.add_message(
                chat_id=chat_id,
                user_id=user_id,
                role=request.role,
                content=request.message,
                source=request.source,
                metadata=request.metadata,
                tool_call=request.tool_call,
            )

            # Only invoke LLM for user messages from actual chat (not tool results or assistant messages)
            if request.role != "user" or request.source == "tool":
                yield f"data: {json.dumps({'type': 'done', 'chat_id': chat_id})}\n\n"
                logger.info(
                    "Skipping agent invocation (v2)",
                    role=request.role,
                    source=request.source,
                    reason="non-user role or tool source",
                )
                return

            # ===== CREDIT SYSTEM INTEGRATION =====
            # Check balance before expensive LLM call
            has_credits = await credit_service.check_balance(
                user_id=user_id,
                estimated_cost=10.0,  # Conservative estimate
            )

            if not has_credits:
                error_data = {
                    "error": "Insufficient credits. Minimum 10 credits required.",
                    "error_code": "INSUFFICIENT_CREDITS",
                    "type": "error",
                }
                yield f"data: {json.dumps(error_data)}\n\n"
                logger.warning(
                    "Request blocked - insufficient credits (v2)", user_id=user_id
                )
                return

            # Create PENDING transaction (safety net)
            transaction = await credit_service.create_pending_transaction(
                user_id=user_id,
                chat_id=chat_id,
                estimated_cost=10.0,
                model=request.model,
            )

            logger.info(
                "Credits checked and transaction created (v2)",
                user_id=user_id,
                model=request.model,
                thinking_enabled=request.thinking_enabled,
                transaction_id=transaction.transaction_id,
            )

            # Get conversation history for context
            messages_list = await chat_service.get_chat_messages(
                chat_id=chat_id, user_id=user_id
            )

            # Convert messages to format expected by ChatAgent
            conversation_history = [
                {"role": msg.role, "content": msg.content} for msg in messages_list
            ]

            logger.info(
                "Prepared conversation history (v2)",
                message_count=len(conversation_history),
                chat_id=chat_id,
            )

            # Stream LLM response with timeout protection
            full_response = ""
            try:
                async def stream_with_timeout():
                    nonlocal full_response
                    async for chunk in agent.stream_chat(
                        messages=conversation_history,
                        model=request.model,
                        thinking_enabled=request.thinking_enabled,
                        max_tokens=request.max_tokens,
                    ):
                        full_response += chunk
                        yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"

                async for chunk_data in asyncio.wait_for(
                    stream_with_timeout(),
                    timeout=120.0  # 2 minutes max
                ):
                    yield chunk_data

            except asyncio.TimeoutError:
                logger.error(
                    "Agent streaming timeout (v2)",
                    chat_id=chat_id,
                    user_id=user_id,
                    timeout_seconds=120,
                )
                # Fail transaction to release credits
                if transaction:
                    await credit_service.fail_transaction(transaction.transaction_id)
                error_data = {
                    "error": "Request timeout. The response is taking too long. Please try again.",
                    "error_code": "STREAM_TIMEOUT",
                    "type": "error",
                }
                yield f"data: {json.dumps(error_data)}\n\n"
                return
            except Exception as e:
                logger.error(
                    "Agent streaming error (v2)",
                    chat_id=chat_id,
                    user_id=user_id,
                    error=str(e),
                    exc_info=True,
                )
                # Fail transaction to release credits
                if transaction:
                    await credit_service.fail_transaction(transaction.transaction_id)
                error_data = {
                    "error": f"Streaming failed: {str(e)}",
                    "error_code": "STREAM_ERROR",
                    "type": "error",
                }
                yield f"data: {json.dumps(error_data)}\n\n"
                return

            # Get token usage from agent
            token_usage = agent.get_last_token_usage(model=request.model)

            if not token_usage:
                logger.error(
                    "No token usage available after streaming (v2)",
                    transaction_id=transaction.transaction_id,
                )
                # Fail the transaction - no charge
                await credit_service.fail_transaction(transaction.transaction_id)
                error_data = {
                    "error": "Failed to track token usage. No charge applied.",
                    "type": "error",
                }
                yield f"data: {json.dumps(error_data)}\n\n"
                return

            # Save assistant message with transaction linkage
            from ..models.message import MessageMetadata

            assistant_message = await chat_service.add_message(
                chat_id=chat_id,
                user_id=user_id,
                role="assistant",
                content=full_response,
                source="llm",
                metadata=MessageMetadata(
                    model=request.model,
                    tokens=token_usage.total_tokens,
                    input_tokens=token_usage.input_tokens,
                    output_tokens=token_usage.output_tokens,
                    transaction_id=transaction.transaction_id,
                ),
            )

            # Complete transaction and deduct credits atomically
            updated_transaction, updated_user = (
                await credit_service.complete_transaction_with_deduction(
                    transaction_id=transaction.transaction_id,
                    message_id=assistant_message.message_id,
                    input_tokens=token_usage.input_tokens,
                    output_tokens=token_usage.output_tokens,
                    model=request.model,
                    thinking_enabled=request.thinking_enabled,
                )
            )

            if not updated_transaction or not updated_user:
                logger.error(
                    "Failed to complete transaction (v2)",
                    transaction_id=transaction.transaction_id,
                )
                error_data = {
                    "error": "Failed to process payment. Please contact support.",
                    "type": "error",
                }
                yield f"data: {json.dumps(error_data)}\n\n"
                return

            logger.info(
                "Transaction completed successfully (v2)",
                transaction_id=transaction.transaction_id,
                tokens=token_usage.total_tokens,
                cost=updated_transaction.actual_cost,
                new_balance=updated_user.credits,
            )

            yield f"data: {json.dumps({'type': 'done', 'chat_id': chat_id})}\n\n"

        except Exception as e:
            logger.error("Stream error (v2)", error=str(e), chat_id=chat_id)
            # Fail transaction if one was created
            if transaction:
                await credit_service.fail_transaction(transaction.transaction_id)
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(generate_stream(), media_type="text/event-stream")


async def _stream_with_react_agent(
    request: ChatRequest,
    user_id: str,
    chat_service: ChatService,
    agent: FinancialAnalysisReActAgent,
    credit_service: CreditService,
    debug: bool = False,
) -> StreamingResponse:
    """Stream using SDK ReAct Agent (v3).

    Args:
        request: Chat request with message and options
        user_id: Current user ID
        chat_service: Chat service instance
        agent: ReAct agent instance
        credit_service: Credit service instance
        debug: If True, log full LLM prompts for debugging
    """

    async def generate_stream() -> AsyncGenerator[str, None]:
        chat_id = None
        transaction = None

        try:
            # Create or get chat
            chat_id, chat_created_event = await get_or_create_chat(request, user_id, chat_service)
            if chat_created_event:
                yield f"data: {json.dumps(chat_created_event)}\n\n"

            # Save message
            logger.debug(
                "Saving message with tool_call",
                has_tool_call=request.tool_call is not None,
            )
            await chat_service.add_message(
                chat_id=chat_id,
                user_id=user_id,
                role=request.role,
                content=request.message,
                source=request.source or "chat",
                metadata=request.metadata,
                tool_call=request.tool_call,
            )

            # Only invoke LLM for user messages from actual chat (not tool results or assistant messages)
            if request.role != "user" or request.source == "tool":
                yield f"data: {json.dumps({'type': 'done', 'chat_id': chat_id})}\n\n"
                logger.info(
                    "Skipping agent invocation (v3)",
                    role=request.role,
                    source=request.source,
                    reason="non-user role or tool source",
                )
                return

            # ===== CREDIT SYSTEM INTEGRATION (v3 - Agent Mode) =====
            # Check balance before expensive LLM call
            estimated_cost = 10.0  # Conservative estimate for agent with tools
            has_credits = await credit_service.check_balance(
                user_id=user_id, estimated_cost=estimated_cost
            )

            if not has_credits:
                error_data = {
                    "error": "Insufficient credits. Minimum 10 credits required.",
                    "error_code": "INSUFFICIENT_CREDITS",
                    "type": "error",
                }
                yield f"data: {json.dumps(error_data)}\n\n"
                return

            # Create PENDING transaction (safety net before LLM call)
            transaction = await credit_service.create_pending_transaction(
                user_id=user_id,
                chat_id=chat_id,
                estimated_cost=estimated_cost,
                model=request.model,
            )

            logger.info(
                "Credits checked and transaction created for v3 agent",
                user_id=user_id,
                chat_id=chat_id,
                transaction_id=transaction.transaction_id,
                estimated_cost=estimated_cost,
            )

            # Get conversation history for context
            # Messages are already in chronological order (oldest first) from get_chat_messages
            messages = await chat_service.get_chat_messages(chat_id, user_id, limit=10)
            conversation_history = [
                {"role": msg.role, "content": msg.content} for msg in messages
            ]

            # Exclude the last user message if it matches the current message
            # (we saved it to DB first, but will pass it separately to the agent)
            if (
                conversation_history
                and conversation_history[-1]["role"] == "user"
                and conversation_history[-1]["content"] == request.message
            ):
                conversation_history = conversation_history[:-1]

            logger.info(
                "Conversation history prepared for agent",
                chat_id=chat_id,
                total_messages=len(messages),
                conversation_history_count=len(conversation_history),
                preview=[
                    {"role": msg["role"], "content": msg["content"][:50]}
                    for msg in conversation_history[-3:]
                ],
            )

            # Invoke ReAct agent (auto-loop handles tool chaining) with timeout protection
            try:
                result = await asyncio.wait_for(
                    agent.ainvoke(
                        user_message=request.message,
                        conversation_history=conversation_history,
                        debug=debug,
                    ),
                    timeout=120.0  # 2 minutes max for agent response
                )
            except asyncio.TimeoutError:
                logger.error(
                    "Agent execution timeout",
                    chat_id=chat_id,
                    user_id=user_id,
                    timeout_seconds=120,
                )
                # Fail transaction to release credits
                if transaction:
                    await credit_service.fail_transaction(transaction.transaction_id)
                error_data = {
                    "error": "Request timeout. The analysis is taking too long. Please try again with a simpler question.",
                    "error_code": "AGENT_TIMEOUT",
                    "type": "error",
                }
                yield f"data: {json.dumps(error_data)}\n\n"
                return
            except Exception as e:
                logger.error(
                    "Agent execution error",
                    chat_id=chat_id,
                    user_id=user_id,
                    error=str(e),
                    exc_info=True,
                )
                # Fail transaction to release credits
                if transaction:
                    await credit_service.fail_transaction(transaction.transaction_id)
                error_data = {
                    "error": f"Agent execution failed: {str(e)}",
                    "error_code": "AGENT_ERROR",
                    "type": "error",
                }
                yield f"data: {json.dumps(error_data)}\n\n"
                return

            final_answer = result["final_answer"]
            tool_executions = result.get("tool_executions", 0)
            trace_id = result.get("trace_id", "unknown")

            # Extract token usage from agent result
            token_usage = extract_token_usage_from_agent_result(result)
            input_tokens = token_usage["input_tokens"]
            output_tokens = token_usage["output_tokens"]
            total_tokens = token_usage["total_tokens"]

            # Check if agent execution failed
            if "error" in result:
                logger.error(
                    "Agent execution failed with error",
                    chat_id=chat_id,
                    trace_id=trace_id,
                    error=result["error"],
                )
                # Fail transaction and return clear error
                if transaction:
                    await credit_service.fail_transaction(transaction.transaction_id)
                error_data = {
                    "error": result["error"],
                    "error_code": "AGENT_EXECUTION_FAILED",
                    "type": "error",
                }
                yield f"data: {json.dumps(error_data)}\n\n"
                return

            logger.info(
                "ReAct agent execution completed",
                chat_id=chat_id,
                trace_id=trace_id,
                tool_executions=tool_executions,
                answer_length=len(final_answer),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
            )

            # Validate token usage before proceeding (only if no error)
            if input_tokens == 0 and output_tokens == 0:
                logger.warning(
                    "No token usage extracted from v3 agent result",
                    chat_id=chat_id,
                    trace_id=trace_id,
                )
                # Fail transaction if no token usage available
                if transaction:
                    await credit_service.fail_transaction(transaction.transaction_id)
                error_data = {
                    "error": "Failed to extract token usage from agent",
                    "error_code": "TOKEN_EXTRACTION_FAILED",
                    "type": "error",
                }
                yield f"data: {json.dumps(error_data)}\n\n"
                return

            # Send tool execution count (optional metadata)
            if tool_executions > 0:
                tool_info = {
                    "type": "tool_info",
                    "tool_executions": tool_executions,
                    "trace_id": trace_id,
                }
                yield f"data: {json.dumps(tool_info)}\n\n"

            # Stream final answer character-by-character
            for char in final_answer:
                chunk = {"type": "chunk", "content": char}
                yield f"data: {json.dumps(chunk)}\n\n"
                await asyncio.sleep(0.01)  # Smooth streaming

            # Save assistant message with metadata (including transaction linkage)
            assistant_message = await chat_service.add_message(
                chat_id=chat_id,
                user_id=user_id,
                role="assistant",
                content=final_answer,
                source="llm",
                metadata={
                    "tool_executions": tool_executions,
                    "trace_id": trace_id,
                    "agent_type": "react_sdk",
                    "transaction_id": transaction.transaction_id,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                },
            )

            # ===== COMPLETE TRANSACTION AND DEDUCT CREDITS =====
            updated_transaction, updated_user = (
                await credit_service.complete_transaction_with_deduction(
                    transaction_id=transaction.transaction_id,
                    message_id=assistant_message.message_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    model=request.model,
                    thinking_enabled=request.thinking_enabled,
                )
            )

            if updated_transaction and updated_user:
                logger.info(
                    "Transaction completed successfully for v3 agent",
                    transaction_id=updated_transaction.transaction_id,
                    actual_cost=updated_transaction.actual_cost,
                    remaining_credits=updated_user.credits,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )
            else:
                logger.error(
                    "Failed to complete transaction for v3 agent",
                    transaction_id=transaction.transaction_id,
                )

            # Send completion event (include credit info)
            completion_event = {
                "type": "done",
                "chat_id": chat_id,
                "tool_executions": tool_executions,
                "trace_id": trace_id,
                "credits_used": (
                    updated_transaction.actual_cost if updated_transaction else 0
                ),
                "remaining_credits": updated_user.credits if updated_user else None,
            }
            yield f"data: {json.dumps(completion_event)}\n\n"

        except Exception as e:
            logger.error("Stream error (v3)", error=str(e), chat_id=chat_id)

            # Fail transaction if it exists
            if transaction:
                await credit_service.fail_transaction(transaction.transaction_id)
                logger.info(
                    "Transaction marked as FAILED due to error",
                    transaction_id=transaction.transaction_id,
                )

            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(generate_stream(), media_type="text/event-stream")

