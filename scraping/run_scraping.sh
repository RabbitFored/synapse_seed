#!/bin/bash
# ============================================================
# Synapse PYQ Scraping Pipeline
# Downloads, organizes, splits, and extracts TNMGRMU PYQ PDFs
#
# Usage: ./run_scraping.sh
#
# Steps:
#   1. scrape_pyq.py     — Download all PDFs from TNMGRMU website
#   2. organize_pyq.py   — Organize PDFs by Subject / Year / Paper
#   3. analyze_pdfs.py   — Classify PDFs (digital / scanned / mixed)
#   4. split_pyq.py      — Split multi-year PDFs into individual years
#   5. extract_to_json.py — Parse PDFs into structured JSON
#
# Prerequisites:
#   pip install requests beautifulsoup4 PyMuPDF tqdm
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Always run from project root so that data/ directory is created there
cd "$PROJECT_ROOT"

# Activate virtual environment
if [ -f "$PROJECT_ROOT/venv/bin/activate" ]; then
    source "$PROJECT_ROOT/venv/bin/activate"
fi

echo "╔══════════════════════════════════════════════════╗"
echo "║  Synapse PYQ Scraping Pipeline                   ║"
echo "║  Source: TNMGRMU (tnmgrmu.ac.in)                 ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── Step 1: Download PDFs ──
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Step 1/5: Downloading PYQ PDFs from TNMGRMU..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python3 "$SCRIPT_DIR/scrape_pyq.py"
echo ""

# ── Step 2: Organize by Subject ──
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Step 2/5: Organizing PDFs by Subject/Year/Paper..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python3 "$SCRIPT_DIR/organize_pyq.py"
echo ""

# ── Step 3: Analyze PDFs ──
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Step 3/5: Analyzing PDFs (digital vs scanned)..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python3 "$SCRIPT_DIR/analyze_pdfs.py"
echo ""

# ── Step 4: Split multi-year PDFs ──
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Step 4/5: Splitting multi-year PDFs..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python3 "$SCRIPT_DIR/split_pyq.py"
echo ""

# ── Step 5: Extract to JSON ──
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Step 5/5: Extracting structured JSON from PDFs..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python3 "$SCRIPT_DIR/extract_to_json.py"
echo ""

echo "═══════════════════════════════════════════════════"
echo "  🎉 Scraping pipeline complete!"
echo "  Output: data/pyq/TNMGRU/processed/json/"
echo ""
echo "  Next step: Run the AI pipeline"
echo "    cd pipeline && python flatten.py Pathology"
echo "═══════════════════════════════════════════════════"
