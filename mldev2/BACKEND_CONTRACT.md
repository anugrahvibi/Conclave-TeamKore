# Backend Integration Contract
## AI/ML Developer #2 ↔ Backend Developer

**Purpose:** Define the exact interface between ML components and backend API  
**Status:** Ready to discuss on Day 1 AM  
**Last Updated:** September 13, 2026

---

## Overview

The backend will integrate two functions from the ML module:

1. **Correction Model** — Called inside `/forecast` endpoint
2. **Advisory Engine** — Called inside `/advisory` endpoint

Both are wrapped in the `WeatherCorrectionAndAdvisory` class.

---

## Function 1: Training (One-time Setup)

### Call Signature
```python
pipeline = WeatherCorrectionAndAdvisory()
pipeline.train_correction_model(X, y)
pipeline.save_artifacts("model.pkl", "rules.json")
```

### When
- At server startup
- Or when new training data is available

### Inputs
- `X`: numpy array of shape `(n_samples, 6)`
  - Columns: `[block_temp, block_rain, block_humidity, elevation, dist_to_water, land_cover]`
  - `land_cover` numeric codes: agriculture=0, forest=1, urban=2, water=3, barren=4
  - dtype: float
- `y`: numpy array of shape `(n_samples,)`
  - Correction deltas (what to add to baseline forecast)
  - dtype: float

### Output
- `None` (saves model to disk internally)

### Example
```python
import numpy as np

# From ML Dev #1, we get:
block_forecasts = np.array([
    [25.2, 30.5, 70, 150, 2.5, 0],
    [24.8, 15.2, 65, 300, 5.0, 1],
    [26.1, 0.5, 55, 400, 8.0, 2]
])

ground_truth_deltas = np.array([1.2, -0.5, -1.8])

# We call:
pipeline.train_correction_model(block_forecasts, ground_truth_deltas)
pipeline.save_artifacts("correction_model.pkl", "advisory_rules.json")
```

---

## Function 2: Runtime Prediction (Per-Request)

### Call Signature
```python
result = pipeline.forecast_and_advise(
    block_forecast,
    static_features,
    crop_stage
)
```

### When
- Every time someone calls `/forecast` or `/advisory` endpoint

### Inputs

