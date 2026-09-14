"""
Isolated Crop Recommendation API Router.
Exposes village-level crop recommendation endpoints without modifying existing routes.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field

from backend.app.services.spatial_service import spatial_service
from backend.app.services.forecast_service import forecast_service
from backend.app.services.crop_recommendation_service import recommend_crops

# Isolated APIRouter instance
crop_router = APIRouter(tags=["Crop Recommendation"])


class CropRecommendationItem(BaseModel):
    crop: str = Field(..., description="Crop identifier (e.g. rice, banana, coconut, tapioca, vegetables, rubber)")
    suitability_score: float = Field(..., ge=0.0, le=1.0, description="Agronomic suitability score between 0.0 and 1.0")
    confidence: str = Field(..., description="Confidence rating: 'high', 'medium', or 'low'")
    explanation: str = Field(..., description="One-line agronomic rationale based on current forecast and terrain")


class CropRecommendationResponse(BaseModel):
    panchayat_id: str = Field(..., description="Panchayat or village identifier")
    recommendations: List[CropRecommendationItem] = Field(..., description="Ranked list of suitable crops")


@crop_router.get(
    "/recommend-crop/{panchayat_id}",
    response_model=CropRecommendationResponse,
    summary="Village-Level Crop Suitability Recommendations"
)
def get_crop_recommendation(
    panchayat_id: str = Path(..., description="Panchayat ID (e.g. KL_PANCH_0001), Village ID (e.g. VIL_0001), or Village Name")
):
    """
    Fetches the village's existing downscaled 3-day weather forecast and micro-topographic
    static features (read-only), evaluates conditions against ICAR/Kerala Department of
    Agriculture suitability rules, and returns a ranked list of recommended crops.
    """
    clean_id = panchayat_id.strip()
    village = spatial_service.get_village(clean_id)
    if not village:
        raise HTTPException(
            status_code=404,
            detail=f"Village or Panchayat '{clean_id}' not found. Please verify the ID or name."
        )

    forecast = forecast_service.get_forecast_for_village(clean_id)
    if not forecast:
        raise HTTPException(
            status_code=404,
            detail=f"Forecast data not available for Village or Panchayat '{clean_id}'."
        )

    static_features = village.get("static_features", {})
    recommendations = recommend_crops(forecast, static_features)

    return {
        "panchayat_id": village.get("panchayat_id", clean_id),
        "recommendations": recommendations
    }


def register_crop_router(app, prefix: str = ""):
    """Helper to cleanly register the isolated router to a FastAPI application instance."""
    app.include_router(crop_router, prefix=prefix)


router = crop_router
