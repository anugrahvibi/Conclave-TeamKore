"""
Forecast Service: Connects spatial IDW interpolation with ML correction model
to generate downscaled 3-day village forecasts.
"""

from typing import Any, Dict, List, Optional, Tuple
import logging
import time
import numpy as np
import pandas as pd

from backend.app.config import settings
from backend.app.services.data_service import data_service
from backend.app.services.spatial_service import spatial_service, haversine_km
from mldev2.correction_and_advisory import WeatherCorrectionAndAdvisory

logger = logging.getLogger("backend.forecast_service")


class ForecastService:
    def __init__(self):
        self.pipeline: Optional[WeatherCorrectionAndAdvisory] = None
        self.df_blocks: Optional[pd.DataFrame] = None
        self.timestamps: List[str] = []
        self._forecast_cache: Dict[str, Dict[str, Any]] = {}
        self._initialize()
        self._precompute_all_villages_async()

    def _precompute_all_villages_async(self):
        """Warms the forecast cache for all villages in a background thread.

        Uses the batched ML predict so each village costs ~15ms instead of
        ~400ms, making the whole state computable in seconds without blocking
        startup or request handling.
        """
        import threading

        def _warm():
            try:
                t0 = time.perf_counter()
                for vid in list(spatial_service.villages.keys()):
                    self.get_forecast_for_village(vid)
                print(
                    f"Precomputed forecasts for {len(self._forecast_cache)} villages "
                    f"in {time.perf_counter() - t0:.1f}s"
                )
            except Exception as e:
                print(f"Forecast precompute failed (will compute on demand): {e}")

        threading.Thread(target=_warm, daemon=True).start()

    def _initialize(self):
        """Loads ML correction model and pre-caches block weather observations."""
        model_path = str(settings.MODEL_PATH) if settings.MODEL_PATH.exists() else None
        rules_path = str(settings.RULES_PATH) if settings.RULES_PATH.exists() else None

        self.pipeline = WeatherCorrectionAndAdvisory(
            model_path=model_path,
            rules_path=rules_path
        )

        if settings.BLOCK_FORECAST_CSV.exists():
            self.df_blocks = pd.read_csv(settings.BLOCK_FORECAST_CSV)
            self.timestamps = sorted(self.df_blocks["timestamp"].unique().tolist())
        else:
            raise FileNotFoundError(f"Block forecast CSV not found at {settings.BLOCK_FORECAST_CSV}")

    def get_forecast_for_village(self, identifier: str) -> Optional[Dict[str, Any]]:
        """
        Computes downscaled 3-day weather forecast for a village or panchayat.
        """
        village = spatial_service.get_village(identifier)
        if not village:
            return None

        # Serve from cache when available (warmed at startup / on first compute)
        vid = village["village_id"]
        cached = self._forecast_cache.get(vid)
        if cached is not None:
            return cached

        v_lat = village["lat"]
        v_lon = village["lon"]
        static_features = village["static_features"]

        forecast_steps = []
        temps, rains, humids, winds = [], [], [], []

        # First pass: IDW interpolation for every timestep
        idw_results = []
        for ts in self.timestamps:
            ts_df = self.df_blocks[self.df_blocks["timestamp"] == ts]
            
            # Vectorized IDW across stations
            station_lats = ts_df["lat"].values
            station_lons = ts_df["lon"].values
            
            # Haversine distance
            dists = np.array([
                haversine_km(v_lat, v_lon, slat, slon)
                for slat, slon in zip(station_lats, station_lons)
            ])

            # Exact match check
            zero_mask = dists < 1e-4
            if np.any(zero_mask):
                idx = np.where(zero_mask)[0][0]
                interp = ts_df[["temp", "rainfall", "humidity", "wind"]].values[idx]
            else:
                k = min(settings.IDW_K_NEAREST, len(dists))
                k_idx = np.argsort(dists)[:k]
                k_dists = dists[k_idx]
                weights = 1.0 / (k_dists ** settings.IDW_POWER)
                weights /= np.sum(weights)
                vals = ts_df[["temp", "rainfall", "humidity", "wind"]].values[k_idx]
                interp = np.dot(weights, vals)

            idw_results.append((ts, ts_df, interp))

        # Second pass: ONE batched ML predict for all timesteps (~15ms vs ~350ms
        # for 12 individual sklearn calls; identical math, row-independent).
        if self.pipeline and self.pipeline.correction_model.is_trained:
            block_forecasts = [
                {"temp_c": float(i[2][0]), "rain_mm": max(0.0, float(i[2][1])), "humidity_pct": float(np.clip(i[2][2], 0.0, 100.0))}
                for i in idw_results
            ]
            static_feat_input = {
                "elevation_m": static_features["elevation_m"],
                "dist_to_water_km": static_features["dist_to_water_km"],
                "land_cover": static_features.get("land_cover", "agriculture")
            }
            deltas = self.pipeline.correction_model.predict_batch(block_forecasts, static_feat_input)
        else:
            deltas = [0.0] * len(idw_results)

        # Third pass: assemble steps with corrected values
        for (ts, ts_df, interp), correction_delta in zip(idw_results, deltas):
            base_temp = float(interp[0])
            base_rain = max(0.0, float(interp[1]))
            base_humid = float(np.clip(interp[2], 0.0, 100.0))
            base_wind = max(0.0, float(interp[3]))

            corrected_temp = round(base_temp + correction_delta, 2)
            final_rain = round(base_rain, 2)
            final_humid = round(base_humid, 1)
            final_wind = round(base_wind, 1)

            # Weather condition text
            if final_rain > 15.0:
                condition = "Heavy Rain"
            elif final_rain > 2.0:
                condition = "Moderate Rain"
            elif final_rain > 0.1:
                condition = "Light Rain"
            elif corrected_temp > 32.0:
                condition = "Hot & Sunny"
            elif final_humid > 85.0:
                condition = "Humid & Overcast"
            else:
                condition = "Partly Cloudy"

            step = {
                "timestamp": ts,
                "baseline_temp_c": round(base_temp, 2),
                "correction_delta_c": round(correction_delta, 2),
                "temp_c": corrected_temp,
                "baseline_rainfall_mm": round(base_rain, 2),
                "rainfall_mm": final_rain,
                "baseline_humidity_pct": round(base_humid, 1),
                "humidity_pct": final_humid,
                "baseline_wind_kmh": round(base_wind, 1),
                "wind_kmh": final_wind,
                "weather_condition": condition
            }
            forecast_steps.append(step)

            temps.append(corrected_temp)
            rains.append(final_rain)
            humids.append(final_humid)
            winds.append(final_wind)

        summary = {
            "min_temp_c": round(float(np.min(temps)), 2),
            "max_temp_c": round(float(np.max(temps)), 2),
            "avg_temp_c": round(float(np.mean(temps)), 2),
            "total_rainfall_mm": round(float(np.sum(rains)), 2),
            "avg_humidity_pct": round(float(np.mean(humids)), 1),
            "max_wind_kmh": round(float(np.max(winds)), 1)
        }

        nearest_block_info = {
            "block_id": village["nearest_block_id"],
            "name": village["nearest_block_name"],
            "district": village["district"],
            "distance_km": village["nearest_block_dist_km"]
        }

        result = {
            "village_id": vid,
            "panchayat_id": village["panchayat_id"],
            "village_name": village["name"],
            "village_name_ml": village["name_ml"],
            "nearest_block": nearest_block_info,
            "static_features": static_features,
            "summary": summary,
            "forecast_steps": forecast_steps
        }
        self._forecast_cache[vid] = result
        return result


forecast_service = ForecastService()
