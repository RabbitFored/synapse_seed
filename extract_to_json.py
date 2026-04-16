"""
Extract structured question data from TNMGRMU split PYQ PDFs into JSON.
Handles Theory and MCQ formats, splits by exam session, and merges both.
Output: data/pyq/TNMGRU/processed/json/<Subject>/<Year>/<Paper>.json
"""

import os
import re
import sys
import json
from pathlib import Path

try:
    import fitz
except ImportError:
    os.system(f"{sys.executable} -m pip install PyMuPDF")
    import fitz

from tqdm import tqdm

source_dir = Path("data/pyq/TNMGRU/processed/subject_yr_split")
target_dir = Path("data/pyq/TNMGRU/processed/json")

MONTHS = (
    "JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER"
    "|JAN|FEB|MAR|APR|JUN|JUL|AUG|SEP|OCT|NOV|DEC"
)

# Session boundary: "THE TAMIL NADU DR. M.G.R. MEDICAL UNIVERSITY"
SESSION_HEADER_RE = re.compile(
    r"THE\s+TAMIL\s+NADU\s+DR[.\s]+M[.\s]*G[.\s]*R[.\s]+MEDICAL\s+UNIVERSITY",
    re.IGNORECASE,
)

# Month + Year in header
MONTH_YEAR_RE = re.compile(
    rf"({MONTHS})\s*/?\s*({MONTHS})?\s*,?\s*(\d{{4}})",
    re.IGNORECASE,
)

# QP Code
QP_CODE_RE = re.compile(r"Q\.?P\.?\s*Code\s*[:\s]+(\d+)", re.IGNORECASE)

# Sub code
SUB_CODE_RE = re.compile(r"Sub\.?\s*Code\s*[:\s]+(\d+)", re.IGNORECASE)

# Paper title
PAPER_TITLE_RE = re.compile(r"PAPER\s+[IVXLC]+\s*[-–]\s*(.+)", re.IGNORECASE)

# Supplementary check
SUPPL_RE = re.compile(r"SUPPLEMENT", re.IGNORECASE)

# Section headers: "I. Essay:", "II. Short Notes:", "III. Multiple Choice Questions:"
# Also handles roman numeral sections like "II. Write Short notes on:" or "III. Short Answers"
SECTION_RE = re.compile(
    r"^\s*[IVX]+\.\s+(?:Write\s+)?(?:(?:Short\s*)?Notes?(?:\s+on)?|Short\s*Answers?(?:\s*Questions?)?|Essay|Multiple\s*Choice\s*Questions?|MCQs?)[:\s]",
    re.IGNORECASE | re.MULTILINE,
)

# Marks formula: "(2 x 15 = 30)" or "(10 x 5 = 50)"
MARKS_RE = re.compile(r"\((\d+)\s*[x×]\s*(\d+)\s*=\s*(\d+)\)")

# Numbered question: "1.", "1)", "1 ."
Q_NUM_RE = re.compile(r"^\s*(\d{1,2})[.)]\s+", re.MULTILINE)

# MCQ option line: "A)" or "A. "
OPT_RE = re.compile(r"^\s*([A-D])\s*[.)]\s*(.+)", re.MULTILINE)


# ─── helpers ────────────────────────────────────────────────────────────────

def clean(s: str) -> str:
    """Collapse whitespace and strip."""
    return re.sub(r"\s+", " ", s).strip()


def extract_sessions(pdf_path: Path) -> list[str]:
    """Extract and split sessions by detecting new paper headers at page boundaries."""
    doc = fitz.open(str(pdf_path))
    sessions = []
    current = []
    
    for page in doc:
        text = page.get_text("text").strip()
        header = text[:600]
        
        has_uni = bool(re.search(r"TAMIL\s+NADU\s+DR", header, re.IGNORECASE))
        has_degree = bool(re.search(r"M\.?B\.?B\.?S\.?\s*DEGREE", header, re.IGNORECASE))
        has_month_yr = bool(MONTH_YEAR_RE.search(header))
        
        # A new session paper always starts on a fresh page with Degree/Uni AND Month/Year
        if (has_uni or has_degree) and has_month_yr:
            if current:
                sessions.append("\n".join(current))
                current = []
                
        current.append(text)
        
    if current:
        sessions.append("\n".join(current))
        
    doc.close()
    return sessions


