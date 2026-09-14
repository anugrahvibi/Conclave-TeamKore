"""
Crop Recommendation Service root proxy.
Provides direct top-level access to recommend_crops.
"""

from backend.app.services.crop_recommendation_service import (
    CropRecommendationEngine,
    crop_recommendation_engine,
    recommend_crops,
    MIN_SUITABILITY_THRESHOLD,
)

__all__ = [
    "CropRecommendationEngine",
    "crop_recommendation_engine",
    "recommend_crops",
    "MIN_SUITABILITY_THRESHOLD",
]
