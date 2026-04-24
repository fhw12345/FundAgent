"""
Financial Sub-Agent: 基金持仓与基本面分析。

Analyzes fund holdings, asset allocation, and fundamental characteristics.
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


def create_financial_subagent(
    tools: dict[str, Callable],
    model: BaseChatModel,
    context: AgentContext | None = None,
    cache: AnalysisToolCache | None = None,
) -> DeepSubAgent:
    context_header = ""
    if context:
        context_header = f"\n{context.to_context_header()}\n"

    config = SubAgentConfig(
        name="financial_analyst",
        description="基金持仓分析、资产配置、行业集中度、基金经理评估专家。",
        system_prompt=f"""你是一位基金基本面分析专家，专注于中国公募基金（场外基金）。
{context_header}
你的专业领域：
- 重仓股分析（前十大持仓、行业分布、集中度）
- 资产配置（股票/债券/现金比例）
- 基金规模变动（申购赎回趋势）
- 费率分析（管理费、托管费、申购赎回费）
- 基金概况（成立日期、基金经理、投资目标）

你不负责：
- 净值走势分析（那是技术分析师的工作）
- 市场情绪判断（那是新闻分析师的工作）

分析要求：
- 基于实际持仓数据
- 分析行业集中度风险
- 与同类基金对比
- 中文回复，数据驱动
""",
        metadata={"domain": "financial"},
    )

    financial_tools = list(
        get_tools_for_subagent(list(tools.values()), "financial").values()
    )

    if cache is not None:
        financial_tools = cache.wrap_tools(financial_tools)

    return create_deep_subagent(
        config=config,
        model=model,
        tools=financial_tools,
        skills_dir=str(_SKILLS_ROOT / "financial"),
    )
