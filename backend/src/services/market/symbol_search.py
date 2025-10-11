"""
Symbol search utilities for deduplication and ranking.

Provides helpers to eliminate duplicate companies across exchanges
and prioritize US exchanges over foreign ones.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...api.market_data import SymbolSearchResult

# Exchange priority for deduplication (lower number = higher priority)
EXCHANGE_PRIORITY = {
    "NMS": 1,  # NASDAQ
    "NAS": 2,  # NASDAQ
    "NYQ": 3,  # NYSE
    "NYE": 4,  # NYSE Arca
    "PCX": 5,  # NYSE Arca
    "": 999,  # Unknown
}


def calculate_match_confidence(
    query: str, symbol: str, name: str
) -> tuple[str, float] | None:
    """
    Calculate match type and confidence score for symbol search.

    Args:
        query: User search query
        symbol: Stock symbol (e.g., "AAPL")
        name: Company name (e.g., "Apple Inc.")

    Returns:
        Tuple of (match_type, confidence) or None if no match.
        - match_type: "exact_symbol" | "symbol_prefix" | "name_prefix" | "fuzzy"
        - confidence: Float between 0.5 and 1.0

    Examples:
        >>> calculate_match_confidence("aapl", "AAPL", "Apple Inc.")
        ("exact_symbol", 1.0)
        >>> calculate_match_confidence("app", "AAPL", "Apple Inc.")
        ("symbol_prefix", 0.89)
        >>> calculate_match_confidence("apple", "AAPL", "Apple Inc.")
        ("name_prefix", 0.75)
    """
    q_lower = query.lower()
    symbol_lower = symbol.lower()
    name_lower = name.lower()

    if symbol_lower == q_lower:
        return ("exact_symbol", 1.0)
    elif symbol_lower.startswith(q_lower):
        # Penalize longer symbols slightly
        confidence = 0.9 - (len(symbol_lower) - len(q_lower)) * 0.01
        return ("symbol_prefix", confidence)
    elif name_lower.startswith(q_lower):
        return ("name_prefix", 0.75)
    elif q_lower in symbol_lower or q_lower in name_lower:
        return ("fuzzy", 0.5)
    else:
        return None


def should_replace_duplicate(
    existing: "SymbolSearchResult",
    new_confidence: float,
    new_exchange: str,
) -> bool:
    """
    Determine if new result should replace existing duplicate company.

    Replaces if: better confidence OR same confidence but better exchange.

    Args:
        existing: Current best result for this company
        new_confidence: Confidence score of new result
        new_exchange: Exchange code of new result

    Returns:
        True if new result should replace existing

    Examples:
        >>> # Higher confidence always wins
        >>> existing = SymbolSearchResult(confidence=0.75, exchange="NMS", ...)
        >>> should_replace_duplicate(existing, 0.9, "FRA")
        True

        >>> # Same confidence: better exchange wins (NMS > FRA)
        >>> should_replace_duplicate(existing, 0.75, "FRA")
        False
        >>> should_replace_duplicate(existing, 0.75, "NYQ")  # NYQ has priority 3 vs NMS=1
        False
    """
    existing_priority = EXCHANGE_PRIORITY.get(existing.exchange, 999)
    new_priority = EXCHANGE_PRIORITY.get(new_exchange, 999)

    return new_confidence > existing.confidence or (
        new_confidence == existing.confidence and new_priority < existing_priority
    )
