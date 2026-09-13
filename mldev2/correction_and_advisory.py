"""
Village-Level Weather Downscaling & Agro-Advisory Platform
AI/ML Developer #2: Correction Model + Advisory Engine

This is a complete, hackathon-ready module. No external dependencies beyond sklearn & numpy.
"""

import json
import numpy as np
import pickle
from pathlib import Path
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler


# ============================================================================
# PART 1: MOCK DATA GENERATOR
# ============================================================================
# Why: We don't need ML Dev #1's data to start. This generates realistic
# training pairs that prove the correction model concept works.

def generate_mock_training_data(n_samples=500):
    """
    Generate synthetic block-forecast vs village-level ground-truth pairs.
    
    Simulates: Block-level weather has systematic bias. Our correction model
    learns to fix it.
    
    Returns:
        X (features): array of shape (n_samples, 5)
                      [block_temp, block_rain, block_humidity, elevation, dist_to_water]
        y (corrections): array of shape (n_samples,)
                         Correction delta to add to block forecast
    """
    np.random.seed(42)
    
    # Generate random block forecasts
    block_temp = np.random.uniform(15, 35, n_samples)  # 15-35°C
    block_rain = np.random.exponential(scale=5, size=n_samples)  # ~5mm avg
    block_humidity = np.random.uniform(40, 90, n_samples)  # 40-90%
    
    # Generate static features (same for all samples, but vary slightly per "village")
    elevation = np.random.uniform(100, 500, n_samples)  # 100-500m
    dist_to_water = np.random.uniform(0.5, 10, n_samples)  # 0.5-10km
    
    # Combine into feature matrix
    X = np.column_stack([block_temp, block_rain, block_humidity, elevation, dist_to_water])
    
    # Generate corrections: Simulate real bias patterns
    # Higher elevation → cooler (negative correction)
    # Far from water → hotter & drier (positive temp correction, negative rain correction)
    # High humidity block forecast → tends to overestimate (negative rain correction)
    
    y = (
        -0.05 * (elevation - 300) +  # Elevation effect
        0.1 * (dist_to_water - 5) +   # Distance to water effect
        -0.02 * (block_humidity - 65)  # Humidity effect
        + np.random.normal(0, 0.3, n_samples)  # Small noise
    )
    
    return X, y


# ============================================================================
# PART 2: CORRECTION MODEL
# ============================================================================
# What it does: Takes block-level forecast + static features, outputs a
# correction delta (how much to add/subtract from the baseline).

