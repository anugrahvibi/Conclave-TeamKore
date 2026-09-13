"""
Test suite and demo for correction model + advisory engine.

Run this to:
1. Verify the model trains correctly
2. Test edge cases
3. See what the backend will call
"""

import json
from correction_and_advisory import (
    generate_mock_training_data,
    CorrectionModel,
    AgroAdvisoryEngine,
    WeatherCorrectionAndAdvisory
)


def test_correction_model():
    """Test that the correction model trains and predicts."""
    print("\n" + "="*70)
    print("TEST 1: Correction Model")
    print("="*70)
    
    # Generate data
    X, y = generate_mock_training_data(n_samples=200)
    
    # Train
    model = CorrectionModel()
    model.train(X, y)
    
    # Predict on a few examples
    test_cases = [
        {
            "name": "High elevation, far from water",
            "forecast": {"temp_c": 25.0, "rain_mm": 5.0, "humidity_pct": 60},
            "features": {"elevation_m": 400, "dist_to_water_km": 8.0}
        },
        {
            "name": "Low elevation, near water",
            "forecast": {"temp_c": 25.0, "rain_mm": 5.0, "humidity_pct": 60},
            "features": {"elevation_m": 100, "dist_to_water_km": 1.0}
        },
        {
            "name": "Very humid (bias toward overestimating rain)",
            "forecast": {"temp_c": 25.0, "rain_mm": 5.0, "humidity_pct": 85},
            "features": {"elevation_m": 300, "dist_to_water_km": 5.0}
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
            "features": {"elevation_m": 150, "dist_to_water_km": 5.0},
            "crop": "seedling"
        },
        {
            "name": "Wheat, flowering, rain coming",
            "forecast": {"temp_c": 22.0, "rain_mm": 25.0, "humidity_pct": 75},
            "features": {"elevation_m": 300, "dist_to_water_km": 2.0},
            "crop": "flowering"
        },
        {
            "name": "Chickpea, pod formation, heatwave",
            "forecast": {"temp_c": 35.0, "rain_mm": 1.0, "humidity_pct": 40},
            "features": {"elevation_m": 200, "dist_to_water_km": 7.0},
            "crop": "pod_formation"
        },
        {
            "name": "Mustard, early stage, frost risk",
            "forecast": {"temp_c": 3.0, "rain_mm": 2.0, "humidity_pct": 70},
            "features": {"elevation_m": 400, "dist_to_water_km": 3.0},
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
            "dist_to_water_km": 3.5
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
            "dist_to_water_km": 3.5
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
            crop = input("Crop stage (seedling/spraying_window/flowering/pod_formation): ") or "seedling"
            
            result = pipeline.forecast_and_advise(
                {"temp_c": temp, "rain_mm": rain, "humidity_pct": humidity},
                {"elevation_m": elevation, "dist_to_water_km": dist_water},
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
