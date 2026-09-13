"""
Forecast Service: Connects spatial IDW interpolation with ML correction model
to generate downscaled 3-day village forecasts.
"""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from backend.app.config import settings
from backend.app.services.data_service import data_service
from backend.app.services.spatial_service import spatial_service, haversine_km
from mldev2.correction_and_advisory import WeatherCorrectionAndAdvisory


class ForecastService:
    def __init__(self):
        self.pipeline: Optional[WeatherCorrectionAndAdvisory] = None
        self.df_blocks: Optional[pd.DataFrame] = None
        self.timestamps: List[str] = []
        self._initialize()

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

        v_lat = village["lat"]
        v_lon = village["lon"]
        static_features = village["static_features"]

        forecast_steps = []
        temps, rains, humids, winds = [], [], [], []

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

            base_temp = float(interp[0])
            base_rain = max(0.0, float(interp[1]))
            base_humid = float(np.clip(interp[2], 0.0, 100.0))
            base_wind = max(0.0, float(interp[3]))

            # Call ML correction model
            block_forecast_input = {
                "temp_c": base_temp,
                "rain_mm": base_rain,
                "humidity_pct": base_humid
            }
            static_feat_input = {
                "elevation_m": static_features["elevation_m"],
                "dist_to_water_km": static_features["dist_to_water_km"],
                "land_cover": static_features.get("land_cover", "agriculture")
            }

            if self.pipeline and self.pipeline.correction_model.is_trained:
                correction_delta = self.pipeline.correction_model.predict(
                    block_forecast_input,
                    static_feat_input
                )
            else:
                correction_delta = 0.0

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

        return {
            "village_id": village["village_id"],
            "panchayat_id": village["panchayat_id"],
            "village_name": village["name"],
            "village_name_ml": village["name_ml"],
            "nearest_block": nearest_block_info,
            "static_features": static_features,
            "summary": summary,
            "forecast_steps": forecast_steps
        }


forecast_service = ForecastService()
