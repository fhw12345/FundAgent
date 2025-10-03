"""Core financial analysis entry point.
Provides clean interface to modular analysis components.
"""

# Import modular analysis components
from .analysis.fibonacci import FibonacciAnalyzer
from .analysis.macro_analyzer import MacroAnalyzer
from .analysis.stock_analyzer import StockAnalyzer
from .analysis.stochastic_analyzer import StochasticAnalyzer
from .data.stock_data_fetcher import StockDataFetcher

# Re-export for backward compatibility
__all__ = [
    'FibonacciAnalyzer',
    'MacroAnalyzer',
    'StockAnalyzer',
    'StochasticAnalyzer',
    'StockDataFetcher'
]
