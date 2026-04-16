"""
Stage 5: Seed MongoDB Atlas
============================
Takes clustered_topics.json and inserts into MongoDB with proper schema.

Safety: Refuses to seed if source has 0 topics.

Schema:
  topics:
    - topic_name, display_title, subject
    - chapter, paper, paper_id          ← navigation hierarchy
    - frequency_count, year_frequency   ← analytics
    - study_checklist, high_yield_angles ← study aids
    - is_high_yield (auto-calculated)   ← convenience flag

  questions:
    - topic_id (ref), question_id (deterministic hash)
    - text, subject, year, month
    - paper, paper_title, section, marks

Usage:
  python seed_mongo.py Pathology
  python seed_mongo.py --ping          # Test connection only
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


def ping():
    """Test MongoDB connectivity and print stats."""
    client = MongoClient(config.MONGO_URI.strip(), serverSelectionTimeoutMS=10000)
    try:
        client.admin.command('ping')
        db = client[config.MONGO_DB]
        print(f"✅ MongoDB connection OK — {config.MONGO_DB}")
        for coll in sorted(db.list_collection_names()):
            count = db[coll].count_documents({})
            print(f"   {coll}: {count} documents")

        # Subject breakdown
        if 'topics' in db.list_collection_names():
            pipeline = [
                {"$group": {"_id": "$subject", "topics": {"$sum": 1}, "total_q": {"$sum": "$frequency_count"}}},
                {"$sort": {"_id": 1}}
            ]
            print("\n   Subject breakdown:")
            for row in db.topics.aggregate(pipeline):
                print(f"     {row['_id']:<20} {row['topics']:>4} topics  {row['total_q']:>5} questions")

        client.close()
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        sys.exit(1)


def seed(subject):
    """Seed a subject's clustered_topics.json into MongoDB."""
    input_path = os.path.join(config.OUTPUT_DIR, subject, 'clustered_topics.json')

    if not os.path.exists(input_path):
        print(f"❌ Not found: {input_path}")
        print(f"   Run first: python canonicalize.py {subject}")
        sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        topics_data = json.load(f)

    # Safety check
    if len(topics_data) == 0:
        print(f"❌ ABORT: {input_path} has 0 topics!")
        print(f"   This would wipe production data. Fix canonicalize.py first.")
        sys.exit(1)

    total_questions = sum(t.get('frequency_count', 0) for t in topics_data)
    print(f"📚 Seeding {subject}: {len(topics_data)} topics, {total_questions} questions")

    # Connect
    client = MongoClient(config.MONGO_URI.strip(), serverSelectionTimeoutMS=10000)
    try:
        client.admin.command('ping')
        print(f"✅ Connected to {config.MONGO_DB}")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)

    db = client[config.MONGO_DB]

    # Clear existing data for this subject (idempotent)
    print(f"🗑️  Clearing existing {subject} data...")
    old_topics = db.topics.count_documents({'subject': subject})
    old_questions = db.questions.count_documents({'subject': subject})
    db.topics.delete_many({'subject': subject})
    db.questions.delete_many({'subject': subject})
    if old_topics:
        print(f"   Removed {old_topics} old topics, {old_questions} old questions")

    # ── Insert Topics & Questions ──
    topics_inserted = 0
    questions_inserted = 0

    for topic in topics_data:
        questions_list = topic.pop('questions', [])

        # Determine if high-yield (asked 3+ times)
        is_high_yield = topic.get('frequency_count', 0) >= 3

        topic_doc = {
            'topic_name': topic['topic_name'],
            'display_title': topic.get('display_title', topic['topic_name']),
            'subject': subject,
            'chapter': topic.get('chapter', 'General'),
            'paper': topic.get('paper', 'Unknown'),
            'paper_id': topic.get('paper_id', 'paper_1'),
            'frequency_count': topic.get('frequency_count', len(questions_list)),
            'is_high_yield': is_high_yield,
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
                'question_id': q.get('id', ''),
                'text': q['text'],
                'subject': subject,
                'year': q.get('year'),
                'month': q.get('month', ''),
                'paper': q.get('paper', ''),
                'paper_title': q.get('paper_title', ''),
                'section': q.get('section', ''),
                'marks': q.get('marks', 0),
            })

        if question_docs:
            db.questions.insert_many(question_docs)
            questions_inserted += len(question_docs)

    # ── Create Indexes ──
    print("📇 Creating indexes...")

    # Topics: navigate by subject → paper → chapter, sort by frequency
    db.topics.create_index('subject')
    db.topics.create_index('topic_name')
    db.topics.create_index([('subject', 1), ('paper_id', 1), ('chapter', 1)])
    db.topics.create_index([('subject', 1), ('chapter', 1)])
    db.topics.create_index([('subject', 1), ('frequency_count', -1)])
    db.topics.create_index([('subject', 1), ('is_high_yield', 1)])

    # Questions: lookup by topic, filter by subject+year
    db.questions.create_index('topic_id')
    db.questions.create_index('subject')
    db.questions.create_index([('subject', 1), ('year', -1)])
    db.questions.create_index('question_id', unique=False)

    # ── Summary ──
    print(f"\n{'='*50}")
    print(f"✅ MongoDB Seeding Complete — {subject}")
    print(f"   Topics:    {topics_inserted}")
    print(f"   Questions: {questions_inserted}")
    print(f"{'='*50}")

    # Show top topic
    sample = db.topics.find_one({'subject': subject}, sort=[('frequency_count', -1)])
    if sample:
        print(f"\n📋 Most asked topic: {sample['display_title']}")
        print(f"   Chapter:    {sample['chapter']}")
        print(f"   Paper:      {sample['paper']}")
        print(f"   Frequency:  {sample['frequency_count']} PYQs")
        print(f"   High yield: {'Yes' if sample['is_high_yield'] else 'No'}")

    # Show chapter distribution
    pipeline = [
        {"$match": {"subject": subject}},
        {"$group": {"_id": "$chapter", "count": {"$sum": 1}, "total_q": {"$sum": "$frequency_count"}}},
        {"$sort": {"total_q": -1}}
    ]
    print(f"\n  Chapter breakdown:")
    for row in db.topics.aggregate(pipeline):
        print(f"    {row['_id']:<45} {row['count']:>3} topics  {row['total_q']:>4} PYQs")

    client.close()


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--ping':
        ping()
        return

    subject = sys.argv[1] if len(sys.argv) > 1 else 'Pathology'
    seed(subject)


if __name__ == '__main__':
    main()
