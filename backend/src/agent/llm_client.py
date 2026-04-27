"""
Multi-provider LLM client factory for Agent Maestro proxy.

Routes all LLM calls through Agent Maestro (localhost:23333) using
native LangChain wrappers for each vendor:
- OpenAI (ChatOpenAI) → gpt-5.4
- Anthropic (ChatAnthropic) → claude-opus-4.7
- Google (ChatGoogleGenerativeAI) → gemini-3.1-pro-preview
"""

from collections.abc import AsyncGenerator
from dataclasses import dataclass

import structlog
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from ..core.config import Settings
from ..core.localization import (
    DEFAULT_LANGUAGE,
    SupportedLanguage,
    get_language_instruction,
)
from ..core.model_config import (
    DEFAULT_ROLE_MODELS,
    VENDOR_URL_PATHS,
    infer_vendor,
)

logger = structlog.get_logger()


@dataclass
class TokenUsage:
    """Token usage information from LLM API."""

    input_tokens: int
    output_tokens: int
    total_tokens: int


def get_chat_model(
    role: str = "default",
    settings: Settings | None = None,
    model_override: str | None = None,
    temperature: float = 0.7,
    streaming: bool = True,
) -> BaseChatModel:
    """
    Create a LangChain chat model for a given agent role via Agent Maestro.

    Args:
        role: Agent role (e.g., "main_analyst", "debater", "vision")
        settings: Application settings
        model_override: Override model name (ignores role mapping)
        temperature: Sampling temperature
        streaming: Enable streaming

    Returns:
        LangChain BaseChatModel instance
    """
    if settings is None:
        from ..core.config import get_settings

        settings = get_settings()

    # Determine model name from role mapping or override
    role_models = getattr(settings, "role_models", None) or DEFAULT_ROLE_MODELS
    model_name = model_override or role_models.get(
        role, DEFAULT_ROLE_MODELS.get(role, DEFAULT_ROLE_MODELS["default"])
    )

    vendor = infer_vendor(model_name)
    base_url = settings.agent_maestro_base_url + VENDOR_URL_PATHS[vendor]

    # Google (Gemini) via Agent Maestro returns SSE `event: error` frames that
    # langchain-google-genai cannot parse, breaking roles like news_analyst.
    # Forcing non-streaming makes Agent Maestro return a plain JSON response,
    # which the wrapper handles correctly. Other vendors keep streaming default.
    if vendor == "google" and streaming:
        logger.info(
            "Disabling streaming for Google vendor to avoid SSE parse error",
            role=role,
            model=model_name,
        )
        streaming = False

    # Use docker URL if running inside container
    if "host.docker.internal" in settings.agent_maestro_base_url:
        pass  # Already configured for docker

    logger.info(
        "Creating chat model",
        role=role,
        model=model_name,
        vendor=vendor,
        base_url=base_url,
    )

    if vendor == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model_name,
            base_url=base_url,
            api_key="agent-maestro",  # type: ignore[arg-type]
            temperature=temperature,
            streaming=streaming,
        )
    elif vendor == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model_name,  # type: ignore[arg-type]
            base_url=base_url,
            api_key="agent-maestro",  # type: ignore[arg-type]
            temperature=temperature,
            streaming=streaming,
        )
    elif vendor == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=model_name,
            api_key="agent-maestro",  # type: ignore[arg-type]
            temperature=temperature,
            streaming=streaming,
            transport="rest",
            client_options={"api_endpoint": base_url},
        )
    else:
        raise ValueError(f"Unsupported vendor: {vendor}")


