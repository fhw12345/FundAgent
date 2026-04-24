"""
News Sub-Agent: 基金舆情与市场情绪分析。

Analyzes fund manager reputation, market sentiment, and sector news.
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


def create_news_subagent(
    tools: dict[str, Callable],
    model: BaseChatModel,
    context: AgentContext | None = None,
    cache: AnalysisToolCache | None = None,
) -> DeepSubAgent:
    context_header = ""
    if context:
        context_header = f"\n{context.to_context_header()}\n"

    config = SubAgentConfig(
        name="news_analyst",
        description="基金舆情分析、市场情绪、基金经理口碑、行业动态专家。",
        system_prompt=f"""你是一位基金舆情与市场情绪分析专家，专注于中国公募基金（场外基金）。
{context_header}
你的专业领域：
- 基金经理口碑与任职稳定性
- 基金公司信誉与治理
- 行业/板块热度与轮动
- 监管政策变化对基金的影响
- 同类基金对比排名与评级

你不负责：
- 净值走势分析（那是技术分析师的工作）
- 具体持仓分析（那是财务分析师的工作）

分析要求：
- 关注近期基金经理变动、规模异常变化
- 评估行业/板块配置的时效性
- 结合市场环境给出定性判断
- 中文回复，平衡正反面信息
""",
        metadata={"domain": "news"},
    )

    news_tools = list(get_tools_for_subagent(list(tools.values()), "news").values())

    if cache is not None:
        news_tools = cache.wrap_tools(news_tools)

    return create_deep_subagent(
        config=config,
        model=model,
        tools=news_tools,
        skills_dir=str(_SKILLS_ROOT / "news"),
    )
