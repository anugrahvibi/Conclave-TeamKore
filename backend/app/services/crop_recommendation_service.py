"""
Crop Recommendation Service for village-level agro-advisory platform.
Evaluates 3-day weather forecasts and micro-topographic static features
against agronomic suitability rules for major Kerala crops.
Includes soil pH and texture evaluation from pre-fetched SoilGrids data.
"""

import csv
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

MIN_SUITABILITY_THRESHOLD = 0.40

# Potential rule file locations
SEARCH_PATHS = [
    Path(__file__).resolve().parent.parent.parent / "artifacts" / "crop_suitability_rules.json",
    Path(__file__).resolve().parent / "crop_suitability_rules.json",
    Path.cwd() / "backend" / "artifacts" / "crop_suitability_rules.json",
    Path.cwd() / "crop_suitability_rules.json",
]


def classify_soil_texture(clay_pct: float, sand_pct: float) -> str:
    """
    Classifies soil texture into USDA standard textural classes based on clay% and sand%.
    Silt% is calculated as 100 - (clay + sand).
    """
    clay = max(0.0, min(100.0, clay_pct))
    sand = max(0.0, min(100.0, sand_pct))
    silt = max(0.0, 100.0 - (clay + sand))

    if clay >= 40.0:
        if sand >= 45.0:
            return "sandy_clay"
        elif silt >= 40.0:
            return "silty_clay"
        else:
            return "clay"
    elif clay >= 27.0:
        if sand >= 45.0:
            return "sandy_clay_loam"
        elif sand <= 20.0:
            return "silty_clay_loam"
        else:
            return "clay_loam"
    elif clay >= 20.0:
        if sand >= 45.0:
            return "sandy_clay_loam"
        else:
            return "loam"
    else:  # clay < 20.0
        if sand >= 85.0:
            return "sand"
        elif sand >= 70.0:
            return "loamy_sand"
        elif sand >= 50.0:
            return "sandy_loam"
        elif silt >= 80.0:
            return "silt"
        elif silt >= 50.0:
            return "silt_loam"
        else:
            return "loam"


