"""
Advisory Service: Evaluates agro-climatic conditions and delivers risk-rated advisory guidance.
"""

from typing import Any, Dict, List, Optional
from backend.app.config import settings
from backend.app.services.spatial_service import spatial_service
from backend.app.services.forecast_service import forecast_service
from mldev2.correction_and_advisory import AgroAdvisoryEngine


VALID_CROP_STAGES = [
    "seedling",
    "young_seedling",
    "vegetative",
    "spraying_window",
    "flowering",
    "pod_formation",
    "mature"
]


class AdvisoryService:
    def __init__(self):
        rules_path = str(settings.RULES_PATH) if settings.RULES_PATH.exists() else None
        self.engine = AgroAdvisoryEngine(rules_path=rules_path)

    def get_advisory_for_village(
        self,
        identifier: str,
        crop_stage: str = "spraying_window"
    ) -> Optional[Dict[str, Any]]:
        """
        Generates current agro-advisory, risk rating, and actionable recommendations for a village.
        """
        village = spatial_service.get_village(identifier)
        if not village:
            return None

        forecast_data = forecast_service.get_forecast_for_village(identifier)
        if not forecast_data or not forecast_data.get("forecast_steps"):
            return None

        # Normalize crop stage
        stage = crop_stage.strip().lower()
        if stage not in VALID_CROP_STAGES:
            stage = "spraying_window"

        # Evaluate weather condition across the next 24-48 hours
        steps = forecast_data["forecast_steps"]
        next_24h_steps = steps[:4]  # 4 steps * 6h = 24 hours
        total_24h_rain = sum(s["rainfall_mm"] for s in next_24h_steps)
        max_temp_24h = max(s["temp_c"] for s in next_24h_steps)
        avg_humid_24h = sum(s["humidity_pct"] for s in next_24h_steps) / len(next_24h_steps)
        max_wind_24h = max(s["wind_kmh"] for s in next_24h_steps)

        # Immediate current step
        curr_step = steps[0]
        current_weather = {
            "temp_c": curr_step["temp_c"],
            "rainfall_mm": curr_step["rainfall_mm"],
            "humidity_pct": curr_step["humidity_pct"],
            "wind_kmh": curr_step["wind_kmh"],
            "rain_next_24h_mm": round(total_24h_rain, 2)
        }

        # Weather condition inference
        if total_24h_rain >= 35.0 or curr_step["rainfall_mm"] >= 25.0:
            weather_code = "heavy_rain"
        elif total_24h_rain >= 15.0 or curr_step["rainfall_mm"] >= 10.0:
            weather_code = "rain_24h"
        elif total_24h_rain <= 1.0 and forecast_data["summary"]["total_rainfall_mm"] <= 3.0:
            weather_code = "no_rain_7d"
        elif max_temp_24h < 5.0:
            weather_code = "frost_risk"
        elif max_temp_24h >= 32.0 and avg_humid_24h <= 55.0:
            weather_code = "high_temp_dry"
        elif max_wind_24h >= 18.0:
            weather_code = "high_wind"
        else:
            weather_code = "normal"

        # Query rule engine
        rule_result = self.engine.get_advisory(weather_code, stage)
        advisory_text = rule_result["text"]
        confidence = rule_result["confidence"]
        matched_rule = rule_result.get("matched_rule")

        # Determine risk level and actionable steps
        risk_level, recommendations = self._compute_risk_and_actions(
            weather_code=weather_code,
            crop_stage=stage,
            total_24h_rain=total_24h_rain,
            max_temp=max_temp_24h,
            max_wind=max_wind_24h,
            elevation_m=village["static_features"]["elevation_m"]
        )

        return {
            "village_id": village["village_id"],
            "panchayat_id": village["panchayat_id"],
            "village_name": village["name"],
            "crop_stage": stage,
            "weather_inferred": weather_code,
            "current_weather": current_weather,
            "advisory": {
                "text": advisory_text,
                "confidence": confidence,
                "matched_rule": matched_rule,
                "risk_level": risk_level,
                "actionable_recommendations": recommendations
            }
        }

    def _compute_risk_and_actions(
        self,
        weather_code: str,
        crop_stage: str,
        total_24h_rain: float,
        max_temp: float,
        max_wind: float,
        elevation_m: float
    ) -> tuple[str, List[str]]:
        """Determines categorical risk level and practical recommendations."""
        actions = []

        if weather_code == "heavy_rain":
            if crop_stage == "pod_formation":
                risk = "critical"
                actions.extend([
                    "Heavy rain during pod formation causes pod rot. Immediately open field drainage channels.",
                    "Clear field bunds to prevent soil erosion and waterlogging.",
                    "Halt fertilizer top-dressing to prevent nutrient leaching."
                ])
            else:
                risk = "critical" if crop_stage in ["seedling", "spraying_window"] else "high"
                actions.extend([
                    "Heavy downpour expected. Inspect drainage channels to prevent field inundation.",
                    "Postpone all chemical spraying and harvesting until conditions improve."
                ])

        elif weather_code == "rain_24h":
            if crop_stage == "spraying_window":
                risk = "critical"
                actions.extend([
                    "Immediately postpone pesticide/fungicide application; chemical runoff expected.",
                    "Inspect field drainage bunds to prevent waterlogging in low-lying tracts.",
                    "Reschedule foliar spraying to 48 hours post-rainfall."
                ])
            elif crop_stage in ["seedling", "young_seedling"]:
                risk = "high"
                actions.extend([
                    "Ensure nursery drainage channels are unblocked to prevent seedling submergence.",
                    "Avoid applying top-dress urea during high precipitation."
                ])
            elif crop_stage == "flowering":
                risk = "medium"
                actions.extend([
                    "Rain will aid moisture levels, but monitor for fungal spore development.",
                    "Check crop canopy ventilation after rain stops."
                ])
            else:
                risk = "medium"
                actions.append("Ensure regular field clearing and check for standing water.")

        elif weather_code == "no_rain_7d":
            if crop_stage in ["seedling", "flowering"]:
                risk = "high"
                actions.extend([
                    "Implement drip or furrow irrigation every 24-48 hours.",
                    "Apply organic mulch around root zones to conserve soil moisture."
                ])
            else:
                risk = "medium"
                actions.extend([
                    "Schedule supplementary irrigation during early morning or late evening hours.",
                    "Monitor soil moisture tension."
                ])

        elif weather_code == "high_temp_dry":
            risk = "high"
            actions.extend([
                "Maintain thin water layer in paddy fields to moderate canopy temperature.",
                "Provide shade netting for sensitive nursery saplings."
            ])

        elif weather_code == "high_wind":
            risk = "high" if crop_stage == "flowering" else "medium"
            actions.extend([
                "Provide propping/staking for tall crops (banana, cassava, sugarcane).",
                "Halt chemical mist spraying to prevent droplet drift."
            ])

        elif weather_code == "frost_risk":
            risk = "critical"
            actions.extend([
                "Irrigate fields late in the afternoon to retain ambient ground heat.",
                "Apply light surface mulching over vegetable beds."
            ])

        else:
            risk = "low"
            if crop_stage == "mature":
                actions.extend([
                    "Conditions normal. Harvest when pods and grains are dry.",
                    "Ensure clean storage and threshing facilities are prepared."
                ])
            else:
                actions.extend([
                    "Conditions optimal for field activities, fertilization, and crop weeding.",
                    "Continue standard agricultural calendar routines."
                ])

        return risk, actions


advisory_service = AdvisoryService()
