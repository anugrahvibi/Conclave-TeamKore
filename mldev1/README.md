# AI/ML Dev #1: Interpolation Baseline & Evaluation Pipeline
**Project:** Village-Level Weather Downscaling & Agro-Advisory Platform  
**Target:** Kerala, India

---

## Overview
This module implements the spatial downscaling foundation and evaluation harness for the platform:
1. **Phase 0 (Environment & Data):** Generates realistic block-level forecasts and ground truth for Kerala incorporating Western Ghats elevation, marine boundary layers, and microclimates.
2. **Phase 1 (IDW Baseline):** Fast, vectorized Inverse Distance Weighting (IDW) interpolation mapping block predictions to village centroids.
3. **Phase 2 (Static Features):** High-resolution digital elevation (DEM), land cover classification (Bhuvan/ESA categories), and distance to water bodies.
4. **Phase 3 (Handoff Dataset):** Merged, spatial-holdout split dataset with target residual `correction_delta` ready for ML Dev #2's correction model.
5. **Phase 4 (Evaluation Harness):** Reusable evaluation script computing RMSE and MAE across held-out villages and generating pitch-ready comparison charts.

---

## Directory Structure

```text
mldev1/
├── requirements.txt                   # Environment dependencies
├── README.md                          # Technical docs & handoff specifications
├── data/
│   ├── block_forecast.csv             # Block weather forecasts across timestamps
│   ├── village_centroids.csv          # Village centroids with panchayat mapping
│   ├── mock_ground_truth.csv          # Microclimate ground truth readings
│   ├── village_static_features.csv    # Elevation, land cover, water distance
│   └── training_dataset.csv           # Handoff dataset for ML Dev #2
├── models/
│   ├── __init__.py
│   └── idw_baseline.py                # IDW engine and idw_predict function
├── scripts/
│   ├── __init__.py
│   ├── generate_synthetic_data.py     # Phase 0 data generation
│   ├── extract_static_features.py     # Phase 2 feature pipeline
│   ├── build_training_dataset.py      # Phase 3 merge and spatial splitting
│   └── run_pipeline.py                # Master end-to-end runner
├── evaluation/
│   ├── __init__.py
│   └── compare_baseline_vs_corrected.py # Phase 4 RMSE/MAE evaluator & chart
├── outputs/
│   ├── baseline_predictions.csv       # Phase 1 IDW predictions
│   ├── evaluation_metrics.csv         # Phase 4 metric summary table
│   └── evaluation_chart.png           # Phase 4 comparative bar chart
└── tests/
    ├── __init__.py
    └── test_idw_baseline.py           # Unit tests
```

---

## Data Schemas

### 1. `data/block_forecast.csv`
| Column | Type | Description |
|---|---|---|
| `block_id` | str | Block identifier (e.g. `BLK_IDK_01`) |
| `timestamp` | str | `YYYY-MM-DD HH:MM:SS` |
| `temp` | float | Temperature (°C) |
| `rainfall` | float | Precipitation (mm) |
| `humidity` | float | Relative humidity (%) |
| `wind` | float | Wind speed (km/h) |
| `lat` | float | Block center latitude |
| `lon` | float | Block center longitude |

### 2. `data/village_centroids.csv`
| Column | Type | Description |
|---|---|---|
| `village_id` | str | Unique village ID (e.g. `VIL_0001`) |
| `panchayat_id` | str | Administrative panchayat ID |
| `lat` | float | Village centroid latitude |
| `lon` | float | Village centroid longitude |

### 3. `data/village_static_features.csv`
| Column | Type | Description |
|---|---|---|
| `village_id` | str | Unique village ID |
| `elevation` | float | Meters above sea level (DEM) |
| `land_cover` | str | Categorical (`plantation`, `evergreen_forest`, `paddy_wetland`, etc.) |
| `dist_to_water` | float | Distance to nearest recognized water body / coastline (meters) |

### 4. `data/training_dataset.csv` (Handoff for ML Dev #2)
| Column | Type | Description |
|---|---|---|
| `village_id` | str | Unique village ID |
| `timestamp` | str | Forecast timestamp |
| `variable` | str | Weather variable (`temp`, `rainfall`, `humidity`, `wind`) |
| `baseline_pred` | float | Raw IDW baseline prediction |
| `elevation` | float | Static feature: elevation in meters |
| `land_cover` | str | Static feature: land cover category |
| `dist_to_water` | float | Static feature: distance in meters |
| `ground_truth` | float | Actual observed value |
| `correction_delta`| float | Learning target: `ground_truth - baseline_pred` |
| `split` | str | Spatial village split: `train` or `test` |

---

## Backend Integration Guide (`/forecast` endpoint)

Backend Dev can import and call the baseline prediction directly:

```python
from mldev1.models.idw_baseline import idw_predict

# Exact PRD signature:
temp_estimate = idw_predict(village_id="VIL_0001", variable="temp", k_nearest=4)
rainfall_estimate = idw_predict(village_id="VIL_0001", variable="rainfall", k_nearest=4)
```

---

## How to Run the Entire Pipeline

From the project root:

```bash
# 1. Activate venv
source mldev1/.venv/bin/activate

# 2. Run the master pipeline (Phases 0 through 4)
python3 mldev1/scripts/run_pipeline.py

# 3. Run unit tests
pytest mldev1/tests/
```
