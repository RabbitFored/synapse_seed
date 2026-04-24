"""
Centralized Configuration for Synapse Seed Pipeline
=====================================================
Single source of truth for all paths, env vars, and settings.

Supports 3 AI providers: gemini (recommended), groq, ollama

LICENSING (all models verified for commercial use):
  Gemini mode → gemma-3-27b-it  : Apache 2.0 (fully open)
  Groq mode   → llama-3.1-8b    : Meta Community License (commercial OK, <700M MAU)
  Ollama mode → qwen3:8b        : Apache 2.0 (fully open)

  Note: Google AI Studio free tier — Google may use prompts/outputs for training.
        Since we process public exam questions (not proprietary data), this is acceptable.
        For paid tier: data is NOT used for training.
"""

import os

try:
    from dotenv import load_dotenv
    _project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    _env_path = os.path.join(_project_root, '.env')
    load_dotenv(_env_path)
except ImportError:
    pass

# ── Project Paths ──────────────────────────────────────────
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
OUTPUT_DIR = os.path.join(DATA_DIR, 'pipeline_output')
RAW_JSON_DIR = os.path.join(DATA_DIR, 'pyq', '{university}', 'processed', 'json')
TAXONOMY_DIR = os.path.join(os.path.dirname(__file__), 'taxonomy_keys')
OVERRIDES_DIR = os.path.join(TAXONOMY_DIR, 'overrides')

# ── University settings ────────────────────────────────────
UNIVERSITY = os.environ.get('UNIVERSITY', 'TNMGRU')
RAW_JSON_DIR = RAW_JSON_DIR.format(university=UNIVERSITY)

# ── Subject Name Mapping ──────────────────────────────────
# Maps canonical taxonomy names → actual data folder names.
# Only subjects with mismatched names need to be listed here.
# If a subject is NOT in this map, it uses its taxonomy name as-is.
SUBJECT_FOLDER_MAP = {
    'Forensic Medicine and Toxicology': 'Forensic Medicine',
    'Obstetrics and Gynaecology': 'Obstetrics & Gynaecology',
    'Ophthalmology': 'Opthalmology',
    'ENT': 'Oto-Rhino-Laryngology',
    'Paediatrics': 'Pediatrics',
}

# Reverse map: folder name → canonical taxonomy name
FOLDER_SUBJECT_MAP = {v: k for k, v in SUBJECT_FOLDER_MAP.items()}


def get_subject_folder(canonical_name):
    """Get the actual data folder name for a canonical taxonomy subject name."""
    return SUBJECT_FOLDER_MAP.get(canonical_name, canonical_name)


def get_canonical_subject(folder_name):
    """Get the canonical taxonomy name from a data folder name."""
    return FOLDER_SUBJECT_MAP.get(folder_name, folder_name)

# ── AI Provider ────────────────────────────────────────────
# Options: 'gemini', 'groq', 'ollama'
AI_PROVIDER = os.environ.get('AI_PROVIDER', 'gemini').lower()

# ── Gemini (via Google AI Studio) ──────────────────────────
# Default: gemma-3-27b-it (Apache 2.0, best free-tier limits)
#
# Model comparison (free tier):
#   gemma-3-27b-it       : 30 RPM, 15K TPM, 14.4K RPD ← BEST for pipeline
#   gemma-3-12b-it       : 30 RPM, 15K TPM, 14.4K RPD (faster, slightly less accurate)
#   gemma-3-4b-it        : 30 RPM, 15K TPM, 14.4K RPD (fastest, less accurate)
#   gemini-2.5-flash     :  5 RPM, 250K TPM,    20 RPD ← Too few RPD!
#   gemini-2.5-flash-lite: 10 RPM, 250K TPM,    20 RPD ← Too few RPD!
#   gemini-2.0-flash     :  Test-out, limits vary
#
# License: Gemma = Apache 2.0 | Gemini API outputs = OK for commercial use
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemma-3-27b-it')

# ── Groq ───────────────────────────────────────────────────
# Default: llama-3.1-8b-instant (best throughput on free tier)
#
# Model comparison (free tier):
#   llama-3.1-8b-instant      : 30 RPM, 14.4K RPD,   6K TPM, 500K TPD ← BEST throughput
#   llama-3.3-70b-versatile   : 30 RPM,  1K RPD,  12K TPM, 100K TPD (better quality, low RPD)
#   qwen/qwen3-32b            : 60 RPM,  1K RPD,   6K TPM, 500K TPD (Apache 2.0, low RPD)
#   meta-llama/llama-4-scout  : 30 RPM,  1K RPD,  30K TPM, 500K TPD
#
# License: Llama 3.1 = Meta Community License (commercial OK, <700M MAU, needs "Built with Llama" attribution)
#          Qwen3 = Apache 2.0 (fully open)
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
GROQ_MODEL = os.environ.get('GROQ_MODEL', 'llama-3.1-8b-instant')

# ── Ollama ─────────────────────────────────────────────────
# License: Qwen3 = Apache 2.0 (fully open)
OLLAMA_URL = os.environ.get('OLLAMA_API', 'http://127.0.0.1:11434').rstrip('/')
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'qwen3:8b')

# ── MongoDB ────────────────────────────────────────────────
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017')
MONGO_DB = os.environ.get('MONGO_DB', 'synapse_db')

