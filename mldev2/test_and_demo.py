"""
Test suite and demo for correction model + advisory engine.

Run this to:
1. Verify the model trains correctly
2. Test edge cases
3. See what the backend will call
"""

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
import numpy as np

# Ensure module directory is on sys.path for robust imports from anywhere
_MODULE_DIR = Path(__file__).resolve().parent
if str(_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(_MODULE_DIR))

from correction_and_advisory import (
    generate_mock_training_data,
    load_training_data,
    CorrectionModel,
    AgroAdvisoryEngine,
    WeatherCorrectionAndAdvisory,
    encode_land_cover,
)


def test_correction_model():
    """Test that the correction model trains and predicts."""
    print("\n" + "="*70)
    print("TEST 1: Correction Model")
    print("="*70)
    
    # Generate data
    X, y = generate_mock_training_data(n_samples=200)
    assert X.shape == (200, 6), f"Expected X shape (200, 6), got {X.shape}"
    
    # Train
    model = CorrectionModel()
    model.train(X, y)
    
    # Predict on a few examples
    test_cases = [
        {
            "name": "High elevation, far from water, forest",
            "forecast": {"temp_c": 25.0, "rain_mm": 5.0, "humidity_pct": 60},
            "features": {"elevation_m": 400, "dist_to_water_km": 8.0, "land_cover": "forest"}
        },
        {
            "name": "Low elevation, near water, agriculture",
            "forecast": {"temp_c": 25.0, "rain_mm": 5.0, "humidity_pct": 60},
            "features": {"elevation_m": 100, "dist_to_water_km": 1.0, "land_cover": "agriculture"}
        },
        {
            "name": "Very humid urban (bias toward overestimating rain)",
            "forecast": {"temp_c": 25.0, "rain_mm": 5.0, "humidity_pct": 85},
            "features": {"elevation_m": 300, "dist_to_water_km": 5.0, "land_cover": "urban"}
        }
    ]
    
    for test in test_cases:
        correction = model.predict(test["forecast"], test["features"])
        corrected_temp = test["forecast"]["temp_c"] + correction
        print(f"\n  {test['name']}")
        print(f"    Block temp: {test['forecast']['temp_c']}°C")
        print(f"    Correction: {correction:+.2f}°C")
        print(f"    Corrected: {corrected_temp:.2f}°C")
    
    print("\n  ✓ Model trained and predicted successfully")


def test_advisory_engine():
    """Test that advisory engine returns sensible outputs."""
    print("\n" + "="*70)
    print("TEST 2: Advisory Engine")
    print("="*70)
    
    engine = AgroAdvisoryEngine()
    
    test_cases = [
        ("rain_24h", "spraying_window"),
        ("rain_24h", "flowering"),
        ("frost_risk", "young_seedling"),
        ("high_temp_dry", "flowering"),
        ("no_rain_7d", "seedling"),
        ("high_wind", "flowering"),
        ("heavy_rain", "pod_formation"),
        ("normal", "mature"),
        ("normal", "any")
    ]
    
    for weather, stage in test_cases:
        advisory = engine.get_advisory(weather, stage)
        print(f"\n  Weather: {weather} | Stage: {stage}")
        print(f"    → {advisory['text']}")
        print(f"    Confidence: {advisory['confidence']}")
    
    print("\n  ✓ Advisory engine working correctly")


