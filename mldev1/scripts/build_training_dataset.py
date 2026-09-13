"""
Phase 3: Dataset Merge Pipeline (Handoff-Ready Dataset for ML Dev #2)
Joins baseline IDW predictions, static features, and ground-truth observations.
Calculates correction_delta = ground_truth - baseline_pred.
Performs spatial hold-out splitting by village.
Output: mldev1/data/training_dataset.csv
"""

import os
import numpy as np
import pandas as pd

def build_training_dataset(
    baseline_pred_path: str = "mldev1/outputs/baseline_predictions.csv",
    static_features_path: str = "mldev1/data/village_static_features.csv",
    ground_truth_path: str = "mldev1/data/mock_ground_truth.csv",
    output_path: str = "mldev1/data/training_dataset.csv",
    train_ratio: float = 0.75,
    random_seed: int = 42
) -> pd.DataFrame:
    """
    Constructs the handoff dataset for ML Dev #2.
    Format per PRD:
    village_id, timestamp, variable, baseline_pred, elevation, land_cover, dist_to_water, ground_truth, correction_delta, split
    """
    print("Loading datasets for Phase 3 merge...")
    df_base = pd.read_csv(baseline_pred_path)
    df_static = pd.read_csv(static_features_path)
    df_truth = pd.read_csv(ground_truth_path)

    # Validate inputs
    assert "village_id" in df_base.columns and "timestamp" in df_base.columns
    assert "village_id" in df_static.columns
    assert "village_id" in df_truth.columns and "timestamp" in df_truth.columns

    # 1. Merge baseline and static features
    df_merged = pd.merge(df_base, df_static, on="village_id", how="inner")

    # 2. Merge ground truth on (village_id, timestamp)
    truth_cols = ["village_id", "timestamp", "temp_true", "rainfall_true", "humidity_true", "wind_true"]
    df_merged = pd.merge(df_merged, df_truth[truth_cols], on=["village_id", "timestamp"], how="inner")

    # 3. Spatial village-level hold-out split
    # Holding out entire villages ensures models are evaluated on unseen geographic locations!
    unique_villages = df_merged["village_id"].unique()
    np.random.seed(random_seed)
    shuffled_villages = np.random.permutation(unique_villages)
    n_train = int(len(shuffled_villages) * train_ratio)
    train_villages = set(shuffled_villages[:n_train])

    village_split_map = {vid: ("train" if vid in train_villages else "test") for vid in unique_villages}
    df_merged["split"] = df_merged["village_id"].map(village_split_map)

    # 4. Melt into long format: variable, baseline_pred, ground_truth, correction_delta
    # Variables: temp, rainfall, humidity, wind
    variables = ["temp", "rainfall", "humidity", "wind"]
    records = []

    for var in variables:
        pred_col = f"{var}_pred"
        true_col = f"{var}_true"

        sub_df = df_merged[[
            "village_id", "timestamp", pred_col, "elevation", "land_cover",
            "dist_to_water", true_col, "split"
        ]].copy()

        sub_df["variable"] = var
        sub_df["baseline_pred"] = sub_df[pred_col]
        sub_df["ground_truth"] = sub_df[true_col]
        sub_df["correction_delta"] = sub_df["ground_truth"] - sub_df["baseline_pred"]

        sub_df = sub_df[[
            "village_id", "timestamp", "variable", "baseline_pred", "elevation",
            "land_cover", "dist_to_water", "ground_truth", "correction_delta", "split"
        ]]
        records.append(sub_df)

    df_final = pd.concat(records, ignore_index=True)

    # Verify zero missing values
    assert df_final.isnull().sum().sum() == 0, "Error: Missing values found in training dataset!"

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df_final.to_csv(output_path, index=False)

    print(f"Handoff training dataset successfully written to {output_path}")
    print(f"Total rows: {len(df_final)}")
    print(f"Split distribution: {df_final['split'].value_counts().to_dict()}")
    print(f"Variables: {df_final['variable'].unique().tolist()}")
    return df_final

if __name__ == "__main__":
    build_training_dataset()
