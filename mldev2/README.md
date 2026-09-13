# Village-Level Weather Downscaling & Agro-Advisory Platform
## AI/ML Developer #2 Component

**Status:** Hackathon-ready ✓  
**Your Role:** Correction Model + Advisory Engine  
**Built with:** Python, scikit-learn, no magic ✨

---

## What This Code Does (In Plain English)

### The Problem
- ML Dev #1 gives us a block-level weather forecast (e.g., "the whole farming region will be 25°C")
- But we need **village-level** accuracy (e.g., "your specific village at 250m elevation will be 26°C")
- The block forecast has systematic bias (cooler at high elevation, warmer near cities, etc.)

### Our Solution: Two Components

#### 1. **Correction Model** 
A small Random Forest that learns: "For a village at this elevation + this distance to water, add X degrees to the block forecast"

- **Input:** Block forecast (temp, rain, humidity) + static features (elevation, distance to water)
- **Output:** Correction delta (e.g., +1.2°C means add 1.2°C to the baseline)
- **Why Random Forest?** Dead simple, no deep learning needed, judges love it, works great on tabular data

#### 2. **Advisory Engine**
A rule-based lookup table that turns forecasts into explainable farmer-friendly guidance.

- **Input:** Weather condition (e.g., "rain expected") + crop stage (e.g., "spraying window")
- **Output:** Actionable advisory (e.g., "Delay pesticide spray; rain expected in next 24 hours")
- **Why rule-based?** Judges love explainability. No black box. Easy to extend during the hackathon.

---

## Quick Start

### Setup
```bash
# Copy the files to your project
cp correction_and_advisory.py your_project/
cp test_and_demo.py your_project/

# Install dependencies (if not already there)
pip install scikit-learn numpy
```

### Run Tests
```bash
python test_and_demo.py
```

Output:
- ✓ Correction model trains and predicts
- ✓ Advisory engine matches weather/crop combinations
- ✓ Full pipeline works end-to-end
- ✓ Backend integration contract verified

### Interactive Demo (Great for Q&A!)
```bash
python test_and_demo.py interactive
```

Type in your own values, see what the system outputs in real-time.

### Feature Importance & Farmer Interpretability Analysis
```bash
python debug_feature_importance.py
```
Analyzes the retrained Random Forest model, computes percentage importances, displays an in-terminal bar chart, generates a publication-quality chart at `outputs/feature_importance.png`, and explains what each feature means for farmers on the ground.

---

## How to Use (For Backend Dev)

### Step 1: Train the Model (Once, at startup)
```python
from correction_and_advisory import WeatherCorrectionAndAdvisory, load_training_data

# Load training data from ML Dev #1
X, y = load_training_data("data/training_data.csv")

# Create pipeline
pipeline = WeatherCorrectionAndAdvisory()

# Train
pipeline.train_correction_model(X, y)

# Save for later
pipeline.save_artifacts("model.pkl", "advisory_rules.json")
```

### Step 2: Use at Runtime (When answering API requests)
```python
# Load the trained pipeline
pipeline = WeatherCorrectionAndAdvisory(
    model_path="model.pkl",
    rules_path="advisory_rules.json"
)

# Someone requests forecast for village 42
result = pipeline.forecast_and_advise(
    block_forecast={"temp_c": 25.5, "rain_mm": 22.0, "humidity_pct": 72},
    static_features={"elevation_m": 250, "dist_to_water_km": 3.5, "land_cover": "agriculture"},
    crop_stage="spraying_window"
)

# Return to frontend
return {
    "corrected_temp_c": result["corrected_temp_c"],
    "correction_delta": result["correction_delta"],
    "advisory": result["advisory"]
}
```

---

## File Structure

```
correction_and_advisory.py
├── generate_mock_training_data()      # Create synthetic training data
├── CorrectionModel                    # Random Forest wrapper
│   ├── train(X, y)
│   ├── predict(forecast, features)
│   ├── save()
│   └── load()
├── AgroAdvisoryEngine                 # Rule lookup
│   ├── get_advisory(weather, crop_stage)
│   ├── save()
│   └── load()
└── WeatherCorrectionAndAdvisory       # Complete pipeline (backend uses this)
    ├── forecast_and_advise(...)
    ├── train_correction_model(X, y)
    └── save_artifacts()

test_and_demo.py
├── test_correction_model()
├── test_advisory_engine()
├── test_full_pipeline()
├── test_backend_integration()         # Shows backend contract
└── interactive_demo()                 # For hackathon Q&A
```

---

## Key Concepts (No ML Jargon Needed)

### Random Forest
Think of it like this:
- You have 50 "trees" (decision trees)
- Each tree asks: "Is elevation > 300m? Is distance to water < 5km? ..."
- Each tree votes on what the correction should be
- Final answer = average of all 50 votes

