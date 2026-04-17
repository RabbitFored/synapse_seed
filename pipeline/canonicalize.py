"""
Stage 2-4: Canonicalize, Cluster, and Generate Metadata
=========================================================
Uses configured AI provider (Gemini/Groq/Ollama) for topic assignment.

Key features:
  - Crash-resilient: saves progress after every batch, resumes automatically
  - Provider-agnostic: uses ai_client facade
  - FIXED: Progress bar only advances for successfully processed items
  - FIXED: Failed batches are retried before moving on
  - FIXED: Stage 4 doesn't create empty placeholders on API failure

Usage:
  python canonicalize.py Pathology
  python canonicalize.py Pharmacology
"""

import json
import os
import sys
import time
from collections import defaultdict

try:
    from tqdm import tqdm
except ImportError:
    print("❌ tqdm not installed. Run: pip install tqdm")
    sys.exit(1)

import config
import ai_client

OUTPUT_DIR = config.OUTPUT_DIR
TAXONOMY_DIR = config.TAXONOMY_DIR
CANON_BATCH_SIZE = config.CANON_BATCH_SIZE
META_BATCH_SIZE = config.META_BATCH_SIZE
COOLDOWN_SECONDS = config.COOLDOWN_SECONDS


# =====================================================
# TAXONOMY
# =====================================================

def load_taxonomy(subject):
    for fname in ['yr1_subject_paper_chapters.json', 'yr2_subject_paper_chapters.json']:
        path = os.path.join(TAXONOMY_DIR, fname)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if subject in data:
                    return data[subject]
    return None


def get_all_chapters(taxonomy):
    if not taxonomy:
        return ["General"]
    chapters = []
    for pk in ['paper_1', 'paper_2']:
        if pk in taxonomy:
            chapters.extend(taxonomy[pk].get('chapters', []))
    return chapters


def resolve_paper_for_topic(topic_questions, taxonomy):
    if not taxonomy:
        return 'paper_1', 'Unknown'

    paper_counts = defaultdict(int)
    for q in topic_questions:
        pt = (q.get('paper_title') or "").upper()
        matched = None
        for pk in ['paper_1', 'paper_2']:
            patterns = taxonomy.get(pk, {}).get('paper_title_patterns', [])
            if any(p.upper() in pt for p in patterns):
                matched = pk
                break
        if not matched:
            raw = str(q.get('paper', '')).lower()
            matched = 'paper_1' if raw == 'p1' else ('paper_2' if raw == 'p2' else None)
        if matched:
            paper_counts[matched] += 1

    if paper_counts:
        dominant = max(paper_counts, key=paper_counts.get)
        return dominant, taxonomy.get(dominant, {}).get('name', dominant)
    return 'paper_1', taxonomy.get('paper_1', {}).get('name', 'Paper 1')


# =====================================================
# PROGRESS HELPERS (crash-resilient)
# =====================================================

def load_progress(filepath):
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return {k: v for k, v in data.items() if isinstance(v, str) and v.strip()}
        except (json.JSONDecodeError, IOError):
            backup = filepath + '.bak'
            if os.path.exists(filepath):
                os.rename(filepath, backup)
                print(f"  ⚠️ Corrupted progress file backed up to {backup}")
            return {}
    return {}


def load_progress_raw(filepath):
    """Load progress without filtering (for metadata which stores dicts)."""
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            backup = filepath + '.bak'
            if os.path.exists(filepath):
                os.rename(filepath, backup)
                print(f"  ⚠️ Corrupted progress file backed up to {backup}")
            return {}
    return {}


