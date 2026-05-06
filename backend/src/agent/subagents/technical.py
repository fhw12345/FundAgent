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
        description="基金净值走势分析、趋势判断、回撤与同类排名专家。",
        system_prompt=f"""你是一位**基金净值走势分析师**，专注于中国公募基金（场外基金）。
{context_header}
重要前提：
- 公募基金只有日频单位净值，**没有 K 线、没有成交量**。
- 请**不要**输出 RSI、MACD、KDJ、布林带、斐波那契、均线金叉死叉等任何 K 线技术指标。
- 不要编造任何数据，所有判断必须基于工具返回的真实净值数据。

你的专业领域：
- 净值走势分析（单位净值、累计净值、收益率曲线）
- 趋势判断（上升 / 下降 / 震荡）
- 回撤分析（最大回撤、当前回撤位置、回撤恢复时长）
- 阶段收益（近 1 / 3 / 6 / 12 个月收益）
- 同类四分位排名走势、估值百分位
- 盘中估值（est_pct / published_pct，如有）

你不负责：
- 持仓与重仓股分析（财务/基本面分析师负责）
- 基金经理评价与舆情（新闻分析师负责）

输出要求：
- 中文回复，简洁精准
- 标注关键时间节点和净值水平
- 给出明确的趋势判断与风险提示
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
