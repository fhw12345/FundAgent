"""
Financial Agent module for LLM-powered conversational analysis.

This module implements a lightweight chat agent using Alibaba Cloud Qwen model
with in-memory session management (v0.2.0).

Future versions will add:
- MongoDB session persistence
- LangGraph workflow orchestration
- Multi-modal analysis (chart interpretation)
"""

from .chat_agent import ChatAgent
from .session_manager import SessionManager
from .state import ChatMessage, ChatSession

__all__ = ["ChatAgent", "SessionManager", "ChatMessage", "ChatSession"]
