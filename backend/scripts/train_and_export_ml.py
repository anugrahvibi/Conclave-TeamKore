"""
Trains the ML correction model on real Kerala training data and exports artifacts for the backend.
"""

import os
import sys
from pathlib import Path
import numpy as np
import pandas as pd

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mldev2.correction_and_advisory import CorrectionModel, AgroAdvisoryEngine, WeatherCorrectionAndAdvisory

def train_and_export():
    dataset_path = PROJECT_ROOT / "mldev1" / "data" / "training_dataset.csv"
    artifacts_dir = PROJECT_ROOT / "backend" / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    
    model_path = artifacts_dir / "correction_model.pkl"
    rules_path = artifacts_dir / "advisory_rules.json"

    print("=" * 70)
    print("Training ML Correction Model on Kerala Dataset...")
    print("=" * 70)

    if not dataset_path.exists():
        raise FileNotFoundError(f"Training dataset not found at {dataset_path}")

    df = pd.read_csv(dataset_path)
    
    # Pivot features: temp, rainfall, humidity, elevation, dist_to_water
    pivoted = df.pivot(
        index=["village_id", "timestamp", "elevation", "dist_to_water", "split"],
        columns="variable",
        values=["baseline_pred", "correction_delta"]
    ).reset_index()

    train_data = pivoted[pivoted["split"] == "train"]
    print(f"Loaded {len(train_data)} spatial training records.")

    # Prepare features [block_temp, block_rain, block_humidity, elevation, dist_to_water]
    block_temp = train_data["baseline_pred"]["temp"].values
    block_rain = train_data["baseline_pred"]["rainfall"].values
    block_humidity = train_data["baseline_pred"]["humidity"].values
    elevation = train_data["elevation"].values
    dist_to_water_km = train_data["dist_to_water"].values / 1000.0  # meters to km

    X = np.column_stack([block_temp, block_rain, block_humidity, elevation, dist_to_water_km])
    y_temp_delta = train_data["correction_delta"]["temp"].values

    # Train model
    model = CorrectionModel()
    model.train(X, y_temp_delta)

    # Save trained model
    model.save(str(model_path))

    # Initialize and save advisory rules
    advisory_engine = AgroAdvisoryEngine()
    advisory_engine.save(str(rules_path))

    print(f"✓ Model successfully saved to {model_path}")
    print(f"✓ Advisory rules successfully saved to {rules_path}")
    print("=" * 70)

if __name__ == "__main__":
    train_and_export()
