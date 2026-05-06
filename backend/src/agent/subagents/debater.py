"""
Debater Sub-Agent: Adversarial analysis using independent sources.

Placeholder — fund-specific independent verification tools added in M1-4.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from . import _SKILLS_ROOT, DeepSubAgent, SubAgentConfig, create_deep_subagent

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

    from ..context import AgentContext

TERMINATION_SIGNAL = "NO FURTHER CONCERNS"

STRUCTURED_OUTPUT_INSTRUCTION = """
回复格式要求：你的回答中**必须**包含一段 JSON，结构如下：

```json
{{
  "concerns": [
    {{
      "id": "C1",
      "claim": "你所质疑的研究报告中的具体论断",
      "category": "nav_trend|holdings|manager|fees|liquidity|sentiment",
      "challenge": "为什么这个论断是错的或不完整",
      "severity": "CRITICAL|MAJOR|MINOR",
      "evidence": "支撑你这条质疑的数据或来源（必须出自其他三位分析师已经引用过的数据，不得编造）"
    }}
  ]
}}
```

请提出 3-5 条顾虑，每条都**必须**附带证据。
如果你在充分审视后确实没有任何顾虑，请仅回复："{termination}"
"""


def create_debater_subagent(
    model: BaseChatModel,
    context: AgentContext | None = None,
    exa_api_key: str = "",
) -> DeepSubAgent:
    """Create the Debater sub-agent.

    Independent verification tools will be added in M1-4 (fund domain refactor).
    """
    context_header = ""
    if context:
        context_header = f"\n{context.to_context_header()}\n"

    config = SubAgentConfig(
        name="debater",
        description=(
            "Contrarian analyst who challenges investment theses. "
            "Verifies claims against independent sources."
        ),
        system_prompt=f"""你是一位**基金研究质疑者**，专注于中国公募基金（场外基金）。
{context_header}
你的职责是对其他三位分析师（净值走势、持仓基本面、舆情）给出的研究结论提出有价值的质疑，找出其中的薄弱环节。

硬性约束：
- **不得编造任何数据**。你只能基于其他三位分析师在报告中已经引用过的数据进行质疑。
- 不要泛泛而谈，每条质疑都必须指向报告中可被定位的具体论断。

重点关注维度：
- **净值走势 (nav_trend)**：是否过度乐观，是否忽略了最大回撤、近期回撤、同类排名下滑
- **持仓 (holdings)**：行业/个股集中度风险、风格漂移、与宣称策略不符
- **基金经理 (manager)**：任职年限过短、任职稳定性、与历史代表作业绩不可比
- **费率 (fees)**：管理费/托管费/销售服务费对长期收益的拖累
- **流动性/规模 (liquidity)**：规模过小（清盘风险）或过大（建仓困难、收益稀释）
- **舆情/板块 (sentiment)**：所投板块/行业的下行风险、监管风险、热度退潮

{STRUCTURED_OUTPUT_INSTRUCTION.format(termination=TERMINATION_SIGNAL)}

终止规则：
若经充分审视确实无重大顾虑，请仅回复："{TERMINATION_SIGNAL}"
""",
        metadata={"domain": "debater", "termination_signal": TERMINATION_SIGNAL},
    )

    return create_deep_subagent(
        config=config,
        model=model,
        tools=[],
        skills_dir=str(_SKILLS_ROOT / "debater"),
    )
