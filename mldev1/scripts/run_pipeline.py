"""
Master Pipeline Runner for AI/ML Dev #1
Executes all phases end-to-end:
  Phase 0: Synthetic Data Generation
  Phase 1: IDW Baseline Generation
  Phase 2: Static Geo-Feature Extraction
  Phase 3: Dataset Merge & Handoff Preparation
  Phase 4: Evaluation Harness & Chart Generation
"""

import os
import sys
import time

def run_phase(phase_name: str, func):
    print("\n" + "#" * 70)
    print(f"RUNNING {phase_name.upper()}...")
    print("#" * 70)
    start = time.time()
    func()
    elapsed = time.time() - start
    print(f"✓ {phase_name} completed in {elapsed:.2f}s")

def main():
    print("=" * 70)
    print("STARTING ML DEV #1 END-TO-END PIPELINE EXECUTION")
    print("Project: Village-Level Weather Downscaling & Agro-Advisory Platform")
    print("=" * 70)

    # Ensure scripts and root are on sys.path
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    # 1. Phase 0
    from mldev1.scripts.generate_synthetic_data import main as phase0_main
    run_phase("Phase 0 — Environment & Data Setup", phase0_main)

    # 2. Phase 1
    from mldev1.models.idw_baseline import IDWBaselineModel
    def phase1_main():
        model = IDWBaselineModel()
        model.generate_all_baseline_predictions()
    run_phase("Phase 1 — IDW Interpolation Baseline", phase1_main)

    # 3. Phase 2
    from mldev1.scripts.extract_static_features import extract_static_features
    run_phase("Phase 2 — Static Feature Pipeline", extract_static_features)

    # 4. Phase 3
    from mldev1.scripts.build_training_dataset import build_training_dataset
    run_phase("Phase 3 — Baseline + Feature Merge (Handoff-Ready Dataset)", build_training_dataset)

    # 5. Phase 4
    from mldev1.evaluation.compare_baseline_vs_corrected import evaluate_models
    run_phase("Phase 4 — Evaluation Harness & Chart Generation", evaluate_models)

    print("\n" + "=" * 70)
    print("ALL PHASES COMPLETED SUCCESSFULLY!")
    print("Handoff dataset ready at: mldev1/data/training_dataset.csv")
    print("Evaluation chart ready at: mldev1/outputs/evaluation_chart.png")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    main()