class CorrectionModel:
    """
    Lightweight Random Forest model to correct block-level forecasts.
    
    Train it once, call predict() at runtime. That's it.
    """
    
    def __init__(self, model_path=None):
        """
        Init the model.
        
        Args:
            model_path: If you've already trained and saved the model, 
                       load it from here. Otherwise, start fresh.
        """
        self.model = RandomForestRegressor(
            n_estimators=50,      # 50 trees (small & fast)
            max_depth=8,          # Not too deep
            random_state=42,
            n_jobs=-1             # Use all CPU cores
        )
        self.scaler = StandardScaler()
        self.is_trained = False
        
        if model_path and Path(model_path).exists():
            self.load(model_path)
    
    def train(self, X, y):
        """
        Train the model on (features, corrections) pairs.
        
        Args:
            X: array of shape (n_samples, 5)
               Columns: [block_temp, block_rain, block_humidity, elevation, dist_to_water]
            y: array of shape (n_samples,)
               Correction deltas (what to add to the baseline)
        """
        # Normalize features (helps RF learn faster)
        X_scaled = self.scaler.fit_transform(X)
        
        # Train
        self.model.fit(X_scaled, y)
        self.is_trained = True
        
        print(f"✓ Model trained on {len(X)} samples")
        print(f"  Feature importances: {self._get_feature_names_and_importance()}")
    
    def predict(self, block_forecast, static_features):
        """
        Predict correction delta for a new village forecast.
        
        Args:
            block_forecast: dict with keys: temp_c, rain_mm, humidity_pct
                           Example: {"temp_c": 25.2, "rain_mm": 30.5, "humidity_pct": 70}
            
            static_features: dict with keys: elevation_m, dist_to_water_km
                            Example: {"elevation_m": 150, "dist_to_water_km": 2.5}
        
        Returns:
            float: Correction delta (e.g., +1.2 means add 1.2°C to baseline)
        
        Raises:
            RuntimeError: If model hasn't been trained yet
        """
        if not self.is_trained:
            raise RuntimeError("Model not trained. Call train() first.")
        
        # Extract features in the same order as training
        x_single = np.array([
            block_forecast.get("temp_c", 25),
            block_forecast.get("rain_mm", 5),
            block_forecast.get("humidity_pct", 65),
            static_features.get("elevation_m", 300),
            static_features.get("dist_to_water_km", 5)
        ]).reshape(1, -1)
        
        # Normalize using the fitted scaler
        x_scaled = self.scaler.transform(x_single)
        
        # Predict
        correction = self.model.predict(x_scaled)[0]
        
        return float(correction)
    
    def save(self, model_path):
        """Save the trained model to disk."""
        with open(model_path, 'wb') as f:
            pickle.dump({
                'model': self.model,
                'scaler': self.scaler
            }, f)
        print(f"✓ Model saved to {model_path}")
    
    def load(self, model_path):
        """Load a previously trained model from disk."""
        with open(model_path, 'rb') as f:
            data = pickle.load(f)
            self.model = data['model']
            self.scaler = data['scaler']
        self.is_trained = True
        print(f"✓ Model loaded from {model_path}")
    
    def _get_feature_names_and_importance(self):
        """Helper to show which features matter most."""
        names = ['block_temp', 'block_rain', 'block_humidity', 'elevation', 'dist_to_water']
        importances = self.model.feature_importances_
        return {name: f"{imp:.3f}" for name, imp in zip(names, importances)}


# ============================================================================
# PART 3: AGRO-ADVISORY RULE ENGINE
# ============================================================================
# What it does: Given weather forecast + crop stage, look up the rule and
# return explainable guidance for the farmer.

