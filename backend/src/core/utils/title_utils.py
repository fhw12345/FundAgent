"""
Chat title generation utilities.

Provides functions for generating meaningful chat titles from conversation content.
Used to replace default "New Chat" titles with context-aware titles like "AAPL Analysis".
"""

import re

import structlog

logger = structlog.get_logger()

# Stock symbols pattern: 1-5 uppercase letters
SYMBOL_PATTERN = re.compile(r"\b[A-Z]{1,5}\b")

# LLM-generated title pattern: [chat_title: Title Here]
CHAT_TITLE_PATTERN = re.compile(r"\[chat_title:\s*(.+?)\]\s*$", re.IGNORECASE)

# Common words that look like symbols but aren't
STOP_WORDS = frozenset(
    {
        "I",
        "A",
        "THE",
        "AND",
        "OR",
        "FOR",
        "TO",
        "IN",
        "ON",
        "AT",
        "OF",
        "IS",
        "IT",
        "MY",
        "AN",
        "AS",
        "BE",
        "BY",
        "DO",
        "GO",
        "HE",
        "IF",
        "ME",
        "NO",
        "SO",
        "UP",
        "WE",
        "ALL",
        "CAN",
        "GET",
        "HAS",
        "HOW",
        "ITS",
        "LET",
        "NEW",
        "NOW",
        "OLD",
        "OUR",
        "OUT",
        "OWN",
        "SAY",
        "SHE",
        "TOO",
        "TWO",
        "USE",
        "WAY",
        "WHO",
        "WHY",
        "YOU",
        "ARE",
        "BUT",
        "ETF",
        "IPO",
        "CEO",
        "CFO",
        "SEC",
        "NYSE",
        "USD",
        "EUR",
        "GBP",
        "JPY",
        "CNY",
        "HKD",
    }
)

# Action keywords mapped to title suffixes
ACTION_KEYWORDS: dict[str, list[str]] = {
    "Technical Analysis": [
        "sma",
        "ema",
        "rsi",
        "macd",
        "stoch",
        "bollinger",
        "bbands",
        "indicator",
        "technical",
        "chart",
        "trend",
        "momentum",
        "support",
        "resistance",
    ],
    "Fundamental Analysis": [
        "earnings",
        "revenue",
        "profit",
        "margin",
        "p/e",
        "pe ratio",
        "eps",
        "fundamental",
        "valuation",
        "growth",
    ],
    "Cash Flow": [
        "cash flow",
        "cashflow",
        "fcf",
        "free cash",
        "operating cash",
        "capex",
    ],
    "Balance Sheet": [
        "balance sheet",
        "assets",
        "liabilities",
        "equity",
        "debt",
        "current ratio",
    ],
    "News": [
        "news",
        "headlines",
        "article",
        "sentiment",
        "media",
        "announcement",
    ],
    "Price": [
        "price",
        "quote",
        "stock price",
        "current price",
        "how much",
        "trading at",
    ],
    "Insider Activity": ["insider", "executive", "buy", "sell", "transaction"],
    "ETF Holdings": ["etf", "holdings", "fund", "composition", "allocation"],
    "Market Movers": ["movers", "gainers", "losers", "most active", "top stocks"],
    "Comparison": ["compare", "versus", "vs", "difference", "better"],
    "Portfolio": ["portfolio", "holdings", "positions", "watchlist"],
}

# Maximum title length
MAX_TITLE_LENGTH = 50


def extract_symbols(text: str) -> list[str]:
    """
    Extract likely stock symbols from text.

    Args:
        text: Text to extract symbols from

    Returns:
        List of unique symbols found (deduplicated, ordered by first occurrence)

    Examples:
        >>> extract_symbols("What's the price of AAPL?")
        ['AAPL']
        >>> extract_symbols("Compare GOOGL and META earnings")
        ['GOOGL', 'META']
    """
    candidates = SYMBOL_PATTERN.findall(text)

    # Deduplicate while preserving order
    seen = set()
    unique_symbols = []
    for symbol in candidates:
        if symbol not in seen and symbol not in STOP_WORDS:
            seen.add(symbol)
            unique_symbols.append(symbol)

    return unique_symbols


