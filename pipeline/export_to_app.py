"""
Export Clustered Topics to Synapse Flutter App JSON Schema
Reads data/pipeline_output/<Subject>/clustered_topics.json
Writes a new all_questions.json that matches the Flutter app's expectations.

Usage:
  python export_to_app.py Pathology
  python export_to_app.py Pharmacology
"""

import json
import os
import sys

import config

YEAR_MAP = {
    'Anatomy': ('year_1', '1st Year MBBS'),
    'Physiology': ('year_1', '1st Year MBBS'),
    'Biochemistry': ('year_1', '1st Year MBBS'),
    'Pathology': ('year_2', '2nd Year MBBS'),
    'Pharmacology': ('year_2', '2nd Year MBBS'),
    'Microbiology': ('year_2', '2nd Year MBBS'),
}


def main():
    subject = sys.argv[1] if len(sys.argv) > 1 else 'Pathology'
    input_path = os.path.join(config.OUTPUT_DIR, subject, 'clustered_topics.json')
    output_path = os.path.join(config.PROJECT_ROOT, '..', 'synapse_api', 'data', 'all_questions.json')

    if not os.path.exists(input_path):
        print(f"❌ Input not found: {input_path}")
        return

    with open(input_path, 'r', encoding='utf-8') as f:
        topics = json.load(f)

    if not topics:
        print(f"❌ No topics found in {input_path}")
        return

    year_id, year_name = YEAR_MAP.get(subject, ('year_2', '2nd Year MBBS'))

    p1_chapters = []
    p2_chapters = []

    for idx, t in enumerate(topics):
        topic_id = f"topic_{idx}"
        topic_name = t.get('display_title') or t.get('topic_name')

        app_questions = []
        p1_count = 0
        p2_count = 0

        for q in t.get('questions', []):
            if q.get('paper') == 'p1':
                p1_count += 1
            else:
                p2_count += 1

            app_questions.append({
                "id": q.get('id'),
                "title": q.get('text')[:40] + "..." if len(q.get('text', '')) > 40 else q.get('text'),
                "type": "long" if q.get('marks', 0) >= 10 else "short",
                "tags": [str(q.get('year'))],
                "importance": "high" if t.get('frequency_count', 0) >= 3 else "normal",
                "description": q.get('text')
            })

        chapter_obj = {
            "id": topic_id,
            "name": f"{topic_name} [{t.get('frequency_count')} PYQs]",
            "questions": app_questions
        }

        if p1_count >= p2_count:
            p1_chapters.append(chapter_obj)
        else:
            p2_chapters.append(chapter_obj)

    schema = {
        "years": [
            {
                "id": year_id,
                "name": year_name,
                "subjects": [
                    {
                        "id": subject.lower(),
                        "name": subject.upper(),
                        "papers": [
                            {
                                "id": "paper_1",
                                "name": "Paper 1",
                                "chapters": p1_chapters
                            },
                            {
                                "id": "paper_2",
                                "name": "Paper 2",
                                "chapters": p2_chapters
                            }
                        ]
                    }
                ]
            }
        ]
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)

    print(f"✅ Exported {len(topics)} topics for {subject} → Flutter App format")
    print(f"   Paper 1: {len(p1_chapters)} chapters | Paper 2: {len(p2_chapters)} chapters")
    print(f"💾 Saved to {output_path}")


if __name__ == '__main__':
    main()
