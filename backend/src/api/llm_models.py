"""
LLM Models API endpoints for model selection and configuration.
Provides available models with pricing and capabilities.
"""

import structlog
from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..core.model_config import MODELS, ModelConfig

logger = structlog.get_logger()

router = APIRouter(prefix="/api", tags=["llm_models"])


# ===== Response Models =====


class ModelPricingResponse(BaseModel):
    """Model pricing information."""

    input_cost_per_1k: float = Field(..., description="Input cost (CNY per 1K tokens)")
    output_cost_per_1k: float = Field(..., description="Output cost (CNY per 1K tokens)")
    thinking_output_multiplier: float = Field(
        ..., description="Cost multiplier for thinking mode (e.g., 4.0 = 4x)"
    )


class ModelInfoResponse(BaseModel):
    """Complete model information for frontend."""

    model_id: str = Field(..., description="Model identifier (e.g., 'qwen-plus')")
    display_name: str = Field(..., description="Human-readable model name")
    provider: str = Field(..., description="Model provider (e.g., 'alibaba')")
    pricing: ModelPricingResponse = Field(..., description="Pricing information")
    max_tokens: int = Field(..., description="Maximum tokens allowed")
    default_max_tokens: int = Field(..., description="Recommended default max tokens")
    supports_thinking: bool = Field(
        ..., description="Whether model supports thinking mode"
    )
    description: str = Field(..., description="Model description for UI")
    order: int = Field(..., description="Display order (1=highest priority)")

    class Config:
        protected_namespaces = ()  # Allow model_id field
        json_schema_extra = {
            "example": {
                "model_id": "qwen-plus",
                "display_name": "Qwen Plus",
                "provider": "alibaba",
                "pricing": {
                    "input_cost_per_1k": 0.0008,
                    "output_cost_per_1k": 0.002,
                    "thinking_output_multiplier": 4.0,
                },
                "max_tokens": 32768,
                "default_max_tokens": 3000,
                "supports_thinking": True,
                "description": "Balanced - Best value",
                "order": 1,
            }
        }


class ModelsListResponse(BaseModel):
    """List of available LLM models."""

    models: list[ModelInfoResponse] = Field(
        ..., description="Available models sorted by display order"
    )
    default_model: str = Field(
        ..., description="Default model ID (recommended for most users)"
    )


# ===== Endpoints =====


@router.get("/models", response_model=ModelsListResponse)
async def list_available_models() -> ModelsListResponse:
    """
    Get list of available LLM models with pricing and capabilities.

    **No authentication required** - public endpoint for model discovery.

    **Response:**
    ```json
    {
      "models": [
        {
          "model_id": "qwen-plus",
          "display_name": "Qwen Plus",
          "provider": "alibaba",
          "pricing": {
            "input_cost_per_1k": 0.0008,
            "output_cost_per_1k": 0.002,
            "thinking_output_multiplier": 4.0
          },
          "max_tokens": 32768,
          "default_max_tokens": 3000,
          "supports_thinking": true,
          "description": "Balanced - Best value",
          "order": 1
        }
      ],
      "default_model": "qwen-plus"
    }
    ```

    **Model Ordering:**
    Models are ordered by `order` field (lower number = higher priority).
    Typically ordered by price (cheapest first).

    **Thinking Mode:**
    - Supported models: qwen-plus (4x cost), deepseek-v3.2-exp (4x cost)
    - Not supported: qwen3-max, deepseek-v3 (grey out in UI)
    """
    # Convert model configs to response format
    model_responses = []

    for model_config in MODELS.values():
        model_responses.append(
            ModelInfoResponse(
                model_id=model_config.model_id,
                display_name=model_config.display_name,
                provider=model_config.provider,
                pricing=ModelPricingResponse(
                    input_cost_per_1k=model_config.pricing.input_cost_per_1k,
                    output_cost_per_1k=model_config.pricing.output_cost_per_1k,
                    thinking_output_multiplier=model_config.pricing.thinking_output_multiplier,
                ),
                max_tokens=model_config.max_tokens,
                default_max_tokens=model_config.default_max_tokens,
                supports_thinking=model_config.supports_thinking,
                description=model_config.description,
                order=model_config.order,
            )
        )

    # Sort by display order
    model_responses.sort(key=lambda m: m.order)

    logger.info("Available models listed", count=len(model_responses))

    return ModelsListResponse(
        models=model_responses,
        default_model="qwen-plus",  # Default recommendation
    )