def test_full_pipeline():
    """Test the complete integration."""
    print("\n" + "="*70)
    print("TEST 3: Full Pipeline (Correction + Advisory)")
    print("="*70)
    
    # Generate and train
    X, y = generate_mock_training_data(n_samples=300)
    pipeline = WeatherCorrectionAndAdvisory()
    pipeline.train_correction_model(X, y)
    
    # Test scenarios (realistic for demo)
    scenarios = [
        {
            "name": "Rice, seedling stage, dry spell",
            "forecast": {"temp_c": 28.0, "rain_mm": 0.5, "humidity_pct": 45},
            "features": {"elevation_m": 150, "dist_to_water_km": 5.0, "land_cover": "agriculture"},
            "crop": "seedling"
        },
        {
            "name": "Wheat, flowering, rain coming",
            "forecast": {"temp_c": 22.0, "rain_mm": 25.0, "humidity_pct": 75},
            "features": {"elevation_m": 300, "dist_to_water_km": 2.0, "land_cover": "agriculture"},
            "crop": "flowering"
        },
        {
            "name": "Chickpea, pod formation, heatwave",
            "forecast": {"temp_c": 35.0, "rain_mm": 1.0, "humidity_pct": 40},
            "features": {"elevation_m": 200, "dist_to_water_km": 7.0, "land_cover": "barren"},
            "crop": "pod_formation"
        },
        {
            "name": "Mustard, early stage, frost risk",
            "forecast": {"temp_c": 3.0, "rain_mm": 2.0, "humidity_pct": 70},
            "features": {"elevation_m": 400, "dist_to_water_km": 3.0, "land_cover": "forest"},
            "crop": "young_seedling"
        }
    ]
    
    for scenario in scenarios:
        result = pipeline.forecast_and_advise(
            scenario["forecast"],
            scenario["features"],
            scenario["crop"]
        )
        
        print(f"\n  Scenario: {scenario['name']}")
        print(f"    Forecast: {scenario['forecast']['temp_c']}°C, {scenario['forecast']['rain_mm']}mm rain")
        print(f"    ↓ Correction: {result['correction_delta']:+.2f}°C")
        print(f"    ↓ Corrected: {result['corrected_temp_c']}°C")
        print(f"    Weather inferred: {result['weather_inferred']}")
        print(f"    Advisory: {result['advisory']['text']}")
    
    print("\n  ✓ Full pipeline working end-to-end")


def test_backend_integration():
    """
    Show exactly what the backend will call.
    This is the contract between your ML code and their API.
    """
    print("\n" + "="*70)
    print("TEST 4: Backend Integration Contract")
    print("="*70)
    
    # Setup
    X, y = generate_mock_training_data(n_samples=300)
    pipeline = WeatherCorrectionAndAdvisory()
    pipeline.train_correction_model(X, y)
    
    # This is what backend will do (pseudo-code):
    print("\n  Backend will call:")
    print("""
    import requests
    
    # When someone requests forecast for village 42
    response = requests.post("http://api/forecast", json={
        "village_id": 42,
        "block_forecast": {
            "temp_c": 25.5,
            "rain_mm": 22.0,
            "humidity_pct": 72
        },
        "static_features": {
            "elevation_m": 250,
            "dist_to_water_km": 3.5,
            "land_cover": "agriculture"
        },
        "crop": "spraying_window"
    })
    
    # Backend gets back:
    {
        "corrected_temp_c": 26.4,
        "correction_delta": 1.2,
        "advisory": {
            "text": "Rain expected in next 24 hours...",
            "confidence": "high",
            "matched_rule": "rain_24h + spraying_window"
        }
    }
    """)
    
    # Simulate the call
    print("\n  Simulating backend call:")
    request = {
        "village_id": 42,
        "block_forecast": {
            "temp_c": 25.5,
            "rain_mm": 22.0,
            "humidity_pct": 72
        },
        "static_features": {
            "elevation_m": 250,
            "dist_to_water_km": 3.5,
            "land_cover": "agriculture"
        },
        "crop": "spraying_window"
    }
    
    response = pipeline.forecast_and_advise(
        request["block_forecast"],
        request["static_features"],
        request["crop"]
    )
    
    print(f"\n    Request: {json.dumps(request, indent=6)}")
    print(f"\n    Response: {json.dumps(response, indent=6)}")
    print(f"\n  ✓ Backend integration looks good!")


def test_load_real_training_data():
    """Load CSV from ML Dev #1, split X/y, confirm 6-feature shape."""
    print("\n" + "="*70)
    print("TEST 5: Load real training CSV")
    print("="*70)

    X, y = load_training_data("data/training_data.csv")
    assert X.shape[1] == 6, f"Expected 6 features, got {X.shape}"
    assert len(X) == len(y)
    print(f"\n  Loaded {len(X)} rows, X shape {X.shape}")
    print("  ✓ CSV loader splits features vs correction_delta")


