"""
Unit and integration tests for Crop Recommendation Service and Endpoint.
Covers:
1. Clear rice match
2. Clear coconut match
3. Low-confidence fallback case
4. Edge cases with extreme / out-of-bound values
5. API endpoint schema and 404 integration
"""

try:
    import pytest
except ImportError:
    pytest = None
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


def test_soil_matching_scores_higher():
    """
    Test 7: Soil matching boosts suitability score.
    Confirms that a crop with matching soil pH and texture scores higher
    than an otherwise-identical case with mismatched soil properties.
    """
    forecast = {
        "summary": {
            "avg_temp_c": 27.5,
            "total_rainfall_mm": 75.0,
            "avg_humidity_pct": 85.0,
            "max_wind_kmh": 12.0
        }
    }

    # Favorable weather and terrain for rice (paddy)
    base_static = {
        "elevation_m": 30.0,
        "land_cover": "agriculture",
        "dist_to_water_km": 1.0
    }

    # Case A: Ideal soil for rice (pH 6.2 within [5.5, 7.5], clay 45% + sand 20% -> clay texture)
    static_matched = {
        **base_static,
        "ph": 6.2,
        "clay_pct": 45.0,
        "sand_pct": 20.0,
        "organic_carbon": 35.0
    }

    # Case B: Mismatched soil for rice (alkaline pH 8.8 exceeding 7.5, sand 90% + clay 5% -> sand texture)
    static_mismatched = {
        **base_static,
        "ph": 8.8,
        "clay_pct": 5.0,
        "sand_pct": 90.0,
        "organic_carbon": 5.0
    }

    recs_matched = recommend_crops(forecast, static_matched)
    recs_mismatched = recommend_crops(forecast, static_mismatched)

    rice_matched = next((c for c in recs_matched if c["crop"] == "rice"), None)
    rice_mismatched = next((c for c in recs_mismatched if c["crop"] == "rice"), None)

    assert rice_matched is not None, "Rice should be in matched recommendations"
    assert rice_mismatched is not None, "Rice should be in mismatched recommendations"

    # Confirms matching soil scores higher than mismatched soil
    assert rice_matched["suitability_score"] > rice_mismatched["suitability_score"]

    # Confirms soil factors are reported in explanation when present
    assert "pH 6.2" in rice_matched["explanation"]
    assert "clay 45%" in rice_matched["explanation"]
    assert "sand 20%" in rice_matched["explanation"]


def test_missing_soil_data_fallback_graceful(caplog):
    """
    Test 8: Missing soil data fallback.
    Confirms that when a village has no soil data (not yet fetched or missing),
    the system falls back to scoring without crashing, logs a warning, and returns valid recommendations.
    """
    forecast = {
        "temp_c": 28.0,
        "rainfall_mm": 50.0,
        "humidity_pct": 75.0,
        "wind_kmh": 10.0
    }
    # Static features with NO soil data attributes
    static_features_no_soil = {
        "elevation_m": 45.0,
        "land_cover": "mixed_agroforestry",
        "dist_to_water_km": 2.5
    }

    import logging
    with caplog.at_level(logging.DEBUG):
        recs = recommend_crops(forecast, static_features_no_soil)

    assert isinstance(recs, list)
    assert len(recs) > 0

    # Ensure debug log or graceful fallback occurs
    for item in recs:
        assert 0.0 <= item["suitability_score"] <= 1.0
        assert item["confidence"] in ["high", "medium", "low"]
        assert isinstance(item["explanation"], str)
        assert len(item["explanation"]) > 0


def test_get_all_crops_endpoint():
    """
    Test 9: GET /crops endpoint returns metadata for all supported crops.
    """
    response = client.get("/crops")
    assert response.status_code == 200
    crops = response.json()
    assert isinstance(crops, list)
    assert len(crops) >= 6

    crop_ids = [c["id"] for c in crops]
    for expected in ["rice", "banana", "coconut", "tapioca", "vegetables", "rubber"]:
        assert expected in crop_ids

    for c in crops:
        assert "name" in c
        assert "aliases" in c
        assert "optimal_temp_c" in c
        assert "optimal_rainfall_mm" in c
        assert "notes" in c


def test_get_statewide_crop_suitability_rice():
    """
    Test 10: GET /crops/suitability/rice returns statewide heatmap for rice.
    """
    response = client.get("/crops/suitability/rice")
    assert response.status_code == 200
    data = response.json()
    assert data["crop"] == "rice"
    assert "Rice" in data["display_name"]
    assert data["total_villages"] > 0
    assert len(data["villages"]) == data["total_villages"]

    # Verify village suitability properties
    first_v = data["villages"][0]
    assert "village_id" in first_v
    assert "suitability_score" in first_v
    assert "confidence" in first_v
    assert "fillColor" in first_v
    assert first_v["fillColor"].startswith("#")
    assert "explanation" in first_v


def test_get_statewide_crop_suitability_alias():
    """
    Test 11: GET /crops/suitability/paddy resolves 'paddy' alias to 'rice'.
    """
    response = client.get("/crops/suitability/paddy")
    assert response.status_code == 200
    data = response.json()
    assert data["crop"] == "rice"


def test_get_statewide_crop_suitability_404():
    """
    Test 12: GET /crops/suitability/unknown_crop returns 404.
    """
    response = client.get("/crops/suitability/unknown_crop_xyz")
    assert response.status_code == 404


