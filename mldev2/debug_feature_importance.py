#!/usr/bin/env python3
"""
=============================================================================
Village-Level Weather Downscaling & Agro-Advisory Platform
Feature Importance Debug & Farmer Impact Analysis Tool
=============================================================================

This script:
1. Loads the trained ML correction model (RandomForest).
2. Computes and displays feature importances as percentages.
3. Visualizes importances using an in-terminal bar chart and saves a
   high-resolution graphical chart (PNG).
4. Explains in plain English what each feature's importance means for
   farmers and agricultural decision-making.

Usage:
    python debug_feature_importance.py
    python debug_feature_importance.py --model-path mldev2/model.pkl
    python debug_feature_importance.py --output-chart outputs/feature_importance.png
"""

import argparse
import os
import pickle
import sys
from pathlib import Path

# Feature order in training dataset and model input vector:
# [block_temp, block_rain, block_humidity, elevation, dist_to_water, land_cover]
FEATURE_CONFIG = [
    {
        "id": "elevation",
        "index": 3,
        "name": "Elevation / Altitude",
        "category": "Micro-Topography",
        "unit": "meters (m)",
        "meaning": (
            "Measures how high the village is above sea level. Because air cools "
            "rapidly with altitude (adiabatic lapse rate ~6.5°C per 1,000m), mountain "
            "slopes and plateau villages are significantly cooler than valley bottoms "
            "under the exact same regional forecast."
        ),
        "farmer_impact": (
            "Directly controls frost danger, heat accumulation (growing degree days), "
            "and disease susceptibility. A regional block forecast of 28°C might feel "
            "mild, but a highland farm at 800m elevation could be 22°C or lower. "
            "High elevation alerts farmers to protect tender nursery seedlings from "
            "chills and adjust harvest timings."
        ),
        "practical_advice": (
            "Highland plots should prepare frost covers and adjust pesticide spray "
            "schedules, as pest activity slows down in cooler mountain microclimates."
        ),
    },
    {
        "id": "dist_to_water",
        "index": 4,
        "name": "Distance to Water Bodies",
        "category": "Hydrological Buffer",
        "unit": "kilometers (km)",
        "meaning": (
            "Measures proximity to rivers, lakes, reservoirs, or coastal backwaters. "
            "Water has high thermal inertia, moderating nearby air temperatures and "
            "supplying persistent ambient humidity."
        ),
        "farmer_impact": (
            "Farms near water bodies experience gentler temperature swings (cooler "
            "afternoons, warmer nights) and higher morning dew, reducing heat shock. "
            "Inland farms far from water heat up much faster during the day and dry out "
            "rapidly, increasing crop evapotranspiration stress."
        ),
        "practical_advice": (
            "Inland fields require earlier and more frequent irrigation during sunny "
            "stretches, along with mulching to retain precious topsoil moisture."
        ),
    },
    {
        "id": "block_temp",
        "index": 0,
        "name": "Regional Block Temperature",
        "category": "Macro Weather Baseline",
        "unit": "degrees Celsius (°C)",
        "meaning": (
            "The regional meteorological station's broad area forecast. It serves as "
            "the baseline anchor for the regional air mass before local terrain shifts it."
        ),
        "farmer_impact": (
            "Provides the overarching thermal backdrop. When the regional baseline "
            "spikes, local microclimates shift proportionally. It alerts farmers to "
            "widespread heatwaves or cold waves across the state."
        ),
        "practical_advice": (
            "Guides macro planning, such as deploying shade netting during extreme "
            "regional heatwaves or delaying transplanting until heatwaves break."
        ),
    },
    {
        "id": "block_humidity",
        "index": 2,
        "name": "Regional Block Humidity",
        "category": "Atmospheric Moisture",
        "unit": "percent (%)",
        "meaning": (
            "The broad atmospheric moisture level across the district. Controls "
            "vapor pressure deficit (VPD) and radiative heat trapping at night."
        ),
        "farmer_impact": (
            "High humidity traps night heat and keeps foliage wet for longer hours. "
            "Combined with warm temperatures, high humidity creates a high-risk breeding "
            "environment for fungal blights, mold, and bacterial pathogens."
        ),
        "practical_advice": (
            "When humidity is high, farmers should inspect leaf undersides for fungal "
            "spores and apply prophylactic organic or chemical protectants before rain."
        ),
    },
    {
        "id": "block_rain",
        "index": 1,
        "name": "Regional Block Rainfall",
        "category": "Precipitation Forecast",
        "unit": "millimeters (mm)",
        "meaning": (
            "Regional rain amount forecast by the synoptic weather model. In downscaled "
            "temperature correction, its direct weight is moderate because evaporative "
            "cooling is largely captured by humidity and terrain."
        ),
        "farmer_impact": (
            "Critical for immediate field operations: heavy rain washes away newly applied "
            "fertilizers and pesticide sprays, causing costly chemical waste and runoff."
        ),
        "practical_advice": (
            "Any imminent rain (>20mm in 24h) triggers immediate advisory to halt chemical "
            "spraying and open drainage ditches in waterlogged lowlands."
        ),
    },
    {
        "id": "land_cover",
        "index": 5,
        "name": "Local Land Cover Type",
        "category": "Surface Characteristics",
        "unit": "class (forest/plantation/urban/etc.)",
        "meaning": (
            "Classifies the immediate surface cover around the village (dense forest canopy, "
            "rubber/tea plantations, paddy wetlands, or built-up settlements)."
        ),
        "farmer_impact": (
            "Canopy cover cools the local microclimate through evapotranspiration and shade, "
            "while paved/urban surfaces store heat. In our Kerala dataset, elevation and water "
            "proximity dominate macro variance, but land cover provides localized fine-tuning."
        ),
        "practical_advice": (
            "Farms bordered by tree windbreaks or agroforestry retain better microclimatic "
            "stability than open, barren parcels."
        ),
    },
]


