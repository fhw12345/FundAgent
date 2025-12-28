"""
Shared formatting utilities.

Provides centralized number formatting, type conversion, and display helpers
used across API endpoints, services, and agent tools.

Consolidates duplicate implementations from:
- api/analysis.py (4 copies of safe_float)
- services/alphavantage_response_formatter.py
- services/alphavantage_market_data.py
"""

from typing import Any


def safe_float(value: str | float | int | None, default: float = 0.0) -> float:
    """
    Safely convert a value to float.

    Handles string values from API responses, None values, and the literal
    string "None" commonly returned by some APIs.

    Args:
        value: Value to convert (string, number, or None)
        default: Default value if conversion fails

    Returns:
        Float value or default

    Examples:
        >>> safe_float("123.45")
        123.45
        >>> safe_float(None)
        0.0
        >>> safe_float("None", -1.0)
        -1.0
        >>> safe_float("invalid")
        0.0
    """
    if value is None or value == "None" or value == "":
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value: str | float | int | None, default: int = 0) -> int:
    """
    Safely convert a value to integer.

    Args:
        value: Value to convert
        default: Default value if conversion fails

    Returns:
        Integer value or default

    Examples:
        >>> safe_int("123")
        123
        >>> safe_int(45.7)
        45
        >>> safe_int(None)
        0
    """
    if value is None or value == "None" or value == "":
        return default
    try:
        return int(float(value))  # Handle "123.45" -> 123
    except (ValueError, TypeError):
        return default


def format_large_number(
    value: float | int | None,
    currency_prefix: str = "$",
    include_sign: bool = False,
) -> str:
    """
    Format large numbers with K/M/B suffixes.

    Args:
        value: Number to format
        currency_prefix: Prefix to add (default "$", use "" for none)
        include_sign: Whether to include +/- sign

    Returns:
        Formatted string (e.g., "$1.5B", "250.3M", "+$100K")

    Examples:
        >>> format_large_number(1_500_000_000)
        "$1.50B"
        >>> format_large_number(250_300_000)
        "$250.3M"
        >>> format_large_number(None)
        "N/A"
        >>> format_large_number(1500, currency_prefix="")
        "1.5K"
    """
    if value is None or (isinstance(value, float) and value == 0):
        return "N/A"

    abs_value = abs(value)
    sign = ""
    if include_sign:
        sign = "+" if value >= 0 else "-"
        abs_value = abs(value)
        value = abs_value

    if abs_value >= 1e9:
        return f"{sign}{currency_prefix}{value / 1e9:.2f}B"
    elif abs_value >= 1e6:
        return f"{sign}{currency_prefix}{value / 1e6:.1f}M"
    elif abs_value >= 1e3:
        return f"{sign}{currency_prefix}{value / 1e3:.1f}K"
    else:
        return f"{sign}{currency_prefix}{value:.2f}"


def format_percentage(
    value: float | None,
    decimal_places: int = 1,
    include_sign: bool = True,
) -> str:
    """
    Format a value as a percentage string.

    Args:
        value: Percentage value (already multiplied by 100)
        decimal_places: Number of decimal places
        include_sign: Whether to include +/- sign

    Returns:
        Formatted percentage string (e.g., "+5.2%", "-2.1%")

    Examples:
        >>> format_percentage(5.234)
        "+5.2%"
        >>> format_percentage(-2.1, decimal_places=2)
        "-2.10%"
        >>> format_percentage(None)
        "N/A"
    """
    if value is None:
        return "N/A"

    sign = ""
    if include_sign and value >= 0:
        sign = "+"

    return f"{sign}{value:.{decimal_places}f}%"


def calculate_qoq_growth(
    current: float | int | None,
    previous: float | int | None,
) -> str:
    """
    Calculate quarter-over-quarter growth percentage.

    Args:
        current: Current quarter value
        previous: Previous quarter value

    Returns:
        Formatted growth string (e.g., "+5.2%", "-2.1%", "N/A")

    Examples:
        >>> calculate_qoq_growth(105, 100)
        "+5.0%"
        >>> calculate_qoq_growth(98, 100)
        "-2.0%"
        >>> calculate_qoq_growth(100, 0)
        "N/A"
    """
    if current is None or previous is None or previous == 0:
        return "N/A"

    growth = ((current - previous) / previous) * 100
    return format_percentage(growth)


def format_metric_value(
    value: Any,
    metric_type: str = "number",
    decimal_places: int = 2,
) -> str:
    """
    Format a metric value based on its type.

    Args:
        value: Value to format
        metric_type: Type of metric ("number", "percentage", "currency", "ratio")
        decimal_places: Number of decimal places

    Returns:
        Formatted string appropriate for the metric type

    Examples:
        >>> format_metric_value(1_500_000, "currency")
        "$1.5M"
        >>> format_metric_value(0.125, "percentage")
        "+12.5%"
        >>> format_metric_value(15.234, "ratio")
        "15.23"
    """
    if value is None or value == "None":
        return "N/A"

    float_val = safe_float(value)

    if metric_type == "currency":
        return format_large_number(float_val)
    elif metric_type == "percentage":
        return format_percentage(float_val * 100)
    elif metric_type == "ratio":
        return f"{float_val:.{decimal_places}f}"
    else:
        if abs(float_val) >= 1000:
            return format_large_number(float_val, currency_prefix="")
        return f"{float_val:.{decimal_places}f}"