def generate_synthetic_test_data(n_samples=250, seed=999):
    """
    Generate synthetic test villages that the model never saw during training.
    Uses a distinct random seed and variable ranges from training data.
    """
    np.random.seed(seed)
    block_temp = np.random.uniform(16, 34, n_samples)
    block_rain = np.random.exponential(scale=5.5, size=n_samples)
    block_humidity = np.random.uniform(42, 88, n_samples)
    elevation = np.random.uniform(120, 480, n_samples)
    dist_to_water = np.random.uniform(0.6, 9.5, n_samples)
    land_covers = ["agriculture", "forest", "urban", "water", "barren"]
    land_cover_raw = np.random.choice(land_covers, size=n_samples)

    land_cover_effect = {
        "agriculture": 0.0,
        "forest": -0.6,
        "urban": 1.0,
        "water": -0.4,
        "barren": 0.5,
    }

    block_forecasts = []
    static_features_list = []
    ground_truth_temps = []

    for i in range(n_samples):
        b_temp = float(block_temp[i])
        b_rain = float(block_rain[i])
        b_hum = float(block_humidity[i])
        elev = float(elevation[i])
        dist = float(dist_to_water[i])
        lc = land_cover_raw[i]

        delta = (
            -0.05 * (elev - 300)
            + 0.1 * (dist - 5)
            - 0.02 * (b_hum - 65)
            + land_cover_effect.get(lc, 0.0)
            + np.random.normal(0, 0.3)
        )
        gt_temp = b_temp + delta

        block_forecasts.append({"temp_c": b_temp, "rain_mm": b_rain, "humidity_pct": b_hum})
        static_features_list.append({"elevation_m": elev, "dist_to_water_km": dist, "land_cover": lc})
        ground_truth_temps.append(float(gt_temp))

    return block_forecasts, static_features_list, ground_truth_temps


