"""
LLM Models API endpoints for model selection.
Returns available models via Agent Maestro.
"""

import structlog
from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..core.model_config import DEFAULT_MODEL, DEFAULT_ROLE_MODELS, MODELS

logger = structlog.get_logger()

router = APIRouter(prefix="/api", tags=["llm_models"])


class ModelInfoResponse(BaseModel):
    """Model information for frontend."""

    model_id: str = Field(..., description="Model identifier")
    display_name: str = Field(..., description="Human-readable name")
    vendor: str = Field(..., description="Model vendor")
    max_tokens: int = Field(..., description="Maximum tokens")
    default_max_tokens: int = Field(..., description="Default max tokens")
    supports_vision: bool = Field(default=False)
    description: str = Field(default="")
    order: int = Field(default=1)

    class Config:
        protected_namespaces = ()


class RoleMappingResponse(BaseModel):
    """Role to model mapping."""

    role: str
    model_id: str
    vendor: str


class ModelsListResponse(BaseModel):
    """Available models and role mappings."""

    models: list[ModelInfoResponse]
    default_model: str
    role_mappings: list[RoleMappingResponse]


@router.get("/models", response_model=ModelsListResponse)
async def list_available_models() -> ModelsListResponse:
    model_responses = []
    for mc in MODELS.values():
        model_responses.append(
            ModelInfoResponse(
                model_id=mc.model_id,
                display_name=mc.display_name,
                vendor=mc.vendor,
                max_tokens=mc.max_tokens,
                default_max_tokens=mc.default_max_tokens,
                supports_vision=mc.supports_vision,
                description=mc.description,
                order=mc.order,
            )
        )
    model_responses.sort(key=lambda m: m.order)

    from ..core.model_config import infer_vendor

    role_mappings = [
        RoleMappingResponse(
            role=role,
            model_id=model_id,
            vendor=infer_vendor(model_id),
        )
        for role, model_id in DEFAULT_ROLE_MODELS.items()
    ]

    return ModelsListResponse(
        models=model_responses,
        default_model=DEFAULT_MODEL,
        role_mappings=role_mappings,
    )
