"""
LangGraph ReAct Agent with SDK Auto-Loop.

Uses create_react_agent for autonomous tool chaining.
Tools are empty for now — fund-specific tools added in M1-3/M1-4.
"""

import asyncio
import random
import time
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

import structlog
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from ..core.config import Settings
from ..core.localization import (
    DEFAULT_LANGUAGE,
    SupportedLanguage,
    get_brief_language_instruction,
)
from ..core.utils import extract_token_usage_from_messages
from .llm_client import get_fund_agent_system_prompt

logger = structlog.get_logger()

if TYPE_CHECKING:
    from langfuse.langchain import CallbackHandler

try:
    from langfuse import Langfuse
    from langfuse.langchain import CallbackHandler as LangfuseCallbackHandler

    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    LangfuseCallbackHandler = None
    Langfuse = None
    logger.warning("Langfuse not available - observability disabled")


class FinancialAnalysisReActAgent:
    """LangGraph SDK-based ReAct agent for fund analysis."""

    def __init__(
        self,
        settings: Settings,
        redis_cache=None,
    ):
        self.settings = settings
        self.redis_cache = redis_cache

        self.langfuse_enabled = False
        self.langfuse_client = None
        if (
            LANGFUSE_AVAILABLE
            and settings.langfuse_public_key
            and settings.langfuse_secret_key
        ):
            try:
                self.langfuse_client = Langfuse(
                    public_key=settings.langfuse_public_key,
                    secret_key=settings.langfuse_secret_key,
                    host=settings.langfuse_host,
                )
                self.langfuse_enabled = True
                logger.info("Langfuse initialized", langfuse_host=settings.langfuse_host)
            except Exception as e:
                logger.warning("Langfuse init failed", error=str(e))

        from .llm_client import get_chat_model

        self.llm = get_chat_model(
            role="main_analyst",
            settings=settings,
            temperature=settings.default_llm_temperature,
        )

        # Fund data tools via AkShare
        from .tools.akshare_fund_tools import create_akshare_fund_tools
        from .tools.eastmoney_tools import create_eastmoney_tools

        self.tools: list[Any] = create_akshare_fund_tools() + create_eastmoney_tools()

        self.checkpointer = MemorySaver()

        def _dynamic_system_prompt(state: dict) -> str:
            return get_fund_agent_system_prompt()

        self.agent = create_react_agent(
            self.llm,
            self.tools,
            checkpointer=self.checkpointer,
            prompt=_dynamic_system_prompt,
        )

        logger.info(
            "FinancialAnalysisReActAgent initialized",
            agent_type="langgraph_sdk",
            total_tools=len(self.tools),
        )

    def _get_langfuse_handler(self) -> "CallbackHandler | None":
        if not self.langfuse_enabled or not LANGFUSE_AVAILABLE:
            return None
        try:
            return LangfuseCallbackHandler()
        except Exception as e:
            logger.warning("Failed to create Langfuse handler", error=str(e))
            return None

    async def ainvoke(
        self,
        user_message: str,
        conversation_history: list[dict[str, str]] | None = None,
        debug: bool = False,
        additional_callbacks: list | None = None,
        language: SupportedLanguage = DEFAULT_LANGUAGE,
    ) -> dict[str, Any]:
        trace_id = f"trace_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        thread_id = (
            f"thread_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        )

        langfuse_trace = None
        agent_start_time = time.perf_counter()
        if self.langfuse_enabled and self.langfuse_client:
            try:
                langfuse_trace = self.langfuse_client.trace(
                    id=trace_id,
                    name="react_agent_invocation",
                    input={"user_message": user_message[:500]},
                    metadata={
                        "thread_id": thread_id,
                        "language": language,
                        "history_length": len(conversation_history) if conversation_history else 0,
                    },
                )
            except Exception as e:
                logger.warning("Langfuse trace creation failed", error=str(e))

        logger.info(
            "ReAct agent invocation started",
            trace_id=trace_id,
            thread_id=thread_id,
            user_message_preview=user_message[:100],
        )

        messages = []
        if conversation_history:
            for msg in conversation_history:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    messages.append(AIMessage(content=msg["content"]))

        language_instruction = get_brief_language_instruction(language)
        user_message_with_language = f"{user_message}\n\n{language_instruction}"
        messages.append(HumanMessage(content=user_message_with_language))

        langfuse_handler = self._get_langfuse_handler()
        config: dict[str, Any] = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": 50,
        }

        callbacks = []
        if additional_callbacks:
            callbacks.extend(additional_callbacks)
        if langfuse_handler:
            callbacks.append(langfuse_handler)
        if callbacks:
            config["callbacks"] = callbacks

        if debug:
            logger.info(
                "DEBUG: Full LLM Prompt",
                trace_id=trace_id,
                message_count=len(messages),
                full_messages=[
                    {"type": msg.__class__.__name__, "content": msg.content}
                    for msg in messages
                ],
            )

        try:
            max_retries = 3
            base_delay = 2.0
            max_delay = 30.0
            jitter_factor = 0.25

            retryable_keywords = [
                "ssl", "certificate", "connection", "timeout",
                "max retries", "eof occurred", "rate limit",
                "service unavailable", "bad gateway", "gateway timeout",
            ]

            last_exception = None
            for attempt in range(max_retries):
                try:
                    result = await self.agent.ainvoke(
                        {"messages": messages}, config=config
                    )
                    if attempt > 0:
                        logger.info("ReAct agent retry succeeded", trace_id=trace_id, attempt=attempt + 1)
                    break
                except Exception as e:
                    last_exception = e
                    error_str = str(e).lower()
                    is_retryable = any(kw in error_str for kw in retryable_keywords)

                    if not is_retryable or attempt == max_retries - 1:
                        logger.error(
                            "ReAct agent failed",
                            trace_id=trace_id, attempt=attempt + 1,
                            error=str(e), error_type=type(e).__name__,
                        )
                        raise

                    base_wait = min(base_delay * (2**attempt), max_delay)
                    jitter = random.uniform(0, jitter_factor * base_wait)
                    delay = base_wait + jitter
                    logger.warning(
                        "ReAct agent retry scheduled",
                        trace_id=trace_id, attempt=attempt + 1,
                        retry_delay_seconds=round(delay, 2),
                    )
                    await asyncio.sleep(delay)

            if last_exception:
                raise last_exception

            final_message = result["messages"][-1]
            final_answer = final_message.content if hasattr(final_message, "content") else ""

            tool_messages = [
                msg for msg in result["messages"]
                if msg.__class__.__name__ == "ToolMessage"
            ]

            total_input_tokens, total_output_tokens, _ = (
                extract_token_usage_from_messages(result["messages"])
            )
            agent_duration_ms = int((time.perf_counter() - agent_start_time) * 1000)

            logger.info(
                "ReAct agent completed",
                trace_id=trace_id,
                total_messages=len(result["messages"]),
                tool_executions=len(tool_messages),
                final_answer_length=len(final_answer),
                agent_duration_ms=agent_duration_ms,
            )

            if langfuse_trace:
                try:
                    langfuse_trace.update(
                        output={"final_answer_length": len(final_answer)},
                        metadata={
                            "duration_ms": agent_duration_ms,
                            "tool_executions": len(tool_messages),
                            "input_tokens": total_input_tokens,
                            "output_tokens": total_output_tokens,
                            "status": "success",
                        },
                    )
                    if self.langfuse_client:
                        self.langfuse_client.flush()
                except Exception as e:
                    logger.warning("Langfuse trace update failed", error=str(e))

            return {
                "trace_id": trace_id,
                "messages": result["messages"],
                "final_answer": final_answer,
                "tool_executions": len(tool_messages),
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "total_tokens": total_input_tokens + total_output_tokens,
                "agent_duration_ms": agent_duration_ms,
            }

        except Exception as e:
            import traceback
            tb_str = traceback.format_exc()
            agent_duration_ms = int((time.perf_counter() - agent_start_time) * 1000)

            logger.error(
                "ReAct agent failed",
                trace_id=trace_id, error=str(e),
                error_type=type(e).__name__, traceback=tb_str,
                agent_duration_ms=agent_duration_ms,
            )

            if langfuse_trace:
                try:
                    langfuse_trace.update(
                        output={"error": str(e)},
                        metadata={"duration_ms": agent_duration_ms, "status": "error"},
                    )
                    if self.langfuse_client:
                        self.langfuse_client.flush()
                except Exception:
                    pass

            return {
                "trace_id": trace_id,
                "messages": messages,
                "final_answer": f"Agent execution failed: {str(e)}",
                "error": str(e),
                "tool_executions": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "agent_duration_ms": agent_duration_ms,
            }

    async def ainvoke_structured(
        self,
        prompt: str,
        schema: type,
        context: str | None = None,
    ):
        logger.info(
            "Structured output invocation",
            schema=schema.__name__,
            prompt_preview=prompt[:100],
        )

        try:
            structured_llm = self.llm.with_structured_output(schema)
            full_prompt = f"{context}\n\n---\n\n{prompt}" if context else prompt

            max_retries = 3
            base_delay = 2.0
            retryable_keywords = [
                "ssl", "certificate", "connection", "timeout",
                "max retries", "eof occurred", "rate limit",
            ]

            result = None
            last_exception = None
            for attempt in range(max_retries):
                try:
                    result = await structured_llm.ainvoke(full_prompt)
                    break
                except Exception as e:
                    last_exception = e
                    error_str = str(e).lower()
                    is_retryable = any(kw in error_str for kw in retryable_keywords)
                    if not is_retryable or attempt == max_retries - 1:
                        raise
                    delay = min(base_delay * (2**attempt), 30.0) + random.uniform(0, 0.5)
                    await asyncio.sleep(delay)

            if last_exception and not result:
                raise last_exception

            return result

        except Exception as e:
            logger.error("Structured output failed", schema=schema.__name__, error=str(e))
            raise