def load_held_out_test_data(csv_path=None):
    """
    Load real held-out test villages (split == 'test').
    Returns (block_forecasts, static_features_list, ground_truth_temps) or None if not found.
    """
    module_dir = Path(__file__).resolve().parent
    candidates = [
        Path(csv_path) if csv_path else None,
        module_dir.parent / "mldev1" / "data" / "training_dataset.csv",
        module_dir / "data" / "test_data.csv",
        Path("mldev1/data/training_dataset.csv"),
    ]

    target_csv = None
    for cand in candidates:
        if cand and cand.is_file():
            target_csv = cand
            break

    if not target_csv:
        return None

    grouped = defaultdict(dict)
    with open(target_csv, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("split") == "test":
                key = (row.get("village_id", ""), row.get("timestamp", ""))
                grouped[key][row["variable"]] = row

    if not grouped:
        return None

    block_forecasts = []
    static_features_list = []
    ground_truth_temps = []

    for vars_by_name in grouped.values():
        temp_row = vars_by_name.get("temp")
        if not temp_row or "ground_truth" not in temp_row:
            continue
        rain_row = vars_by_name.get("rainfall") or {}
        humidity_row = vars_by_name.get("humidity") or {}

        dist_m = float(temp_row["dist_to_water"])
        dist_km = dist_m / 1000.0 if dist_m > 100 else dist_m

        block_forecasts.append({
            "temp_c": float(temp_row["baseline_pred"]),
            "rain_mm": float(rain_row.get("baseline_pred", 5.0)),
            "humidity_pct": float(humidity_row.get("baseline_pred", 65.0)),
        })
        static_features_list.append({
            "elevation_m": float(temp_row["elevation"]),
            "dist_to_water_km": dist_km,
            "land_cover": temp_row.get("land_cover", "agriculture"),
        })
        ground_truth_temps.append(float(temp_row["ground_truth"]))

    return block_forecasts, static_features_list, ground_truth_temps


def test_improvement_over_baseline(
    block_forecast=None,
    static_features=None,
    ground_truth_temp=None,
    model=None,
    model_path="model.pkl"
):
    """
    Benchmark the correction model against the baseline (no correction).

    Args:
        block_forecast: Dict or list of dicts with 'temp_c', 'rain_mm', 'humidity_pct'.
                        Can also be a tuple of (block_forecast, static_features, ground_truth_temp).
                        If None, automatically loads held-out test data or generates synthetic test data.
        static_features: Dict or list of dicts with 'elevation_m', 'dist_to_water_km', 'land_cover'.
        ground_truth_temp: Float or list of floats (actual village temperature in °C).
        model: Optional pre-loaded CorrectionModel instance.
        model_path: Path to model artifact (default: 'model.pkl').

    Calculates:
        - MAE for raw block forecast
        - MAE for corrected forecast
        - % improvement

    Prints results in the required format:
        Mean Absolute Error (MAE):
        - Baseline (no correction): X.XX°C
        - With correction model: X.XX°C
        - Improvement: Y.Y%

    Returns:
        dict: {"baseline_mae": float, "corrected_mae": float, "improvement_pct": float}
    """
    print("\n" + "=" * 70)
    print("TEST 6: Improvement Over Baseline (Benchmark)")
    print("=" * 70)

    # Allow tuple / list unpack if passed as single test_data argument
    if static_features is None and ground_truth_temp is None:
        if isinstance(block_forecast, (tuple, list)) and len(block_forecast) == 3:
            block_forecast, static_features, ground_truth_temp = block_forecast

    # If no test data provided, look for held-out test data or generate synthetic
    data_source_desc = ""
    if block_forecast is None or static_features is None or ground_truth_temp is None:
        held_out = load_held_out_test_data()
        if held_out and len(held_out[0]) > 0:
            block_forecast, static_features, ground_truth_temp = held_out
            data_source_desc = f"Loaded {len(ground_truth_temp)} held-out test records (split == 'test')"
        else:
            block_forecast, static_features, ground_truth_temp = generate_synthetic_test_data(n_samples=250)
            data_source_desc = f"Generated {len(ground_truth_temp)} synthetic test villages (unseen by model)"

    # Normalize single dicts/floats to lists
    if isinstance(block_forecast, dict):
        block_forecast = [block_forecast]
    if isinstance(static_features, dict):
        static_features = [static_features]
    if isinstance(ground_truth_temp, (int, float, np.number)):
        ground_truth_temp = [ground_truth_temp]

    n_samples = len(ground_truth_temp)
    if data_source_desc:
        print(f"  {data_source_desc}")
    else:
        print(f"  Evaluating {n_samples} test sample(s)")

    # 1. Load trained model
    module_dir = Path(__file__).resolve().parent
    if model is None:
        candidate_paths = [
            Path(model_path),
            module_dir / model_path,
            module_dir / "model.pkl",
            Path.cwd() / "mldev2" / "model.pkl",
            Path.cwd() / "backend" / "artifacts" / "correction_model.pkl",
            module_dir.parent / "backend" / "artifacts" / "correction_model.pkl",
        ]
        found_path = None
        for p in candidate_paths:
            if p.is_file():
                found_path = p
                break

        model = CorrectionModel()
        if found_path:
            model.load(str(found_path))
        else:
            print("  ⚠️ No saved model artifact found; training on mock data for benchmark...")
            X_mock, y_mock = generate_mock_training_data(n_samples=300)
            model.train(X_mock, y_mock)

    # 2. Extract features and compute predictions (fast vectorized)
    b_temps = np.array([float(bf.get("temp_c", 25.0)) for bf in block_forecast])
    b_rains = np.array([float(bf.get("rain_mm", 5.0)) for bf in block_forecast])
    b_hums = np.array([float(bf.get("humidity_pct", 65.0)) for bf in block_forecast])

    elevs = np.array([float(sf.get("elevation_m", 300.0)) for sf in static_features])
    dists = np.array([float(sf.get("dist_to_water_km", 5.0)) for sf in static_features])
    lcs = np.array([encode_land_cover(sf.get("land_cover", "agriculture")) for sf in static_features], dtype=float)

    gt_temps = np.array([float(gt) for gt in ground_truth_temp])

    X = np.column_stack([b_temps, b_rains, b_hums, elevs, dists, lcs])
    X_scaled = model.scaler.transform(X)
    predicted_deltas = model.model.predict(X_scaled)
    corrected_temps = b_temps + predicted_deltas

    # 3. Calculate MAE for raw block forecast and corrected forecast
    baseline_mae = float(np.mean(np.abs(b_temps - gt_temps)))
    corrected_mae = float(np.mean(np.abs(corrected_temps - gt_temps)))
    improvement = float(((baseline_mae - corrected_mae) / baseline_mae) * 100.0) if baseline_mae > 0 else 0.0

    # 4. Print results in exact requested format
    print("\nMean Absolute Error (MAE):")
    print(f"- Baseline (no correction): {baseline_mae:.2f}°C")
    print(f"- With correction model: {corrected_mae:.2f}°C")
    print(f"- Improvement: {improvement:.1f}%\n")

    if "pytest" in sys.modules:
        return None

    return {
        "baseline_mae": baseline_mae,
        "corrected_mae": corrected_mae,
        "improvement_pct": improvement,
    }


def test_robustness():
    """Test input validation, missing static feature defaults, and safe advisory fallbacks."""
    print("\n" + "="*70)
    print("TEST 7: Robustness & Error Handling")
    print("="*70)

    import warnings
    model = CorrectionModel()
    X, y = generate_mock_training_data(n_samples=200)
    model.train(X, y)

    # 1. Missing static features: should use defaults and issue warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        delta = model.predict({"temp_c": 25.0, "rain_mm": 5.0, "humidity_pct": 65.0}, {})
        assert isinstance(delta, float)
        assert len(w) >= 3, f"Expected at least 3 warnings for missing features, got {len(w)}"
        print(f"  ✓ Missing static features: used sensible defaults, logged {len(w)} warnings")

    # 2. Advisory fallback: unmapped weather code or crop stage must not crash
    engine = AgroAdvisoryEngine()
    adv_unknown = engine.get_advisory("unmapped_weather_xyz", "unmapped_stage_123")
    assert isinstance(adv_unknown, dict)
    assert "text" in adv_unknown and adv_unknown.get("confidence") == "low"
    print("  ✓ Unmapped weather/crop codes: safely returned generic fallback advisory without crashing")

    adv_none = engine.get_advisory(None, None)
    assert isinstance(adv_none, dict)
    assert "text" in adv_none
    print("  ✓ None inputs to advisory: safely handled without crashing")

    # 3. Input validation: missing required forecast keys raises ValueError
    try:
        model.predict({"temp_c": 25.0, "humidity_pct": 65.0}, {"elevation_m": 300})
        assert False, "Should have raised ValueError for missing rain_mm"
    except ValueError as e:
        print(f"  ✓ Missing required forecast key caught: {e}")

    # 4. Input validation: out-of-range forecast values raise ValueError
    try:
        model.predict({"temp_c": 125.0, "rain_mm": 5.0, "humidity_pct": 65.0}, {"elevation_m": 300})
        assert False, "Should have raised ValueError for temp_c=125"
    except ValueError as e:
        print(f"  ✓ Out-of-range temperature caught: {e}")

    try:
        model.predict({"temp_c": 25.0, "rain_mm": 5.0, "humidity_pct": 65.0}, {"elevation_m": 12000})
        assert False, "Should have raised ValueError for elevation_m=12000"
    except ValueError as e:
        print(f"  ✓ Out-of-range elevation caught: {e}")

    print("  ✓ All robustness checks passed!")


def interactive_demo():
    """
    Interactive mode: You can type in values and see what the system outputs.
    Great for hackathon Q&A!
    """
    print("\n" + "="*70)
    print("INTERACTIVE DEMO")
    print("="*70)
    print("\nType in your own forecast values and see the advisory!")
    print("(Or press Ctrl+C to exit)\n")
    
    # Train once
    X, y = generate_mock_training_data(n_samples=300)
    pipeline = WeatherCorrectionAndAdvisory()
    pipeline.train_correction_model(X, y)
    
    while True:
        try:
            print("-" * 70)
            temp = float(input("Block temp (°C): ") or "25")
            rain = float(input("Expected rain (mm): ") or "5")
            humidity = float(input("Humidity (%): ") or "65")
            elevation = float(input("Elevation (m): ") or "300")
            dist_water = float(input("Distance to water (km): ") or "5")
            land_cover = input("Land cover (agriculture/forest/urban/water/barren): ") or "agriculture"
            crop = input("Crop stage (seedling/spraying_window/flowering/pod_formation): ") or "seedling"
            
            result = pipeline.forecast_and_advise(
                {"temp_c": temp, "rain_mm": rain, "humidity_pct": humidity},
                {"elevation_m": elevation, "dist_to_water_km": dist_water, "land_cover": land_cover},
                crop
            )
            
            print(f"\n✓ RESULT:")
            print(f"  Corrected temp: {result['corrected_temp_c']}°C (was {temp}°C, {result['correction_delta']:+.2f}°C adjustment)")
            print(f"  Advisory: {result['advisory']['text']}")
            print()
        
        except ValueError:
            print("Invalid input, try again")
        except KeyboardInterrupt:
            print("\nBye!")
            break


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "interactive":
        interactive_demo()
    else:
        # Run all tests
        test_correction_model()
        test_advisory_engine()
        test_full_pipeline()
        test_backend_integration()
        test_load_real_training_data()
        test_improvement_over_baseline()
        test_robustness()
        
        print("\n" + "="*70)
        print("All tests passed! ✓")
        print("="*70)
        print("\nNext steps:")
        print("1. Copy these files into your Cursor project")
        print("2. Run: python test_and_demo.py")
        print("3. Run interactive: python test_and_demo.py interactive")
        print("4. Share the function signatures with backend dev")
        print("5. On Day 2, retrain with real data from ML Dev #1")
        print("\n")
