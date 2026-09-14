"""
Unit and integration tests for Crop Recommendation Service and Endpoint.
Covers:
1. Clear rice match
2. Clear coconut match
3. Low-confidence fallback case
4. Edge cases with extreme / out-of-bound values
5. API endpoint schema and 404 integration
"""

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from backend.app.main import app
from backend.app.api.crop_routes import crop_router
from backend.app.services.crop_recommendation_service import recommend_crops, CropRecommendationEngine


# Mount crop_router onto app for endpoint testing (non-destructive isolated mount)
if not any(getattr(r, "path", "") == "/recommend-crop/{panchayat_id}" for r in app.routes):
    app.include_router(crop_router)

client = TestClient(app)


def test_rice_recommendation_clear_match():
    """
    Test 1: Clear rice match under warm tropical, high-moisture lowland conditions.
    Expects 'rice' to be top-ranked with confidence 'high' and score >= 0.85.
    """
    forecast = {
        "summary": {
            "avg_temp_c": 27.5,
            "total_rainfall_mm": 75.0,
            "avg_humidity_pct": 85.0,
            "max_wind_kmh": 12.0
        }
    }
    static_features = {
        "elevation_m": 30.0,
        "land_cover": "wetland",
        "dist_to_water_km": 1.2
    }

    recs = recommend_crops(forecast, static_features)

    assert isinstance(recs, list)
    assert len(recs) > 0

    top_crop = recs[0]
    assert top_crop["crop"] == "rice"
    assert top_crop["suitability_score"] >= 0.85
    assert top_crop["confidence"] == "high"
    assert "explanation" in top_crop
    assert len(top_crop["explanation"]) > 10


def test_coconut_recommendation_clear_match():
    """
    Test 2: Clear coconut match under coastal warm humid conditions with moderate rain.
    Expects 'coconut' to be top-ranked with confidence 'high' and score >= 0.85.
    """
    forecast = {
        "temp_c": 28.5,
        "rainfall_mm": 25.0,
        "humidity_pct": 82.0,
        "wind_kmh": 14.0
    }
    static_features = {
        "elevation_m": 10.0,
        "land_cover": "coastal",
        "dist_to_water_km": 0.4
    }

    recs = recommend_crops(forecast, static_features)

    assert isinstance(recs, list)
    assert len(recs) > 0

    top_crop = recs[0]
    assert top_crop["crop"] == "coconut"
    assert top_crop["suitability_score"] >= 0.85
    assert top_crop["confidence"] == "high"
    assert "explanation" in top_crop


def test_low_confidence_fallback():
    """
    Test 3: Low-confidence fallback when weather and terrain are hostile to all standard crops
    (severe cold frost, zero rainfall, high alpine altitude, barren terrain).
    Expects exactly 1 crop returned with confidence 'low' and score < 0.40.
    """
    forecast = {
        "temp_c": 2.0,
        "rainfall_mm": 0.0,
        "humidity_pct": 15.0,
        "wind_kmh": 45.0
    }
    static_features = {
        "elevation_m": 3500.0,
        "land_cover": "barren",
        "dist_to_water_km": 60.0
    }

    recs = recommend_crops(forecast, static_features)

    assert isinstance(recs, list)
    assert len(recs) == 1, "Fallback must return single closest match"

    fallback_crop = recs[0]
    assert fallback_crop["confidence"] == "low"
    assert fallback_crop["suitability_score"] < 0.40
    assert "explanation" in fallback_crop


def test_edge_case_extreme_values():
    """
    Test 4: Edge case with extreme, out-of-bounds, or abnormal values.
    Verifies that the service does not raise uncaught exceptions and bounds all scores in [0.0, 1.0].
    """
    forecast = {
        "temp_c": 62.0,
        "rainfall_mm": 2500.0,
        "humidity_pct": 180.0,
        "wind_kmh": -25.0
    }
    static_features = {
        "elevation_m": 8848.0,
        "land_cover": "unmapped_volcanic_crater",
        "dist_to_water_km": -10.0
    }

    recs = recommend_crops(forecast, static_features)

    assert isinstance(recs, list)
    assert len(recs) >= 1
    for item in recs:
        assert 0.0 <= item["suitability_score"] <= 1.0
        assert item["confidence"] in ["high", "medium", "low"]
        assert isinstance(item["explanation"], str)


def test_recommend_crop_endpoint_valid_panchayat():
    """
    Test 5: Integration test for GET /recommend-crop/{panchayat_id}.
    Verifies 200 response with correct schema.
    """
    response = client.get("/recommend-crop/KL_PANCH_0001")
    assert response.status_code == 200

    data = response.json()
    assert "panchayat_id" in data
    assert data["panchayat_id"] == "KL_PANCH_0001"
    assert "recommendations" in data
    assert isinstance(data["recommendations"], list)
    assert len(data["recommendations"]) > 0

    first = data["recommendations"][0]
    assert "crop" in first
    assert "suitability_score" in first
    assert "confidence" in first
    assert "explanation" in first
    assert 0.0 <= first["suitability_score"] <= 1.0


def test_recommend_crop_endpoint_404_not_found():
    """
    Test 6: Integration test for non-existent village/panchayat.
    """
    response = client.get("/recommend-crop/NON_EXISTENT_PANCHAYAT_99999")
    assert response.status_code == 404
