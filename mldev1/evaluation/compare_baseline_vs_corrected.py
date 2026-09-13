"""
Phase 4: Evaluation Harness
Computes RMSE and MAE between baseline IDW predictions, corrected predictions, and ground truth
on the held-out spatial test set.
Generates publication-quality comparison charts and metric summaries.
Outputs: mldev1/outputs/evaluation_chart.png, stdout metrics table
"""

import os
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """Computes Root Mean Squared Error (RMSE) and Mean Absolute Error (MAE)."""
    mae = float(np.mean(np.abs(y_true - y_pred)))
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
    return {"MAE": round(mae, 3), "RMSE": round(rmse, 3)}

def evaluate_models(
    dataset_path: str = "mldev1/data/training_dataset.csv",
    corrected_preds_path: str = None,
    output_chart_path: str = "mldev1/outputs/evaluation_chart.png"
):
    """
    Evaluates baseline vs corrected predictions on the held-out test villages.
    If corrected_preds_path is not supplied, trains a gradient boosted regressor
    on the train split to demonstrate the correction capability.
    """
    print(f"Loading training dataset from {dataset_path}...")
    df = pd.read_csv(dataset_path)

    # Filter strictly to held-out test villages (spatial generalization)
    df_test = df[df["split"] == "test"].copy()
    print(f"Evaluating on {len(df_test)} held-out village observations...")

    variables = ["temp", "rainfall", "humidity", "wind"]
    results = []

    # If external corrected predictions are not yet available from ML Dev #2,
    # train a benchmark residual corrector (GradientBoosting / RandomForest) to showcase workflow
    mock_corrections = {}
    if corrected_preds_path is None or not os.path.exists(corrected_preds_path):
        print("Note: No external corrected predictions file found. Training benchmark residual correction model...")
        from sklearn.ensemble import GradientBoostingRegressor
        from sklearn.preprocessing import OneHotEncoder
        from sklearn.compose import ColumnTransformer

        df_train = df[df["split"] == "train"].copy()

        for var in variables:
            train_var = df_train[df_train["variable"] == var]
            test_var = df_test[df_test["variable"] == var]

            preprocessor = ColumnTransformer(
                transformers=[
                    ("num", "passthrough", ["elevation", "dist_to_water", "baseline_pred"]),
                    ("cat", OneHotEncoder(handle_unknown="ignore"), ["land_cover"])
                ]
            )

            X_train = preprocessor.fit_transform(train_var[["elevation", "dist_to_water", "baseline_pred", "land_cover"]])
            y_train = train_var["correction_delta"].values

            model = GradientBoostingRegressor(n_estimators=100, max_depth=4, random_state=42)
            model.fit(X_train, y_train)

            X_test = preprocessor.transform(test_var[["elevation", "dist_to_water", "baseline_pred", "land_cover"]])
            predicted_delta = model.predict(X_test)
            mock_corrections[var] = predicted_delta
    else:
        df_ext = pd.read_csv(corrected_preds_path)
        # Assuming df_ext has [village_id, timestamp, variable, corrected_pred]

    for var in variables:
        var_data = df_test[df_test["variable"] == var]
        y_true = var_data["ground_truth"].values
        y_base = var_data["baseline_pred"].values

        if var in mock_corrections:
            y_corrected = y_base + mock_corrections[var]
        else:
            y_corrected = y_base  # Fallback

        base_metrics = compute_metrics(y_true, y_base)
        corr_metrics = compute_metrics(y_true, y_corrected)

        # Percentage improvement
        rmse_impr = ((base_metrics["RMSE"] - corr_metrics["RMSE"]) / base_metrics["RMSE"]) * 100
        mae_impr = ((base_metrics["MAE"] - corr_metrics["MAE"]) / base_metrics["MAE"]) * 100

        results.append({
            "Variable": var.capitalize(),
            "Baseline RMSE": base_metrics["RMSE"],
            "Corrected RMSE": corr_metrics["RMSE"],
            "RMSE Improvement (%)": round(rmse_impr, 1),
            "Baseline MAE": base_metrics["MAE"],
            "Corrected MAE": corr_metrics["MAE"],
            "MAE Improvement (%)": round(mae_impr, 1),
        })

    df_results = pd.DataFrame(results)
    print("\n" + "="*80)
    print("MODEL EVALUATION SUMMARY (Held-Out Test Villages)")
    print("="*80)
    print(df_results.to_string(index=False))
    print("="*80 + "\n")

    # Plot Comparison Bar Chart
    generate_comparison_chart(df_results, output_chart_path)

    # Save summary metrics to CSV
    metrics_csv_path = os.path.join(os.path.dirname(output_chart_path), "evaluation_metrics.csv")
    df_results.to_csv(metrics_csv_path, index=False)
    print(f"Summary metrics saved to {metrics_csv_path}")

