"""
Model configuration for Agent Maestro multi-provider LLM routing.
Maps agent roles to specific models and vendors for cross-vendor debate quality.
"""

from dataclasses import dataclass, field


@dataclass
class ModelConfig:
    """Configuration for an LLM model."""

    model_id: str
    display_name: str
    vendor: str  # "openai", "anthropic", "google"
    max_tokens: int = 8192
    default_max_tokens: int = 4000
    supports_vision: bool = False
    supports_thinking: bool = False
    description: str = ""
    order: int = 1


# Agent Maestro base URL paths per vendor
VENDOR_URL_PATHS = {
    "openai": "/api/openai/v1",
    "anthropic": "/api/anthropic",
    "google": "/api/gemini",
}


def infer_vendor(model_name: str) -> str:
    """Infer vendor from model name prefix."""
    name = model_name.lower()
    if "gpt" in name or "o1" in name or "o3" in name:
        return "openai"
    if "claude" in name:
        return "anthropic"
    if "gemini" in name:
        return "google"
    return "openai"


# Available models via Agent Maestro
MODELS: dict[str, ModelConfig] = {
    "gpt-5.4": ModelConfig(
        model_id="gpt-5.4",
        display_name="GPT-5.4",
        vendor="openai",
        max_tokens=16384,
        default_max_tokens=4000,
        supports_vision=True,
        description="OpenAI flagship - vision capable",
        order=1,
    ),
    "claude-opus-4.7": ModelConfig(
        model_id="claude-opus-4.7",
        display_name="Claude Opus 4.7",
        vendor="anthropic",
        max_tokens=16384,
        default_max_tokens=4000,
        description="Anthropic flagship - deep reasoning",
        order=2,
    ),
    "gemini-3.1-pro-preview": ModelConfig(
        model_id="gemini-3.1-pro-preview",
        display_name="Gemini 3.1 Pro Preview",
        vendor="google",
        max_tokens=65536,
        default_max_tokens=4000,
        description="Google flagship - long context",
        order=3,
    ),
    "claude-haiku-4.5": ModelConfig(
        model_id="claude-haiku-4.5",
        display_name="Claude Haiku 4.5",
        vendor="anthropic",
        max_tokens=8192,
        default_max_tokens=2000,
        description="Fast and efficient",
        order=4,
    ),
}


# Default role → model mapping for cross-vendor debate
DEFAULT_ROLE_MODELS: dict[str, str] = {
    "main_analyst": "claude-opus-4.7",
    "technical": "claude-opus-4.7",
    "fundamentals": "gpt-5.4",
    "news": "gemini-3.1-pro-preview",
    "holdings": "claude-opus-4.7",
    "debater": "gemini-3.1-pro-preview",  # MUST differ from main vendor
    "summarize": "claude-haiku-4.5",
    "vision": "gpt-5.4",
    "pdf_reader": "gemini-3.1-pro-preview",
    "default": "claude-opus-4.7",
}


DEFAULT_MODEL = "claude-opus-4.7"


def get_model_config(model_id: str) -> ModelConfig:
    if model_id not in MODELS:
        raise ValueError(
            f"Model '{model_id}' not found. Available: {list(MODELS.keys())}"
        )
    return MODELS[model_id]


def get_all_models() -> list[ModelConfig]:
    return sorted(MODELS.values(), key=lambda m: m.order)
