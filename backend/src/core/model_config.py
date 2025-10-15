"""
Model configuration and pricing for LLM selection.
Centralizes model metadata, pricing, and capabilities.
"""

from dataclasses import dataclass


@dataclass
class ModelPricing:
    """Pricing information for a specific model."""

    input_cost_per_1k: float  # CNY per 1000 tokens
    output_cost_per_1k: float  # CNY per 1000 tokens
    thinking_output_multiplier: float = 1.0  # Multiplier for thinking mode output


@dataclass
class ModelConfig:
    """Complete configuration for an LLM model."""

    model_id: str  # API model identifier
    display_name: str  # User-facing name
    provider: str  # "alibaba" for DashScope models
    pricing: ModelPricing
    max_tokens: int  # Maximum output tokens
    default_max_tokens: int  # Default for UI
    supports_thinking: bool
    description: str
    order: int  # Display order (lower = higher priority)


# Credit baseline: 1 credit = 0.001 CNY
# Formula: credits = (cost_in_cny / 0.001) = cost_in_cny * 1000
CREDIT_TO_CNY_RATE = 0.001


def calculate_cost_in_credits(
    input_tokens: int,
    output_tokens: int,
    model_config: ModelConfig,
    thinking_enabled: bool = False,
) -> float:
    """
    Calculate credit cost based on actual model pricing.

    Args:
        input_tokens: Number of input tokens (prompt + context)
        output_tokens: Number of output tokens (response)
        model_config: Model configuration with pricing info
        thinking_enabled: Whether thinking mode is enabled

    Returns:
        Cost in credits (rounded to 2 decimals)

    Raises:
        ValueError: If input_tokens or output_tokens is negative
    """
    # Validate inputs
    if input_tokens < 0:
        raise ValueError(f"input_tokens must be non-negative, got {input_tokens}")
    if output_tokens < 0:
        raise ValueError(f"output_tokens must be non-negative, got {output_tokens}")

    # Calculate input cost
    input_cost_cny = (input_tokens / 1000) * model_config.pricing.input_cost_per_1k

    # Calculate output cost (with thinking multiplier if applicable)
    output_multiplier = (
        model_config.pricing.thinking_output_multiplier
        if thinking_enabled and model_config.supports_thinking
        else 1.0
    )
    output_cost_cny = (
        (output_tokens / 1000)
        * model_config.pricing.output_cost_per_1k
        * output_multiplier
    )

    # Total cost in CNY
    total_cost_cny = input_cost_cny + output_cost_cny

    # Convert to credits
    credits = total_cost_cny / CREDIT_TO_CNY_RATE

    return round(credits, 2)


# ===== Model Registry =====

MODELS = {
    "qwen-plus": ModelConfig(
        model_id="qwen-plus",
        display_name="Qwen Plus",
        provider="alibaba",
        pricing=ModelPricing(
            input_cost_per_1k=0.0008,  # ¥0.0008/1K tokens
            output_cost_per_1k=0.002,  # ¥0.002/1K tokens (non-thinking)
            thinking_output_multiplier=4.0,  # 4x for thinking mode (¥0.008/1K)
        ),
        max_tokens=32768,
        default_max_tokens=3000,
        supports_thinking=True,
        description="Balanced - Best value",
        order=1,
    ),
    "qwen3-max": ModelConfig(
        model_id="qwen3-max",
        display_name="Qwen3 Max",
        provider="alibaba",
        pricing=ModelPricing(
            input_cost_per_1k=0.006,  # ¥0.006/1K tokens (tier 1: 0-32K)
            output_cost_per_1k=0.024,  # ¥0.024/1K tokens (tier 1)
        ),
        max_tokens=65536,
        default_max_tokens=4000,
        supports_thinking=False,  # Empirically tested: thinking mode not working
        description="Premium - Flagship model",
        order=4,
    ),
    "deepseek-v3.2-exp": ModelConfig(
        model_id="deepseek-v3.2-exp",
        display_name="DeepSeek V3.2 Exp",
        provider="alibaba",
        pricing=ModelPricing(
            input_cost_per_1k=0.002,  # ¥0.002/1K tokens
            output_cost_per_1k=0.003,  # ¥0.003/1K tokens (same for thinking)
        ),
        max_tokens=32768,
        default_max_tokens=3000,
        supports_thinking=True,
        description="Experimental - Latest features",
        order=2,
    ),
    "deepseek-v3": ModelConfig(
        model_id="deepseek-v3",
        display_name="DeepSeek V3",
        provider="alibaba",
        pricing=ModelPricing(
            input_cost_per_1k=0.002,  # ¥0.002/1K tokens
            output_cost_per_1k=0.008,  # ¥0.008/1K tokens
        ),
        max_tokens=32768,
        default_max_tokens=3000,
        supports_thinking=False,
        description="Flagship - High performance",
        order=3,
    ),
}

# Default model (backward compatibility)
DEFAULT_MODEL = "qwen-plus"


def get_model_config(model_id: str) -> ModelConfig:
    """
    Get model configuration by ID.

    Args:
        model_id: Model identifier (e.g., "qwen-plus")

    Returns:
        ModelConfig for the requested model

    Raises:
        ValueError: If model_id is not found
    """
    if model_id not in MODELS:
        raise ValueError(
            f"Model '{model_id}' not found. Available models: {list(MODELS.keys())}"
        )

    return MODELS[model_id]


def get_all_models() -> list[ModelConfig]:
    """
    Get all available models sorted by display order.

    Returns:
        List of ModelConfig objects sorted by order
    """
    return sorted(MODELS.values(), key=lambda m: m.order)


def estimate_cost(
    model_id: str,
    estimated_input_tokens: int,
    estimated_output_tokens: int,
    thinking_enabled: bool = False,
) -> float:
    """
    Estimate cost for a chat request.

    Args:
        model_id: Model identifier
        estimated_input_tokens: Estimated input tokens
        estimated_output_tokens: Estimated output tokens
        thinking_enabled: Whether thinking mode is enabled

    Returns:
        Estimated cost in credits
    """
    model_config = get_model_config(model_id)

    return calculate_cost_in_credits(
        input_tokens=estimated_input_tokens,
        output_tokens=estimated_output_tokens,
        model_config=model_config,
        thinking_enabled=thinking_enabled,
    )