#### `block_forecast` (dict)
Block-level weather forecast (from ML Dev #1)

```python
{
    "temp_c": 25.5,         # Temperature in Celsius (float)
    "rain_mm": 22.0,        # Expected rainfall in mm (float)
    "humidity_pct": 72      # Relative humidity 0-100 (float)
}
```

#### `static_features` (dict)
Village-specific unchanging features

```python
{
    "elevation_m": 250,         # Elevation above sea level in meters (int/float)
    "dist_to_water_km": 3.5,    # Distance to nearest water body in km (float)
    "land_cover": "agriculture" # agriculture|forest|urban|water|barren (or 0-4)
}
```

#### `crop_stage` (str)
Current stage of the crop. One of:
- `"seedling"` — Just planted, very young
- `"young_seedling"` — Older seedling, still fragile
- `"vegetative"` — Growing leaves/stems
- `"spraying_window"` — Safe time to apply pesticides
- `"flowering"` — Flowers blooming
- `"pod_formation"` — Pods/fruits forming
- `"mature"` — Ready to harvest

### Output

```python
{
    "corrected_temp_c": 26.4,      # Adjusted temperature (float)
    "correction_delta": 1.2,       # What we added (float)
    "weather_inferred": "rain_24h", # Inferred condition (string)
    "advisory": {
        "text": "Delay pesticide spray; rain expected in next 24 hours",
        "confidence": "high",      # "high", "medium", or "low"
        "matched_rule": "rain_24h + spraying_window"
    }
}
```

### Example Full Flow

```python
# Backend receives HTTP request:
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

# Backend calls ML module:
result = pipeline.forecast_and_advise(
    block_forecast=request["block_forecast"],
    static_features=request["static_features"],
    crop_stage=request["crop"]
)

# Backend returns to frontend:
response = {
    "village_id": 42,
    "corrected_temp_c": result["corrected_temp_c"],
    "correction_delta": result["correction_delta"],
    "advisory_text": result["advisory"]["text"],
    "advisory_confidence": result["advisory"]["confidence"]
}
```

---

## Function 3: Loading Pre-trained Model

### Call Signature
```python
pipeline = WeatherCorrectionAndAdvisory(
    model_path="correction_model.pkl",
    rules_path="advisory_rules.json"
)
```

### When
- At server startup, after training is complete
- Avoids re-training every request

### Inputs
- `model_path`: Path to saved model file (string)
- `rules_path`: Path to saved rules file (string)

### Output
- `None` (loads from disk internally)

### Example
```python
# At app startup:
pipeline = WeatherCorrectionAndAdvisory(
    model_path="models/correction_model.pkl",
    rules_path="rules/advisory_rules.json"
)

# Then, handle requests:
for request in incoming_requests:
    result = pipeline.forecast_and_advise(...)
```

---

## Error Handling

### If Model Not Trained
```python
pipeline = WeatherCorrectionAndAdvisory()
pipeline.predict(...)  # ❌ RuntimeError: "Model not trained"
```

**Solution:** Call `train()` or `load()` first.

### If Invalid Input
```python
# Missing "temp_c" key
forecast = {"rain_mm": 5}  # ❌ Missing temp_c
result = pipeline.forecast_and_advise(forecast, ...)
```

**Solution:** Code will use defaults (25°C, 5mm rain, 65% humidity). Consider validation on backend side.

### If Weather Code Not Found
```python
advisory = pipeline.advisory_engine.get_advisory("unknown_weather", "seedling")
# Returns: {"text": "No specific advisory available...", "confidence": "low"}
```

**Solution:** Check your weather_codes. Valid codes are in `config.json`.

---

## Data Types & Validation

| Field | Type | Range | Example |
|-------|------|-------|---------|
| `temp_c` | float | -40 to 50 | 25.5 |
| `rain_mm` | float | 0 to 500 | 22.0 |
| `humidity_pct` | float | 0 to 100 | 72 |
| `elevation_m` | float | 0 to 3000 | 250 |
| `dist_to_water_km` | float | 0 to 100 | 3.5 |
| `land_cover` | string or 0-4 | agriculture, forest, urban, water, barren | "agriculture" |
| `crop_stage` | string | (list above) | "spraying_window" |

---

## Performance Notes

### Training
- ~300-500 samples: < 1 second on standard laptop
- Can train async at startup

### Prediction
- Per request: < 10ms (very fast)
- Can handle 100+ requests/second easily

### Memory
- Trained model: ~200KB on disk
- Loaded in memory: ~2MB
- JSON rules: ~10KB

---

## Version Control & Updates

### Model Versioning
```python
# Save with timestamp
pipeline.save_artifacts(
    f"models/correction_model_{datetime.now().isoformat()}.pkl",
    f"rules/advisory_rules_{datetime.now().isoformat()}.json"
)
```

### Rules Updates
```python
# Update rules.json without retraining model
pipeline.advisory_engine.load("new_rules.json")
```

---

## Day 1 Alignment Checklist

- [ ] Backend dev confirms inputs match their forecast structure
- [ ] Backend dev confirms they can call `forecast_and_advise()` once per request
- [ ] Backend dev sets up model loading at startup
- [ ] Agree on error handling strategy
- [ ] Agree on logging/debugging approach
- [ ] Confirm data types and ranges

---

## Day 2 Integration

1. Backend creates `/forecast` endpoint that calls `pipeline.forecast_and_advise()`
2. Backend creates `/advisory` endpoint (might use same pipeline)
3. Both endpoints return corrected forecast + advisory
4. Frontend displays results to farmer

---

## Questions for Backend Dev

1. Where will you store the trained model + rules files?
2. How often do you want to retrain?
3. Do you need logging for each prediction?
4. Should we add timestamps to the response?
5. Should advisory confidence level affect response priority?

---

## Sign-Off

- **ML Dev #2 (You):** `correction_and_advise.py` is ready
- **Backend Dev:** Confirm you can integrate by end of Day 1
- **ML Dev #1:** Confirm training data format matches our X shape

---

*Print this and discuss with backend dev first thing Day 1 AM.*
