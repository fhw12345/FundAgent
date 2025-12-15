"""
Chat API module for conversational financial analysis.

This module provides a unified router that combines CRUD endpoints and streaming
functionality. Following Factor 11 & 12: Triggerable via API, Stateless Service.

The module is organized as:
- endpoints.py: CRUD operations (create, list, get, delete, update UI state)
- streaming/: Modular streaming handlers package
  - handlers.py: Main unified handler with version routing
  - simple_agent.py: Simple Agent (v2) streaming logic
  - react_agent.py: ReAct Agent (v3) streaming logic
  - helpers.py: SSE formatting and error handling utilities
- helpers.py: Utility functions for context management and symbol handling

Backward compatibility is maintained - you can still import `router` directly:
    from src.api.chat import router
"""

from fastapi import APIRouter

from .endpoints import router as endpoints_router
from .helpers import build_symbol_context_instruction
from .streaming import chat_stream_unified

# Backward compatibility alias for test imports
_build_symbol_context_instruction = build_symbol_context_instruction

# Create main router with prefix and tags
router = APIRouter(prefix="/api/chat", tags=["chat"])

# Include CRUD endpoints
router.include_router(endpoints_router)

# Add streaming endpoint
router.add_api_route(
    "/stream",
    chat_stream_unified,
    methods=["POST"],
    name="chat_stream_unified",
)

# Export router and helpers for backward compatibility
__all__ = [
    "router",
    "_build_symbol_context_instruction",
    "build_symbol_context_instruction",
]