class AgroAdvisoryEngine:
    """
    Rule-based advisory system. Keeps it simple and explainable.
    
    Load from JSON, query at runtime. That's it.
    """
    
    def __init__(self, rules_path=None):
        """
        Init the advisory engine.
        
        Args:
            rules_path: Path to JSON file with rules. If None, use defaults.
        """
        self.rules = []
        
        if rules_path and Path(rules_path).exists():
            self.load(rules_path)
        else:
            self._load_default_rules()
    
    def _load_default_rules(self):
        """
        Hardcoded rules for demo. Replace with your JSON file on Day 1.
        
        Rule format:
        {
            "condition": {
                "weather": "<weather_code>",
                "crop_stage": "<stage>"
            },
            "advisory": {
                "text": "...",
                "confidence": "high" | "medium" | "low"
            }
        }
        """
        self.rules = [
            # Rainfall-related
            {
                "condition": {"weather": "rain_24h", "crop_stage": "spraying_window"},
                "advisory": {
                    "text": "⚠️ Rain expected in next 24 hours. Delay pesticide spray until soil dries.",
                    "confidence": "high"
                }
            },
            {
                "condition": {"weather": "rain_24h", "crop_stage": "flowering"},
                "advisory": {
                    "text": "✓ Good news! Rain during flowering supports pollination. No action needed.",
                    "confidence": "high"
                }
            },
            {
                "condition": {"weather": "no_rain_7d", "crop_stage": "seedling"},
                "advisory": {
                    "text": "⚠️ No rain expected for 7 days. Increase irrigation frequency (daily if possible).",
                    "confidence": "high"
                }
            },
            
            # Frost-related
            {
                "condition": {"weather": "frost_risk", "crop_stage": "young_seedling"},
                "advisory": {
                    "text": "❄️ Frost risk tonight. Irrigate fields to raise soil temperature. Monitor temps after sunset.",
                    "confidence": "high"
                }
            },
            {
                "condition": {"weather": "frost_risk", "crop_stage": "mature"},
                "advisory": {
                    "text": "❄️ Frost risk, but mature crop can tolerate. Monitor; irrigate only if temps drop below -2°C.",
                    "confidence": "medium"
                }
            },
            
            # Heat-related
            {
                "condition": {"weather": "high_temp_dry", "crop_stage": "flowering"},
                "advisory": {
                    "text": "🌡️ High heat + low humidity during flowering. Increase irrigation to 1.5x normal. Mulch to retain soil moisture.",
                    "confidence": "high"
                }
            },
            {
                "condition": {"weather": "high_temp_dry", "crop_stage": "pod_formation"},
                "advisory": {
                    "text": "🌡️ Critical: Heat stress during pod formation reduces yield. Irrigate 2x daily if possible.",
                    "confidence": "high"
                }
            },
            
            # Wind-related
            {
                "condition": {"weather": "high_wind", "crop_stage": "flowering"},
                "advisory": {
                    "text": "💨 Strong winds expected during flowering. Avoid spraying; pollen dispersal may be affected.",
                    "confidence": "medium"
                }
            },
            
            # Default fallback
            {
                "condition": {"weather": "normal", "crop_stage": "any"},
                "advisory": {
                    "text": "✓ Conditions normal. Follow standard management practices.",
                    "confidence": "high"
                }
            }
        ]
    
    def get_advisory(self, weather_code, crop_stage):
        """
        Look up advisory for weather + crop stage.
        
        Args:
            weather_code: str, e.g., "rain_24h", "frost_risk", "high_temp_dry", "normal"
            crop_stage: str, e.g., "seedling", "spraying_window", "flowering", "pod_formation"
        
        Returns:
            dict with keys: text, confidence, matched_rule (or None if no match)
                Example: {
                    "text": "Rain expected in next 24 hours...",
                    "confidence": "high",
                    "matched_rule": "rain_24h + spraying_window"
                }
        """
        # Try exact match
        for rule in self.rules:
            if (rule["condition"]["weather"] == weather_code and
                (rule["condition"]["crop_stage"] == crop_stage or 
                 rule["condition"]["crop_stage"] == "any")):
                return {
                    "text": rule["advisory"]["text"],
                    "confidence": rule["advisory"]["confidence"],
                    "matched_rule": f"{weather_code} + {crop_stage}"
                }
        
        # Fallback to "normal"
        return {
            "text": "No specific advisory available. Follow standard practices.",
            "confidence": "low",
            "matched_rule": None
        }
    
    def save(self, rules_path):
        """Save rules to JSON (for easy sharing with team)."""
        with open(rules_path, 'w') as f:
            json.dump(self.rules, f, indent=2)
        print(f"✓ Rules saved to {rules_path}")
    
    def load(self, rules_path):
        """Load rules from JSON."""
        with open(rules_path, 'r') as f:
            self.rules = json.load(f)
        print(f"✓ Rules loaded from {rules_path}")


# ============================================================================
# PART 4: INTEGRATION WRAPPER (For Backend Dev)
# ============================================================================
# This is what the backend will call. Clean interface.

