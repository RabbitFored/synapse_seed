"""
Stage 1: Flatten & Normalize
Reads all JSON question paper files for a given subject and produces
a single flat list of question dictionaries.

FIXED: Removed hardcoded 2016-2025 year filter — now processes ALL available years.

Output: data/pipeline_output/<Subject>/flattened_questions.json
"""

import json
import os
import re
import sys
import hashlib

import config

BASE_JSON_DIR = config.RAW_JSON_DIR
OUTPUT_DIR = config.OUTPUT_DIR


def clean_question_text(text: str) -> str:
    """Remove leading question numbers, trailing asterisks, and extra whitespace."""
    text = re.sub(r'^\d+\.\s*', '', text.strip())
    text = re.sub(r'\*+$', '', text).strip()
    return text


def generate_question_id(subject: str, year: int, paper: str, month: str, section: str, q_num: int) -> str:
    """Generate a deterministic unique ID for each question."""
    raw = f"{subject}_{year}_{paper}_{month}_{section}_{q_num}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def flatten_subject(subject: str) -> list[dict]:
    """Flatten all JSON files for a subject into a list of question dicts."""
    subject_dir = os.path.join(BASE_JSON_DIR, subject)
    if not os.path.isdir(subject_dir):
        print(f"❌ Subject directory not found: {subject_dir}")
        sys.exit(1)

    all_questions = []

    for year_dir in sorted(os.listdir(subject_dir)):
        year_path = os.path.join(subject_dir, year_dir)
        if not os.path.isdir(year_path):
            continue

        # FIXED: Accept any valid numeric year (no hardcoded range)
        try:
            year_int = int(year_dir)
        except ValueError:
            continue  # Skip non-numeric year directories

        for json_file in sorted(os.listdir(year_path)):
            if not json_file.endswith('.json'):
                continue

            filepath = os.path.join(year_path, json_file)
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            university = data.get('university', 'TNMGRMU')
            file_subject = data.get('subject', subject)
            file_year = data.get('year', int(year_dir))
            file_paper = data.get('paper', json_file.replace('.json', ''))

            for session in data.get('sessions', []):
                month = session.get('month', 'UNKNOWN')
                session_year = session.get('year', file_year)
                exam_name = session.get('exam_name', '')
                is_supplementary = session.get('is_supplementary', False)
                paper_title = session.get('paper_title', '')
                max_marks = session.get('max_marks', 0)

                for section in session.get('theory_sections', []):
                    section_type = section.get('section', '')
                    marks_info = section.get('marks') or {}
                    marks_each = marks_info.get('each', 0)

                    for q in section.get('questions', []):
                        q_num = q.get('number', 0)
                        raw_text = q.get('text', '')
                        cleaned_text = clean_question_text(raw_text)

                        if not cleaned_text:
                            continue

                        q_id = generate_question_id(
                            file_subject, session_year, file_paper, month, section_type, q_num
                        )

                        all_questions.append({
                            'id': q_id,
                            'text': cleaned_text,
                            'raw_text': raw_text,
                            'subject': file_subject,
                            'university': university,
                            'year': session_year,
                            'month': month,
                            'paper': file_paper,
                            'paper_title': paper_title,
                            'section': section_type,
                            'marks': marks_each,
                            'max_marks': max_marks,
                            'exam_name': exam_name,
                            'is_supplementary': is_supplementary,
                        })

    return all_questions


def main():
    subject = sys.argv[1] if len(sys.argv) > 1 else 'Pathology'
    print(f"📚 Flattening questions for: {subject}")

    questions = flatten_subject(subject)
    print(f"✅ Extracted {len(questions)} questions from {subject}")

    # Year range info
    if questions:
        years = sorted(set(q['year'] for q in questions))
        print(f"📅 Years: {years[0]}–{years[-1]} ({len(years)} years)")

    # Save output
    out_dir = os.path.join(OUTPUT_DIR, subject)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, 'flattened_questions.json')

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(questions, f, indent=2, ensure_ascii=False)

    print(f"💾 Saved to: {out_path}")

    # Print sample
    print(f"\n--- Sample (first 3 questions) ---")
    for q in questions[:3]:
        print(f"  [{q['year']} {q['month']}] [{q['section']}, {q['marks']}m] {q['text']}")

    return questions


if __name__ == '__main__':
    main()