def find_default_model():
    """Locate the trained model file across standard project directories."""
    cwd = Path.cwd()
    script_dir = Path(__file__).resolve().parent

    candidates = [
        script_dir / "model.pkl",
        script_dir / "mldev2" / "model.pkl",
        cwd / "mldev2" / "model.pkl",
        cwd / "model.pkl",
        cwd / "backend" / "artifacts" / "correction_model.pkl",
        script_dir.parent / "backend" / "artifacts" / "correction_model.pkl",
    ]

    for cand in candidates:
        if cand.is_file():
            return cand.resolve()
    return None


def load_model_and_scaler(model_path: Path):
    """Load model dictionary from disk."""
    if not model_path.is_file():
        raise FileNotFoundError(
            f"Model artifact not found at: {model_path}\n"
            "Please ensure the model is trained first, e.g.:\n"
            "  python backend/scripts/train_and_export_ml.py"
        )

    with open(model_path, "rb") as f:
        data = pickle.load(f)

    if isinstance(data, dict) and "model" in data:
        rf_model = data["model"]
        scaler = data.get("scaler")
    else:
        rf_model = data
        scaler = None

    if not hasattr(rf_model, "feature_importances_"):
        raise ValueError(
            f"Loaded object of type {type(rf_model)} has no 'feature_importances_' attribute."
        )

    return rf_model, scaler


def extract_feature_importances(rf_model):
    """Map raw model feature importances to structured metadata."""
    raw_importances = rf_model.feature_importances_
    total_raw = sum(raw_importances) if sum(raw_importances) > 0 else 1.0

    features_out = []
    for item in FEATURE_CONFIG:
        idx = item["index"]
        val = raw_importances[idx] if idx < len(raw_importances) else 0.0
        pct = (val / total_raw) * 100.0
        features_out.append({
            **item,
            "raw_importance": float(val),
            "percentage": float(pct),
        })

    # Sort descending by importance
    features_out.sort(key=lambda x: x["percentage"], reverse=True)

    # Compute cumulative percentage
    cum = 0.0
    for feat in features_out:
        cum += feat["percentage"]
        feat["cumulative_pct"] = cum

    return features_out