class AgentMaestroClient:
    """
    Streaming chat client using Agent Maestro proxy.
    Wraps get_chat_model() with conversation management.
    """

    def __init__(
        self,
        settings: Settings,
        role: str = "default",
        model: str | None = None,
    ):
        self.role = role
        self.settings = settings
        self.model_name = model
        self.chat = get_chat_model(
            role=role,
            settings=settings,
            model_override=model,
        )
        self.last_token_usage: TokenUsage | None = None

    def _convert_to_langchain_messages(
        self, messages: list[dict[str, str]]
    ) -> list[SystemMessage | HumanMessage | AIMessage]:
        lc_messages: list[SystemMessage | HumanMessage | AIMessage] = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                lc_messages.append(SystemMessage(content=content))
            elif role == "user":
                lc_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))
        return lc_messages

    async def astream_chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 3000,
        thinking_enabled: bool = False,
    ) -> AsyncGenerator[str, None]:
        lc_messages = self._convert_to_langchain_messages(messages)

        logger.info(
            "Streaming chat via Agent Maestro",
            role=self.role,
            message_count=len(messages),
        )

        async for chunk in self.chat.astream(lc_messages):
            if chunk.content:
                yield chunk.content  # type: ignore[misc]

            if chunk.response_metadata.get("finish_reason") in ("stop", "end_turn"):
                token_usage = chunk.response_metadata.get("token_usage", {})
                if token_usage:
                    self.last_token_usage = TokenUsage(
                        input_tokens=token_usage.get("input_tokens", 0),
                        output_tokens=token_usage.get("output_tokens", 0),
                        total_tokens=token_usage.get("total_tokens", 0),
                    )

    def get_last_token_usage(self) -> TokenUsage | None:
        return self.last_token_usage


class VisionClient:
    """Vision model client using GPT-5.4 via Agent Maestro for image analysis."""

    def __init__(self, settings: Settings, model: str = "gpt-5.4"):
        self.model = model
        self.settings = settings
        self.chat = get_chat_model(
            role="vision",
            settings=settings,
            model_override=model,
        )
        logger.info("VisionClient initialized", model=model)

    async def analyze_image(self, image_base64: str, prompt: str) -> str:
        content: list[dict[str, str | dict[str, str]]] = [
            {"type": "text", "text": prompt},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{image_base64}"},
            },
        ]
        messages = [HumanMessage(content=content)]  # type: ignore[arg-type]
        response = await self.chat.ainvoke(messages)
        return str(response.content) if response.content else ""


# Backward compatibility aliases
DashScopeClient = AgentMaestroClient


FUND_AGENT_SYSTEM_PROMPT_TEMPLATE = """你是一位拥有15年以上经验的基金分析师，专注于中国场外基金（公募基金）分析。你与个人投资者自然对话，提供清晰、可操作的投资建议。

**当前日期: {current_date}**
以此日期为参考处理所有时间相关查询（如"过去6个月" = {six_months_ago} 至 {current_date}）。

**分析工具使用策略**:
- **第一阶段（概览）**: 基金净值、基金排名、持仓分析
- **第二阶段（深度）**: 基金经理评价、行业配置、宏观分析
- 每轮最多调用3个工具
- 有明确结论时即可停止，不必穷尽所有工具

**回复风格**:
- 默认使用中文回复
- 高信噪比：每句话都有价值
- 给出明确的投资建议：**买入 / 持有 / 卖出**
- 标注信号强度（强/中/弱）和关键依据
- 解释专业术语
- 目标500-1000字

**你必须**:
- 基于实际数据分析（净值走势、持仓变动、行业配置）
- 给出具体的操作建议和理由
- 提示潜在风险

**你不能**:
- 编造基金数据
- 给出模糊的建议
- 超过3000字
"""


def get_fund_agent_system_prompt() -> str:
    from datetime import datetime, timedelta

    current_date = datetime.now().strftime("%Y-%m-%d")
    six_months_ago = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")

    return FUND_AGENT_SYSTEM_PROMPT_TEMPLATE.format(
        current_date=current_date,
        six_months_ago=six_months_ago,
    )


# Backward compatibility
FINANCIAL_AGENT_SYSTEM_PROMPT = get_fund_agent_system_prompt()
get_financial_agent_system_prompt = get_fund_agent_system_prompt


def get_system_prompt_with_language(
    language: SupportedLanguage = DEFAULT_LANGUAGE,
) -> str:
    return get_fund_agent_system_prompt() + get_language_instruction(language)