def save_progress(filepath, data):
    """Atomic save — write to temp then rename to prevent corruption on crash."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    tmp_path = filepath + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, filepath)


# =====================================================
# PROMPT BUILDER
# =====================================================

def build_prompt(base_prompt):
    """Add provider-specific prefix if needed."""
    if config.AI_PROVIDER == 'ollama' and 'qwen' in config.OLLAMA_MODEL.lower():
        return f"/no_think\n{base_prompt}"
    return base_prompt


# =====================================================
# STAGE 2: CANONICALIZE
# =====================================================

def canonicalize_batch(questions_batch):
    """Assign canonical topics to a small batch of questions."""
    lines = [f"{q['id']}: {q['text']}" for q in questions_batch]
    text = "\n".join(lines)

    prompt = build_prompt(f"""Assign a canonical medical topic name to each question. Rules:
- Concise standard topic (e.g. "Necrosis", "Shock", "Iron Deficiency Anemia")
- Similar questions get the SAME topic name
- NOT chapter names like "General Pathology"

Return a JSON dictionary mapping the EXACT question ID from the prompt to its assigned topic name.
DO NOT use "id1" or "id2" or "question_id". Use the actual question ID provided.

Example format:
{{
  "actual_question_id_here": "Topic1",
  "another_question_id_here": "Topic2"
}}