# ── Pipeline Tuning (per-provider optimized) ───────────────
#
# Rate limit math:
#
# GEMINI (gemma-3-27b-it): 30 RPM, 15K TPM, 14.4K RPD
#   Canon batch ~700 tokens → 15000/700 ≈ 21 req/min safe
#   Meta batch ~1500 tokens → 15000/1500 ≈ 10 req/min safe
#   Cooldown 4s → ~15 RPM effective → stays under both RPM and TPM
#   14.4K RPD ÷ ~130 requests/subject = ~110 subjects/day capacity
#
# GROQ (llama-3.1-8b-instant): 30 RPM, 6K TPM, 14.4K RPD
#   6K TPM is tight → need 3s cooldown (20 RPM × ~400 tokens ≈ 8K near limit)
#   Canon batch ~500 tokens (8B generates less) → OK at 3s cooldown
#   14.4K RPD → plenty
#
# OLLAMA (qwen3:8b on CPU): No rate limits, CPU is bottleneck
#   30-170s per request → cooldown is just for CPU breathing room
#
_PROVIDER_SETTINGS = {
    'gemini': {
        'canon_batch': 10,    # 27B handles 10 well, keeps token count moderate
        'meta_batch': 5,      # Meta batches use more tokens, keep smaller
        'cooldown': 4,        # 15 RPM effective → safe under 30 RPM and 15K TPM
        'timeout': 60,        # 27B model needs more time than small models
        'max_retries': 3,
    },
    'groq': {
        'canon_batch': 10,    # 8B model, fast inference
        'meta_batch': 5,      # Keep moderate for token budget
        'cooldown': 3,        # 20 RPM → safe under 30 RPM, ~8K < 6K TPM with headroom
        'timeout': 30,        # Groq is very fast
        'max_retries': 3,
    },
    'ollama': {
        'canon_batch': 5,     # CPU can't handle large batches
        'meta_batch': 3,      # Slow inference
        'cooldown': 3,        # Let CPU breathe
        'timeout': 300,       # 5 min for CPU inference
        'max_retries': 3,
    },
}

_settings = _PROVIDER_SETTINGS.get(AI_PROVIDER, _PROVIDER_SETTINGS['gemini'])

CANON_BATCH_SIZE = int(os.environ.get('CANON_BATCH_SIZE', _settings['canon_batch']))
META_BATCH_SIZE = int(os.environ.get('META_BATCH_SIZE', _settings['meta_batch']))
COOLDOWN_SECONDS = int(os.environ.get('COOLDOWN_SECONDS', _settings['cooldown']))
REQUEST_TIMEOUT = int(os.environ.get('REQUEST_TIMEOUT', _settings['timeout']))
MAX_RETRIES = int(os.environ.get('MAX_RETRIES', _settings['max_retries']))


if __name__ == '__main__':
    print(f"Project Root:    {PROJECT_ROOT}")
    print(f"Data Dir:        {DATA_DIR}")
    print(f"Output Dir:      {OUTPUT_DIR}")
    print(f"Raw JSON Dir:    {RAW_JSON_DIR}")
    print(f"Taxonomy Dir:    {TAXONOMY_DIR}")
    print(f"")
    print(f"AI Provider:     {AI_PROVIDER}")
    print(f"  Gemini Model:  {GEMINI_MODEL}")
    print(f"  Gemini Key:    {'✅ set' if GEMINI_API_KEY else '❌ not set'}")
    print(f"  Groq Model:    {GROQ_MODEL}")
    print(f"  Groq Key:      {'✅ set' if GROQ_API_KEY else '❌ not set'}")
    print(f"  Ollama URL:    {OLLAMA_URL}")
    print(f"  Ollama Model:  {OLLAMA_MODEL}")
    print(f"")
    print(f"Batch Sizes:     canon={CANON_BATCH_SIZE}, meta={META_BATCH_SIZE}")
    print(f"Cooldown:        {COOLDOWN_SECONDS}s")
    print(f"Timeout:         {REQUEST_TIMEOUT}s")
    print(f"Max Retries:     {MAX_RETRIES}")
    print(f"")
    print(f"Mongo URI:       {MONGO_URI[:30]}...")
    print(f"Mongo DB:        {MONGO_DB}")
    print(f"")
    print(f"═══ LICENSING ═══")
    if AI_PROVIDER == 'gemini':
        if 'gemma' in GEMINI_MODEL.lower():
            print(f"  {GEMINI_MODEL}: Apache 2.0 — ✅ Full commercial use")
        else:
            print(f"  {GEMINI_MODEL}: Google API ToS — ✅ Commercial use OK")
            print(f"  ⚠️  Free tier: Google may use prompts for training (public data = low risk)")
    elif AI_PROVIDER == 'groq':
        if 'llama' in GROQ_MODEL.lower():
            print(f"  {GROQ_MODEL}: Meta Community License — ✅ Commercial (<700M MAU)")
            print(f"  📝 Attribution: Display 'Built with Llama' in app/docs")
        elif 'qwen' in GROQ_MODEL.lower():
            print(f"  {GROQ_MODEL}: Apache 2.0 — ✅ Full commercial use")
    elif AI_PROVIDER == 'ollama':
        if 'qwen' in OLLAMA_MODEL.lower():
            print(f"  {OLLAMA_MODEL}: Apache 2.0 — ✅ Full commercial use")
