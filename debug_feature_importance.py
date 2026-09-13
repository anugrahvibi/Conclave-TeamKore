#!/usr/bin/env python3
"""
Root wrapper for mldev2/debug_feature_importance.py
Allows running `python debug_feature_importance.py` directly from project root.
"""
import sys
from pathlib import Path

# Add project root and mldev2 to path
PROJECT_ROOT = Path(__file__).resolve().parent
MLDEV2_DIR = PROJECT_ROOT / "mldev2"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(MLDEV2_DIR) not in sys.path:
    sys.path.insert(0, str(MLDEV2_DIR))

from mldev2.debug_feature_importance import main

if __name__ == "__main__":
    main()
