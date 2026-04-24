"""
Stage 5: Seed MongoDB Atlas — Upsert Mode
============================================
Takes clustered_topics.json and upserts into MongoDB with proper schema.

Safety: Refuses to seed if source has 0 topics.

Usage:
  python seed_mongo.py Pathology
  python seed_mongo.py Pathology --clean     # Delete + re-insert
  python seed_mongo.py Pathology --dry-run   # Preview changes without saving
  python seed_mongo.py Pathology --cleanup   # Remove orphaned questions
  python seed_mongo.py --ping                # Test connection only
"""

import json
import os
import sys
from collections import defaultdict, Counter

try:
    from pymongo import MongoClient, UpdateOne, DeleteOne
except ImportError:
    print("❌ pymongo not installed. Run: pip install pymongo")
    sys.exit(1)

import config
import pipeline_utils


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





def seed(subject, clean_mode=False, dry_run=False, cleanup=False):
    """Seed a subject's clustered_topics.json into MongoDB."""
    input_path = os.path.join(config.OUTPUT_DIR, subject, 'clustered_topics.json')

    if not os.path.exists(input_path):
        print(f"❌ Not found: {input_path}")
        print(f"   Run first: python canonicalize.py {subject}")
        sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        topics_data = json.load(f)

    if len(topics_data) == 0:
        print(f"❌ ABORT: {input_path} has 0 topics!")
        sys.exit(1)

    total_questions = sum(t.get('frequency_count', 0) for t in topics_data)
    mode_str = "DRY-RUN (no changes)" if dry_run else ("CLEAN (delete + insert)" if clean_mode else "UPSERT (incremental)")
    print(f"📚 Seeding {subject}: {len(topics_data)} topics, {total_questions} questions")
    print(f"   Mode: {mode_str}")

    overrides = pipeline_utils.load_overrides(subject)
    if overrides:
        print(f"   Loaded {len(overrides)} chapter overrides for {config.UNIVERSITY}")

    if dry_run:
        print("   [Dry Run] Validating topic paper assignments...")
        for topic in topics_data[:5]:
            qs = topic.get('questions', [])
            paper = pipeline_utils.resolve_paper_latest_year(qs, topic.get('chapter', ''), overrides)
            print(f"     -> '{topic['topic_name']}' assigned to {paper}")
        print("   [Dry Run] Validating questions formatting...")
        print(f"     -> First QID: {topics_data[0].get('questions', [{}])[0].get('id', 'N/A')}")
        print("   [Dry Run] Exiting.")
        return

    client = MongoClient(config.MONGO_URI.strip(), serverSelectionTimeoutMS=10000)
    try:
        client.admin.command('ping')
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)

    db = client[config.MONGO_DB]

    if clean_mode:
        print(f"🗑️  Clearing existing {subject} data...")
        old_topics = db.topics.count_documents({'subject': subject})
        old_questions = db.questions.count_documents({'subject': subject})
        db.topics.delete_many({'subject': subject})
        db.questions.delete_many({'subject': subject})
        print(f"   Removed {old_topics} old topics, {old_questions} old questions")

    topics_upserted = 0
    questions_upserted = 0
    all_seen_qids = set()

    try:
        from tqdm import tqdm
        iterable = tqdm(topics_data, desc="  Seeding MongoDB", unit="topic", 
                        bar_format='{l_bar}{bar:30}{r_bar}', colour='cyan')
    except ImportError:
        iterable = topics_data
        
    for topic in iterable:
        questions_list = topic.get('questions', [])
        is_high_yield = topic.get('frequency_count', len(questions_list)) >= 3
        
        # Data-driven paper resolution
        chapter = topic.get('chapter', 'General')
        paper_id = pipeline_utils.resolve_paper_latest_year(questions_list, chapter, overrides)
        paper_name = f"Paper {1 if '1' in str(paper_id).upper() else 2}"

        topic_filter = {
            'topic_name': topic['topic_name'],
            'subject': subject,
        }

        topic_doc = {
            'topic_name': topic['topic_name'],
            'display_title': topic.get('display_title', topic['topic_name']),
            'subject': subject,
            'chapter': chapter,
            'paper': paper_name,
            'paper_id': paper_id,
            'frequency_count': topic.get('frequency_count', len(questions_list)),
            'is_high_yield': is_high_yield,
            'study_checklist': topic.get('study_checklist', []),
            'high_yield_angles': topic.get('high_yield_angles', []),
            'year_frequency': topic.get('year_frequency', {}),
        }

        result = db.topics.update_one(topic_filter, {'$set': topic_doc}, upsert=True)
        if result.upserted_id:
            topic_id = result.upserted_id
        else:
            topic_id = db.topics.find_one(topic_filter)['_id']
        topics_upserted += 1

        if questions_list:
            q_ops = []
            for q in questions_list:
                qid = str(q.get('id', '')).strip()
                if not qid:
                    continue  # Protect against empty ID bug
                    
                all_seen_qids.add(qid)
                
                q_filter = {'question_id': qid, 'subject': subject}
                q_doc = {
                    'topic_id': topic_id,
                    'question_id': qid,
                    'text': q['text'],
                    'subject': subject,
                    'year': q.get('year'),
                    'month': q.get('month', ''),
                    'paper': q.get('paper', ''),
                    'paper_title': q.get('paper_title', ''),
                    'section': q.get('section', ''),
                    'marks': q.get('marks', 0),
                    'options': q.get('options', {}),
                }
                q_ops.append(UpdateOne(q_filter, {'$set': q_doc}, upsert=True))

            if q_ops:
                result = db.questions.bulk_write(q_ops, ordered=False)
                questions_upserted += (result.upserted_count + result.modified_count)

    if cleanup and not clean_mode:
        print(f"🧹 Running orphan cleanup...")
        db_qids = set(doc['question_id'] for doc in db.questions.find({'subject': subject}, {'question_id': 1}))
        orphans = db_qids - all_seen_qids
        if orphans:
            db.questions.delete_many({'question_id': {'$in': list(orphans)}, 'subject': subject})
            print(f"   Deleted {len(orphans)} orphaned questions.")
        else:
            print(f"   No orphans found.")

    # ── Create Indexes ──
    print("📇 Creating indexes...")
    db.topics.create_index('subject')
    db.topics.create_index('topic_name')
    db.topics.create_index([('subject', 1), ('paper_id', 1), ('chapter', 1)])
    db.topics.create_index([('subject', 1), ('chapter', 1)])
    db.topics.create_index([('subject', 1), ('frequency_count', -1)])
    db.topics.create_index([('subject', 1), ('is_high_yield', 1)])

    try:
        db.topics.create_index([('topic_name', 1), ('subject', 1)], unique=True)
    except Exception as e:
        if 'duplicate' not in str(e).lower() and 'E11000' not in str(e):
            print(f"  ⚠️ Index warning: {e}")

    db.questions.create_index('topic_id')
    db.questions.create_index('subject')
    db.questions.create_index([('subject', 1), ('year', -1)])

    try:
        db.questions.create_index([('question_id', 1), ('subject', 1)], unique=True)
    except Exception as e:
        if 'duplicate' not in str(e).lower() and 'E11000' not in str(e):
            print(f"  ⚠️ Index warning: {e}")

    actual_topics = db.topics.count_documents({'subject': subject})
    actual_questions = db.questions.count_documents({'subject': subject})

    print(f"\n{'='*50}")
    print(f"✅ MongoDB Seeding Complete — {subject}")
    print(f"   Topics in DB:    {actual_topics}")
    print(f"   Questions in DB: {actual_questions}")
    print(f"{'='*50}")

    client.close()


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('subject', nargs='?', default='Pathology')
    parser.add_argument('--ping', action='store_true')
    parser.add_argument('--clean', action='store_true', help="Delete existing subject data before seeding")
    parser.add_argument('--dry-run', action='store_true', help="Preview without making DB changes")
    parser.add_argument('--cleanup', action='store_true', help="Remove questions that exist in DB but not in source JSON")
    args = parser.parse_args()

    if args.ping:
        ping()
        return

    seed(args.subject, clean_mode=args.clean, dry_run=args.dry_run, cleanup=args.cleanup)


if __name__ == '__main__':
    main()
