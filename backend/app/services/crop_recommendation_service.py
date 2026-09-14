"""
Crop Recommendation Service for village-level agro-advisory platform.
Evaluates 3-day weather forecasts and micro-topographic static features
against agronomic suitability rules for major Kerala crops.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

MIN_SUITABILITY_THRESHOLD = 0.40

# Potential rule file locations
SEARCH_PATHS = [
    Path(__file__).resolve().parent.parent.parent / "artifacts" / "crop_suitability_rules.json",
    Path(__file__).resolve().parent / "crop_suitability_rules.json",
    Path.cwd() / "backend" / "artifacts" / "crop_suitability_rules.json",
    Path.cwd() / "crop_suitability_rules.json",
]


class CropRecommendationEngine:
    def __init__(self, rules_path: Optional[str] = None):
        self.rules: Dict[str, Dict[str, Any]] = {}
        self.rules_path = rules_path
        self._load_rules()

    def _load_rules(self):
        """Loads crop suitability rules from JSON artifact."""
        loaded_path = None
        if self.rules_path and Path(self.rules_path).exists():
            loaded_path = Path(self.rules_path)
        else:
            for p in SEARCH_PATHS:
                if p.exists():
                    loaded_path = p
                    break

        if loaded_path and loaded_path.exists():
            with open(loaded_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "crops" in data:
                self.rules = data["crops"]
            elif isinstance(data, dict):
                self.rules = data
            elif isinstance(data, list):
                self.rules = {item.get("crop_name", f"crop_{i}"): item for i, item in enumerate(data)}
        else:
            # Fallback embedded default rules if file is missing
            self.rules = {
                "rice": {
                    "crop_name": "rice",
                    "display_name": "Rice (Paddy)",
                    "temp_range_c": [20.0, 38.0],
                    "optimal_temp_c": [24.0, 32.0],
                    "rainfall_range_mm": [20.0, 180.0],
                    "optimal_rainfall_mm": [40.0, 120.0],
                    "suitable_land_cover_types": ["agriculture", "wetland", "mixed_agroforestry", "paddy_field", "alluvial_plain"],
                    "max_elevation_m": 800.0,
                    "season": ["Virippu", "Mundakan", "Puncha"],
                    "notes": "Thrives in warm humid conditions with high water availability and lowland alluvial soils."
                },
                "banana": {
                    "crop_name": "banana",
                    "display_name": "Banana (Nendran / Plantain)",
                    "temp_range_c": [16.0, 38.0],
                    "optimal_temp_c": [22.0, 32.0],
                    "rainfall_range_mm": [10.0, 90.0],
                    "optimal_rainfall_mm": [20.0, 60.0],
                    "suitable_land_cover_types": ["agriculture", "mixed_agroforestry", "homestead", "alluvial_plain", "river_valley"],
                    "max_elevation_m": 1200.0,
                    "season": ["Year-round", "Nendran (Aug-Sep)"],
                    "notes": "Requires warm tropical conditions with steady soil moisture and well-drained loam."
                },
                "coconut": {
                    "crop_name": "coconut",
                    "display_name": "Coconut",
                    "temp_range_c": [20.0, 36.0],
                    "optimal_temp_c": [25.0, 32.0],
                    "rainfall_range_mm": [5.0, 85.0],
                    "optimal_rainfall_mm": [15.0, 50.0],
                    "suitable_land_cover_types": ["coastal", "mixed_agroforestry", "agriculture", "homestead", "sandy_loam"],
                    "max_elevation_m": 600.0,
                    "season": ["Year-round"],
                    "notes": "Ideal for coastal and midland belts with high humidity and well-drained sandy loam/lateritic soils."
                },
                "tapioca": {
                    "crop_name": "tapioca",
                    "display_name": "Tapioca (Cassava)",
                    "temp_range_c": [20.0, 40.0],
                    "optimal_temp_c": [25.0, 35.0],
                    "rainfall_range_mm": [0.0, 60.0],
                    "optimal_rainfall_mm": [5.0, 35.0],
                    "suitable_land_cover_types": ["agriculture", "laterite_upland", "mixed_agroforestry", "slopes", "dryland"],
                    "max_elevation_m": 1000.0,
                    "season": ["Main crop (Apr-May)", "Second crop (Sep-Oct)"],
                    "notes": "Drought-hardy tuber crop well-suited to undulating laterite midlands; intolerant of waterlogging."
                },
                "vegetables": {
                    "crop_name": "vegetables",
                    "display_name": "Vegetables (Generic / Seasonal)",
                    "temp_range_c": [18.0, 34.0],
                    "optimal_temp_c": [22.0, 30.0],
                    "rainfall_range_mm": [2.0, 45.0],
                    "optimal_rainfall_mm": [5.0, 25.0],
                    "suitable_land_cover_types": ["homestead", "agriculture", "mixed_agroforestry", "alluvial_plain", "riverbed"],
                    "max_elevation_m": 1500.0,
                    "season": ["Onattukara / Summer", "Post-monsoon", "Pre-monsoon"],
                    "notes": "Requires mild to warm temperatures and well-drained fertile loam; vulnerable to rot during torrential rains."
                },
                "rubber": {
                    "crop_name": "rubber",
                    "display_name": "Rubber (Hevea brasiliensis)",
                    "temp_range_c": [20.0, 34.0],
                    "optimal_temp_c": [23.0, 30.0],
                    "rainfall_range_mm": [20.0, 140.0],
                    "optimal_rainfall_mm": [35.0, 90.0],
                    "suitable_land_cover_types": ["plantation", "forest_fringe", "hills_and_slopes", "mixed_agroforestry", "agriculture"],
                    "max_elevation_m": 650.0,
                    "season": ["Year-round tapping", "Monsoon planting"],
                    "notes": "Thrives on warm humid slopes and lateritic foothill plantations with heavy rainfall."
                }
            }

    def _extract_weather(self, village_forecast: Optional[Dict[str, Any]]) -> Tuple[float, float, float, float]:
        """Extracts (temp_c, rainfall_mm, humidity_pct, wind_kmh) from forecast dict."""
        if not village_forecast:
            return 27.0, 25.0, 75.0, 12.0

        # Handle nested summary
        summary = village_forecast.get("summary", {})
        temp = summary.get("avg_temp_c")
        rain = summary.get("total_rainfall_mm")
        humidity = summary.get("avg_humidity_pct")
        wind = summary.get("max_wind_kmh")

        # Handle flat structure or direct keys
        if temp is None:
            temp = village_forecast.get("temp_c", village_forecast.get("temp", 27.0))
        if rain is None:
            rain = village_forecast.get("rainfall_mm", village_forecast.get("rainfall", 25.0))
        if humidity is None:
            humidity = village_forecast.get("humidity_pct", village_forecast.get("humidity", 75.0))
        if wind is None:
            wind = village_forecast.get("wind_kmh", village_forecast.get("wind", 12.0))

        # Handle forecast_steps aggregation if present
        steps = village_forecast.get("forecast_steps")
        if steps and isinstance(steps, list) and len(steps) > 0:
            if temp is None or (temp == 27.0 and "temp_c" not in village_forecast and "avg_temp_c" not in summary):
                temp = sum(s.get("temp_c", 27.0) for s in steps) / len(steps)
            if rain is None or (rain == 25.0 and "rainfall_mm" not in village_forecast and "total_rainfall_mm" not in summary):
                rain = sum(s.get("rainfall_mm", 0.0) for s in steps)
            if humidity is None:
                humidity = sum(s.get("humidity_pct", 75.0) for s in steps) / len(steps)
            if wind is None:
                wind = max((s.get("wind_kmh", 10.0) for s in steps), default=12.0)

        return float(temp), float(rain), float(humidity), float(wind)

    def _extract_static(self, village_static_features: Optional[Dict[str, Any]]) -> Tuple[float, str, float]:
        """Extracts (elevation_m, land_cover, dist_to_water_km)."""
        if not village_static_features:
            return 100.0, "agriculture", 5.0

        elev = village_static_features.get("elevation_m", village_static_features.get("elevation", 100.0))
        land_cover = str(village_static_features.get("land_cover", village_static_features.get("land_cover_type", "agriculture")))
        dist_to_water = village_static_features.get("dist_to_water_km", village_static_features.get("distance_to_water_km", 5.0))

        return float(elev), land_cover, float(dist_to_water)

    def _score_temperature(self, temp: float, temp_range: List[float], optimal_range: List[float]) -> Tuple[float, str]:
        t_min, t_max = temp_range[0], temp_range[1]
        o_min, o_max = optimal_range[0], optimal_range[1]

        if o_min <= temp <= o_max:
            return 1.0, f"optimal temperature ({temp:.1f}°C)"
        elif t_min <= temp <= t_max:
            if temp < o_min:
                score = 0.75 + 0.25 * ((temp - t_min) / max(0.1, o_min - t_min))
                return score, f"acceptable temperature ({temp:.1f}°C)"
            else:
                score = 0.75 + 0.25 * ((t_max - temp) / max(0.1, t_max - o_max))
                return score, f"acceptable temperature ({temp:.1f}°C)"
        else:
            if temp < t_min:
                diff = t_min - temp
                score = max(0.0, 0.70 - (diff / 10.0) * 0.70)
                return score, f"temperature ({temp:.1f}°C) below crop minimum ({t_min:.1f}°C)"
            else:
                diff = temp - t_max
                score = max(0.0, 0.70 - (diff / 10.0) * 0.70)
                return score, f"temperature ({temp:.1f}°C) exceeds crop tolerance ({t_max:.1f}°C)"

    def _score_rainfall(self, rain: float, rain_range: List[float], optimal_range: List[float]) -> Tuple[float, str]:
        r_min, r_max = rain_range[0], rain_range[1]
        ro_min, ro_max = optimal_range[0], optimal_range[1]

        if ro_min <= rain <= ro_max:
            return 1.0, f"optimal 3-day rainfall ({rain:.1f}mm)"
        elif r_min <= rain <= r_max:
            if rain < ro_min:
                score = 0.75 + 0.25 * ((rain - r_min) / max(0.1, ro_min - r_min))
                return score, f"adequate rainfall ({rain:.1f}mm)"
            else:
                score = 0.75 + 0.25 * ((r_max - rain) / max(0.1, r_max - ro_max))
                return score, f"heavy rainfall ({rain:.1f}mm)"
        else:
            if rain < r_min:
                diff = r_min - rain
                score = max(0.0, 0.70 - (diff / 30.0) * 0.70)
                return score, f"insufficient rainfall ({rain:.1f}mm vs min {r_min:.1f}mm)"
            else:
                diff = rain - r_max
                score = max(0.0, 0.70 - (diff / 60.0) * 0.70)
                return score, f"excess rainfall ({rain:.1f}mm vs max {r_max:.1f}mm)"

    def _score_land_cover(self, land_cover: str, suitable_types: List[str]) -> Tuple[float, str]:
        clean_lc = land_cover.strip().lower().replace(" ", "_")
        clean_suitable = [s.strip().lower().replace(" ", "_") for s in suitable_types]

        if clean_lc in clean_suitable:
            return 1.0, f"ideal land cover '{land_cover}'"
        elif any(sub in clean_lc or clean_lc in sub for sub in clean_suitable):
            return 0.85, f"compatible land cover '{land_cover}'"
        elif clean_lc in ["agriculture", "mixed_agroforestry", "homestead", "plantation"]:
            return 0.75, f"agricultural land cover '{land_cover}'"
        elif clean_lc in ["urban", "water", "water_body", "barren", "rock", "builtup", "industrial", "mining"]:
            return 0.05, f"unfavorable non-cultivable land cover '{land_cover}'"
        else:
            return 0.50, f"marginal land cover '{land_cover}'"

    def _score_elevation(self, elev: float, max_elev: float) -> Tuple[float, str]:
        if elev <= max_elev:
            return 1.0, f"suitable elevation ({elev:.0f}m)"
        else:
            diff = elev - max_elev
            score = max(0.0, 1.0 - (diff / 800.0))
            return score, f"high elevation ({elev:.0f}m exceeds {max_elev:.0f}m limit)"

    def evaluate(
        self,
        village_forecast: Optional[Dict[str, Any]],
        village_static_features: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Evaluates and ranks crops for given forecast and static features.
        """
        temp, rain, humidity, wind = self._extract_weather(village_forecast)
        elev, land_cover, dist_to_water = self._extract_static(village_static_features)

        scored_crops = []

        for crop_key, crop_rule in self.rules.items():
            crop_name = crop_rule.get("crop_name", crop_key)
            temp_range = crop_rule.get("temp_range_c", [15.0, 40.0])
            optimal_temp = crop_rule.get("optimal_temp_c", temp_range)
            rain_range = crop_rule.get("rainfall_range_mm", [0.0, 200.0])
            optimal_rain = crop_rule.get("optimal_rainfall_mm", rain_range)
            suitable_lc = crop_rule.get("suitable_land_cover_types", ["agriculture"])
            max_elev = crop_rule.get("max_elevation_m", 1500.0)
            notes = crop_rule.get("notes", "")

            s_temp, s_temp_note = self._score_temperature(temp, temp_range, optimal_temp)
            s_rain, s_rain_note = self._score_rainfall(rain, rain_range, optimal_rain)
            s_land, s_land_note = self._score_land_cover(land_cover, suitable_lc)
            s_elev, s_elev_note = self._score_elevation(elev, max_elev)

            # Combined weighted score
            raw_score = 0.35 * s_temp + 0.35 * s_rain + 0.20 * s_land + 0.10 * s_elev
            score = round(max(0.0, min(1.0, raw_score)), 2)

            if score >= 0.75:
                confidence = "high"
                explanation = f"Highly suitable: {s_temp_note} and {s_rain_note} on {s_land_note}. {notes}"
            elif score >= 0.50:
                confidence = "medium"
                explanation = f"Moderately suitable: {s_temp_note}, {s_rain_note}, with {s_land_note}. {notes}"
            else:
                confidence = "low"
                explanation = f"Suboptimal conditions: {s_temp_note}, {s_rain_note}, and {s_land_note}. {notes}"

            scored_crops.append({
                "crop": crop_name,
                "suitability_score": score,
                "confidence": confidence,
                "explanation": explanation
            })

        # Rank crops descending by suitability_score
        scored_crops.sort(key=lambda x: x["suitability_score"], reverse=True)

        # Filter by threshold
        suitable_list = [c for c in scored_crops if c["suitability_score"] >= MIN_SUITABILITY_THRESHOLD]

        # Low-confidence fallback if no crop meets threshold
        if not suitable_list:
            top_match = scored_crops[0]
            top_match["confidence"] = "low"
            return [top_match]

        return suitable_list


# Singleton instance
crop_recommendation_engine = CropRecommendationEngine()


def recommend_crops(
    village_forecast: Optional[Dict[str, Any]],
    village_static_features: Optional[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Public entrypoint for crop recommendations.
    Matches current village forecast and static features against ICAR/Kerala crop rules.
    """
    return crop_recommendation_engine.evaluate(village_forecast, village_static_features)
