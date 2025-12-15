"""
Order Optimization Module - Phase 3 of Portfolio Analysis.

This module has been refactored into a modular structure under optimizer/.
This file maintains backward compatibility by re-exporting the OrderOptimizer class.

New structure:
- optimizer/base.py: Base class with initialization
- optimizer/plan_builder.py: Building execution plans from trading decisions
- optimizer/executor.py: Order execution via trading service
- optimizer/__init__.py: Main OrderOptimizer class (composition of above)

Migration guide:
- Old: from src.agent.order_optimizer import OrderOptimizer
- New: from src.agent.optimizer import OrderOptimizer (recommended)
- Both imports work identically for backward compatibility.
"""

# Re-export for backward compatibility
from .optimizer import OrderOptimizer

__all__ = ["OrderOptimizer"]