def render_terminal_dashboard(features_out, model_path, rf_model):
    """Print a rich terminal visualization and summary table."""
    term_width = 80
    print("\n" + "=" * term_width)
    print("🌾  VILLAGE WEATHER DOWNSCALING — MODEL FEATURE IMPORTANCE REPORT  🌾")
    print("=" * term_width)
    print(f"📁 Model Source:     {model_path}")
    print(f"🌲 Trees in Forest:  {getattr(rf_model, 'n_estimators', 'N/A')}")
    print(f"📐 Max Depth:        {getattr(rf_model, 'max_depth', 'N/A')}")
    print(f"🎯 Target Variable:  Local Temperature Correction Delta (°C)")
    print("-" * term_width)

    print("\n📊 FEATURE IMPORTANCE SUMMARY TABLE:")
    print("┌──────┬───────────────────────────────┬──────────────────────┬─────────────┬──────────────┬──────────────────────────────────────────┐")
    print("│ Rank │ Feature Name                  │ Category             │  Importance │ Cumulative % │ Visual Relative Impact                   │")
    print("├──────┼───────────────────────────────┼──────────────────────┼─────────────┼──────────────┼──────────────────────────────────────────┤")

    max_bar_width = 40
    for rank, feat in enumerate(features_out, 1):
        pct = feat["percentage"]
        cum = feat["cumulative_pct"]
        bar_len = int(round((pct / 100.0) * max_bar_width))
        bar_str = "█" * bar_len + "░" * (max_bar_width - bar_len)
        name_str = feat["name"][:29].ljust(29)
        cat_str = feat["category"][:20].ljust(20)
        print(f"│  #{rank:<2} │ {name_str} │ {cat_str} │ {pct:>9.2f}% │ {cum:>10.2f}% │ {bar_str} │")

    print("└──────┴───────────────────────────────┴──────────────────────┴─────────────┴──────────────┴──────────────────────────────────────────┘")

    # In-terminal horizontal bar chart
    print("\n📈 IN-TERMINAL RELATIVE WEIGHT BAR CHART:")
    print("-" * term_width)
    for feat in features_out:
        pct = feat["percentage"]
        bar_len = int(round((pct / 50.0) * 45))  # scaled relative to 50%
        bar = "▓" * bar_len
        print(f"  {feat['name']:<26} │ {bar} {pct:.2f}%")
    print("-" * term_width)

    # Top drivers takeaway
    top2_pct = features_out[0]["percentage"] + features_out[1]["percentage"]
    print(f"\n💡 KEY INSIGHT:")
    print(f"   The top 2 geographic features ({features_out[0]['name']} & {features_out[1]['name']})")
    print(f"   account for {top2_pct:.1f}% of the model's total predictive power!")
    print(f"   This mathematically proves why generic district-level forecasts fail farmers:")
    print(f"   local terrain variations dramatically alter local temperatures.")


def render_farmer_explanations(features_out):
    """Print clear, actionable explanations of what each feature means for farmers."""
    print("\n" + "=" * 80)
    print("🌱 WHAT THESE FEATURE IMPORTANCES MEAN FOR FARMERS ON THE GROUND")
    print("=" * 80)

    for rank, feat in enumerate(features_out, 1):
        pct = feat["percentage"]
        print(f"\n[{rank}] {feat['name'].upper()} — {pct:.2f}% Importance (Rank #{rank})")
        print(f"    Category:     {feat['category']} ({feat['unit']})")
        print(f"    Description:  {feat['meaning']}")
        print(f"    🚜 Farmer Impact:")
        print(f"       {feat['farmer_impact']}")
        print(f"    💡 Actionable Farmer Guidance:")
        print(f"       {feat['practical_advice']}")

    print("\n" + "=" * 80)
    print("🌾 PRACTICAL ADVISORY APPLICATION SUMMARY FOR EXTENSION OFFICERS:")
    print("=" * 80)
    print("1. Micro-Climate Tuning:")
    print("   Farmers just 5 km apart often experience totally different temperatures if")
    print("   separated by 200m elevation or if one plot sits next to a backwater river.")
    print("2. Chemical Spray Savings:")
    print("   Downscaled temperatures prevent spraying during high-volatility heat hours,")
    print("   and downscaled humidity/rain warnings prevent wash-off loss.")
    print("3. Irrigation Optimization:")
    print("   Inland farms with lower humidity and higher corrected temperatures receive")
    print("   timely warnings to increase irrigation before crops exhibit leaf curl.")
    print("=" * 80 + "\n")


