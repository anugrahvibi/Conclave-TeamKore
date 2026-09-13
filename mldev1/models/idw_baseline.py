"""
Phase 1: Inverse Distance Weighting (IDW) Baseline Model
Provides spatial downscaling from block forecast points to village centroids.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple

def haversine_distance(lat1: float, lon1: float, lat2: np.ndarray, lon2: np.ndarray) -> np.ndarray:
    """
    Compute great circle distance between a single point (lat1, lon1)
    and an array of points (lat2, lon2) in kilometers using the Haversine formula.
    """
    R = 6371.0  # Earth radius in kilometers
    phi1 = np.radians(lat1)
    phi2 = np.radians(lat2)
    delta_phi = np.radians(lat2 - lat1)
    delta_lambda = np.radians(lon2 - lon1)

    a = np.sin(delta_phi / 2.0) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(delta_lambda / 2.0) ** 2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))
    return R * c

def idw_interpolate(
    target_lat: float,
    target_lon: float,
    source_lats: np.ndarray,
    source_lons: np.ndarray,
    source_values: np.ndarray,
    power: float = 2.0,
    k_nearest: int = 4
) -> float:
    """
    Calculates Inverse Distance Weighted interpolation value.

    Args:
        target_lat: Target point latitude
        target_lon: Target point longitude
        source_lats: Array of source latitudes
        source_lons: Array of source longitudes
        source_values: Array of source variable values
        power: IDW power parameter (default: 2.0)
        k_nearest: Limit to k nearest neighbor points (default: 4)

    Returns:
        Interpolated float estimate
    """
    distances = haversine_distance(target_lat, target_lon, source_lats, source_lons)

    # Check for exact spatial co-location (distance = 0)
    zero_idx = np.where(distances < 1e-5)[0]
    if len(zero_idx) > 0:
        return float(source_values[zero_idx[0]])

    # Select k nearest neighbors
    if len(distances) > k_nearest:
        nearest_indices = np.argpartition(distances, k_nearest)[:k_nearest]
        # Sort the nearest k points
        nearest_indices = nearest_indices[np.argsort(distances[nearest_indices])]
    else:
        nearest_indices = np.argsort(distances)

    k_distances = distances[nearest_indices]
    k_values = source_values[nearest_indices]

    weights = 1.0 / (k_distances ** power)
    weighted_value = np.sum(weights * k_values) / np.sum(weights)

    return float(weighted_value)


class IDWBaselineModel:
    """
    IDW Baseline Model Manager
    Loads block forecasts and village centroids to provide downscaled predictions.
    """
    def __init__(
        self,
        block_forecast_path: str = "mldev1/data/block_forecast.csv",
        village_centroids_path: str = "mldev1/data/village_centroids.csv",
        power: float = 2.0
    ):
        self.power = power
        self.df_blocks = pd.read_csv(block_forecast_path)
        self.df_villages = pd.read_csv(village_centroids_path)

        # Index villages by village_id for fast lookup
        self.village_map = self.df_villages.set_index("village_id").to_dict("index")

    def predict_point(
        self,
        lat: float,
        lon: float,
        timestamp: str,
        variable: str,
        k_nearest: int = 4
    ) -> float:
        """Predict variable for an arbitrary lat/lon coordinate at a specific timestamp."""
        ts_blocks = self.df_blocks[self.df_blocks["timestamp"] == timestamp]
        if ts_blocks.empty:
            raise ValueError(f"Timestamp {timestamp} not found in block forecast data.")

        lats = ts_blocks["lat"].values
        lons = ts_blocks["lon"].values
        values = ts_blocks[variable].values

        return idw_interpolate(lat, lon, lats, lons, values, power=self.power, k_nearest=k_nearest)

    def idw_predict(
        self,
        village_id: str,
        variable: str,
        timestamp: Optional[str] = None,
        k_nearest: int = 4
    ) -> float:
        """
        PRD-specified function wrapper:
        def idw_predict(village_id, variable, k_nearest=4) -> float

        If timestamp is None, evaluates on the latest available forecast timestamp.
        """
        if village_id not in self.village_map:
            raise KeyError(f"village_id '{village_id}' not found in village centroids.")

        v_coord = self.village_map[village_id]
        lat, lon = v_coord["lat"], v_coord["lon"]

        if timestamp is None:
            # Default to first/latest available timestamp
            timestamp = self.df_blocks["timestamp"].iloc[0]

        return self.predict_point(lat, lon, timestamp, variable, k_nearest=k_nearest)

    def generate_all_baseline_predictions(
        self,
        output_path: str = "mldev1/outputs/baseline_predictions.csv",
        k_nearest: int = 4
    ) -> pd.DataFrame:
        """
        Generates full baseline prediction table across all villages and timestamps.
        Output columns: village_id, timestamp, temp_pred, rainfall_pred, humidity_pred, wind_pred
        """
        timestamps = self.df_blocks["timestamp"].unique()
        records = []

        variables = ["temp", "rainfall", "humidity", "wind"]

        print(f"Generating IDW predictions for {len(self.df_villages)} villages across {len(timestamps)} timestamps...")
        for ts in timestamps:
            ts_blocks = self.df_blocks[self.df_blocks["timestamp"] == ts]
            s_lats = ts_blocks["lat"].values
            s_lons = ts_blocks["lon"].values

            var_values = {var: ts_blocks[var].values for var in variables}

            for _, v_row in self.df_villages.iterrows():
                vid = v_row["village_id"]
                v_lat = v_row["lat"]
                v_lon = v_row["lon"]

                preds = {}
                for var in variables:
                    val = idw_interpolate(
                        v_lat, v_lon, s_lats, s_lons, var_values[var],
                        power=self.power, k_nearest=k_nearest
                    )
                    # Physical bounds clipping
                    if var == "rainfall":
                        val = max(0.0, val)
                    elif var == "humidity":
                        val = np.clip(val, 0.0, 100.0)
                    elif var == "wind":
                        val = max(0.0, val)

                    preds[f"{var}_pred"] = round(val, 2)

                records.append({
                    "village_id": vid,
                    "timestamp": ts,
                    **preds
                })

        df_preds = pd.DataFrame(records)
        df_preds.to_csv(output_path, index=False)
        print(f"Baseline predictions saved to {output_path} ({len(df_preds)} rows).")
        return df_preds

# Global convenience instance / function matching the exact PRD signature:
# def idw_predict(village_id, variable, k_nearest=4) -> float
_DEFAULT_MODEL = None

def get_default_model():
    global _DEFAULT_MODEL
    if _DEFAULT_MODEL is None:
        _DEFAULT_MODEL = IDWBaselineModel()
    return _DEFAULT_MODEL

def idw_predict(village_id: str, variable: str, k_nearest: int = 4) -> float:
    """Wrapper matching PRD signature def idw_predict(village_id, variable, k_nearest=4) -> float"""
    model = get_default_model()
    return model.idw_predict(village_id, variable, k_nearest=k_nearest)

if __name__ == "__main__":
    model = IDWBaselineModel()
    sample_vil = model.df_villages.iloc[0]["village_id"]
    test_temp = idw_predict(sample_vil, "temp")
    print(f"Sample test: {sample_vil} temp_pred = {test_temp}°C")
    model.generate_all_baseline_predictions()
