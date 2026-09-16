"""
Unit and Integration Tests for Live Weather Ingestion Pipeline (Open-Meteo API).
"""

import pytest
from fastapi.testclient import TestClient
import pandas as pd
from unittest.mock import patch, MagicMock

from backend.app.main import app
from backend.app.services.live_weather_service import LiveWeatherService, live_weather_service
from backend.app.services.forecast_service import forecast_service
from backend.app.services.data_service import data_service, KERALA_BLOCK_STATIONS
from backend.app.config import settings

client = TestClient(app)


def test_weather_status_endpoint():
    """Verify /weather/status returns proper structure and fields."""
    response = client.get("/weather/status")
    assert response.status_code == 200
    data = response.json()
    assert "data_source" in data
    assert "is_live" in data
    assert "station_count" in data
    assert data["station_count"] == len(KERALA_BLOCK_STATIONS)
    assert "cache_ttl_seconds" in data
    assert "ttl_remaining_seconds" in data


def test_health_endpoint_includes_weather_source():
    """Verify /health endpoint reports weather source."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "weather_source" in data
    assert "is_live_weather" in data


def test_live_weather_service_fallback_on_error():
    """Verify LiveWeatherService falls back to historical CSV when network fails."""
    svc = LiveWeatherService()
    
    # Mock network error on fetch_live_block_forecasts
    with patch.object(svc, "fetch_live_block_forecasts", side_effect=Exception("Network timeout simulation")):
        df = svc.get_forecast_dataframe(force_refresh=True)
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        assert svc._data_source == "FALLBACK_HISTORICAL"
        assert "Network timeout simulation" in (svc._last_error or "")


def test_live_weather_caching():
    """Verify LiveWeatherService respects TTL caching without redundant network calls."""
    svc = LiveWeatherService()
    
    mock_df = pd.DataFrame([{
        "block_id": "BLK_TVM_NED",
        "block_name": "Nedumangad",
        "district": "Thiruvananthapuram",
        "timestamp": "2026-09-16 00:00:00",
        "temp": 28.5,
        "rainfall": 0.0,
        "humidity": 75.0,
        "wind": 10.0,
        "lat": 8.601,
        "lon": 76.998
    }])
    
    with patch.object(svc, "fetch_live_block_forecasts", return_value=mock_df) as mock_fetch:
        # First call: triggers fetch
        df1 = svc.get_forecast_dataframe(force_refresh=False)
        assert mock_fetch.call_count == 1
        
        # Second call within TTL: uses cache, does NOT call fetch again
        df2 = svc.get_forecast_dataframe(force_refresh=False)
        assert mock_fetch.call_count == 1
        assert len(df2) == 1
        
        # Third call with force_refresh=True: triggers fetch again
        df3 = svc.get_forecast_dataframe(force_refresh=True)
        assert mock_fetch.call_count == 2


def test_forecast_downscaling_with_live_service():
    """Verify forecast downscaling runs seamlessly with live weather data."""
    # Test sample village
    forecast = forecast_service.get_forecast_for_village("KL_PANCH_0001")
    assert forecast is not None
    assert "village_id" in forecast
    assert "forecast_steps" in forecast
    assert len(forecast["forecast_steps"]) > 0
    
    step0 = forecast["forecast_steps"][0]
    assert "temp_c" in step0
    assert "baseline_temp_c" in step0
    assert "correction_delta_c" in step0
    assert "rainfall_mm" in step0
    assert "humidity_pct" in step0
    assert "weather_condition" in step0


def test_weather_refresh_endpoint():
    """Verify POST /weather/refresh endpoint execution."""
    response = client.post("/weather/refresh")
    assert response.status_code == 200
    data = response.json()
    assert "data_source" in data
    assert data["station_count"] == 31
