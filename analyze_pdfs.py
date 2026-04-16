"""
Analyze all downloaded PYQ PDFs to determine:
1. Which are digital text PDFs vs scanned image PDFs
2. Whether year markers can be extracted from the text
3. Page counts per year-range PDF
"""
import os
import sys
from pathlib import Path
import json

try:
    import fitz  # PyMuPDF
except ImportError:
    print("Installing PyMuPDF...")
    os.system(f"{sys.executable} -m pip install PyMuPDF")
    import fitz

source_dir = Path("data/pyq/TNMGRU/processed/subjects")

results = {
    "digital": [],
    "scanned": [],
    "mixed": [],
    "year_detection": {},
    "summary_by_range": {}
}

def analyze_pdf(pdf_path):
    """Analyze a single PDF: check if digital, extract year markers."""
    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)
    pages_with_text = 0
    year_pages = {}  # year -> list of page numbers where that year appears
    
    for page_num in range(total_pages):
        page = doc[page_num]
        text = page.get_text("text").strip()
        
        if len(text) > 50:  # meaningful text content
            pages_with_text += 1
        
        # Look for year patterns like "MAY 2023", "FEBRUARY 2022", "2021", etc.
        import re
        # Match patterns like "MAY 2023", "FEBRUARY 2024", "APRIL/MAY 2022"
        year_matches = re.findall(
            r'(?:JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER|JAN|FEB|MAR|APR|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[/\s]*(?:JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER|JAN|FEB|MAR|APR|JUN|JUL|AUG|SEP|OCT|NOV|DEC)?[,\s]*(\d{4})',
            text, re.IGNORECASE
        )
        # Also match standalone year after common exam text
        year_matches2 = re.findall(r'(?:EXAM(?:INATION)?|Q\.?P\.?\s*CODE)[^\n]*(\d{4})', text, re.IGNORECASE)
        
        all_years = set(year_matches + year_matches2)
        for yr in all_years:
            yr = yr.strip()
            if 1990 <= int(yr) <= 2026:
                if yr not in year_pages:
                    year_pages[yr] = []
                year_pages[yr].append(page_num + 1)  # 1-indexed
    
    doc.close()
    
    text_ratio = pages_with_text / total_pages if total_pages > 0 else 0
    if text_ratio > 0.8:
        pdf_type = "digital"
    elif text_ratio < 0.2:
        pdf_type = "scanned"
    else:
        pdf_type = "mixed"
    
    return {
        "total_pages": total_pages,
        "pages_with_text": pages_with_text,
        "text_ratio": round(text_ratio, 2),
        "type": pdf_type,
        "years_found": {yr: pages for yr, pages in sorted(year_pages.items())},
    }

print("=" * 80)
print("PDF ANALYSIS REPORT")
print("=" * 80)

all_analyses = {}

for subject_dir in sorted(source_dir.iterdir()):
    if not subject_dir.is_dir():
        continue
    for year_dir in sorted(subject_dir.iterdir()):
        if not year_dir.is_dir():
            continue
        for paper_dir in sorted(year_dir.iterdir()):
            if not paper_dir.is_dir():
                continue
            pdfs_dir = paper_dir / "pdfs"
            if not pdfs_dir.exists():
                continue
            for pdf_file in sorted(pdfs_dir.glob("*.pdf")):
                rel = pdf_file.relative_to(source_dir)
                analysis = analyze_pdf(pdf_file)
                all_analyses[str(rel)] = analysis

# Print summary grouped by type
print("\n--- DIGITAL PDFs (text extractable) ---")
digital_count = 0
for path, info in sorted(all_analyses.items()):
    if info["type"] == "digital":
        digital_count += 1
        years_str = ", ".join(f"{yr}(pg {','.join(map(str,pgs))})" for yr, pgs in info["years_found"].items())
        print(f"  {path} | {info['total_pages']} pages | Years: {years_str or 'none detected'}")

print(f"\n--- SCANNED PDFs (image-based) ---")
scanned_count = 0
for path, info in sorted(all_analyses.items()):
    if info["type"] == "scanned":
        scanned_count += 1
        print(f"  {path} | {info['total_pages']} pages | text_ratio={info['text_ratio']}")

print(f"\n--- MIXED PDFs ---")
mixed_count = 0
for path, info in sorted(all_analyses.items()):
    if info["type"] == "mixed":
        mixed_count += 1
        years_str = ", ".join(f"{yr}(pg {','.join(map(str,pgs))})" for yr, pgs in info["years_found"].items())
        print(f"  {path} | {info['total_pages']} pages | text_ratio={info['text_ratio']} | Years: {years_str or 'none detected'}")

print(f"\n{'='*80}")
print(f"SUMMARY: Digital={digital_count}, Scanned={scanned_count}, Mixed={mixed_count}, Total={len(all_analyses)}")
print(f"{'='*80}")

# Save full analysis to JSON
out_path = Path("data/pyq/TNMGRU/processed/pdf_analysis.json")
out_path.parent.mkdir(parents=True, exist_ok=True)
with open(out_path, 'w') as f:
    json.dump(all_analyses, f, indent=2)
print(f"\nFull analysis saved to {out_path}")
