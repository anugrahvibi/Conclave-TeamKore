"""
FastAPI route handlers for downscaling and agro-advisory endpoints.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Path

from backend.app.config import settings
from backend.app.schemas import (
    ForecastResponse,
    AdvisoryResponse,
    BlockSummaryResponse,
    HealthResponse,
    GeoJSONFeatureCollection,
    VillageDetail,
    ForecastSummary,
    RiskDistribution,
    BlockVillageOverview,
    Coordinates
)
from backend.app.services.data_service import data_service, KERALA_BLOCK_STATIONS
from backend.app.services.spatial_service import spatial_service
from backend.app.services.forecast_service import forecast_service
from backend.app.services.advisory_service import advisory_service

router = APIRouter()


@router.get("/health", response_model=HealthResponse, summary="System Health Check")
def health_check():
    """Returns runtime health status and loaded dataset statistics."""
    model_trained = (
        forecast_service.pipeline is not None
        and forecast_service.pipeline.correction_model.is_trained
    )
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "loaded_villages": spatial_service.total_villages,
        "loaded_blocks": len(KERALA_BLOCK_STATIONS),
        "model_trained": model_trained,
        "spatial_engine": "In-Memory KDTree + OSM GeoJSON Polygons"
    }


@router.get("/forecast/{panchayat_id}", response_model=ForecastResponse, summary="Downscaled 3-Day Village Forecast")
def get_forecast(
    panchayat_id: str = Path(..., description="Panchayat ID (e.g. KL_PANCH_0001), Village ID (e.g. VIL_0001), or Village Name")
):
    """
    Returns high-resolution downscaled 3-day weather forecast (12 timesteps / 6h steps)
    for the specified village or panchayat, combining spatial IDW with ML microclimate correction.
    """
    forecast = forecast_service.get_forecast_for_village(panchayat_id)
    if not forecast:
        raise HTTPException(
            status_code=404,
            detail=f"Village or Panchayat '{panchayat_id}' not found. Please verify the ID or name."
        )
    return forecast


@router.get("/advisory/{panchayat_id}", response_model=AdvisoryResponse, summary="Village Agro-Advisory & Risk Evaluation")
def get_advisory(
    panchayat_id: str = Path(..., description="Panchayat ID, Village ID, or Name"),
    crop_stage: str = Query(
        "spraying_window",
        description="Current crop development stage: seedling, young_seedling, vegetative, spraying_window, flowering, pod_formation, mature"
    )
):
    """
    Returns immediate agro-climatic advisory guidance, risk severity rating,
    and actionable field management steps based on downscaled weather.
    """
    advisory = advisory_service.get_advisory_for_village(panchayat_id, crop_stage=crop_stage)
    if not advisory:
        raise HTTPException(
            status_code=404,
            detail=f"Village or Panchayat '{panchayat_id}' not found. Please verify the ID or name."
        )
    return advisory


@router.get("/villages", summary="Village List with Centroids & Boundary Geometries")
def get_villages(
    district: Optional[str] = Query(None, description="Filter by district (e.g. 'Kasargod', 'Idukki')"),
    block_id: Optional[str] = Query(None, description="Filter by nearest block station ID (e.g. 'BLK_KSD_KAN')"),
    search: Optional[str] = Query(None, description="Search by village/panchayat name or ID"),
    format: str = Query("geojson", description="Response format: 'geojson' (FeatureCollection) or 'json' (list)"),
    limit: Optional[int] = Query(None, description="Max number of items to return"),
    offset: int = Query(0, description="Offset for pagination")
):
    """
    Returns Kerala Panchayats/villages with centroid coordinates and authentic OSM boundary polygons
    for map rendering in Mapbox, Leaflet, or OpenLayers.
    """
    if format.lower() == "json":
        villages = spatial_service.get_villages(
            district=district,
            block_id=block_id,
            search=search,
            limit=limit,
            offset=offset
        )
        return {
            "total": len(villages),
            "villages": villages
        }

    return spatial_service.get_villages_geojson(
        district=district,
        block_id=block_id,
        search=search,
        limit=limit,
        offset=offset
    )


@router.get("/block/{block_id}/summary", response_model=BlockSummaryResponse, summary="Officer Dashboard Block-Wide Summary")
def get_block_summary(
    block_id: str = Path(..., description="Agro-climatic block station ID (e.g. 'BLK_KSD_KAN', 'BLK_IDK_MUN')")
):
    """
    Aggregates weather conditions, risk distributions, and alerts across all villages
    assigned to the specified block station for the agricultural officer dashboard.
    """
    clean_bid = block_id.strip()
    block_info = data_service.get_block_info(clean_bid)
    if not block_info:
        raise HTTPException(
            status_code=404,
            detail=f"Block ID '{clean_bid}' not found. Available blocks: {list(KERALA_BLOCK_STATIONS.keys())[:5]}..."
        )

    villages = spatial_service.get_villages_for_block(clean_bid)
    if not villages:
        # Fallback: if no villages mapped, query all villages in the same district
        district = block_info["district"]
        villages = spatial_service.get_villages(district=district)

    # Weather forecast for the block station itself
    block_forecasts = data_service.get_block_forecasts(clean_bid)
    if block_forecasts:
        temps = [f["temp"] for f in block_forecasts]
        rains = [f["rainfall"] for f in block_forecasts]
        humids = [f["humidity"] for f in block_forecasts]
        winds = [f["wind"] for f in block_forecasts]
        weather_summary = {
            "min_temp_c": round(min(temps), 2),
            "max_temp_c": round(max(temps), 2),
            "avg_temp_c": round(sum(temps) / len(temps), 2),
            "total_rainfall_mm": round(sum(rains), 2),
            "avg_humidity_pct": round(sum(humids) / len(humids), 1),
            "max_wind_kmh": round(max(winds), 1)
        }
    else:
        weather_summary = {
            "min_temp_c": 22.0, "max_temp_c": 31.0, "avg_temp_c": 26.5,
            "total_rainfall_mm": 12.5, "avg_humidity_pct": 82.0, "max_wind_kmh": 14.0
        }

    # Village overview and risk counts
    risk_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    village_overviews = []

    for v in villages:
        adv = advisory_service.get_advisory_for_village(v["village_id"])
        if adv:
            risk = adv["advisory"]["risk_level"]
            risk_counts[risk] = risk_counts.get(risk, 0) + 1
            text = adv["advisory"]["text"]
            curr_temp = adv["current_weather"]["temp_c"]
            curr_rain = adv["current_weather"]["rainfall_mm"]
        else:
            risk = "low"
            risk_counts["low"] += 1
            text = "Normal management conditions."
            curr_temp = weather_summary["avg_temp_c"]
            curr_rain = 0.0

        village_overviews.append({
            "village_id": v["village_id"],
            "panchayat_id": v["panchayat_id"],
            "name": v["name"],
            "temp_c": curr_temp,
            "rainfall_mm": curr_rain,
            "risk_level": risk,
            "advisory_summary": text
        })

    severe_alerts = risk_counts["critical"] + risk_counts["high"]

    return {
        "block_id": clean_bid,
        "block_name": block_info["name"],
        "district": block_info["district"],
        "center": {"lat": block_info["lat"], "lon": block_info["lon"]},
        "total_villages": len(villages),
        "aggregated_weather": weather_summary,
        "risk_distribution": risk_counts,
        "severe_alerts_count": severe_alerts,
        "villages": village_overviews
    }
