"""Quarterly report PDF interpretation service.

Extracts key metrics from Chinese mutual fund quarterly reports (季报):
- Top holdings changes
- Asset allocation shifts
- NAV performance vs benchmark
- Manager commentary highlights
"""

import base64
import io
import json
import re
from typing import Any

import structlog

from ..agent.llm_client import VisionClient, get_chat_model
from ..core.config import Settings

logger = structlog.get_logger()

QUARTERLY_REPORT_PROMPT = """你是一位专业的基金季报分析师。请分析这份基金季报页面，提取以下关键信息：

1. **基金基本信息**: 基金代码、名称、报告期
2. **业绩表现**: 本期净值增长率、同期业绩比较基准、超额收益
3. **资产配置**: 股票/债券/现金占比及变化
4. **前十大重仓股**: 股票名称、占比、较上期变化（增持/减持/新进/退出）
5. **基金经理观点**: 对市场的判断、后续操作思路
6. **风险提示**: 需要关注的风险因素

请以结构化 JSON 格式返回：
```json
{
  "fund_code": "基金代码",
  "fund_name": "基金名称",
  "report_period": "报告期",
  "performance": {
    "nav_growth": "净值增长率%",
    "benchmark_growth": "基准增长率%",
    "excess_return": "超额收益%"
  },
  "asset_allocation": {
    "stock_pct": 股票占比,
    "bond_pct": 债券占比,
    "cash_pct": 现金占比
  },
  "top_holdings": [
    {"name": "股票名称", "pct": 占比, "change": "增持/减持/新进/持平"}
  ],
  "manager_outlook": "基金经理观点摘要",
  "risk_factors": ["风险1", "风险2"]
}
```

如果某项信息不在当前页面中，设为 null。只返回 JSON，不要其他文字。"""

TEXT_ANALYSIS_PROMPT = """你是一位专业的基金季报分析师。以下是基金季报的文本内容，请提取关键信息并给出投资建议。

## 季报内容
{text}

## 请分析并回答：
1. 基金本季度表现如何？与基准比较如何？
2. 前十大重仓股有哪些变化？增减持信号是什么？
3. 基金经理对后市怎么看？
4. 有哪些需要关注的风险？
5. 综合给出一句话投资建议

请用中文回答，重点突出，500字以内。"""


def _extract_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    match = re.search(r"```(?:json)?\s*(\{.*?})\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)
    elif not text.startswith("{"):
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start != -1 and brace_end != -1:
            text = text[brace_start : brace_end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


async def analyze_quarterly_report_image(
    image_base64: str,
    settings: Settings,
) -> dict[str, Any]:
    """Analyze a quarterly report page image using vision model."""
    vision = VisionClient(settings)
    raw = await vision.analyze_image(image_base64, QUARTERLY_REPORT_PROMPT)
    parsed = _extract_json(raw)
    if parsed:
        return {"status": "ok", "structured": parsed, "raw": raw}
    return {"status": "ok", "structured": None, "raw": raw}


async def analyze_quarterly_report_text(
    text: str,
    settings: Settings,
) -> str:
    """Analyze quarterly report text content using LLM."""
    llm = get_chat_model(role="main_analyst", settings=settings)
    from langchain_core.messages import HumanMessage

    prompt = TEXT_ANALYSIS_PROMPT.format(text=text[:8000])
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    return str(response.content) if response.content else ""
