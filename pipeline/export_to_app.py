"""
Export Clustered Topics to Legacy Synapse App JSON Schema
Reads data/pipeline_output/Pathology/clustered_topics.json
Writes a new all_questions.json that matches the Flutter app's expectations.

The app expects:
{
  "years": [
    {
      "id": "year_2",
      "name": "2nd Year MBBS",
      "subjects": [
        {
          "id": "pathology",
          "name": "PATHOLOGY",
          "papers": [
            {
              "id": "paper_1",
              "name": "Paper 1",
              "chapters": [
                {
                  "id": "necrosis",
                  "name": "Necrosis",
                  "questions": [ ... ]
                }
              ]
            }
          ]
        }
      ]
    }
  ]
}
"""

import json
import os

INPUT_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'pipeline_output', 'Pathology', 'clustered_topics.json')
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'synapse', 'assets', 'data', 'all_questions.json')

def main():
    if not os.path.exists(INPUT_PATH):
        print(f"❌ Input not found: {INPUT_PATH}")
        return

    with open(INPUT_PATH, 'r', encoding='utf-8') as f:
        topics = json.load(f)
    
    # In the app, topics act as chapters. We'll group them under Paper 1 and Paper 2.
    # We will map "Pathology" to "year_2"
    
    p1_chapters = []
    p2_chapters = []

    for idx, t in enumerate(topics):
        topic_id = f"topic_{idx}"
        topic_name = t.get('display_title') or t.get('topic_name')
        
        # A topic contains multiple questions, which have a text, importance, tags etc
        app_questions = []
        
        # Group sub-questions to paper 1 or paper 2 based on where they appear most
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

    # Build the final hierarchy
    schema = {
        "years": [
            {
                "id": "year_2",
                "name": "2nd Year MBBS",
                "subjects": [
                    {
                        "id": "pathology",
                        "name": "PATHOLOGY",
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
    
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)
        
    print(f"✅ Migrated {len(topics)} topics to Flutter App format!")
    print(f"💾 Saved to {OUTPUT_PATH}")

if __name__ == '__main__':
    main()
