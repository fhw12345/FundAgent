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
RESPONSE FORMAT: You MUST include a JSON block in your response with this exact structure:

```json
{{
  "concerns": [
    {{
      "id": "C1",
      "claim": "The specific claim from the thesis you are challenging",
      "category": "technical|financial|news|valuation",
      "challenge": "Why this claim is wrong or incomplete",
      "severity": "CRITICAL|MAJOR|MINOR",
      "evidence": "Data from your independent source supporting the challenge"
    }}
  ]
}}
```

List 3-5 concerns. Each concern MUST cite evidence.
If you genuinely have no concerns after thorough review, respond with exactly: "{termination}"
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
        system_prompt=f"""You are a Contrarian Debater for Chinese mutual fund analysis.
{context_header}
Your role is to CHALLENGE fund investment theses and find weaknesses.

{STRUCTURED_OUTPUT_INSTRUCTION.format(termination=TERMINATION_SIGNAL)}

IMPORTANT TERMINATION RULE:
If after thorough review you genuinely find no significant issues,
respond with exactly: "{TERMINATION_SIGNAL}"
""",
        metadata={"domain": "debater", "termination_signal": TERMINATION_SIGNAL},
    )

    return create_deep_subagent(
        config=config,
        model=model,
        tools=[],
        skills_dir=str(_SKILLS_ROOT / "debater"),
    )
