"""Simple agent streaming handler (v2) — no credit system."""

import asyncio
from collections.abc import AsyncGenerator

import structlog
from fastapi.responses import StreamingResponse

from ....agent.chat_agent import ChatAgent
from ....database.repositories.message_repository import MessageRepository
from ....models.message import MessageMetadata
from ....services.chat_service import ChatService
from ....services.context_window_manager import ContextWindowManager
from ...schemas.chat_models import ChatRequest
from ..helpers import (
    compact_context_if_needed,
    get_active_symbol_instruction,
    get_or_create_chat,
)
from .helpers import (
    create_chunk_event,
    create_done_event,
    create_error_event,
    format_sse_event,
)

logger = structlog.get_logger()


async def stream_with_simple_agent(
    request: ChatRequest,
    user_id: str,
    chat_service: ChatService,
    agent: ChatAgent,
    context_manager: ContextWindowManager,
    message_repo: MessageRepository,
) -> StreamingResponse:

    async def generate_stream() -> AsyncGenerator[str, None]:
        chat_id = None
        try:
            chat_id, chat_created_event = await get_or_create_chat(request, user_id, chat_service)
            if chat_created_event:
                yield format_sse_event(chat_created_event)

            await chat_service.add_message(
                chat_id=chat_id, user_id=user_id, role=request.role,
                content=request.message, source=request.source,
                metadata=request.metadata, tool_call=request.tool_call,
            )

            if request.role != "user" or request.source == "tool":
                yield create_done_event(chat_id)
                return

            messages_list = await chat_service.get_chat_messages(chat_id=chat_id, user_id=user_id)
            conversation_history = await compact_context_if_needed(
                messages=messages_list, chat_id=chat_id, context_manager=context_manager,
                message_repo=message_repo, model=request.model,
            )

            symbol_instruction = await get_active_symbol_instruction(
                chat_id=chat_id, user_id=user_id, chat_service=chat_service,
                request_symbol=request.current_symbol,
            )
            if symbol_instruction and conversation_history and conversation_history[-1]["role"] == "user":
                conversation_history[-1]["content"] += symbol_instruction

            full_response = ""
            try:
                async for chunk in agent.stream_chat(
                    messages=conversation_history, model=request.model,
                    thinking_enabled=request.thinking_enabled, max_tokens=request.max_tokens,
                ):
                    full_response += chunk
                    yield create_chunk_event(chunk)
            except TimeoutError:
                yield create_error_event("Request timeout.", "STREAM_TIMEOUT")
                return
            except Exception as e:
                yield create_error_event(f"Streaming failed: {e}", "STREAM_ERROR")
                return

            token_usage = agent.get_last_token_usage(model=request.model)

            await chat_service.add_message(
                chat_id=chat_id, user_id=user_id, role="assistant",
                content=full_response, source="llm",
                metadata=MessageMetadata(
                    model=request.model,
                    tokens=token_usage.total_tokens if token_usage else 0,
                    input_tokens=token_usage.input_tokens if token_usage else 0,
                    output_tokens=token_usage.output_tokens if token_usage else 0,
                ),
            )

            yield create_done_event(chat_id)

        except Exception as e:
            logger.error("Stream error (v2)", error=str(e), chat_id=chat_id)
            yield format_sse_event({"type": "error", "error": str(e)})

    return StreamingResponse(generate_stream(), media_type="text/event-stream")
