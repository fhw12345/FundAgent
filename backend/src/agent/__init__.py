"""
Financial Agent module for LLM-powered conversational analysis.

This module implements a lightweight chat agent using Alibaba Cloud Qwen model.
Message history is managed by MongoDB (v0.5.0).

Future versions will add:
- LangGraph workflow orchestration
- Multi-modal analysis (chart interpretation)
"""

from .chat_agent import ChatAgent

__all__ = ["ChatAgent"]