**Why it works for us:**
- Fast to train (runs in seconds)
- Handles non-linear relationships (elevation has a curve effect)
- Explainable feature importance (shows which factors matter most)
- No GPU needed (just CPU)

### Advisory Rules
Simple if-then logic:
```
if weather == "rain_24h" AND crop_stage == "spraying_window":
    return "Delay pesticide spray"
```

Judges love this because:
- Explainable: You can trace exactly why a farmer got a specific advisory
- Domain-grounded: Rules come from agronomy, not a black box
- Easy to extend: Add new rules during hackathon if judges want

---

## Day 1 Checklist

- [ ] Copy files to Cursor project
- [ ] Run `python test_and_demo.py` to verify everything works
- [ ] Agree on function signatures with backend dev (see `test_backend_integration()`)
- [ ] Customize advisory rules (hardcoded in `_load_default_rules()`, replace with your crops)
- [ ] Ask ML Dev #1 for training data structure (or stick with mock data for now)
- [ ] Commit to git

---

## Day 2 Checklist

- [ ] Retrain model with real/better data from ML Dev #1
- [ ] Test end-to-end with backend dev (API integration)
- [ ] Fine-tune advisory rules based on domain expert feedback
- [ ] Add 2-3 edge-case rules that judges might ask about

---

## Customization: How to Add Your Own Rules

Open `correction_and_advisory.py`, find `_load_default_rules()`:

```python
def _load_default_rules(self):
    self.rules = [
        {
            "condition": {"weather": "rain_24h", "crop_stage": "spraying_window"},
            "advisory": {
                "text": "Delay pesticide spray; rain expected in next 24 hours",
                "confidence": "high"
            }
        },
        # ADD YOUR OWN RULES HERE
        {
            "condition": {"weather": "YOUR_WEATHER_CODE", "crop_stage": "YOUR_STAGE"},
            "advisory": {
                "text": "Your advisory text here",
                "confidence": "high" or "medium" or "low"
            }
        }
    ]
```

Weather codes we're using:
- `rain_24h` — Rain expected in next 24 hours
- `no_rain_7d` — No rain for 7 days
- `frost_risk` — Temperature below 5°C
- `high_temp_dry` — Temp > 32°C AND humidity < 50%
- `high_wind` — Strong winds expected
- `normal` — Baseline conditions

Crop stages (add your own):
- `seedling` — Young plants just sprouted
- `young_seedling` — Even younger
- `spraying_window` — Safe to spray pesticides
- `flowering` — Flowers blooming
- `pod_formation` — Pods/fruits forming
- `mature` — Ready to harvest

---

## What Judges Want to See

### Demo Walkthrough
"Here's a farmer in village X with elevation Y and crop Z. Block forecast says 25°C. Our model corrects it to 26.4°C because elevation has a cooling effect. Advisory system returns: 'Rain expected → delay spray.' Explainable. Reproducible. Done."

### Explainability
"This is Random Forest, not neural nets. We can show feature importance. Elevation matters most, then distance to water. This matches real agronomy."

### Hackathon Realism
"Training data is mocked today, but integration is clean. On Day 2, we plug in real data from ML Dev #1. No changes needed."

---

## Troubleshooting

### "Model not trained" error
```python
# You need to call train() first:
pipeline.train_correction_model(X, y)
```

### Advisory returns None
```python
# Make sure weather code and crop stage match your rules
# Default: if no match, returns generic "follow standard practices"
```

### Backend integration failing
```python
# Double-check function signatures:
result = pipeline.forecast_and_advise(
    block_forecast={"temp_c": 25, "rain_mm": 5, "humidity_pct": 65},
    static_features={"elevation_m": 300, "dist_to_water_km": 5},
    crop_stage="seedling"
)
# Must be these exact keys and order
```

---

## Next Steps

1. **Copy to Cursor**: Drag `correction_and_advisory.py` and `test_and_demo.py` into your project
2. **Run tests**: `python test_and_demo.py`
3. **Show backend dev**: "Here's what I'll call, here's what you get back"
4. **Iterate on rules**: Get farmer/domain expert feedback
5. **Day 2**: Swap mock data for real data, retrain, ship

---

## Questions?

- **"Why not deep learning?"** → Judges prefer explainability. RF is faster, simpler, no GPU needed.
- **"What if rules are wrong?"** → Easy to fix (just JSON). Judges love the agility.
- **"Can I modify the model?"** → Yes! All code is yours. This is just a clean starting point.

---

**Good luck at the hackathon! 🚀**

Built for AI Conclave Hackathon (Sept 16, 2026)