def detect_action(text: str) -> str:
    """
    Detect the type of analysis/action from message text.

    Args:
        text: Message text to analyze

    Returns:
        Action string (e.g., "Technical Analysis", "Cash Flow", "Analysis")

    Examples:
        >>> detect_action("Show me the RSI for AAPL")
        'Technical Analysis'
        >>> detect_action("What's the cash flow for MRVL?")
        'Cash Flow'
    """
    text_lower = text.lower()

    for action, keywords in ACTION_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return action

    return "Analysis"


def generate_chat_title(
    user_message: str,
    assistant_response: str | None = None,
) -> str:
    """
    Generate a meaningful chat title from conversation content.

    Priority:
    1. Symbol + Action: "AAPL Technical Analysis"
    2. Multiple symbols: "AAPL vs MSFT" or "AAPL, MSFT Analysis"
    3. Symbol only: "MRVL Analysis"
    4. Topic only: "Portfolio Review"
    5. Fallback: "Chat Analysis"

    Args:
        user_message: User's first message
        assistant_response: Assistant's first response (optional, for additional context)

    Returns:
        Generated title (max 50 characters)

    Examples:
        >>> generate_chat_title("Analyze AAPL stock")
        'AAPL Analysis'
        >>> generate_chat_title("What's the cash flow for MRVL?")
        'MRVL Cash Flow'
        >>> generate_chat_title("Compare GOOGL and META")
        'GOOGL vs META'
    """
    # Combine texts for symbol extraction (user message takes priority)
    combined_text = user_message
    if assistant_response:
        combined_text += " " + assistant_response

    # Extract symbols
    symbols = extract_symbols(user_message)

    # Detect action from user message
    action = detect_action(user_message)

    # Build title based on what we found
    if len(symbols) >= 2:
        # Multiple symbols - check for comparison
        if any(
            kw in user_message.lower()
            for kw in ["compare", "vs", "versus", "difference", "better"]
        ):
            title = f"{symbols[0]} vs {symbols[1]}"
        else:
            # List first 2-3 symbols
            symbol_str = ", ".join(symbols[:3])
            title = f"{symbol_str} {action}"
    elif len(symbols) == 1:
        # Single symbol
        title = f"{symbols[0]} {action}"
    else:
        # No symbols found - use action or fallback
        if action != "Analysis":
            title = action
        else:
            title = "Chat Analysis"

    # Truncate if needed
    if len(title) > MAX_TITLE_LENGTH:
        title = title[: MAX_TITLE_LENGTH - 3] + "..."

    return title


def extract_title_from_response(response: str | None) -> tuple[str | None, str | None]:
    """
    Extract LLM-generated title from response and return cleaned content.

    The LLM is instructed to include a title at the end of responses in format:
    [chat_title: Your Title Here]

    Args:
        response: Full LLM response text

    Returns:
        Tuple of (extracted_title, cleaned_response):
        - extracted_title: The title if found, None if not
        - cleaned_response: Response with title line removed

    Examples:
        >>> extract_title_from_response("Analysis here...\\n[chat_title: AAPL Analysis]")
        ('AAPL Analysis', 'Analysis here...')
        >>> extract_title_from_response("No title here")
        (None, 'No title here')
    """
    if not response:
        return None, response

    # Search for title pattern at end of response
    match = CHAT_TITLE_PATTERN.search(response)

    if match:
        title = match.group(1).strip()

        # Validate title length (max 30 chars as per prompt instructions)
        if len(title) > 30:
            title = title[:27] + "..."

        # Remove the title line from response
        cleaned = response[: match.start()].rstrip()

        logger.info(
            "Extracted LLM-generated title",
            title=title,
            original_length=len(response),
            cleaned_length=len(cleaned),
        )

        return title, cleaned

    logger.debug("No LLM-generated title found in response")
    return None, response