def parse_header(session_text: str) -> dict:
    """Extract metadata from a session header block (first ~500 chars)."""
    header = session_text[:600]
    meta = {
        "month": None,
        "year": None,
        "exam_name": "M.B.B.S. DEGREE EXAMINATION",
        "is_supplementary": bool(SUPPL_RE.search(header)),
        "qp_code": None,
        "sub_code": None,
        "paper_title": None,
        "max_marks": None,
    }

    m = MONTH_YEAR_RE.search(header)
    if m:
        meta["month"] = clean(m.group(1)).upper()
        meta["year"] = int(m.group(3))

    m = QP_CODE_RE.search(session_text[:400])
    if m:
        meta["qp_code"] = m.group(1)

    m = SUB_CODE_RE.search(header)
    if m:
        meta["sub_code"] = m.group(1)

    m = PAPER_TITLE_RE.search(header)
    if m:
        meta["paper_title"] = clean(m.group(1))

    m = re.search(r"Maximum\s*[:\s]+(\d+)\s*Marks", header, re.IGNORECASE)
    if m:
        meta["max_marks"] = int(m.group(1))

    return meta


# ─── Theory parser ──────────────────────────────────────────────────────────

def _classify_section(raw_match: str) -> str:
    """Determine a clean section name from the match text."""
    t = raw_match.strip().lower()
    if "essay" in t:
        return "Essay"
    if "short answer" in t or "answer" in t:
        return "Short Answers"
    if "notes" in t:
        return "Short Notes"
    if "multiple" in t or "mcq" in t:
        return "MCQ"
    return "Unknown"


def parse_theory_session(session_text: str) -> list[dict]:
    """Parse essay + short-notes sections from a theory session."""
    sections_raw = []
    matches = list(SECTION_RE.finditer(session_text))

    for i, sec_match in enumerate(matches):
        sec_name = _classify_section(sec_match.group(0))
        # Skip MCQ sections in theory file (they appear at end in older formats)
        if sec_name == "MCQ":
            continue
        start = sec_match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(session_text)
        body = session_text[start:end]

        # Marks formula is usually at the start of each section body
        marks_match = MARKS_RE.search(body[:200])
        marks_info = None
        if marks_match:
            marks_info = {
                "count": int(marks_match.group(1)),
                "each": int(marks_match.group(2)),
                "total": int(marks_match.group(3)),
            }

        questions = _split_numbered_questions(body)
        sections_raw.append({
            "section": sec_name,
            "marks": marks_info,
            "questions": questions,
        })

    return sections_raw


def _split_numbered_questions(text: str) -> list[dict]:
    """Split text into numbered questions."""
    positions = [(m.start(), m.group(1)) for m in Q_NUM_RE.finditer(text)]
    questions = []
    for i, (start, num) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        # Skip the "N." prefix
        q_text_start = start + len(f"{num}.")
        q_body = clean(text[q_text_start:end])
        if q_body and len(q_body) > 5:
            questions.append({
                "number": int(num),
                "text": q_body,
            })
    return questions


# ─── MCQ parser ─────────────────────────────────────────────────────────────

def parse_mcq_session(session_text: str) -> list[dict]:
    """Parse MCQ section from a session block."""
    # Find the MCQ section strictly by title (prevent matching III. Short Answers)
    mcq_match = re.search(
        r"Multiple\s*Choice\s*Questions?|MCQs?",
        session_text,
        re.IGNORECASE,
    )
    if not mcq_match:
        return []

    body = session_text[mcq_match.end():]
    positions = [(m.start(), m.group(1)) for m in Q_NUM_RE.finditer(body)]

    questions = []
    for i, (start, num) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(body)
        q_chunk = body[start:end]
        # First line is question text (before first option)
        opt_matches = list(OPT_RE.finditer(q_chunk))
        if opt_matches:
            q_text_raw = q_chunk[: opt_matches[0].start()]
        else:
            q_text_raw = q_chunk

        # Strip leading number
        q_text_raw = re.sub(r"^\s*\d+[.)]\s*", "", q_text_raw)
        q_text = clean(q_text_raw)
        if not q_text or len(q_text) < 5:
            continue

        options = {}
        for opt in opt_matches:
            options[opt.group(1)] = clean(opt.group(2))

        questions.append({
            "number": int(num),
            "text": q_text,
            "options": options,
        })

    return questions


