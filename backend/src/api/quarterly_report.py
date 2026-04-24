"""Quarterly report PDF analysis API."""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..core.config import Settings, get_settings
from ..services.quarterly_report_service import (
    analyze_quarterly_report_image,
    analyze_quarterly_report_text,
)
from .dependencies.auth import get_current_user

logger = structlog.get_logger()
router = APIRouter(prefix="/api/quarterly-report", tags=["quarterly-report"])


class ReportImageRequest(BaseModel):
    image_base64: str = Field(..., description="Base64 encoded report page image")


class ReportTextRequest(BaseModel):
    text: str = Field(..., min_length=50, description="Extracted text from quarterly report PDF")


@router.post("/analyze-image")
async def analyze_report_image(
    request: ReportImageRequest,
    _: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    try:
        result = await analyze_quarterly_report_image(request.image_base64, settings)
        return result
    except Exception as e:
        logger.error("Quarterly report image analysis failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"季报分析失败: {str(e)}") from e


@router.post("/analyze-text")
async def analyze_report_text(
    request: ReportTextRequest,
    _: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    try:
        result = await analyze_quarterly_report_text(request.text, settings)
        return {"status": "ok", "analysis": result}
    except Exception as e:
        logger.error("Quarterly report text analysis failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"季报分析失败: {str(e)}") from e
