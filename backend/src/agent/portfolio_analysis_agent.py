"""
Portfolio Analysis Agent - Backward compatibility module.

DEPRECATED: This module provides backward compatibility for imports.
New code should import from: src.agent.portfolio

The original 1172-line file has been refactored into a modular structure:
- src/agent/portfolio/agent.py: Main orchestration class (~250 lines)
- src/agent/portfolio/phase1_research.py: Symbol research (~280 lines)
- src/agent/portfolio/phase2_decisions.py: Decision making (~350 lines)
- src/agent/portfolio/phase3_execution.py: Order execution (~120 lines)
"""

# Re-export for backward compatibility
from .portfolio import PortfolioAnalysisAgent

__all__ = ["PortfolioAnalysisAgent"]
