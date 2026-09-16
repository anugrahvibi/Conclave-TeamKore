"""
Live Weather Ingestion Service for Kerala Agro-Climatic Block Stations.
Connects to Open-Meteo Forecast API with batch multi-location fetching,
in-memory TTL caching, thread-safety, and offline fallback resilience.
"""

import json
import logging
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from backend.app.config import settings

logger = logging.getLogger("backend.live_weather_service")

# Ensure IPv4 resolution to prevent IPv6 routing stalls on Linux
orig_getaddrinfo = socket.getaddrinfo


def _getaddrinfo_ipv4(host, port, family=0, type=0, proto=0, flags=0):
    return orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)


socket.getaddrinfo = _getaddrinfo_ipv4


class LiveWeatherService:
    def __init__(self):
        self._cached_df: Optional[pd.DataFrame] = None
        self._last_fetched_at: Optional[float] = None
        self._data_source: str = "INITIALIZING"
        self._last_error: Optional[str] = None
        self._lock = threading.Lock()

    def get_status(self) -> Dict[str, Any]:
        """Returns the current operational status of the weather ingestion pipeline."""
        now = time.time()
        ttl = settings.WEATHER_CACHE_TTL_SECONDS
        
        if self._last_fetched_at is not None:
            age = round(now - self._last_fetched_at, 1)
            ttl_remaining = max(0.0, round(ttl - age, 1))
            last_updated_iso = datetime.fromtimestamp(
                self._last_fetched_at, tz=timezone.utc
            ).isoformat()
        else:
            age = None
            ttl_remaining = 0.0
            last_updated_iso = None

        from backend.app.services.data_service import KERALA_BLOCK_STATIONS

        return {
            "status": "healthy",
            "data_source": self._data_source,
            "is_live": self._data_source == "LIVE_OPEN_METEO",
            "last_updated": last_updated_iso,
            "cache_age_seconds": age,
            "cache_ttl_seconds": ttl,
            "ttl_remaining_seconds": ttl_remaining,
            "station_count": len(KERALA_BLOCK_STATIONS),
            "step_hours": settings.WEATHER_STEP_HOURS,
            "api_key_configured": bool(settings.OPEN_METEO_API_KEY),
            "last_error": self._last_error,
        }

    def fetch_live_block_forecasts(self, timeout_sec: int = 15) -> pd.DataFrame:
        """
        Executes a single batch HTTP GET request to Open-Meteo Forecast API
        for all 31 Kerala Agro-Climatic Block Stations.
        """
        from backend.app.services.data_service import KERALA_BLOCK_STATIONS

        block_list = list(KERALA_BLOCK_STATIONS.items())
        lats = [str(info["lat"]) for _, info in block_list]
        lons = [str(info["lon"]) for _, info in block_list]

        lat_param = ",".join(lats)
        lon_param = ",".join(lons)

        base_url = "https://api.open-meteo.com/v1/forecast"
        if settings.OPEN_METEO_API_KEY:
            base_url = "https://customer-api.open-meteo.com/v1/forecast"

        query_params = {
            "latitude": lat_param,
            "longitude": lon_param,
            "hourly": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
            "forecast_days": "3",
        }
        if settings.OPEN_METEO_API_KEY:
            query_params["apikey"] = settings.OPEN_METEO_API_KEY

        url = f"{base_url}?{urllib.parse.urlencode(query_params)}"

        logger.info(f"Fetching real-time weather from Open-Meteo for {len(block_list)} block stations...")
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Kerala-Agro-Platform/1.0 (Live-Weather-Ingestion)"}
        )

        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        if isinstance(data, dict):
            # Single station response wrapped to list
            data = [data]

        if len(data) != len(block_list):
            raise ValueError(
                f"Expected {len(block_list)} station responses from Open-Meteo, received {len(data)}"
            )

        step_hours = max(1, settings.WEATHER_STEP_HOURS)
        records = []

        for (bid, binfo), station_data in zip(block_list, data):
            hourly = station_data.get("hourly", {})
            times = hourly.get("time", [])
            temps = hourly.get("temperature_2m", [])
            humids = hourly.get("relative_humidity_2m", [])
            rains = hourly.get("precipitation", [])
            winds = hourly.get("wind_speed_10m", [])

            lat = binfo["lat"]
            lon = binfo["lon"]
            bname = binfo["name"]
            district = binfo["district"]

            for step in range(0, len(times), step_hours):
                ts_clean = times[step].replace("T", " ")
                if len(ts_clean) == 16:
                    ts_clean += ":00"

                records.append({
                    "block_id": bid,
                    "block_name": bname,
                    "district": district,
                    "timestamp": ts_clean,
                    "temp": round(float(temps[step]), 2),
                    "rainfall": max(0.0, round(float(rains[step]), 2)),
                    "humidity": min(100.0, max(0.0, round(float(humids[step]), 2))),
                    "wind": max(0.0, round(float(winds[step]), 2)),
                    "lat": lat,
                    "lon": lon,
                })

        df = pd.DataFrame(records)
        logger.info(f"Successfully ingested {len(df)} live forecast records across {len(block_list)} stations.")
        return df

    def get_forecast_dataframe(self, force_refresh: bool = False) -> pd.DataFrame:
        """
        Thread-safe retrieval of block forecast DataFrame.
        Uses cached data if within TTL, else fetches live from Open-Meteo.
        Automatically falls back to local baseline CSV on any network/API failure.
        """
        with self._lock:
            now = time.time()
            cache_valid = (
                self._cached_df is not None
                and self._last_fetched_at is not None
                and (now - self._last_fetched_at) < settings.WEATHER_CACHE_TTL_SECONDS
            )

            if cache_valid and not force_refresh:
                return self._cached_df

            # Attempt live fetch if enabled
            if settings.USE_LIVE_WEATHER:
                try:
                    df = self.fetch_live_block_forecasts()
                    self._cached_df = df
                    self._last_fetched_at = now
                    self._data_source = "LIVE_OPEN_METEO"
                    self._last_error = None
                    return df
                except Exception as exc:
                    err_msg = f"Failed to fetch live weather from Open-Meteo: {exc}"
                    logger.warning(f"{err_msg}. Falling back to baseline dataset.")
                    self._last_error = str(exc)

            # Fallback path: load baseline CSV
            if self._cached_df is not None and not force_refresh:
                # Keep previously loaded cache if available
                return self._cached_df

            if settings.BLOCK_FORECAST_CSV.exists():
                logger.info(f"Loading fallback baseline from {settings.BLOCK_FORECAST_CSV}")
                df = pd.read_csv(settings.BLOCK_FORECAST_CSV)
                from backend.app.services.data_service import KERALA_BLOCK_STATIONS
                
                df["block_name"] = df["block_id"].apply(
                    lambda bid: KERALA_BLOCK_STATIONS.get(bid, {}).get("name", bid)
                )
                df["district"] = df["block_id"].apply(
                    lambda bid: KERALA_BLOCK_STATIONS.get(bid, {}).get("district", "Kerala")
                )
                self._cached_df = df
                self._last_fetched_at = now
                self._data_source = "FALLBACK_HISTORICAL"
                return df
            else:
                raise FileNotFoundError(
                    f"Neither live weather nor fallback CSV available at {settings.BLOCK_FORECAST_CSV}"
                )


live_weather_service = LiveWeatherService()
