"""
Technical Sub-Agent: 基金净值走势与技术面分析。

Analyzes fund NAV trends, momentum, and price patterns using AkShare data.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from ..context import AgentContext
from ..tools.categorization import get_tools_for_subagent
from . import _SKILLS_ROOT, DeepSubAgent, SubAgentConfig, create_deep_subagent

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

    from ..tools.analysis_cache import AnalysisToolCache


def create_technical_subagent(
    tools: dict[str, Callable],
    model: BaseChatModel,
    context: AgentContext | None = None,
    cache: AnalysisToolCache | None = None,
) -> DeepSubAgent:
    context_header = ""
    if context:
        context_header = f"\n{context.to_context_header()}\n"

    config = SubAgentConfig(
        name="technical_analyst",
        description="基金净值走势分析、趋势判断、动量指标专家。",
        system_prompt=f"""你是一位基金技术面分析专家，专注于中国公募基金（场外基金）。
{context_header}
你的专业领域：
- 净值走势分析（单位净值、累计净值、收益率曲线）
- 趋势判断（上升/下降/震荡）
- 回撤分析（最大回撤、当前回撤位置）
- 同类排名走势
- 净值估算（盘中估值）

你不负责：
- 持仓分析（那是财务分析师的工作）
- 基金经理评价（那是新闻/舆情分析师的工作）

分析要求：
- 基于实际净值数据，不编造数据
- 给出明确的趋势判断
- 标注关键时间节点和净值水平
- 中文回复，简洁精准
""",
        metadata={"domain": "technical"},
    )

    technical_tools = list(
        get_tools_for_subagent(list(tools.values()), "technical").values()
    )

    if cache is not None:
        technical_tools = cache.wrap_tools(technical_tools)

    return create_deep_subagent(
        config=config,
        model=model,
        tools=technical_tools,
        skills_dir=str(_SKILLS_ROOT / "technical"),
    )
