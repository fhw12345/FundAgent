"""
Shared sanitization utilities.

Provides secure text and response sanitization to prevent API key leakage
in logs, error messages, and user-facing responses.

Consolidates duplicate implementations from:
- services/alphavantage_market_data.py (_sanitize_text, _sanitize_response)
- services/alphavantage_response_formatter.py
"""

import re
from typing import Any

# Pre-compiled regex patterns for performance
_API_KEY_PATTERN = re.compile(r"(apikey[=:]\s*)([A-Z0-9]+)", re.IGNORECASE)
_BEARER_TOKEN_PATTERN = re.compile(r"(Bearer\s+)([A-Za-z0-9._-]+)", re.IGNORECASE)
_PASSWORD_PATTERN = re.compile(r"(password[=:]\s*)([^\s&]+)", re.IGNORECASE)

# Keywords that indicate sensitive content
_SENSITIVE_KEYWORDS = frozenset(
    {"api key", "apikey", "api_key", "bearer", "token", "password", "secret"}
)


def sanitize_text(text: str, mask: str = "****") -> str:
    """
    Remove sensitive information from text strings.

    Sanitizes API keys, bearer tokens, and passwords from text before
    logging or displaying to users.

    Args:
        text: Text to sanitize
        mask: Replacement mask for sensitive values

    Returns:
        Sanitized text with sensitive values masked

    Examples:
        >>> sanitize_text("Error: Invalid apikey=ABC123DEF")
        "Error: Invalid apikey=****"
        >>> sanitize_text("Bearer eyJhbGciOiJIUzI1NiJ9.xyz")
        "Bearer ****"
    """
    if not text:
        return text

    # Quick check for sensitive keywords (optimization)
    text_lower = text.lower()
    has_sensitive = any(keyword in text_lower for keyword in _SENSITIVE_KEYWORDS)

    if not has_sensitive:
        return text

    # Apply sanitization patterns
    result = _API_KEY_PATTERN.sub(rf"\1{mask}", text)
    result = _BEARER_TOKEN_PATTERN.sub(rf"\1{mask}", result)
    result = _PASSWORD_PATTERN.sub(rf"\1{mask}", result)

    return result


def sanitize_api_response(
    response: dict[str, Any], mask: str = "****"
) -> dict[str, Any]:
    """
    Remove API keys from API error responses.

    Sanitizes common error message fields in API responses to prevent
    API key leakage in logs or error displays.

    Args:
        response: API response dictionary
        mask: Replacement mask for sensitive values

    Returns:
        Sanitized copy of the response

    Examples:
        >>> resp = {"Error Message": "Invalid apikey=XYZ123"}
        >>> sanitize_api_response(resp)
        {"Error Message": "Invalid apikey=****"}
    """
    if not response:
        return response

    sanitized = response.copy()

    # Fields commonly containing error messages
    error_fields = (
        "Information",
        "Note",
        "Error Message",
        "error",
        "message",
        "detail",
    )

    for field in error_fields:
        if field in sanitized and isinstance(sanitized[field], str):
            sanitized[field] = sanitize_text(sanitized[field], mask)

    return sanitized


def sanitize_exception_message(exc: Exception, mask: str = "****") -> str:
    """
    Sanitize an exception message for safe logging/display.

    Args:
        exc: Exception to sanitize
        mask: Replacement mask for sensitive values

    Returns:
        Sanitized exception message

    Examples:
        >>> try:
        ...     raise ValueError("apikey=SECRET123 is invalid")
        ... except ValueError as e:
        ...     print(sanitize_exception_message(e))
        "apikey=**** is invalid"
    """
    return sanitize_text(str(exc), mask)


def is_sensitive_field(field_name: str) -> bool:
    """
    Check if a field name indicates sensitive content.

    Args:
        field_name: Name of the field to check

    Returns:
        True if the field likely contains sensitive data

    Examples:
        >>> is_sensitive_field("api_key")
        True
        >>> is_sensitive_field("user_name")
        False
    """
    field_lower = field_name.lower()
    sensitive_indicators = (
        "key",
        "secret",
        "password",
        "token",
        "credential",
        "auth",
        "bearer",
    )
    return any(indicator in field_lower for indicator in sensitive_indicators)
