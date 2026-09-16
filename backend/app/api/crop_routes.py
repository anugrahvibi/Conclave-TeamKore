"""
Isolated Crop Recommendation API Router.
Exposes village-level crop recommendation endpoints without modifying existing routes.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field

from backend.app.services.spatial_service import spatial_service
from backend.app.services.forecast_service import forecast_service
from backend.app.services.data_service import data_service
from backend.app.services.crop_recommendation_service import (
    recommend_crops,
    crop_recommendation_engine,
)

# Isolated APIRouter instance
crop_router = APIRouter(tags=["Crop Recommendation"])

_statewide_cache: Dict[str, Dict[str, Any]] = {}


class CropRecommendationItem(BaseModel):
    crop: str = Field(..., description="Crop identifier (e.g. rice, banana, coconut, tapioca, vegetables, rubber)")
    suitability_score: float = Field(..., ge=0.0, le=1.0, description="Agronomic suitability score between 0.0 and 1.0")
    confidence: str = Field(..., description="Confidence rating: 'high', 'medium', or 'low'")
    explanation: str = Field(..., description="One-line agronomic rationale based on current forecast and terrain")


class CropRecommendationResponse(BaseModel):
    panchayat_id: str = Field(..., description="Panchayat or village identifier")
    recommendations: List[CropRecommendationItem] = Field(..., description="Ranked list of suitable crops")


class CropMetadataItem(BaseModel):
    id: str
    name: str
    aliases: List[str]
    optimal_temp_c: List[float]
    optimal_rainfall_mm: List[float]
    max_elevation_m: float
    season: List[str]
    notes: str


class VillageCropSuitabilityItem(BaseModel):
    village_id: str
    panchayat_id: str
    name: str
    district: str
    elevation_m: float
    suitability_score: float
    confidence: str
    fillColor: str
    explanation: str


class StatewideCropSuitabilityResponse(BaseModel):
    crop: str
    display_name: str
    total_villages: int
    optimal_count: int
    good_count: int
    moderate_count: int
    suboptimal_count: int
    villages: List[VillageCropSuitabilityItem]


@crop_router.get(
    "/crops",
    response_model=List[CropMetadataItem],
    summary="List All Supported Crops for Suitability Mapping & Search"
)
def get_all_crops():
    """Returns metadata and search aliases for all supported crops."""
    return crop_recommendation_engine.get_available_crops()


@crop_router.get(
    "/crops/suitability/{crop_name}",
    response_model=StatewideCropSuitabilityResponse,
    summary="Statewide Village-Level Suitability Heatmap for a Specific Crop"
)
def get_statewide_crop_suitability(
    crop_name: str = Path(..., description="Crop ID or alias (e.g. 'rice', 'paddy', 'banana', 'coconut', 'tapioca', 'rubber', 'vegetables')")
):
    """
    Evaluates every Kerala village/panchayat against ICAR suitability rules for the specified crop,
    generating a statewide heatmap color mapping for instant GIS rendering.
    """
    canonical_id = crop_recommendation_engine.resolve_crop_id(crop_name)
    if not canonical_id or canonical_id not in crop_recommendation_engine.rules:
        raise HTTPException(
            status_code=404,
            detail=f"Crop '{crop_name}' is not recognized. Available crops: {list(crop_recommendation_engine.rules.keys())}"
        )

    if canonical_id in _statewide_cache:
        return _statewide_cache[canonical_id]

    rule = crop_recommendation_engine.rules[canonical_id]
    display_name = rule.get("display_name", canonical_id.capitalize())

    all_villages = spatial_service.get_villages()
    village_items: List[VillageCropSuitabilityItem] = []
    opt_cnt = good_cnt = mod_cnt = sub_cnt = 0

    # Pre-cache block weather summaries
    block_summaries: Dict[str, Dict[str, float]] = {}
    for bid in spatial_service.block_ids_ordered:
        bfs = data_service.get_block_forecasts(bid)
        if bfs:
            temps = [f["temp"] for f in bfs]
            rains = [f["rainfall"] for f in bfs]
            humids = [f["humidity"] for f in bfs]
            winds = [f["wind"] for f in bfs]
            block_summaries[bid] = {
                "avg_temp_c": sum(temps) / len(temps),
                "total_rainfall_mm": sum(rains),
                "avg_humidity_pct": sum(humids) / len(humids),
                "max_wind_kmh": max(winds)
            }
        else:
            block_summaries[bid] = {
                "avg_temp_c": 27.0,
                "total_rainfall_mm": 25.0,
                "avg_humidity_pct": 75.0,
                "max_wind_kmh": 12.0
            }

    for v in all_villages:
        vid = v["village_id"]
        pid = v.get("panchayat_id", vid)
        name = v.get("name", "Village")
        district = v.get("district", "Kerala")
        static = v.get("static_features", {})
        elev = float(static.get("elevation_m", 100.0))
        bid = v.get("nearest_block_id", "BLK_KSD_KAN")

        # Fast lookup: Use detailed cached forecast if available, else block station summary with elevation lapse rate
        fc = forecast_service._forecast_cache.get(vid)
        if not fc:
            b_sum = block_summaries.get(bid, block_summaries.get("BLK_KSD_KAN"))
            adjusted_temp = max(10.0, b_sum["avg_temp_c"] - (elev - 100.0) * 0.0065)
            fc = {
                "summary": {
                    "avg_temp_c": adjusted_temp,
                    "total_rainfall_mm": b_sum["total_rainfall_mm"],
                    "avg_humidity_pct": b_sum["avg_humidity_pct"],
                    "max_wind_kmh": b_sum["max_wind_kmh"]
                }
            }

        recs = crop_recommendation_engine.evaluate(fc, static)

        # Find matching crop in recommendations or calculate specifically
        crop_match = next((r for r in recs if r["crop"] == canonical_id), None)
        if crop_match:
            score = float(crop_match["suitability_score"])
            confidence = crop_match["confidence"]
            explanation = crop_match["explanation"]
        else:
            score = 0.30
            confidence = "low"
            explanation = f"Suboptimal environmental conditions for {display_name}."

        # Assign map color ramp: deep green for best, lime for good, amber for moderate, slate for low
        if score >= 0.75:
            fill_color = "#15803d"  # Optimal
            opt_cnt += 1
        elif score >= 0.60:
            fill_color = "#22c55e"  # Good
            good_cnt += 1
        elif score >= 0.45:
            fill_color = "#eab308"  # Moderate
            mod_cnt += 1
        else:
            fill_color = "#94a3b8"  # Suboptimal
            sub_cnt += 1

        village_items.append(
            VillageCropSuitabilityItem(
                village_id=vid,
                panchayat_id=pid,
                name=name,
                district=district,
                elevation_m=elev,
                suitability_score=score,
                confidence=confidence,
                fillColor=fill_color,
                explanation=explanation
            )
        )

    response_data = StatewideCropSuitabilityResponse(
        crop=canonical_id,
        display_name=display_name,
        total_villages=len(village_items),
        optimal_count=opt_cnt,
        good_count=good_cnt,
        moderate_count=mod_cnt,
        suboptimal_count=sub_cnt,
        villages=village_items
    )

    _statewide_cache[canonical_id] = response_data
    return response_data


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