Questions:
{text}""")

    return ai_client.generate_json(prompt)


def _extract_topic_mappings(result):
    """Extract valid {question_id: topic} mappings from AI response.
    Returns dict of valid mappings (may be empty)."""
    if not result:
        return {}

    extracted = {}

    if isinstance(result, list):
        for item in result:
            if isinstance(item, dict):
                qid = item.get("id") or item.get("question_id")
                topic = (item.get("topic") or item.get("topic_name")
                         or item.get("Topic Name") or item.get("canonical_topic"))
                if qid and topic and isinstance(topic, str):
                    extracted[str(qid)] = topic.strip()

    elif isinstance(result, dict):
        # Check if it's a single {id, topic} object
        qid = result.get("id") or result.get("question_id")
        topic = (result.get("topic") or result.get("topic_name")
                 or result.get("Topic Name") or result.get("canonical_topic"))
        if qid and topic and isinstance(topic, str) and qid != "Topic Name":
            extracted[str(qid)] = topic.strip()
        else:
            # It's a {question_id: topic_name, ...} dictionary
            skip_keys = {"id", "question_id", "topic", "topic_name",
                         "Topic Name", "canonical_topic"}
            for k, v in result.items():
                if k not in skip_keys and isinstance(v, str) and v.strip():
                    extracted[str(k)] = v.strip()

    return extracted


def run_stage2(questions, subject):
    progress_path = os.path.join(OUTPUT_DIR, subject, 'canonicalize_progress.json')
    id_to_topic = load_progress(progress_path)
    remaining = [q for q in questions if q['id'] not in id_to_topic]

    print(f"\n{'━'*60}")
    print(f"  STAGE 2: Canonicalize Topics")
    print(f"  Total: {len(questions)} | Done: {len(questions)-len(remaining)} | Remaining: {len(remaining)}")
    print(f"  Batch size: {CANON_BATCH_SIZE} | Cooldown: {COOLDOWN_SECONDS}s")
    print(f"{'━'*60}")

    if not remaining:
        print("  ✅ Already complete (resume)")
    else:
        batches = [remaining[i:i+CANON_BATCH_SIZE] for i in range(0, len(remaining), CANON_BATCH_SIZE)]
        failed_consecutive = 0
        skipped_total = 0
        MAX_CONSECUTIVE_FAILURES = 5

        with tqdm(total=len(remaining), desc="  Canonicalizing", unit="q",
                  bar_format='{l_bar}{bar:30}{r_bar}', colour='cyan') as pbar:
            for batch in batches:
                # ── Attempt 1 ──
                result = canonicalize_batch(batch)
                extracted = _extract_topic_mappings(result)

                # ── Retry if no valid mappings ──
                if not extracted:
                    failed_consecutive += 1
                    tqdm.write(f"  ⚠️ No valid mappings ({failed_consecutive}/{MAX_CONSECUTIVE_FAILURES}), retrying after {COOLDOWN_SECONDS*2}s...")
                    time.sleep(COOLDOWN_SECONDS * 2)

                    result = canonicalize_batch(batch)
                    extracted = _extract_topic_mappings(result)

                # ── Check result ──
                if not extracted:
                    failed_consecutive += 1
                    skipped_total += len(batch)

                    if failed_consecutive >= MAX_CONSECUTIVE_FAILURES:
                        tqdm.write(f"  ❌ {MAX_CONSECUTIVE_FAILURES} consecutive failures. Stopping.")
                        save_progress(progress_path, id_to_topic)
                        tqdm.write(f"  💾 Progress saved — {len(id_to_topic)}/{len(questions)} done, {skipped_total} skipped.")
                        tqdm.write(f"  🔄 Re-run to retry skipped questions.")
                        break

                    # DON'T advance progress bar — these will be retried on next run
                    tqdm.write(f"  ⚠️ Batch skipped ({len(batch)} questions) — will retry on next run")
                    time.sleep(COOLDOWN_SECONDS)
                    continue

                # ── SUCCESS: Save valid mappings ──
                failed_consecutive = 0  # Reset on success

                for qid, topic in extracted.items():
                    id_to_topic[qid] = topic

                # Only advance progress bar by the number actually mapped
                pbar.update(len(extracted))
                if len(extracted) < len(batch):
                    skipped_total += len(batch) - len(extracted)

                save_progress(progress_path, id_to_topic)
                time.sleep(COOLDOWN_SECONDS)

    # Apply results
    for q in questions:
        q['canonical_topic'] = id_to_topic.get(q['id'], 'Uncategorized')

    cat = sum(1 for q in questions if q['canonical_topic'] != 'Uncategorized')
    uncat = len(questions) - cat
    print(f"  ✅ {cat}/{len(questions)} categorized")
    if uncat > 0:
        print(f"  ⚠️ {uncat} uncategorized — re-run to retry")
    return questions


# =====================================================
# STAGE 3: CLUSTER
# =====================================================

def run_stage3(questions):
    print(f"\n{'━'*60}")
    print(f"  STAGE 3: Cluster by Topic")
    print(f"{'━'*60}")

    clusters = defaultdict(list)
    for q in questions:
        if q['canonical_topic'] != 'Uncategorized':
            clusters[q['canonical_topic']].append(q)

    sorted_topics = sorted(clusters.items(), key=lambda x: len(x[1]), reverse=True)
    print(f"  ✅ {len(sorted_topics)} unique topics")

    print(f"\n  Top 10:")
    for i, (name, qs) in enumerate(sorted_topics[:10]):
        years = sorted(set(q['year'] for q in qs))
        yr = f"{years[0]}-{years[-1]}" if len(years) > 1 else str(years[0])
        print(f"    {i+1:2}. {name:<40} {len(qs):>2} PYQs  ({yr})")

    return sorted_topics


# =====================================================
# STAGE 4: METADATA
# =====================================================

def metadata_batch(subject, topics_batch, all_chapters):
    chapters_str = " | ".join(all_chapters)
    lines = []
    for idx, (name, qs) in enumerate(topics_batch):
        sample = " ; ".join([q['text'] for q in qs[:3]])
        lines.append(f"{idx}: {name} — {sample}")
    text = "\n".join(lines)

    prompt = build_prompt(f"""You are a {subject} expert. For each topic assign metadata.

Allowed chapters: {chapters_str}

For each topic return:
- "chapter": exactly one from allowed list
- "display_title": clear title
- "study_checklist": 3-4 key points to study
- "high_yield_angles": 1-2 most asked angles

Return JSON: {{"0": {{"chapter":"...", "display_title":"...", "study_checklist":["..."], "high_yield_angles":["..."]}}, "1": {{...}}}}

