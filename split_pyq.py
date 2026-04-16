"""
Split combined year-range PDFs into individual year PDFs.
Uses year markers detected in page text to split at year boundaries.
Outputs to: data/pyq/TNMGRU/processed/subject_yr_split/<Subject>/<Year>/<paper>/
"""
import os
import sys
import re
import json
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    os.system(f"{sys.executable} -m pip install PyMuPDF")
    import fitz

from tqdm import tqdm

source_dir = Path("data/pyq/TNMGRU/processed/subjects")
target_dir = Path("data/pyq/TNMGRU/processed/subject_yr_split")
analysis_path = Path("data/pyq/TNMGRU/processed/pdf_analysis.json")

# Load analysis
with open(analysis_path) as f:
    analysis = json.load(f)

MONTH_PATTERN = re.compile(
    r'(?:JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER|'
    r'JAN|FEB|MAR|APR|JUN|JUL|AUG|SEP|OCT|NOV|DEC)'
    r'[/\s]*'
    r'(?:JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER|'
    r'JAN|FEB|MAR|APR|JUN|JUL|AUG|SEP|OCT|NOV|DEC)?'
    r'[,\s]*(\d{4})',
    re.IGNORECASE
)

EXAM_YEAR_PATTERN = re.compile(
    r'(?:EXAM(?:INATION)?|Q\.?P\.?\s*CODE)[^\n]*(\d{4})',
    re.IGNORECASE
)

def detect_year_on_page(page):
    """Detect the exam year from a single page's text."""
    text = page.get_text("text").strip()
    if len(text) < 20:
        return None
    
    matches = MONTH_PATTERN.findall(text)
    matches += EXAM_YEAR_PATTERN.findall(text)
    
    valid_years = [int(y) for y in matches if 1990 <= int(y) <= 2026]
    if valid_years:
        return max(valid_years)  # Take the latest year mentioned (handles edge cases)
    return None

def split_pdf_by_year(pdf_path, info, subject, paper, source_year_range):
    """Split a single combined PDF into per-year PDFs."""
    if info["type"] == "scanned":
        return 0  # Skip scanned PDFs
    
    years_found = info.get("years_found", {})
    if not years_found:
        return 0  # No years detected, skip
    
    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)
    
    # Build page->year mapping by detecting year on each page
    page_years = {}
    for page_num in range(total_pages):
        page = doc[page_num]
        yr = detect_year_on_page(page)
        if yr:
            page_years[page_num] = yr
    
    # For pages without a detected year, inherit from the previous page
    current_year = None
    final_mapping = {}
    for page_num in range(total_pages):
        if page_num in page_years:
            current_year = page_years[page_num]
        if current_year:
            final_mapping[page_num] = current_year
    
    # Group pages by year
    year_groups = {}
    for page_num, yr in final_mapping.items():
        if yr not in year_groups:
            year_groups[yr] = []
        year_groups[yr].append(page_num)
    
    if not year_groups:
        doc.close()
        return 0
    
    # Determine file type suffix from original filename
    fname = pdf_path.stem  # e.g., 526051_the, 526051_mcq, 525051_mbbs
    if "_mcq" in fname:
        file_type = "mcq"
    elif "_the" in fname:
        file_type = "theory"
    else:
        file_type = "combined"  # older PDFs that have theory+mcq together
    
    count = 0
    for yr, pages in sorted(year_groups.items()):
        out_dir = target_dir / subject / str(yr) / paper
        out_dir.mkdir(parents=True, exist_ok=True)
        
        out_filename = f"{subject.lower().replace(' ', '_')}_{yr}_{paper}_{file_type}.pdf"
        out_path = out_dir / out_filename
        
        if out_path.exists():
            continue
        
        new_doc = fitz.open()
        for pg in sorted(pages):
            new_doc.insert_pdf(doc, from_page=pg, to_page=pg)
        
        new_doc.save(str(out_path))
        new_doc.close()
        count += 1
    
    doc.close()
    return count

# Collect all PDFs to process
pdf_tasks = []
for rel_path, info in analysis.items():
    if info["type"] == "scanned":
        continue
    
    parts = Path(rel_path).parts
    # Structure: Subject / YearRange / Paper / pdfs / filename.pdf
    if len(parts) < 5:
        continue
    
    subject = parts[0]
    year_range = parts[1]
    paper = parts[2]
    pdf_path = source_dir / rel_path
    
    if pdf_path.exists():
        pdf_tasks.append((pdf_path, info, subject, paper, year_range))

print(f"Processing {len(pdf_tasks)} digital/mixed PDFs for year splitting...")

total_split = 0
with tqdm(total=len(pdf_tasks), desc="Splitting PDFs", unit="file") as pbar:
    for pdf_path, info, subject, paper, year_range in pdf_tasks:
        pbar.set_postfix_str(f"{subject}/{year_range}/{paper}")
        n = split_pdf_by_year(pdf_path, info, subject, paper, year_range)
        total_split += n
        pbar.update(1)

print(f"\nDone! Created {total_split} individual year PDFs.")
print(f"Output directory: {target_dir}")

# Print summary
print("\nGenerated structure:")
for subject_d in sorted(target_dir.iterdir()):
    if not subject_d.is_dir():
        continue
    years = sorted([y.name for y in subject_d.iterdir() if y.is_dir()])
    print(f"  {subject_d.name}: {', '.join(years)}")
