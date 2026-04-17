#!/bin/bash
# ============================================================
# Synapse AI Pipeline — Process PYQ questions for the Synapse app
#
# Usage:
#   ./run_pipeline.sh                  # Process ALL subjects from taxonomy keys
#   ./run_pipeline.sh Pathology        # Process a single subject
#   ./run_pipeline.sh --ping           # Test MongoDB connectivity
#   ./run_pipeline.sh --config         # Show current config
#
# Stages per subject:
#   1. Flatten raw JSON → flat question list
#   2-4. AI: Canonicalize topics, cluster, generate metadata
#   5. Seed to MongoDB Atlas (upsert mode)
#
# AI Provider (set in .env):
#   gemini  — Google Gemini 2.0 Flash (recommended, ~15 min/subject)
#   groq    — Groq Cloud (fast, ~10 min/subject)
#   ollama  — Local Ollama (slow, ~2-3 hrs/subject)
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON="$PROJECT_ROOT/venv/bin/python3"

# Activate virtual environment
if [ -f "$PROJECT_ROOT/venv/bin/activate" ]; then
    source "$PROJECT_ROOT/venv/bin/activate"
fi

# Use venv python if available, otherwise system python
if [ ! -f "$PYTHON" ]; then
    PYTHON="python3"
fi

# ── Config test ──
if [ "$1" = "--config" ]; then
    $PYTHON "$SCRIPT_DIR/config.py"
    exit 0
fi

# ── MongoDB ping test ──
if [ "$1" = "--ping" ]; then
    echo "🔌 Testing MongoDB connection..."
    $PYTHON "$SCRIPT_DIR/seed_mongo.py" --ping
    exit 0
fi

# ── Discover subjects from taxonomy keys ──
get_all_subjects() {
    $PYTHON -c "
import json, os, config
subjects = []
for fname in os.listdir(config.TAXONOMY_DIR):
    if fname.endswith('.json'):
        with open(os.path.join(config.TAXONOMY_DIR, fname)) as f:
            data = json.load(f)
        for key in data:
            if key != '_meta':
                subjects.append(key)
# Print unique, preserving order
seen = set()
for s in subjects:
    if s not in seen:
        seen.add(s)
        print(s)
"
}

# ── Process a single subject ──
process_subject() {
    local SUBJECT="$1"
    local START_TIME=$(date +%s)

    echo ""
    echo "╔══════════════════════════════════════════════════╗"
    echo "║  📚 $SUBJECT"
    echo "╚══════════════════════════════════════════════════╝"

    echo ""
    echo "  ━━━ Stage 1: Flatten & Normalize ━━━"
    $PYTHON "$SCRIPT_DIR/flatten.py" "$SUBJECT"

    echo ""
    echo "  ━━━ Stage 2-4: Canonicalize + Cluster + Metadata ━━━"
    $PYTHON "$SCRIPT_DIR/canonicalize.py" "$SUBJECT"

    echo ""
    echo "  ━━━ Stage 5: Seed MongoDB (upsert) ━━━"
    $PYTHON "$SCRIPT_DIR/seed_mongo.py" "$SUBJECT"

    local END_TIME=$(date +%s)
    local ELAPSED=$(( END_TIME - START_TIME ))
    local MINS=$(( ELAPSED / 60 ))
    local SECS=$(( ELAPSED % 60 ))
    echo ""
    echo "  ⏱️  $SUBJECT completed in ${MINS}m ${SECS}s"
}

# ── Main ──
TOTAL_START=$(date +%s)

# Show provider info
echo ""
echo "  🤖 AI Provider: $($PYTHON -c 'import ai_client; print(ai_client.get_provider_info())')"
echo ""

if [ -n "$1" ] && [ "$1" != "--all" ]; then
    # Single subject mode
    echo "╔══════════════════════════════════════════════════╗"
    echo "║  Synapse AI Pipeline — Single Subject            ║"
    echo "╚══════════════════════════════════════════════════╝"
    process_subject "$1"
else
    # All subjects mode
    SUBJECTS=$(get_all_subjects)
    SUBJECT_COUNT=$(echo "$SUBJECTS" | wc -l)

    echo "╔══════════════════════════════════════════════════╗"
    echo "║  Synapse AI Pipeline — All Subjects              ║"
    echo "║  Found $SUBJECT_COUNT subjects in taxonomy keys"
    echo "╚══════════════════════════════════════════════════╝"

    echo ""
    echo "  Subjects to process:"
    INDEX=1
    echo "$SUBJECTS" | while read -r S; do
        echo "    $INDEX. $S"
        INDEX=$((INDEX + 1))
    done
    echo ""

    echo "$SUBJECTS" | while read -r SUBJECT; do
        process_subject "$SUBJECT"
    done
fi

TOTAL_END=$(date +%s)
TOTAL_ELAPSED=$(( TOTAL_END - TOTAL_START ))
TOTAL_MINS=$(( TOTAL_ELAPSED / 60 ))
TOTAL_SECS=$(( TOTAL_ELAPSED % 60 ))

echo ""
echo "═══════════════════════════════════════════════════"
echo "  🎉 Pipeline complete! Total time: ${TOTAL_MINS}m ${TOTAL_SECS}s"
echo "═══════════════════════════════════════════════════"