{text}""")

    parsed = ai_client.generate_json(prompt)
    if not parsed:
        return None

    result = {}
    for idx_str, meta in parsed.items():
        try:
            idx = int(idx_str)
            if idx < len(topics_batch) and isinstance(meta, dict):
                name = topics_batch[idx][0]
                ch = meta.get('chapter', '')
                if ch not in all_chapters:
                    ch = all_chapters[0] if all_chapters else 'General'
                meta['chapter'] = ch
                result[name] = meta
        except (ValueError, IndexError, AttributeError):
            pass
    return result


def _is_valid_metadata(meta):
    """Check if a metadata entry has real content (not just a placeholder)."""
    if not isinstance(meta, dict):
        return False
    checklist = meta.get('study_checklist', [])
    return isinstance(checklist, list) and len(checklist) > 0


def run_stage4(sorted_topics, subject, taxonomy):
    metadata_path = os.path.join(OUTPUT_DIR, subject, 'metadata_progress.json')
    existing = load_progress_raw(metadata_path)
    all_chapters = get_all_chapters(taxonomy)

    needs_work = [(n, q) for n, q in sorted_topics
                  if n not in existing or not _is_valid_metadata(existing.get(n))]

    print(f"\n{'━'*60}")
    print(f"  STAGE 4: Generate Metadata")
    print(f"  Total: {len(sorted_topics)} | Need work: {len(needs_work)}")
    print(f"  Batch size: {META_BATCH_SIZE} | Cooldown: {COOLDOWN_SECONDS}s")
    print(f"{'━'*60}")

    if not needs_work:
        print("  ✅ Already complete (resume)")
    else:
        batches = [needs_work[i:i+META_BATCH_SIZE] for i in range(0, len(needs_work), META_BATCH_SIZE)]
        failed_consecutive = 0
        skipped_total = 0
        MAX_CONSECUTIVE_FAILURES = 5

        with tqdm(total=len(needs_work), desc="  Metadata", unit="topic",
                  bar_format='{l_bar}{bar:30}{r_bar}', colour='green') as pbar:
            for batch in batches:
                # ── Attempt 1 ──
                result = metadata_batch(subject, batch, all_chapters)

                # ── Retry if failed ──
                if result is None:
                    failed_consecutive += 1
                    tqdm.write(f"  ⚠️ Failed ({failed_consecutive}/{MAX_CONSECUTIVE_FAILURES}), retrying after {COOLDOWN_SECONDS*2}s...")
                    time.sleep(COOLDOWN_SECONDS * 2)
                    result = metadata_batch(subject, batch, all_chapters)

                # ── Check result ──
                if result is None:
                    failed_consecutive += 1
                    skipped_total += len(batch)

                    if failed_consecutive >= MAX_CONSECUTIVE_FAILURES:
                        tqdm.write(f"  ❌ {MAX_CONSECUTIVE_FAILURES} consecutive failures. Stopping.")
                        save_progress(metadata_path, existing)
                        tqdm.write(f"  💾 Progress saved. Re-run to retry {skipped_total} skipped topics.")
                        break

                    # DON'T advance progress bar — will retry on next run
                    tqdm.write(f"  ⚠️ Batch skipped ({len(batch)} topics) — will retry on next run")
                    time.sleep(COOLDOWN_SECONDS)
                    continue

                # ── SUCCESS: Save valid metadata ──
                failed_consecutive = 0
                mapped_count = 0

                for name, _ in batch:
                    if name in result and _is_valid_metadata(result[name]):
                        existing[name] = result[name]
                        mapped_count += 1
                    # DON'T create empty placeholders for missing topics
                    # They'll be retried on next run

                pbar.update(mapped_count)
                if mapped_count < len(batch):
                    skipped_total += len(batch) - mapped_count

                save_progress(metadata_path, existing)
                time.sleep(COOLDOWN_SECONDS)

    if skipped_total > 0:
        print(f"  ⚠️ {skipped_total} topics skipped — re-run to retry")

    return existing


# =====================================================
# BUILD OUTPUT
# =====================================================

def build_output(sorted_topics, metadata, subject, taxonomy):
    print(f"\n{'━'*60}")
    print(f"  BUILDING FINAL OUTPUT")
    print(f"{'━'*60}")

    output = []
    for name, qs in tqdm(sorted_topics, desc="  Assembling", unit="topic",
                          bar_format='{l_bar}{bar:30}{r_bar}', colour='yellow'):
        meta = metadata.get(name, {})
        year_freq = defaultdict(int)
        for q in qs:
            year_freq[q['year']] += 1

        paper_id, paper_name = resolve_paper_for_topic(qs, taxonomy)

        output.append({
            'topic_name': name,
            'display_title': meta.get('display_title', name),
            'subject': subject,
            'chapter': meta.get('chapter', 'General'),
            'paper': paper_name,
            'paper_id': paper_id,
            'frequency_count': len(qs),
            'study_checklist': meta.get('study_checklist', []),
            'high_yield_angles': meta.get('high_yield_angles', []),
            'year_frequency': dict(sorted(year_freq.items())),
            'questions': [{
                'id': q['id'], 'text': q['text'], 'year': q['year'],
                'month': q['month'], 'paper': q['paper'],
                'paper_title': q.get('paper_title', ''),
                'section': q['section'], 'marks': q['marks'],
            } for q in qs]
        })

    out_path = os.path.join(OUTPUT_DIR, subject, 'clustered_topics.json')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Summary
    ch_dist = defaultdict(int)
    for t in output:
        ch_dist[t['chapter']] += 1
    total_q = sum(t['frequency_count'] for t in output)

    print(f"\n{'═'*60}")
    print(f"  ✅ DONE — {subject}")
    print(f"{'═'*60}")
    print(f"  Topics:    {len(output)}")
    print(f"  Questions: {total_q}")
    print(f"  Output:    {out_path}")
    print(f"\n  Chapter Distribution:")
    for ch, cnt in sorted(ch_dist.items(), key=lambda x: -x[1]):
        print(f"    {ch:<45} {cnt:>3} topics")
    print(f"{'═'*60}\n")


# =====================================================
# MAIN
# =====================================================

def main():
    subject = sys.argv[1] if len(sys.argv) > 1 else 'Pathology'
    input_path = os.path.join(OUTPUT_DIR, subject, 'flattened_questions.json')

    if not os.path.exists(input_path):
        print(f"❌ Not found: {input_path}")
        print(f"   Run first: python flatten.py '{subject}'")
        sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        questions = json.load(f)

    taxonomy = load_taxonomy(subject)

    provider_info = ai_client.get_provider_info()
    print(f"\n{'═'*60}")
    print(f"  SYNAPSE PIPELINE — {subject}")
    print(f"  Questions: {len(questions)} | AI: {provider_info}")
    print(f"  Batch:     canon={CANON_BATCH_SIZE}, meta={META_BATCH_SIZE}")
    print(f"  Cooldown:  {COOLDOWN_SECONDS}s")

    # Estimate time based on provider
    if config.AI_PROVIDER == 'ollama':
        est_secs = (len(questions) // CANON_BATCH_SIZE * 40) + (len(questions) // 3 // META_BATCH_SIZE * 60)
    else:
        est_secs = (len(questions) // CANON_BATCH_SIZE * (COOLDOWN_SECONDS + 3)) + (len(questions) // 3 // META_BATCH_SIZE * (COOLDOWN_SECONDS + 3))
    est_mins = est_secs // 60
    print(f"  Est. time: ~{est_mins} minutes")
    print(f"{'═'*60}")

    questions = run_stage2(questions, subject)
    sorted_topics = run_stage3(questions)
    metadata = run_stage4(sorted_topics, subject, taxonomy)
    build_output(sorted_topics, metadata, subject, taxonomy)


if __name__ == '__main__':
    main()