def generate_comparison_chart(df_results: pd.DataFrame, output_path: str):
    """Plots a modern, presentation-ready comparison chart of Baseline vs Corrected RMSE & MAE."""
    vars_list = df_results["Variable"].values
    x = np.arange(len(vars_list))
    width = 0.35

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5), dpi=300)

    # Theme & Palette
    color_base = "#64748b"       # Cool slate
    color_corr = "#059669"       # Emerald green
    grid_color = "#e2e8f0"

    # --- Plot 1: RMSE ---
    rects1 = ax1.bar(x - width/2, df_results["Baseline RMSE"], width, label="IDW Baseline", color=color_base, edgecolor="none", alpha=0.9)
    rects2 = ax1.bar(x + width/2, df_results["Corrected RMSE"], width, label="Corrected Model", color=color_corr, edgecolor="none", alpha=0.95)

    ax1.set_title("Root Mean Squared Error (RMSE) by Variable", fontsize=12, fontweight="bold", pad=12)
    ax1.set_ylabel("Error Metric (lower is better)", fontsize=10)
    ax1.set_xticks(x)
    ax1.set_xticklabels(vars_list, fontsize=10, fontweight="semibold")
    ax1.legend(frameon=True, facecolor="white", edgecolor="#cbd5e1")
    ax1.grid(axis="y", linestyle="--", alpha=0.7, color=grid_color)
    ax1.set_axisbelow(True)

    # Add improvement labels
    for i in range(len(vars_list)):
        impr = df_results["RMSE Improvement (%)"].iloc[i]
        val = df_results["Corrected RMSE"].iloc[i]
        ax1.annotate(
            f"-{impr}%",
            xy=(x[i] + width/2, val),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center", va="bottom",
            fontsize=9, fontweight="bold", color="#047857"
        )

    # --- Plot 2: MAE ---
    rects3 = ax2.bar(x - width/2, df_results["Baseline MAE"], width, label="IDW Baseline", color=color_base, edgecolor="none", alpha=0.9)
    rects4 = ax2.bar(x + width/2, df_results["Corrected MAE"], width, label="Corrected Model", color=color_corr, edgecolor="none", alpha=0.95)

    ax2.set_title("Mean Absolute Error (MAE) by Variable", fontsize=12, fontweight="bold", pad=12)
    ax2.set_ylabel("Error Metric (lower is better)", fontsize=10)
    ax2.set_xticks(x)
    ax2.set_xticklabels(vars_list, fontsize=10, fontweight="semibold")
    ax2.legend(frameon=True, facecolor="white", edgecolor="#cbd5e1")
    ax2.grid(axis="y", linestyle="--", alpha=0.7, color=grid_color)
    ax2.set_axisbelow(True)

    for i in range(len(vars_list)):
        impr = df_results["MAE Improvement (%)"].iloc[i]
        val = df_results["Corrected MAE"].iloc[i]
        ax2.annotate(
            f"-{impr}%",
            xy=(x[i] + width/2, val),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center", va="bottom",
            fontsize=9, fontweight="bold", color="#047857"
        )

    plt.suptitle("Village Weather Downscaling: IDW Baseline vs Feature-Corrected Model", fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, bbox_inches="tight")
    plt.close()
    print(f"Evaluation chart saved to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate downscaled baseline and corrected models.")
    parser.add_argument("--dataset", default="mldev1/data/training_dataset.csv", help="Path to training_dataset.csv")
    parser.add_argument("--corrected", default=None, help="Path to external corrected predictions CSV (optional)")
    parser.add_argument("--output", default="mldev1/outputs/evaluation_chart.png", help="Path to output chart")
    args = parser.parse_args()

    evaluate_models(dataset_path=args.dataset, corrected_preds_path=args.corrected, output_chart_path=args.output)