class WeatherCorrectionAndAdvisory:
    """
    Complete pipeline: correction model + advisory engine.
    
    Backend calls this, passes forecast + crop info, gets back corrected value + advisory.
    """
    
    def __init__(self, model_path=None, rules_path=None):
        """
        Init both components.
        
        Args:
            model_path: Path to saved correction model (optional)
            rules_path: Path to rules JSON (optional)
        """
        self.correction_model = CorrectionModel(model_path)
        self.advisory_engine = AgroAdvisoryEngine(rules_path)
    
    def forecast_and_advise(self, block_forecast, static_features, crop_stage):
        """
        Complete forecast + advisory for one village.
        
        Args:
            block_forecast: dict
                {"temp_c": 25.2, "rain_mm": 30.5, "humidity_pct": 70}
            
            static_features: dict
                {"elevation_m": 150, "dist_to_water_km": 2.5}
            
            crop_stage: str
                "seedling", "spraying_window", "flowering", etc.
        
        Returns:
            dict:
                {
                    "corrected_temp_c": 26.4,  # Block temp + correction
                    "correction_delta": 1.2,   # What we added
                    "advisory": {
                        "text": "...",
                        "confidence": "high",
                        "matched_rule": "..."
                    }
                }
        """
        # Step 1: Apply correction
        correction_delta = self.correction_model.predict(block_forecast, static_features)
        corrected_temp = block_forecast["temp_c"] + correction_delta
        
        # Step 2: Infer weather code from forecast (simple heuristic for demo)
        weather_code = self._infer_weather_code(block_forecast)
        
        # Step 3: Get advisory
        advisory = self.advisory_engine.get_advisory(weather_code, crop_stage)
        
        return {
            "corrected_temp_c": round(corrected_temp, 2),
            "correction_delta": round(correction_delta, 2),
            "weather_inferred": weather_code,
            "advisory": advisory
        }
    
    def _infer_weather_code(self, block_forecast):
        """
        Simple heuristic to turn forecast dict into a weather code.
        
        (In production, this would come from ML Dev #1's full forecast.)
        """
        rain = block_forecast.get("rain_mm", 0)
        temp = block_forecast.get("temp_c", 25)
        humidity = block_forecast.get("humidity_pct", 65)
        
        if rain > 20:
            return "rain_24h"
        elif temp < 5:
            return "frost_risk"
        elif temp > 32 and humidity < 50:
            return "high_temp_dry"
        else:
            return "normal"
    
    def train_correction_model(self, X, y):
        """Train the model (call this once during setup)."""
        self.correction_model.train(X, y)
    
    def save_artifacts(self, model_path, rules_path):
        """Save both model and rules for deployment."""
        self.correction_model.save(model_path)
        self.advisory_engine.save(rules_path)


# ============================================================================
# PART 5: QUICK START EXAMPLE
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("QUICK START: Village-Level Weather Downscaling & Agro-Advisory")
    print("=" * 70)
    
    # Generate mock training data
    print("\n[1] Generating mock training data...")
    X, y = generate_mock_training_data(n_samples=300)
    print(f"    Generated {len(X)} training samples")
    
    # Create and train the correction model
    print("\n[2] Training correction model...")
    pipeline = WeatherCorrectionAndAdvisory()
    pipeline.train_correction_model(X, y)
    
    # Example forecast
    print("\n[3] Example: Village forecast + advisory")
    block_forecast = {
        "temp_c": 25.5,
        "rain_mm": 22.0,
        "humidity_pct": 72
    }
    static_features = {
        "elevation_m": 250,
        "dist_to_water_km": 3.5
    }
    crop_stage = "spraying_window"
    
    result = pipeline.forecast_and_advise(block_forecast, static_features, crop_stage)
    
    print(f"\n    Block forecast (from ML Dev #1):")
    print(f"      Temp: {block_forecast['temp_c']}°C")
    print(f"      Rain: {block_forecast['rain_mm']}mm")
    print(f"      Humidity: {block_forecast['humidity_pct']}%")
    print(f"\n    Correction model output:")
    print(f"      Correction delta: {result['correction_delta']}°C")
    print(f"      Corrected temp: {result['corrected_temp_c']}°C")
    print(f"\n    Advisory:")
    print(f"      {result['advisory']['text']}")
    print(f"      Confidence: {result['advisory']['confidence']}")
    
    # Save artifacts
    print("\n[4] Saving artifacts for backend...")
    pipeline.save_artifacts("correction_model.pkl", "advisory_rules.json")
    
    print("\n" + "=" * 70)
    print("✓ Ready to integrate with backend dev!")
    print("=" * 70)
