"""ReAct agent streaming handler (v3) — no credit system."""

import asyncio
import json
from collections.abc import AsyncGenerator

import structlog
from fastapi.responses import StreamingResponse

from ....agent.langgraph_react_agent import FinancialAnalysisReActAgent
from ....core.utils import extract_token_usage_from_agent_result
from ....core.utils.date_utils import utcnow
from ....core.utils.title_utils import extract_title_from_response
from ....database.repositories.message_repository import MessageRepository
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
    create_latency_event,
    create_thinking_event,
    format_sse_event,
)

logger = structlog.get_logger()


async def stream_with_react_agent(
    request: ChatRequest,
    user_id: str,
    chat_service: ChatService,
    agent: FinancialAnalysisReActAgent,
    context_manager: ContextWindowManager,
    message_repo: MessageRepository,
    debug: bool = False,
) -> StreamingResponse:

    async def generate_stream() -> AsyncGenerator[str, None]:
        chat_id = None
        tool_event_queue: asyncio.Queue | None = None

        request_start = utcnow()
        ttft_recorded = False
        first_tool_recorded = False

        def get_elapsed_ms() -> int:
            return int((utcnow() - request_start).total_seconds() * 1000)

        try:
            chat_id, chat_created_event = await get_or_create_chat(
                request, user_id, chat_service
            )
            if chat_created_event:
                yield format_sse_event(chat_created_event)

            yield create_thinking_event("initializing", chat_id)

            await chat_service.add_message(
                chat_id=chat_id,
                user_id=user_id,
                role=request.role,
                content=request.message,
                source=request.source or "chat",
                metadata=request.metadata,
                tool_call=request.tool_call,
            )

            if request.role != "user" or request.source == "tool":
                yield create_done_event(chat_id)
                return

            messages = await chat_service.get_chat_messages(chat_id, user_id)

            conversation_history = await compact_context_if_needed(
                messages=messages,
                chat_id=chat_id,
                context_manager=context_manager,
                message_repo=message_repo,
                model=request.model,
            )

            if (
                conversation_history
                and conversation_history[-1]["role"] == "user"
                and conversation_history[-1]["content"] == request.message
            ):
                conversation_history = conversation_history[:-1]

            symbol_instruction = await get_active_symbol_instruction(
                chat_id=chat_id,
                user_id=user_id,
                chat_service=chat_service,
                request_symbol=request.current_symbol,
            )

            user_message_with_context = request.message
            if symbol_instruction:
                user_message_with_context = request.message + symbol_instruction

            yield create_latency_event("context_prepared", get_elapsed_ms())
            yield create_thinking_event("reasoning", chat_id)

            # Tool event streaming setup
            tool_event_queue = asyncio.Queue()
            agent_task = None
            stream_active = True

            async def stream_tool_events_background():
                nonlocal stream_active, agent_task
                MAX_QUEUE_SIZE = 100
                while stream_active:
                    try:
                        queue_size = tool_event_queue.qsize()
                        if queue_size > MAX_QUEUE_SIZE:
                            logger.error("Event queue overflow", queue_size=queue_size)
                            while not tool_event_queue.empty():
                                try:
                                    tool_event_queue.get_nowait()
                                except asyncio.QueueEmpty:
                                    break
                            stream_active = False
                            break

                        event = await asyncio.wait_for(
                            tool_event_queue.get(), timeout=0.1
                        )
                        yield format_sse_event(event)
                    except TimeoutError:
                        if agent_task and agent_task.done():
                            stream_active = False
                            break
                        continue
                    except Exception as e:
                        logger.error("Error streaming tool event", error=str(e))
                        break

                while not tool_event_queue.empty():
                    try:
                        event = tool_event_queue.get_nowait()
                        yield format_sse_event(event)
                    except asyncio.QueueEmpty:
                        break

            try:
                yield create_latency_event("agent_started", get_elapsed_ms())

                agent_task = asyncio.create_task(
                    asyncio.wait_for(
                        agent.ainvoke(
                            user_message=user_message_with_context,
                            conversation_history=conversation_history,
                            debug=debug,
                            language=request.language,
                        ),
                        timeout=120.0,
                    )
                )

                async for tool_event in stream_tool_events_background():
                    if not first_tool_recorded:
                        first_tool_recorded = True
                        tool_name = None
                        if isinstance(tool_event, str) and tool_event.startswith("data: "):
                            try:
                                event_data = json.loads(tool_event[6:].strip())
                                tool_name = event_data.get("tool_name")
                            except (json.JSONDecodeError, AttributeError):
                                pass
                        yield create_latency_event("first_tool", get_elapsed_ms(), tool_name=tool_name)
                    yield tool_event

                result = await agent_task

            except TimeoutError:
                if tool_event_queue:
                    async for tool_event in stream_tool_events_background():
                        yield tool_event
                yield create_error_event("Request timeout.", "AGENT_TIMEOUT")
                return
            except Exception as e:
                logger.error("Agent execution error", error=str(e), exc_info=True)
                if tool_event_queue:
                    async for tool_event in stream_tool_events_background():
                        yield tool_event
                yield create_error_event(f"Agent execution failed: {e}", "AGENT_ERROR")
                return

            raw_answer = result["final_answer"]
            tool_executions = result.get("tool_executions", 0)
            trace_id = result.get("trace_id", "unknown")

            llm_title, final_answer = extract_title_from_response(raw_answer)

            token_usage = extract_token_usage_from_agent_result(result)
            input_tokens = token_usage["input_tokens"]
            output_tokens = token_usage["output_tokens"]

            if "error" in result:
                yield create_error_event(result["error"], "AGENT_EXECUTION_FAILED")
                return

            if tool_executions > 0:
                yield format_sse_event({
                    "type": "tool_info",
                    "tool_executions": tool_executions,
                    "trace_id": trace_id,
                })

            CHUNK_SIZE = 10
            for i in range(0, len(final_answer), CHUNK_SIZE):
                chunk_text = final_answer[i : i + CHUNK_SIZE]
                if not ttft_recorded:
                    ttft_recorded = True
                    yield create_latency_event("first_chunk", get_elapsed_ms())
                yield create_chunk_event(chunk_text)
                await asyncio.sleep(0.03)

            await chat_service.add_message(
                chat_id=chat_id,
                user_id=user_id,
                role="assistant",
                content=final_answer,
                source="llm",
                metadata={
                    "tool_executions": tool_executions,
                    "trace_id": trace_id,
                    "agent_type": "react_sdk",
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                },
            )

            await chat_service.update_title_if_new(
                chat_id=chat_id,
                llm_title=llm_title,
                user_message=request.message,
            )

            total_duration_ms = get_elapsed_ms()
            yield create_latency_event(
                "stream_complete", total_duration_ms,
                trace_id=trace_id, tool_executions=tool_executions,
                input_tokens=input_tokens, output_tokens=output_tokens,
            )

            yield create_done_event(chat_id, tool_executions=tool_executions, trace_id=trace_id)

        except Exception as e:
            logger.error("Stream error (v3)", error=str(e), chat_id=chat_id)
            yield format_sse_event({"type": "error", "error": str(e)})

    return StreamingResponse(generate_stream(), media_type="text/event-stream")
