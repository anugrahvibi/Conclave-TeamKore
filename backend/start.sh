#!/usr/bin/env bash
# ============================================================================
# Turnkey Backend Deployment Script for Demo Day
# Village-Level Weather Downscaling & Agro-Advisory Platform
# AI Conclave Hackathon
# ============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "======================================================================"
echo "🌱 Launching Village Weather Downscaling & Agro-Advisory Platform"
echo "======================================================================"

# Determine Python binary: use active venv or system python3
if [ -n "$VIRTUAL_ENV" ] && [ -f "$VIRTUAL_ENV/bin/python" ]; then
    PYTHON="$VIRTUAL_ENV/bin/python"
elif [ -f "$PROJECT_ROOT/mldev1/.venv/bin/python" ]; then
    PYTHON="$PROJECT_ROOT/mldev1/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON="$(command -v python3)"
else
    echo "❌ Error: Python 3 not found!"
    exit 1
fi

echo "✓ Using Python: $PYTHON ($($PYTHON --version))"

# Check if model artifacts exist; if not, train them
ARTIFACTS_DIR="$PROJECT_ROOT/backend/artifacts"
MODEL_PKL="$ARTIFACTS_DIR/correction_model.pkl"
RULES_JSON="$ARTIFACTS_DIR/advisory_rules.json"

if [ ! -f "$MODEL_PKL" ] || [ ! -f "$RULES_JSON" ]; then
    echo "⚡ ML artifacts not found. Training correction model on Kerala dataset..."
    $PYTHON "$PROJECT_ROOT/backend/scripts/train_and_export_ml.py"
else
    echo "✓ ML correction model & rules artifacts verified."
fi

# Set default host and port if not provided
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

echo "======================================================================"
echo "🚀 Starting Uvicorn Server on http://$HOST:$PORT"
echo "📖 Swagger API Docs: http://localhost:$PORT/docs"
echo "📖 ReDoc UI:         http://localhost:$PORT/redoc"
echo "======================================================================"

export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"
exec $PYTHON -m uvicorn backend.app.main:app --host "$HOST" --port "$PORT"
