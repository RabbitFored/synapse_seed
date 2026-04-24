"""
Shared utility functions for the Synapse pipeline.
Extracted to avoid code duplication across seed_mongo.py and export_to_app.py.
"""

import json
import os
from collections import defaultdict, Counter

import config


def load_overrides(subject):
    """Load manual chapter->paper overrides for the current university."""
    path = os.path.join(config.OVERRIDES_DIR, f"{config.UNIVERSITY}.json")
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get(subject, {})
        except Exception:
            pass
    return {}


def resolve_paper_latest_year(topic_questions, chapter, overrides):
    """
    Resolve paper assignment for a chapter/topic using data-driven logic.

    Priority:
    1. Override file (manual corrections)
    2. Latest year's PYQ data majority vote
    3. Next-most-recent year if latest has no paper
    4. Default P1
    """
    if chapter in overrides:
        return overrides[chapter]

    by_year = defaultdict(list)
    for q in topic_questions:
        by_year[q.get('year', 0)].append(q.get('paper', ''))

    for year in sorted(by_year.keys(), reverse=True):
        papers = [p for p in by_year[year] if p]
        if papers:
            counter = Counter(papers)
            return counter.most_common(1)[0][0]

    return 'P1'


# ── Phase/Year mapping for all 15 MBBS subjects ──
SUBJECT_PHASE_MAP = {
    # Phase 1
    'Anatomy': ('phase_1', 'Phase 1 MBBS'),
    'Physiology': ('phase_1', 'Phase 1 MBBS'),
    'Biochemistry': ('phase_1', 'Phase 1 MBBS'),
    # Phase 2
    'Pathology': ('phase_2', 'Phase 2 MBBS'),
    'Pharmacology': ('phase_2', 'Phase 2 MBBS'),
    'Microbiology': ('phase_2', 'Phase 2 MBBS'),
    'Forensic Medicine and Toxicology': ('phase_2', 'Phase 2 MBBS'),
    'Community Medicine': ('phase_2', 'Phase 2 MBBS'),
    # Phase 3 Part 1
    'Ophthalmology': ('phase_3_1', 'Phase 3 Part 1 MBBS'),
    'ENT': ('phase_3_1', 'Phase 3 Part 1 MBBS'),
    # Phase 3 Part 2
    'General Medicine': ('phase_3_2', 'Phase 3 Part 2 MBBS'),
    'General Surgery': ('phase_3_2', 'Phase 3 Part 2 MBBS'),
    'Obstetrics and Gynaecology': ('phase_3_2', 'Phase 3 Part 2 MBBS'),
    'Paediatrics': ('phase_3_2', 'Phase 3 Part 2 MBBS'),
    'Orthopaedics': ('phase_3_2', 'Phase 3 Part 2 MBBS'),
}


def get_subject_phase(subject):
    """Return (phase_id, phase_name) for a subject."""
    return SUBJECT_PHASE_MAP.get(subject, ('phase_1', 'Phase 1 MBBS'))
