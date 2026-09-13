"""
Pydantic schemas for the Backend API.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ============================================================================
# Village Schemas
# ============================================================================

class Coordinates(BaseModel):
    lat: float
    lon: float

class StaticFeatures(BaseModel):
    elevation_m: float
    dist_to_water_km: float
    land_cover: Optional[str] = "mixed_agroforestry"

class VillageBasic(BaseModel):
    village_id: str
    panchayat_id: str
    name: str
    name_ml: Optional[str] = None
    district: Optional[str] = None
    nearest_block_id: Optional[str] = None
    centroid: Coordinates

class VillageDetail(VillageBasic):
    static_features: StaticFeatures
    geometry: Optional[Dict[str, Any]] = None  # GeoJSON Geometry polygon/multipolygon

class GeoJSONFeature(BaseModel):
    type: str = "Feature"
    id: str
    properties: Dict[str, Any]
    geometry: Optional[Dict[str, Any]] = None

class GeoJSONFeatureCollection(BaseModel):
    type: str = "FeatureCollection"
    total_features: int
    features: List[GeoJSONFeature]


# ============================================================================
# Forecast Schemas
# ============================================================================

class ForecastStep(BaseModel):
    timestamp: str
    baseline_temp_c: float
    correction_delta_c: float
    temp_c: float
    baseline_rainfall_mm: float
    rainfall_mm: float
    baseline_humidity_pct: float
    humidity_pct: float
    baseline_wind_kmh: float
    wind_kmh: float
    weather_condition: str

class ForecastSummary(BaseModel):
    min_temp_c: float
    max_temp_c: float
    avg_temp_c: float
    total_rainfall_mm: float
    avg_humidity_pct: float
    max_wind_kmh: float

class ForecastResponse(BaseModel):
    village_id: str
    panchayat_id: str
    village_name: str
    village_name_ml: Optional[str] = None
    nearest_block: Dict[str, Any]
    static_features: StaticFeatures
    summary: ForecastSummary
    forecast_steps: List[ForecastStep]


# ============================================================================
# Advisory Schemas
# ============================================================================

class AdvisoryDetail(BaseModel):
    text: str
    confidence: str = Field(description="'high', 'medium', or 'low'")
    matched_rule: Optional[str] = None
    risk_level: str = Field(description="'low', 'medium', 'high', or 'critical'")
    actionable_recommendations: List[str]

class AdvisoryResponse(BaseModel):
    village_id: str
    panchayat_id: str
    village_name: str
    crop_stage: str
    weather_inferred: str
    current_weather: Dict[str, float]
    advisory: AdvisoryDetail


# ============================================================================
# Block Summary Schemas
# ============================================================================

class RiskDistribution(BaseModel):
    low: int
    medium: int
    high: int
    critical: int

class BlockVillageOverview(BaseModel):
    village_id: str
    panchayat_id: str
    name: str
    temp_c: float
    rainfall_mm: float
    risk_level: str
    advisory_summary: str

class BlockSummaryResponse(BaseModel):
    block_id: str
    block_name: str
    district: str
    center: Coordinates
    total_villages: int
    aggregated_weather: ForecastSummary
    risk_distribution: RiskDistribution
    severe_alerts_count: int
    villages: List[BlockVillageOverview]


# ============================================================================
# System / Health Schemas
# ============================================================================

class HealthResponse(BaseModel):
    status: str
    version: str
    loaded_villages: int
    loaded_blocks: int
    model_trained: bool
    spatial_engine: str
