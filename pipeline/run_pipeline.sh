#!/bin/bash
# ============================================================
# Synapse PYQ Pipeline — Full run for a single subject
# Usage: ./run_pipeline.sh [Subject]
# Example: ./run_pipeline.sh Pathology
# ============================================================

set -e

SUBJECT="${1:-Pathology}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Activate virtual environment
if [ -f "$PROJECT_ROOT/venv/bin/activate" ]; then
    source "$PROJECT_ROOT/venv/bin/activate"
fi

echo "╔══════════════════════════════════════════════╗"
echo "║  Synapse PYQ Seeding Pipeline                ║"
echo "║  Subject: $SUBJECT"
echo "╚══════════════════════════════════════════════╝"
echo ""

# Stage 1: Flatten
echo "━━━ Stage 1: Flatten & Normalize ━━━"
python3 "$SCRIPT_DIR/flatten.py" "$SUBJECT"
echo ""

# Stage 2-4: Canonicalize + Cluster + Metadata
echo "━━━ Stage 2-4: Canonicalize, Cluster & Generate Metadata ━━━"
python3 "$SCRIPT_DIR/canonicalize.py" "$SUBJECT"
echo ""

# Stage 5: Seed MongoDB
echo "━━━ Stage 5: Seed MongoDB ━━━"
python3 "$SCRIPT_DIR/seed_mongo.py" "$SUBJECT"
echo ""

echo "🎉 Pipeline complete for $SUBJECT!"
