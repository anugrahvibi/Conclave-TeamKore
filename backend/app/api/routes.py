"""
FastAPI route handlers for downscaling and agro-advisory endpoints.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Path

from backend.app.config import settings
from backend.app.schemas import (
    ForecastResponse,
    ForecastRequestPayload,
    ForecastContractResponse,
    ModelInfoResponse,
    FeatureImportanceItem,
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
        "features_count": 6,
        "spatial_engine": "In-Memory KDTree + OSM GeoJSON Polygons"
    }


@router.get("/model/info", response_model=ModelInfoResponse, summary="ML Model Metadata & Feature Importance")
def get_model_info():
    """
    Returns trained Random Forest model architecture, 6-feature importance distribution,
    domain interpretation for farmers, and physical feature ranges.
    """
    model = forecast_service.pipeline.correction_model.model
    scaler = forecast_service.pipeline.correction_model.scaler
    importances = model.feature_importances_ if hasattr(model, "feature_importances_") else [0.0] * 6

    feature_meta = [
        {
            "feature": "elevation",
            "unit": "meters (m)",
            "category": "Micro-Topography",
            "description": "Altitude above sea level. Controls lapse rate cooling (~6.5°C/1000m).",
            "farmer_impact": "Directly controls frost danger, heat accumulation, and disease susceptibility in highland farms."
        },
        {
            "feature": "dist_to_water",
            "unit": "kilometers (km)",
            "category": "Hydrological Buffer",
            "description": "Proximity to rivers, backwaters, and coast. High thermal inertia moderates temperature swings.",
            "farmer_impact": "Farms near water experience gentler diurnal fluctuations; inland farms suffer faster heat shock."
        },
        {
            "feature": "block_temp",
            "unit": "Celsius (°C)",
            "category": "Macro Meteorology",
            "description": "Regional synoptic baseline temperature from IMD/Open-Meteo station forecast.",
            "farmer_impact": "Serves as foundation anchor for downscaled farm canopy prediction."
        },
        {
            "feature": "block_humidity",
            "unit": "percent (%)",
            "category": "Atmospheric Moisture",
            "description": "Ambient relative humidity, indicating cloud cover thickness and evaporative cooling potential.",
            "farmer_impact": "High humidity alerts farmers to blight and fungal risks; dry air prompts irrigation alerts."
        },
        {
            "feature": "block_rain",
            "unit": "millimeters (mm)",
            "category": "Precipitation",
            "description": "Precipitation volume in the forecast interval.",
            "farmer_impact": "Identifies washout risks for pesticides and opportunities for natural soil recharge."
        },
        {
            "feature": "land_cover",
            "unit": "categorical (0-4)",
            "category": "Surface Biophysics",
            "description": "Vegetation canopy class (agriculture, forest, urban, water, barren) altering albedo and shading.",
            "farmer_impact": "Forest canopy buffers extreme sun; urban built environments cause micro heat islands."
        }
    ]

    items = []
    # Names in order: block_temp (0), block_rain (1), block_humidity (2), elevation (3), dist_to_water (4), land_cover (5)
    name_to_idx = {
        "block_temp": 0,
        "block_rain": 1,
        "block_humidity": 2,
        "elevation": 3,
        "dist_to_water": 4,
        "land_cover": 5
    }

    for meta in feature_meta:
        idx = name_to_idx[meta["feature"]]
        pct = round(float(importances[idx]) * 100.0, 2) if idx < len(importances) else 0.0
        items.append({
            "feature": meta["feature"],
            "importance_pct": pct,
            "unit": meta["unit"],
            "category": meta["category"],
            "description": meta["description"],
            "farmer_impact": meta["farmer_impact"]
        })

    # Sort descending by importance
    items.sort(key=lambda x: x["importance_pct"], reverse=True)

    return {
        "model_type": "RandomForestRegressor (n_estimators=50, max_depth=8)",
        "n_features": 6,
        "features": ["block_temp", "block_rain", "block_humidity", "elevation", "dist_to_water", "land_cover"],
        "feature_importances": items,
        "default_static_features": {
            "elevation_m": 300.0,
            "dist_to_water_km": 5.0,
            "land_cover": "agriculture"
        },
        "feature_ranges": {
            "temp_c": [-40.0, 60.0],
            "rain_mm": [0.0, 1000.0],
            "humidity_pct": [0.0, 100.0],
            "elevation_m": [-500.0, 9000.0],
            "dist_to_water_km": [0.0, 500.0]
        }
    }


@router.post("/forecast", response_model=ForecastContractResponse, summary="ML Dev #2 Contract: Predict Downscaled Forecast + Advisory from Payload")
def post_forecast(req: ForecastRequestPayload):
    """
    Direct ML Dev #2 Contract Endpoint (from BACKEND_CONTRACT.md):
    Caller sends block_forecast, static_features, crop_stage.
    Returns corrected_temp_c, correction_delta, weather_inferred, and advisory.
    """
    try:
        static_features = req.static_features.model_dump() if req.static_features else {}
        static_features.setdefault("land_cover", "agriculture")

        result = forecast_service.pipeline.forecast_and_advise(
            block_forecast=req.block_forecast.model_dump(),
            static_features=static_features,
            crop_stage=req.crop_stage,
        )

        return {
            "village_id": req.village_id,
            "corrected_temp_c": result["corrected_temp_c"],
            "correction_delta": result["correction_delta"],
            "weather_inferred": result["weather_inferred"],
            "advisory": result["advisory"],
        }
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


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

    geojson = spatial_service.get_villages_geojson(
        district=district,
        block_id=block_id,
        search=search,
        limit=limit,
        offset=offset
    )

    for feature in geojson.get("features", []):
        props = feature.setdefault("properties", {})
        vid = props.get("village_id") or feature.get("id")
        if "elevation_m" not in props:
            v_data = spatial_service.get_village(vid) if vid else None
            props["elevation_m"] = v_data["static_features"]["elevation_m"] if v_data and "static_features" in v_data else 100.0
        adv = advisory_service.get_advisory_for_village(vid) if vid else None
        if adv and "advisory" in adv:
            props["risk_level"] = adv["advisory"].get("risk_level", "low")
            weather_code = adv.get("weather_inferred", "normal")
            category_map = {
                "frost_risk": "frost",
                "high_temp_dry": "heat",
                "rain_24h": "rain",
                "heavy_rain": "rain",
                "high_wind": "rain",
            }
            props["risk_category"] = category_map.get(weather_code, "none")
        else:
            props["risk_level"] = "low"
            props["risk_category"] = "none"

    return geojson


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
