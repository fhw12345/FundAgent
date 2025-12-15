"""
Shared helper functions for streaming responses.

This module contains utility functions for SSE event formatting
and error handling used by both simple and react agent streams.
"""

import json


def format_sse_event(event_data: dict) -> str:
    """
    Format a dictionary as an SSE (Server-Sent Events) event.

    Args:
        event_data: Dictionary containing event data

    Returns:
        SSE-formatted string with 'data: ' prefix and double newline
    """
    return f"data: {json.dumps(event_data)}\n\n"


def create_error_event(error_message: str, error_code: str) -> str:
    """
    Create a formatted SSE error event.

    Args:
        error_message: Human-readable error message
        error_code: Error code identifier (e.g., 'INSUFFICIENT_CREDITS')

    Returns:
        SSE-formatted error event string
    """
    error_data = {
        "error": error_message,
        "error_code": error_code,
        "type": "error",
    }
    return format_sse_event(error_data)


def create_done_event(chat_id: str, **extra_data) -> str:
    """
    Create a formatted SSE completion event.

    Args:
        chat_id: Chat identifier
        **extra_data: Additional data to include in the event (e.g., credits_used)

    Returns:
        SSE-formatted completion event string
    """
    event_data = {"type": "done", "chat_id": chat_id, **extra_data}
    return format_sse_event(event_data)


def create_chunk_event(content: str) -> str:
    """
    Create a formatted SSE chunk event for streaming text.

    Args:
        content: Text chunk to stream

    Returns:
        SSE-formatted chunk event string
    """
    chunk_data = {"type": "chunk", "content": content}
    return format_sse_event(chunk_data)
