"""
Shared utilities module.

Provides common utility functions used across the backend codebase.
Centralizes duplicate logic to ensure consistency and maintainability.
"""

from .formatters import (
    calculate_qoq_growth,
    format_large_number,
    format_percentage,
    safe_float,
    safe_int,
)
from .sanitizers import (
    sanitize_api_response,
    sanitize_text,
)

__all__ = [
    # Formatters
    "safe_float",
    "safe_int",
    "format_large_number",
    "format_percentage",
    "calculate_qoq_growth",
    # Sanitizers
    "sanitize_text",
    "sanitize_api_response",
]