def generate_graphical_chart(features_out, output_image_path: Path):
    """Generate a clean, high-resolution PNG bar chart using matplotlib if available."""
    try:
        import matplotlib
        matplotlib.use("Agg")  # Non-interactive backend
        import matplotlib.pyplot as plt
    except ImportError:
        print("ℹ️ Note: 'matplotlib' is not installed. To save a PNG chart, install it via:")
        print("        pip install matplotlib")
        return None

    output_image_path.parent.mkdir(parents=True, exist_ok=True)

    names = [f["name"] for f in reversed(features_out)]
    percentages = [f["percentage"] for f in reversed(features_out)]
    categories = [f["category"] for f in reversed(features_out)]

    # Modern color palette (gradient from teal to deep forest green)
    colors = [
        "#10b981" if pct < 5 else
        "#06b6d4" if pct < 15 else
        "#3b82f6" if pct < 35 else
        "#1e3a8a"
        for pct in percentages
    ]

    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
    fig.patch.set_facecolor("#f8fafc")
    ax.set_facecolor("#ffffff")

    bars = ax.barh(names, percentages, color=colors, height=0.6, edgecolor="#cbd5e1", linewidth=1)

    # Gridlines and aesthetics
    ax.grid(axis="x", linestyle="--", alpha=0.5, color="#cbd5e1")
    ax.set_axisbelow(True)

    # Annotate percentage labels on bars
    for bar, pct, cat in zip(bars, percentages, categories):
        width = bar.get_width()
        ax.text(
            width + 0.8,
            bar.get_y() + bar.get_height() / 2,
            f"{pct:.2f}%  ({cat})",
            va="center",
            ha="left",
            fontsize=10,
            fontweight="bold",
            color="#1e293b",
        )

    # Axis limits and labels
    max_val = max(percentages)
    ax.set_xlim(0, max_val + 14)
    ax.set_xlabel("Relative Predictive Importance (%)", fontsize=12, fontweight="bold", labelpad=10)
    ax.set_title(
        "Random Forest Feature Importance: Village Temperature Correction\n"
        "Downscaling District Forecasts to Local Farm Microclimates",
        fontsize=13,
        fontweight="bold",
        pad=15,
        color="#0f172a"
    )

    # Subtle borders
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    for spine in ["bottom", "left"]:
        ax.spines[spine].set_color("#94a3b8")

    plt.tight_layout()
    plt.savefig(output_image_path, bbox_inches="tight")
    plt.close(fig)

    print(f"🖼️  Graphical chart saved to: {output_image_path.resolve()}")
    return output_image_path


def main():
    parser = argparse.ArgumentParser(
        description="Debug Feature Importance & Farmer Interpretation for Village Downscaling Model"
    )
    parser.add_argument(
        "--model-path",
        "-m",
        type=str,
        default=None,
        help="Path to trained model.pkl artifact (default: auto-detected)",
    )
    parser.add_argument(
        "--output-chart",
        "-o",
        type=str,
        default="outputs/feature_importance.png",
        help="Path to save graphical bar chart image (default: outputs/feature_importance.png)",
    )
    parser.add_argument(
        "--no-chart",
        action="store_true",
        help="Skip saving the graphical PNG chart file",
    )

    args = parser.parse_args()

    # Determine model path
    if args.model_path:
        model_path = Path(args.model_path).resolve()
    else:
        model_path = find_default_model()

    if not model_path or not model_path.is_file():
        print(f"❌ Error: Model file could not be found.")
        print("Checked paths:")
        print("  - mldev2/model.pkl")
        print("  - backend/artifacts/correction_model.pkl")
        print("Please train the model first by running:")
        print("  python backend/scripts/train_and_export_ml.py")
        sys.exit(1)

    # 1. Load trained model
    rf_model, scaler = load_model_and_scaler(model_path)

    # 2. Extract feature importances as percentages
    features_out = extract_feature_importances(rf_model)

    # 3. Print terminal dashboard and visualizations
    render_terminal_dashboard(features_out, model_path, rf_model)

    # 4. Print farmer explanations
    render_farmer_explanations(features_out)

    # 5. Generate image chart
    if not args.no_chart:
        # Determine output chart path relative to script or cwd
        chart_path = Path(args.output_chart)
        if not chart_path.is_absolute():
            # Place it inside mldev2/outputs or relative to cwd
            if (Path.cwd() / "mldev2").is_dir():
                chart_path = Path.cwd() / "mldev2" / chart_path
            else:
                chart_path = Path(__file__).resolve().parent / chart_path
        generate_graphical_chart(features_out, chart_path)


if __name__ == "__main__":
    main()
