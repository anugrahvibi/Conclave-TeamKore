"""
Configuration settings for the Backend API.
"""

import os
from pathlib import Path

# Project root: /home/athulvr/Documents/My Projects/ML
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
MLDEV1_DATA_DIR = PROJECT_ROOT / "mldev1" / "data"
ARTIFACTS_DIR = BACKEND_DIR / "artifacts"

class Settings:
    PROJECT_NAME: str = "Village-Level Weather Downscaling & Agro-Advisory API"
    VERSION: str = "1.0.0"
    API_PREFIX: str = ""
    
    # Host & Port
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # CORS
    CORS_ORIGINS: list[str] = ["*"]
    
    # Data Paths
    BLOCK_FORECAST_CSV: Path = MLDEV1_DATA_DIR / "block_forecast.csv"
    VILLAGE_CENTROIDS_CSV: Path = MLDEV1_DATA_DIR / "village_centroids.csv"
    VILLAGE_METADATA_CSV: Path = MLDEV1_DATA_DIR / "village_metadata_kerala.csv"
    VILLAGE_STATIC_FEATURES_CSV: Path = MLDEV1_DATA_DIR / "village_static_features.csv"
    VILLAGE_SOIL_DATA_CSV: Path = PROJECT_ROOT / "data" / "village_soil_data.csv"
    KERALA_GEOJSON: Path = MLDEV1_DATA_DIR / "raw" / "kerala.geojson"
    TRAINING_DATASET_CSV: Path = MLDEV1_DATA_DIR / "training_dataset.csv"
    
    # ML Artifacts
    MODEL_PATH: Path = ARTIFACTS_DIR / "correction_model.pkl"
    RULES_PATH: Path = ARTIFACTS_DIR / "advisory_rules.json"
    CONFIG_JSON: Path = PROJECT_ROOT / "mldev2" / "config.json"
    
    # IDW settings
    IDW_POWER: float = 2.0
    IDW_K_NEAREST: int = 4

settings = Settings()
