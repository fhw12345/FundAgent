"""
ReAct agent streaming handler (v3).

This module contains the streaming response logic for the ReAct Agent (v3),
handling SSE streaming, tool execution callbacks, credit integration,
and context management.

Story 1.4: Streaming Latency Optimization
- Added TTFT (Time-To-First-Token) tracking
- Implemented eager streaming with "thinking" events
- Added latency metrics for Langfuse observability
"""

import asyncio
import json
from collections.abc import AsyncGenerator

import structlog
from fastapi.responses import StreamingResponse

from ....agent.callbacks.tool_execution_callback import ToolExecutionCallback
from ....agent.langgraph_react_agent import FinancialAnalysisReActAgent
from ....core.utils import extract_token_usage_from_agent_result
from ....core.utils.date_utils import utcnow
from ....database.repositories.message_repository import MessageRepository
from ....services.chat_service import ChatService
from ....services.context_window_manager import ContextWindowManager
from ....services.credit_service import CreditService
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
    credit_service: CreditService,
    context_manager: ContextWindowManager,
    message_repo: MessageRepository,
    debug: bool = False,
) -> StreamingResponse:
    """Stream using SDK ReAct Agent (v3) with real-time tool execution visibility and context compaction.

    Args:
        request: Chat request with message and options
        user_id: Current user ID
        chat_service: Chat service instance
        agent: ReAct agent instance
        credit_service: Credit service instance
        context_manager: Context window manager for automatic compaction
        message_repo: Message repository for persisting summaries
        debug: If True, log full LLM prompts for debugging
    """

    async def generate_stream() -> AsyncGenerator[str, None]:
        chat_id = None
        transaction = None
        tool_event_queue = None

        # ===== TTFT TRACKING (Story 1.4) =====
        # Track request start time for latency metrics
        request_start = utcnow()
        ttft_recorded = False  # Track when first content chunk is sent
        first_tool_recorded = False  # Track when first tool event is sent

        def get_elapsed_ms() -> int:
            """Get milliseconds elapsed since request start."""
            return int((utcnow() - request_start).total_seconds() * 1000)

        try:
            # Create or get chat
            chat_id, chat_created_event = await get_or_create_chat(
                request, user_id, chat_service
            )
            if chat_created_event:
                yield format_sse_event(chat_created_event)

            # ===== EAGER STREAMING (Story 1.4) =====
            # Emit thinking event immediately to reduce perceived latency
            # This gives users immediate feedback that processing has started
            yield create_thinking_event("initializing", chat_id)

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
                yield create_done_event(chat_id)
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
                yield create_error_event(
                    "Insufficient credits. Minimum 10 credits required.",
                    "INSUFFICIENT_CREDITS",
                )
                return

            # Create PENDING transaction (safety net before LLM call)
            transaction = await credit_service.create_pending_transaction(
                user_id=user_id,
                chat_id=chat_id,
                estimated_cost=estimated_cost,
                model=request.model,
            )

            # Emit latency metric: credit check complete
            yield create_latency_event("credit_checked", get_elapsed_ms())

            logger.info(
                "Credits checked and transaction created for v3 agent",
                user_id=user_id,
                chat_id=chat_id,
                transaction_id=transaction.transaction_id,
                estimated_cost=estimated_cost,
                elapsed_ms=get_elapsed_ms(),
            )

            # Get conversation history for context
            # Messages are already in chronological order (oldest first) from get_chat_messages
            # NOTE: Removed limit=10 to allow compaction to work with full history
            messages = await chat_service.get_chat_messages(chat_id, user_id)

            # ===== CONTEXT COMPACTION =====
            # Check if context needs compaction (> 75% of limit)
            # If so, summarize old messages and delete them to stay within limits
            conversation_history = await compact_context_if_needed(
                messages=messages,
                chat_id=chat_id,
                context_manager=context_manager,
                message_repo=message_repo,
                model=request.model,
            )

            # Exclude the last user message if it matches the current message
            # (we saved it to DB first, but will pass it separately to the agent)
            if (
                conversation_history
                and conversation_history[-1]["role"] == "user"
                and conversation_history[-1]["content"] == request.message
            ):
                conversation_history = conversation_history[:-1]

            # ===== SYMBOL CONTEXT INJECTION =====
            # Get active symbol instruction to append to user message
            # Priority: request.current_symbol > DB ui_state
            symbol_instruction = await get_active_symbol_instruction(
                chat_id=chat_id,
                user_id=user_id,
                chat_service=chat_service,
                request_symbol=request.current_symbol,
            )

            # Append symbol context to user message (similar to language instruction)
            user_message_with_context = request.message
            if symbol_instruction:
                user_message_with_context = request.message + symbol_instruction
                logger.info(
                    "Symbol context appended to user message (v3)",
                    chat_id=chat_id,
                    original_length=len(request.message),
                    enriched_length=len(user_message_with_context),
                )

            logger.info(
                "Conversation history prepared for agent",
                chat_id=chat_id,
                total_messages=len(messages),
                conversation_history_count=len(conversation_history),
                preview=[
                    {"role": msg["role"], "content": msg["content"][:50]}
                    for msg in conversation_history[-3:]
                ],
                elapsed_ms=get_elapsed_ms(),
            )

            # Emit latency metric: context preparation complete
            yield create_latency_event("context_prepared", get_elapsed_ms())

            # Update thinking stage: now reasoning/analyzing
            yield create_thinking_event("reasoning", chat_id)

            # ===== TOOL EXECUTION CALLBACK SETUP =====
            # Create event queue for real-time tool execution streaming
            tool_event_queue = asyncio.Queue()
            tool_callback = ToolExecutionCallback(tool_event_queue, request.language)
            agent_task = None
            stream_active = True

            # Background task to continuously drain and stream tool events
            async def stream_tool_events_background():
                """Continuously drain tool event queue and yield SSE events in real-time"""
                nonlocal stream_active, agent_task
                MAX_QUEUE_SIZE = 100  # Circuit breaker threshold
                while stream_active:
                    try:
                        # Circuit breaker: Check queue size to prevent overflow
                        queue_size = tool_event_queue.qsize()
                        if queue_size > MAX_QUEUE_SIZE:
                            logger.error(
                                "Event queue overflow - circuit breaker triggered",
                                queue_size=queue_size,
                                max_size=MAX_QUEUE_SIZE,
                            )
                            # Drain queue to prevent memory exhaustion
                            while not tool_event_queue.empty():
                                try:
                                    tool_event_queue.get_nowait()
                                except asyncio.QueueEmpty:
                                    break
                            stream_active = False
                            break

                        # Use short timeout to check stream_active flag frequently
                        event = await asyncio.wait_for(
                            tool_event_queue.get(), timeout=0.1
                        )
                        # Stream tool event immediately to frontend
                        yield format_sse_event(event)
                        logger.debug(
                            "Tool event streamed in real-time",
                            event_type=event["type"],
                            tool_name=event["tool_name"],
                        )
                    except TimeoutError:
                        # No event available - check if agent completed
                        if agent_task and agent_task.done():
                            logger.info("Agent completed, stopping tool event stream")
                            stream_active = False
                            break
                        continue
                    except Exception as e:
                        logger.error(
                            "Error streaming tool event", error=str(e), exc_info=True
                        )
                        break

                # Final drain after agent completes
                while not tool_event_queue.empty():
                    try:
                        event = tool_event_queue.get_nowait()
                        yield format_sse_event(event)
                        logger.debug("Tool event drained", event_type=event["type"])
                    except asyncio.QueueEmpty:
                        break

            # Invoke ReAct agent with callback (auto-loop handles tool chaining)
            try:
                # Emit latency metric: agent starting
                yield create_latency_event("agent_started", get_elapsed_ms())

                # Create agent invocation task
                agent_task = asyncio.create_task(
                    asyncio.wait_for(
                        agent.ainvoke(
                            user_message=user_message_with_context,  # Use enriched message with symbol context
                            conversation_history=conversation_history,
                            debug=debug,
                            additional_callbacks=[tool_callback],
                            language=request.language,
                        ),
                        timeout=120.0,  # 2 minutes max for agent response
                    )
                )

                # Stream tool events concurrently while agent runs
                # The generator will automatically stop when agent completes
                logger.info(
                    "Starting tool event streaming loop",
                    elapsed_ms=get_elapsed_ms(),
                )
                async for tool_event in stream_tool_events_background():
                    # Track first tool event (Story 1.4: TTFT optimization)
                    # Note: tool_event is already an SSE-formatted string from format_sse_event()
                    if not first_tool_recorded:
                        first_tool_recorded = True
                        # Extract tool_name from SSE string if possible
                        tool_name = None
                        if isinstance(tool_event, str) and tool_event.startswith("data: "):
                            try:
                                event_data = json.loads(tool_event[6:].strip())
                                tool_name = event_data.get("tool_name")
                            except (json.JSONDecodeError, AttributeError):
                                pass
                        elif isinstance(tool_event, dict):
                            tool_name = tool_event.get("tool_name")
                        yield create_latency_event(
                            "first_tool",
                            get_elapsed_ms(),
                            tool_name=tool_name,
                        )
                    yield tool_event

                # Generator has exited, agent is done
                logger.info("Tool event streaming completed")
                result = await agent_task
                logger.info("Agent result received", has_result=bool(result))

            except TimeoutError:
                logger.error(
                    "Agent execution timeout",
                    chat_id=chat_id,
                    user_id=user_id,
                    timeout_seconds=120,
                )
                # Drain any pending tool events before erroring
                if tool_event_queue:
                    async for tool_event in stream_tool_events_background():
                        yield tool_event

                # Fail transaction to release credits
                if transaction:
                    await credit_service.fail_transaction(transaction.transaction_id)
                yield create_error_event(
                    "Request timeout. The analysis is taking too long. Please try again with a simpler question.",
                    "AGENT_TIMEOUT",
                )
                return
            except Exception as e:
                logger.error(
                    "Agent execution error",
                    chat_id=chat_id,
                    user_id=user_id,
                    error=str(e),
                    exc_info=True,
                )
                # Drain any pending tool events before erroring
                if tool_event_queue:
                    async for tool_event in stream_tool_events_background():
                        yield tool_event

                # Fail transaction to release credits
                if transaction:
                    await credit_service.fail_transaction(transaction.transaction_id)
                yield create_error_event(
                    f"Agent execution failed: {str(e)}",
                    "AGENT_ERROR",
                )
                return

            final_answer = result["final_answer"]
            tool_executions = result.get("tool_executions", 0)
            trace_id = result.get("trace_id", "unknown")
            logger.info(
                "Extracted result fields",
                answer_len=len(final_answer),
                trace_id=trace_id,
            )

            # Extract token usage from agent result
            token_usage = extract_token_usage_from_agent_result(result)
            logger.info(
                "Token usage extracted",
                input=token_usage["input_tokens"],
                output=token_usage["output_tokens"],
            )
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
                yield create_error_event(
                    result["error"],
                    "AGENT_EXECUTION_FAILED",
                )
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
                yield create_error_event(
                    "Failed to extract token usage from agent",
                    "TOKEN_EXTRACTION_FAILED",
                )
                return

            # Send tool execution count (optional metadata)
            if tool_executions > 0:
                tool_info = {
                    "type": "tool_info",
                    "tool_executions": tool_executions,
                    "trace_id": trace_id,
                }
                yield format_sse_event(tool_info)

            # Stream final answer in batches (10 chars at a time)
            # Reduces SSE events by 90% while maintaining smooth UX
            CHUNK_SIZE = 10
            logger.info(
                "Starting to stream final answer",
                answer_length=len(final_answer),
                chunk_size=CHUNK_SIZE,
                chat_id=chat_id,
                elapsed_ms=get_elapsed_ms(),
            )
            for i in range(0, len(final_answer), CHUNK_SIZE):
                chunk_text = final_answer[i : i + CHUNK_SIZE]
                # Track TTFT (Time-To-First-Token) - Story 1.4
                if not ttft_recorded:
                    ttft_recorded = True
                    ttft_ms = get_elapsed_ms()
                    yield create_latency_event("first_chunk", ttft_ms)
                    logger.info(
                        "TTFT recorded (Time-To-First-Token)",
                        chat_id=chat_id,
                        ttft_ms=ttft_ms,
                        trace_id=trace_id,
                    )
                yield create_chunk_event(chunk_text)
                await asyncio.sleep(0.03)  # Proportional delay (10 chars → 0.03s)

            logger.info(
                "Finished streaming final answer",
                chat_id=chat_id,
                elapsed_ms=get_elapsed_ms(),
            )

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
            (
                updated_transaction,
                updated_user,
            ) = await credit_service.complete_transaction_with_deduction(
                transaction_id=transaction.transaction_id,
                message_id=assistant_message.message_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model=request.model,
                thinking_enabled=request.thinking_enabled,
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

            # Emit final latency metric: stream complete (Story 1.4)
            total_duration_ms = get_elapsed_ms()
            yield create_latency_event(
                "stream_complete",
                total_duration_ms,
                trace_id=trace_id,
                tool_executions=tool_executions,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

            logger.info(
                "Stream latency metrics complete",
                chat_id=chat_id,
                trace_id=trace_id,
                total_duration_ms=total_duration_ms,
                ttft_recorded=ttft_recorded,
                first_tool_recorded=first_tool_recorded,
            )

            # Send completion event (include credit info)
            yield create_done_event(
                chat_id,
                tool_executions=tool_executions,
                trace_id=trace_id,
                credits_used=(
                    updated_transaction.actual_cost if updated_transaction else 0
                ),
                remaining_credits=updated_user.credits if updated_user else None,
            )

        except Exception as e:
            logger.error("Stream error (v3)", error=str(e), chat_id=chat_id)

            # Fail transaction if it exists
            if transaction:
                await credit_service.fail_transaction(transaction.transaction_id)
                logger.info(
                    "Transaction marked as FAILED due to error",
                    transaction_id=transaction.transaction_id,
                )

            yield format_sse_event({"type": "error", "error": str(e)})

    return StreamingResponse(generate_stream(), media_type="text/event-stream")
