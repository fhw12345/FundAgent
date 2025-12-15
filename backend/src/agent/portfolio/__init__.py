"""
Portfolio Analysis Agent - Modular structure.

This package contains the portfolio analysis agent split into focused modules:
- agent.py: Main orchestration class
- phase1_research.py: Independent symbol research
- phase2_decisions.py: Portfolio-wide decision making
- phase3_execution.py: Order execution
"""

from .agent import PortfolioAnalysisAgent

__all__ = ["PortfolioAnalysisAgent"]
