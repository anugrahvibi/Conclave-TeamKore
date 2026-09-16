"""
Integration test suite for the Backend API.
Tests all 4 PRD endpoints + health check + performance benchmark.
"""

import time
try:
    import pytest
except ImportError:
    pytest = None
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_health_endpoint():
    """Verify /health returns 200 and indicates models & spatial index are ready."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["loaded_villages"] == 1031
    assert data["loaded_blocks"] == 31
    assert data["model_trained"] is True
    assert data["features_count"] == 6


def test_model_info_endpoint():
    """Verify /model/info returns 6-feature architecture and farmer impact metadata."""
    response = client.get("/model/info")
    assert response.status_code == 200
    data = response.json()
    assert data["n_features"] == 6
    assert len(data["features"]) == 6
    assert "elevation" in data["features"]
    assert "land_cover" in data["features"]
    assert len(data["feature_importances"]) == 6
    # Top features should be elevation and dist_to_water
    top_feat = data["feature_importances"][0]["feature"]
    assert top_feat in ["elevation", "dist_to_water"]
    assert "farmer_impact" in data["feature_importances"][0]


def test_get_villages_geojson():
    """Verify /villages returns valid GeoJSON FeatureCollection with authentic boundaries."""
    response = client.get("/villages?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 10

    # Inspect first feature
    first = data["features"][0]
    assert "geometry" in first
    assert first["geometry"]["type"] in ["Polygon", "MultiPolygon"]
    assert "properties" in first
    props = first["properties"]
    assert "village_id" in props
    assert "panchayat_id" in props
    assert "name" in props
    assert "centroid" in props
    assert "elevation_m" in props


def test_get_villages_filtered_json():
    """Verify filtering villages by district and json format."""
    response = client.get("/villages?district=Kasargod&format=json")
    assert response.status_code == 200
    data = response.json()
    assert "villages" in data
    assert len(data["villages"]) > 0
    for v in data["villages"]:
        assert v["district"] == "Kasargod"


def test_forecast_by_panchayat_id():
    """Verify /forecast/{panchayat_id} returns 3-day downscaled forecast."""
    response = client.get("/forecast/KL_PANCH_0001")
    assert response.status_code == 200
    data = response.json()
    assert data["panchayat_id"] == "KL_PANCH_0001"
    assert data["village_id"] == "VIL_0001"
    assert "nearest_block" in data
    assert "summary" in data
    assert "forecast_steps" in data
    
    # 12 timesteps = 3 days (6-hour intervals)
    steps = data["forecast_steps"]
    assert len(steps) == 12
    first_step = steps[0]
    assert "temp_c" in first_step
    assert "baseline_temp_c" in first_step
    assert "correction_delta_c" in first_step
    assert "rainfall_mm" in first_step
    assert "humidity_pct" in first_step
    assert "wind_kmh" in first_step
    assert "weather_condition" in first_step


def test_forecast_by_village_id_and_name():
    """Verify /forecast resolves by village_id or name."""
    r_id = client.get("/forecast/VIL_0001")
    assert r_id.status_code == 200

    r_name = client.get("/forecast/Vorkady")
    assert r_name.status_code == 200
    assert r_name.json()["village_id"] == "VIL_0001"


def test_forecast_404():
    """Verify 404 for invalid village ID."""
    response = client.get("/forecast/INVALID_VIL_9999")
    assert response.status_code == 404


def test_post_forecast_contract():
    """Verify POST /forecast handles the exact ML Dev #2 contract payload."""
    payload = {
        "village_id": 42,
        "block_forecast": {"temp_c": 25.5, "rain_mm": 22.0, "humidity_pct": 72},
        "static_features": {"elevation_m": 250, "dist_to_water_km": 3.5, "land_cover": "agriculture"},
        "crop_stage": "spraying_window"
    }
    response = client.post("/forecast", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["village_id"] == 42
    assert "corrected_temp_c" in data
    assert "correction_delta" in data
    assert "weather_inferred" in data
    assert data["weather_inferred"] == "rain_24h"
    assert "advisory" in data
    assert "text" in data["advisory"]
    assert data["advisory"]["confidence"] == "high"


def test_post_forecast_out_of_range_validation():
    """Verify that physically impossible values (e.g. temp=120C) trigger validation errors."""
    payload = {
        "village_id": 42,
        "block_forecast": {"temp_c": 120.0, "rain_mm": 10.0, "humidity_pct": 50.0},
        "crop_stage": "spraying_window"
    }
    response = client.post("/forecast", json=payload)
    assert response.status_code == 422  # Pydantic validation rejection


def test_post_forecast_omitted_static_features_fallback():
    """Verify that omitted static features safely use defaults without crashing."""
    payload = {
        "village_id": "VIL_TEST",
        "block_forecast": {"temp_c": 26.0, "rain_mm": 0.0, "humidity_pct": 60.0},
        "crop_stage": "flowering"
    }
    response = client.post("/forecast", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "corrected_temp_c" in data
    assert "correction_delta" in data
    assert data["weather_inferred"] in ["normal", "no_rain_7d"]


def test_advisory_mature_stage():
    """Verify new rule matching for mature crop stage under normal weather."""
    response = client.get("/advisory/KL_PANCH_0001?crop_stage=mature")
    assert response.status_code == 200
    data = response.json()
    assert data["crop_stage"] == "mature"
    assert "advisory" in data


def test_advisory_endpoint():
    """Verify /advisory/{panchayat_id} returns advisory text, risk level, confidence."""
    response = client.get("/advisory/KL_PANCH_0001?crop_stage=spraying_window")
    assert response.status_code == 200
    data = response.json()
    assert data["village_id"] == "VIL_0001"
    assert "current_weather" in data
    assert "advisory" in data

    adv = data["advisory"]
    assert "text" in adv
    assert adv["confidence"] in ["high", "medium", "low"]
    assert adv["risk_level"] in ["low", "medium", "high", "critical"]
    assert isinstance(adv["actionable_recommendations"], list)
    assert len(adv["actionable_recommendations"]) > 0


def test_block_summary_endpoint():
    """Verify /block/{block_id}/summary returns dashboard aggregation."""
    response = client.get("/block/BLK_KSD_KAN/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["block_id"] == "BLK_KSD_KAN"
    assert "block_name" in data
    assert "district" in data
    assert data["total_villages"] > 0
    assert "aggregated_weather" in data
    assert "risk_distribution" in data
    assert "severe_alerts_count" in data
    assert "villages" in data
    assert len(data["villages"]) == data["total_villages"]


def test_block_summary_404():
    """Verify 404 for non-existent block ID."""
    response = client.get("/block/NON_EXISTENT_BLOCK/summary")
    assert response.status_code == 404


def test_full_chain_latency_under_one_second():
    """
    PRD Success Criterion: Full request chain (village lookup -> forecast -> advisory)
    must resolve in well under a second (< 1000ms).
    """
    t0 = time.time()
    # 1. Village lookup
    r_vil = client.get("/villages?search=Vorkady&format=json")
    assert r_vil.status_code == 200
    vid = r_vil.json()["villages"][0]["village_id"]

    # 2. Downscaled Forecast
    r_fc = client.get(f"/forecast/{vid}")
    assert r_fc.status_code == 200

    # 3. Agro-Advisory
    r_adv = client.get(f"/advisory/{vid}?crop_stage=spraying_window")
    assert r_adv.status_code == 200

    elapsed_ms = (time.time() - t0) * 1000
    print(f"\n⚡ Total chain latency: {elapsed_ms:.2f} ms")
    assert elapsed_ms < 500  # Stricter than 1000ms PRD target!