class CropRecommendationEngine:
    def __init__(self, rules_path: Optional[str] = None, soil_csv_path: Optional[str] = None):
        self.rules: Dict[str, Dict[str, Any]] = {}
        self.rules_path = rules_path
        self.soil_csv_path = soil_csv_path
        self.soil_data: Dict[str, Dict[str, Any]] = {}
        self._load_rules()
        self._load_soil_data()

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
                    "ph_range": [5.5, 7.5],
                    "suitable_soil_texture": ["clay", "clay_loam", "silty_clay", "loam"],
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
                    "ph_range": [5.5, 7.5],
                    "suitable_soil_texture": ["loam", "sandy_loam", "clay_loam", "silt_loam"],
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
                    "ph_range": [5.2, 8.0],
                    "suitable_soil_texture": ["sandy_loam", "sand", "loamy_sand", "loam", "lateritic"],
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
                    "ph_range": [5.5, 6.5],
                    "suitable_soil_texture": ["sandy_loam", "loam", "loamy_sand"],
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
                    "ph_range": [6.0, 7.5],
                    "suitable_soil_texture": ["loam", "sandy_loam", "clay_loam", "silt_loam"],
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
                    "ph_range": [4.5, 6.5],
                    "suitable_soil_texture": ["sandy_loam", "loam", "clay_loam", "lateritic"],
                    "season": ["Year-round tapping", "Monsoon planting"],
                    "notes": "Thrives on warm humid slopes and lateritic foothill plantations with heavy rainfall."
                }
            }

    def _load_soil_data(self):
        """Loads pre-fetched village soil data CSV at service startup (cached in memory)."""
        soil_path = None
        if self.soil_csv_path and Path(self.soil_csv_path).exists():
            soil_path = Path(self.soil_csv_path)
        else:
            candidates = [
                Path(__file__).resolve().parent.parent.parent.parent / "data" / "village_soil_data.csv",
                Path.cwd() / "data" / "village_soil_data.csv",
                Path(__file__).resolve().parent.parent.parent / "artifacts" / "village_soil_data.csv",
            ]
            for c in candidates:
                if c.exists():
                    soil_path = c
                    break

        if soil_path and soil_path.exists():
            try:
                with open(soil_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        vid = row.get("village_id")
                        if not vid:
                            continue
                        try:
                            self.soil_data[vid.strip()] = {
                                "ph": float(row["ph"]) if row.get("ph") else None,
                                "clay_pct": float(row["clay_pct"]) if row.get("clay_pct") else None,
                                "sand_pct": float(row["sand_pct"]) if row.get("sand_pct") else None,
                                "organic_carbon": float(row["organic_carbon"]) if row.get("organic_carbon") else None,
                            }
                        except (ValueError, TypeError):
                            pass
                logger.info(f"Loaded soil cache for {len(self.soil_data)} villages from {soil_path}.")
            except Exception as e:
                logger.warning(f"Could not load soil data at startup ({e}); proceeding without soil cache.")

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

    def _extract_soil(
        self,
        village_static_features: Optional[Dict[str, Any]]
    ) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
        """
        Extracts (ph, clay_pct, sand_pct, organic_carbon) from static features dict,
        falling back to startup cached soil data if village_id is present.
        """
        if not village_static_features:
            return None, None, None, None

        ph = village_static_features.get("ph", village_static_features.get("soil_ph"))
        clay = village_static_features.get("clay_pct", village_static_features.get("clay"))
        sand = village_static_features.get("sand_pct", village_static_features.get("sand"))
        oc = village_static_features.get("organic_carbon", village_static_features.get("soc"))

        # Check village_id lookup from startup cache if values missing
        if (ph is None or clay is None or sand is None) and "village_id" in village_static_features:
            vid = str(village_static_features["village_id"]).strip()
            cached = self.soil_data.get(vid)
            if cached:
                if ph is None:
                    ph = cached.get("ph")
                if clay is None:
                    clay = cached.get("clay_pct")
                if sand is None:
                    sand = cached.get("sand_pct")
                if oc is None:
                    oc = cached.get("organic_carbon")

        if ph is not None and clay is not None and sand is not None:
            try:
                ph_f = float(ph)
                clay_f = float(clay)
                sand_f = float(sand)
                oc_f = float(oc) if oc is not None and str(oc).strip() != "" else None
                return ph_f, clay_f, sand_f, oc_f
            except (ValueError, TypeError):
                return None, None, None, None

        return None, None, None, None

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

    def _score_soil(
        self,
        ph: float,
        clay_pct: float,
        sand_pct: float,
        ph_range: List[float],
        suitable_textures: List[str]
    ) -> Tuple[float, str, str]:
        """
        Scores soil suitability based on pH tolerance and soil texture classification.
        Returns: (soil_score [0.0 - 1.0], note_str, texture_str)
        """
        texture = classify_soil_texture(clay_pct, sand_pct)

        # 1. pH evaluation
        ph_min, ph_max = ph_range[0], ph_range[1]
        if ph_min <= ph <= ph_max:
            s_ph = 1.0
            ph_note = f"optimal soil pH ({ph:.1f})"
        else:
            diff = ph_min - ph if ph < ph_min else ph - ph_max
            s_ph = max(0.0, 1.0 - (diff / 1.5))
            if ph < ph_min:
                ph_note = f"acidic soil pH ({ph:.1f} below min {ph_min:.1f})"
            else:
                ph_note = f"alkaline soil pH ({ph:.1f} above max {ph_max:.1f})"

        # 2. Texture evaluation
        clean_suitable = [t.strip().lower().replace(" ", "_") for t in suitable_textures]
        if texture in clean_suitable:
            s_tex = 1.0
            tex_note = f"ideal {texture.replace('_', ' ')} texture"
        elif any(sub in texture or texture in sub for sub in clean_suitable):
            s_tex = 0.85
            tex_note = f"compatible {texture.replace('_', ' ')} texture"
        elif "loam" in texture and any("loam" in t for t in clean_suitable):
            s_tex = 0.75
            tex_note = f"acceptable {texture.replace('_', ' ')} texture"
        else:
            s_tex = 0.40
            tex_note = f"suboptimal {texture.replace('_', ' ')} texture"

        soil_score = 0.5 * s_ph + 0.5 * s_tex
        soil_note = f"{ph_note} and {tex_note}"
        return round(soil_score, 2), soil_note, texture

    def evaluate(
        self,
        village_forecast: Optional[Dict[str, Any]],
        village_static_features: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Evaluates and ranks crops for given forecast and static features.
        If soil data is available, incorporates soil matching as an additional weighted factor.
        If soil data is missing, logs a warning and falls back to scoring without soil.
        """
        temp, rain, humidity, wind = self._extract_weather(village_forecast)
        elev, land_cover, dist_to_water = self._extract_static(village_static_features)
        ph, clay_pct, sand_pct, oc = self._extract_soil(village_static_features)

        if ph is None or clay_pct is None or sand_pct is None:
            logger.debug("Village has no soil data; falling back to scoring without soil factor.")

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

            if ph is not None and clay_pct is not None and sand_pct is not None:
                ph_range = crop_rule.get("ph_range", [5.0, 7.5])
                suitable_textures = crop_rule.get("suitable_soil_texture", ["loam", "sandy_loam", "clay"])
                s_soil, s_soil_note, soil_tex = self._score_soil(ph, clay_pct, sand_pct, ph_range, suitable_textures)

                # Soil match added as an ADDITIONAL weighted factor (temp 30%, rain 30%, land 15%, elev 10%, soil 15%)
                raw_score = 0.30 * s_temp + 0.30 * s_rain + 0.15 * s_land + 0.10 * s_elev + 0.15 * s_soil
                soil_factor_text = f" with {s_soil_note} (pH {ph:.1f}, clay {clay_pct:.0f}%, sand {sand_pct:.0f}%)"
            else:
                # Fallback to existing 4-term scoring without soil factor
                raw_score = 0.35 * s_temp + 0.35 * s_rain + 0.20 * s_land + 0.10 * s_elev
                soil_factor_text = ""

            score = round(max(0.0, min(1.0, raw_score)), 2)

            if score >= 0.75:
                confidence = "high"
                explanation = f"Highly suitable: {s_temp_note} and {s_rain_note} on {s_land_note}{soil_factor_text}. {notes}"
            elif score >= 0.50:
                confidence = "medium"
                explanation = f"Moderately suitable: {s_temp_note}, {s_rain_note}, with {s_land_note}{soil_factor_text}. {notes}"
            else:
                confidence = "low"
                explanation = f"Suboptimal conditions: {s_temp_note}, {s_rain_note}, and {s_land_note}{soil_factor_text}. {notes}"

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

    def get_available_crops(self) -> List[Dict[str, Any]]:
        """Returns metadata list of all supported crops."""
        aliases_map = {
            "rice": ["paddy", "nellu", "rice paddy", "virippu", "mundakan"],
            "banana": ["nendran", "plantain", "ethakka", "banana plantain"],
            "coconut": ["thengu", "keram", "coconut palm"],
            "tapioca": ["cassava", "kappa", "maravalli", "yucca"],
            "vegetables": ["veg", "seasonal vegetables", "horticulture", "pachakkari"],
            "rubber": ["hevea", "rubber plantation", "latex"],
        }
        crops_list = []
        for key, rule in self.rules.items():
            crop_name = rule.get("crop_name", key)
            crops_list.append({
                "id": crop_name,
                "name": rule.get("display_name", crop_name.capitalize()),
                "aliases": aliases_map.get(crop_name, []),
                "optimal_temp_c": rule.get("optimal_temp_c", [22.0, 32.0]),
                "optimal_rainfall_mm": rule.get("optimal_rainfall_mm", [20.0, 80.0]),
                "max_elevation_m": rule.get("max_elevation_m", 1200.0),
                "season": rule.get("season", []),
                "notes": rule.get("notes", "")
            })
        return crops_list

    def resolve_crop_id(self, query: str) -> Optional[str]:
        """Resolves crop alias or name to canonical crop ID."""
        q = query.strip().lower()
        if q in self.rules:
            return q
        for crop_id, rule in self.rules.items():
            display = rule.get("display_name", "").lower()
            if q == display or q in display:
                return crop_id
        alias_map = {
            "paddy": "rice", "nellu": "rice", "rice": "rice",
            "nendran": "banana", "plantain": "banana", "banana": "banana", "ethakka": "banana",
            "coconut": "coconut", "thengu": "coconut", "keram": "coconut",
            "tapioca": "tapioca", "cassava": "tapioca", "kappa": "tapioca",
            "vegetables": "vegetables", "vegetable": "vegetables", "veg": "vegetables",
            "rubber": "rubber", "hevea": "rubber"
        }
        return alias_map.get(q)


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

