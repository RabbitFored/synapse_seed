"""
Stage 5: Seed MongoDB
Takes the clustered_topics.json output and inserts into MongoDB.

Safety: Refuses to seed if clustered_topics.json has 0 topics.

Collections created:
  - topics: One document per canonical topic with metadata
  - questions: One document per individual PYQ, linked to topic via topic_id

Usage:
  python seed_mongo.py [Subject]
  python seed_mongo.py Pathology
"""

import json
import os
import sys

try:
    from pymongo import MongoClient
except ImportError:
    print("❌ pymongo not installed. Run: pip install pymongo")
    sys.exit(1)

import config


def main():
    subject = sys.argv[1] if len(sys.argv) > 1 else 'Pathology'
    input_path = os.path.join(config.OUTPUT_DIR, subject, 'clustered_topics.json')

    if not os.path.exists(input_path):
        print(f"❌ Clustered topics not found at: {input_path}")
        print(f"   Run canonicalize.py first: python canonicalize.py {subject}")
        sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        topics_data = json.load(f)

    # ── Safety check: prevent seeding empty data ──
    if len(topics_data) == 0:
        print(f"❌ ABORT: clustered_topics.json has 0 topics for {subject}!")
        print(f"   This would wipe existing production data. Fix canonicalize first.")
        sys.exit(1)

    print(f"📚 Seeding MongoDB with {len(topics_data)} topics for: {subject}")

    # Connect to MongoDB
    mongo_uri = config.MONGO_URI.strip()
    db_name = config.MONGO_DB

    print(f"🔌 Connecting to: {db_name}")
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=10000)

    try:
        client.admin.command('ping')
        print("✅ MongoDB connection successful!")
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        print(f"   Check MONGO_URI in .env and verify IP whitelist on Atlas")
        sys.exit(1)

    db = client[db_name]

    # Clear existing data for this subject (idempotent re-runs)
    print(f"🗑️  Clearing existing data for {subject}...")
    db.topics.delete_many({'subject': subject})
    db.questions.delete_many({'subject': subject})

    # ── Insert Topics & Questions ──
    topics_inserted = 0
    questions_inserted = 0

    for topic in topics_data:
        questions_list = topic.pop('questions', [])

        topic_doc = {
            'topic_name': topic['topic_name'],
            'display_title': topic['display_title'],
            'subject': topic['subject'],
            'chapter': topic.get('chapter', 'General'),
            'paper': topic.get('paper', 'Unknown'),
            'paper_id': topic.get('paper_id', 'paper_1'),
            'frequency_count': topic['frequency_count'],
            'study_checklist': topic.get('study_checklist', []),
            'high_yield_angles': topic.get('high_yield_angles', []),
            'year_frequency': topic.get('year_frequency', {}),
        }

        result = db.topics.insert_one(topic_doc)
        topic_id = result.inserted_id
        topics_inserted += 1

        question_docs = []
        for q in questions_list:
            question_docs.append({
                'topic_id': topic_id,
                'question_id': q['id'],
                'text': q['text'],
                'subject': topic['subject'],
                'year': q['year'],
                'month': q['month'],
                'paper': q['paper'],
                'paper_title': q.get('paper_title', ''),
                'section': q['section'],
                'marks': q['marks'],
            })

        if question_docs:
            db.questions.insert_many(question_docs)
            questions_inserted += len(question_docs)

    # ── Create Indexes ──
    print("📇 Creating indexes...")
    db.topics.create_index('subject')
    db.topics.create_index('topic_name')
    db.topics.create_index([('subject', 1), ('paper_id', 1), ('chapter', 1)])
    db.topics.create_index([('subject', 1), ('frequency_count', -1)])
    db.questions.create_index('topic_id')
    db.questions.create_index('subject')
    db.questions.create_index([('subject', 1), ('year', -1)])

    # ── Summary ──
    print(f"\n{'='*50}")
    print(f"✅ MongoDB Seeding Complete!")
    print(f"   Database: {db_name}")
    print(f"   Topics inserted: {topics_inserted}")
    print(f"   Questions inserted: {questions_inserted}")
    print(f"{'='*50}")

    sample = db.topics.find_one({'subject': subject}, sort=[('frequency_count', -1)])
    if sample:
        print(f"\n📋 Top topic: {sample['display_title']}")
        print(f"   Chapter: {sample['chapter']}")
        print(f"   Frequency: {sample['frequency_count']} PYQs")
        print(f"   Checklist: {sample.get('study_checklist', [])[:3]}")

    client.close()


if __name__ == '__main__':
    main()
