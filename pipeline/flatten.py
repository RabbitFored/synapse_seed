"""
Stage 1: Flatten & Normalize
Reads all JSON question paper files for a given subject and produces
a single flat list of question dictionaries.

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


def generate_question_id(university: str, subject: str, year: int, month: str, paper: str, section: str, q_num: int, qp_code: str = "") -> str:
    """Generate a readable deterministic unique ID for each question."""
    p_norm = str(paper).upper()
    if '1' in p_norm: p_norm = 'P1'
    elif '2' in p_norm: p_norm = 'P2'
    else: p_norm = p_norm.replace(' ', '')
    
    m_norm = str(month).upper()[:3]
    sec_norm = str(section).title().replace(' ', '')
    
    qp_part = f"_{qp_code}" if qp_code else ""
    return f"{university}_{year}_{m_norm}_{subject}_{p_norm}{qp_part}_{sec_norm}_{q_num}"


def get_file_hash(filepath: str) -> str:
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        hasher.update(f.read())
    return hasher.hexdigest()


def flatten_subject(subject: str, force: bool = False) -> list[dict]:
    """Flatten all JSON files for a subject into a list of question dicts."""
    folder_name = config.get_subject_folder(subject)
    subject_dir = os.path.join(BASE_JSON_DIR, folder_name)
    if not os.path.isdir(subject_dir):
        print(f"❌ Subject directory not found: {subject_dir}")
        print(f"   (Canonical name: '{subject}' → Folder: '{folder_name}')")
        sys.exit(1)

    out_dir = os.path.join(OUTPUT_DIR, subject)
    os.makedirs(out_dir, exist_ok=True)
    manifest_path = os.path.join(out_dir, 'flatten_manifest.json')
    out_path = os.path.join(out_dir, 'flattened_questions.json')

    manifest = {}
    if not force and os.path.exists(manifest_path):
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)

    existing_questions = []
    if not force and os.path.exists(out_path):
        with open(out_path, 'r', encoding='utf-8') as f:
            existing_questions = json.load(f)
            
    # Keep track of questions belonging to unchanged files
    unchanged_files = set()

    all_questions = []
    new_manifest = {}
    
    # Collect all JSON files to process
    tasks = []
    for year_dir in sorted(os.listdir(subject_dir)):
        year_path = os.path.join(subject_dir, year_dir)
        if not os.path.isdir(year_path):
            continue

        try:
            year_int = int(year_dir)
        except ValueError:
            continue

        for json_file in sorted(os.listdir(year_path)):
            if not json_file.endswith('.json'):
                continue
                
            filepath = os.path.join(year_path, json_file)
            file_key = f"{year_dir}/{json_file}"
            tasks.append((year_int, json_file, filepath, file_key))

    # Process all files with progress bar
    try:
        from tqdm import tqdm
        has_tqdm = True
    except ImportError:
        has_tqdm = False

    iterable = tasks
    if has_tqdm:
        iterable = tqdm(tasks, desc=f"  Flattening {subject}", unit="file",
                        bar_format='{l_bar}{bar:30}{r_bar}', colour='green')
        
    for year_int, json_file, filepath, file_key in iterable:

        for json_file in sorted(os.listdir(year_path)):
            if not json_file.endswith('.json'):
                continue

            filepath = os.path.join(year_path, json_file)
            file_key = f"{year_dir}/{json_file}"
            
            try:
                current_hash = get_file_hash(filepath)
            except Exception as e:
                print(f"⚠️ Could not read {filepath}: {e}")
                continue
                
            new_manifest[file_key] = current_hash
            
            # If not forced and file hasn't changed, skip parsing
            if not force and manifest.get(file_key) == current_hash:
                unchanged_files.add(file_key)
                continue

            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                print(f"⚠️ Could not parse JSON from {filepath}: {e}")
                continue

            university = data.get('university', config.UNIVERSITY)
            raw_subject = data.get('subject', folder_name)
            file_subject = config.get_canonical_subject(raw_subject) if raw_subject != subject else subject
            file_year = data.get('year', year_int)
            file_paper = data.get('paper', json_file.replace('.json', ''))

            for session in data.get('sessions', []):
                month = session.get('month', 'UNKNOWN')
                session_year = session.get('year', file_year)
                exam_name = session.get('exam_name', '')
                is_supplementary = session.get('is_supplementary', False)
                paper_title = session.get('paper_title', '')
                max_marks = session.get('max_marks', 0)
                qp_code = session.get('qp_code', '')

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
                            university, file_subject, session_year, month, file_paper, section_type, q_num, qp_code
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
                            'qp_code': qp_code,
                            'source_file': file_key
                        })

                # ── MCQ questions ──
                for q in session.get('mcq_questions', []):
                    q_num = q.get('number', 0)
                    raw_text = q.get('text', '')
                    cleaned_text = clean_question_text(raw_text)

                    if not cleaned_text:
                        continue

                    q_id = generate_question_id(
                        university, file_subject, session_year, month, file_paper, 'MCQ', q_num, qp_code
                    )

                    all_questions.append({
                        'id': q_id,
                        'text': cleaned_text,
                        'raw_text': raw_text,
                        'options': q.get('options', {}),
                        'subject': file_subject,
                        'university': university,
                        'year': session_year,
                        'month': month,
                        'paper': file_paper,
                        'paper_title': paper_title,
                        'section': 'MCQ',
                        'marks': 1,
                        'max_marks': max_marks,
                        'exam_name': exam_name,
                        'is_supplementary': is_supplementary,
                        'qp_code': qp_code,
                        'source_file': file_key
                    })
                        
    # Combine with unchanged questions
    if existing_questions and unchanged_files:
        for q in existing_questions:
            if q.get('source_file') in unchanged_files:
                all_questions.append(q)
                
    # Save output
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(all_questions, f, indent=2, ensure_ascii=False)
        
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(new_manifest, f, indent=2)

    return all_questions


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('subject', nargs='?', default='Pathology')
    parser.add_argument('--force', action='store_true', help='Force re-flattening all files')
    args = parser.parse_args()
    
    subject = args.subject
    print(f"📚 Flattening questions for: {subject} (Force: {args.force})")

    questions = flatten_subject(subject, args.force)
    print(f"✅ Extracted {len(questions)} questions from {subject}")

    # Year range info
    if questions:
        years = sorted(set(q['year'] for q in questions))
        print(f"📅 Years: {years[0]}–{years[-1]} ({len(years)} years)")

    out_path = os.path.join(OUTPUT_DIR, subject, 'flattened_questions.json')
    print(f"💾 Saved to: {out_path}")

    # Print sample
    print(f"\n--- Sample (first 3 questions) ---")
    for q in questions[:3]:
        print(f"  [{q['id']}] [{q['year']} {q['month']}] [{q['section']}, {q['marks']}m] {q['text'][:50]}...")

    return questions


if __name__ == '__main__':
    main()