# ─── Main merging logic ──────────────────────────────────────────────────────

def process_pair(theory_path: Path | None, mcq_path: Path | None, subject: str, year: int, paper: str) -> dict:
    """Parse both files and merge by session."""
    sessions: dict[str, dict] = {}  # key: (month, qp_code or unique idx)

    def session_key(meta: dict) -> str:
        return f"{meta.get('month','UNK')}_{meta.get('qp_code','')}"

    if theory_path and theory_path.exists():
        for raw in extract_sessions(theory_path):
            meta = parse_header(raw)
            if not meta["year"]:
                continue
            key = session_key(meta)
            sessions.setdefault(key, {**meta, "theory_sections": [], "mcq_questions": []})
            sessions[key]["theory_sections"] = parse_theory_session(raw)

    if mcq_path and mcq_path.exists():
        for raw in extract_sessions(mcq_path):
            meta = parse_header(raw)
            if not meta["year"]:
                continue
            key = session_key(meta)
            sessions.setdefault(key, {**meta, "theory_sections": [], "mcq_questions": []})
            # Update any missing meta fields from mcq file
            for k, v in meta.items():
                if not sessions[key].get(k):
                    sessions[key][k] = v
            sessions[key]["mcq_questions"] = parse_mcq_session(raw)

    return {
        "university": "TNMGRMU",
        "subject": subject,
        "year": year,
        "paper": paper,
        "sessions": list(sessions.values()),
    }


def process_combined(combined_path: Path, subject: str, year: int, paper: str) -> dict:
    """Process older-format PDFs where theory+MCQ are in a single file."""
    sessions: list[dict] = []
    for raw in extract_sessions(combined_path):
        meta = parse_header(raw)
        if not meta["year"]:
            continue
        rec = {**meta, "theory_sections": [], "mcq_questions": []}
        rec["theory_sections"] = parse_theory_session(raw)
        rec["mcq_questions"] = parse_mcq_session(raw)
        sessions.append(rec)
    return {
        "university": "TNMGRMU",
        "subject": subject,
        "year": year,
        "paper": paper,
        "sessions": sessions,
    }


# ─── Batch runner ────────────────────────────────────────────────────────────

tasks = []

for subject_dir in sorted(source_dir.iterdir()):
    if not subject_dir.is_dir():
        continue
    subject = subject_dir.name
    for year_dir in sorted(subject_dir.iterdir()):
        if not year_dir.is_dir():
            continue
        try:
            year = int(year_dir.name)
        except ValueError:
            continue
        for paper_dir in sorted(year_dir.iterdir()):
            if not paper_dir.is_dir():
                continue
            paper = paper_dir.name

            theory = next(paper_dir.glob("*_theory.pdf"), None)
            mcq = next(paper_dir.glob("*_mcq.pdf"), None)
            combined = next(paper_dir.glob("*_combined.pdf"), None)

            if theory or mcq or combined:
                tasks.append((subject, year, paper, theory, mcq, combined))

print(f"Processing {len(tasks)} PDF sets into JSON...")

errors = 0
with tqdm(total=len(tasks), desc="Extracting", unit="set") as pbar:
    for subject, year, paper, theory, mcq, combined in tasks:
        pbar.set_postfix_str(f"{subject}/{year}/{paper}")
        try:
            if combined:
                data = process_combined(combined, subject, year, paper)
            else:
                data = process_pair(theory, mcq, subject, year, paper)

            out_dir = target_dir / subject / str(year)
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"{paper}.json"
            with open(out_path, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            tqdm.write(f"ERROR {subject}/{year}/{paper}: {e}")
            errors += 1
        pbar.update(1)

print(f"\nDone! {len(tasks) - errors} JSONs written, {errors} errors.")
print(f"Output: {target_dir}")
