"""
Streaming response handlers for chat API.

This package contains modular streaming logic for both Simple Agent (v2)
and ReAct Agent (v3), with a unified handler for version routing.

Public API:
    chat_stream_unified: Main unified streaming endpoint (re-exported for backward compatibility)
"""

from .handlers import chat_stream_unified

__all__ = ["chat_stream_unified"]
