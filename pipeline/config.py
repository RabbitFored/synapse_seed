"""
Centralized Configuration for Synapse Seed Pipeline
=====================================================
Single source of truth for all paths, env vars, and settings.
All pipeline scripts import from here instead of doing their own dotenv loading.

Loads .env from the project root (synapse_seed/.env).
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
RAW_JSON_DIR = os.path.join(DATA_DIR, 'pyq', 'TNMGRU', 'processed', 'json')
TAXONOMY_DIR = os.path.join(os.path.dirname(__file__), 'taxonomy_keys')

# ── Ollama ─────────────────────────────────────────────────
OLLAMA_URL = os.environ.get('OLLAMA_API', 'http://127.0.0.1:11434').rstrip('/')
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'qwen3:8b')

# ── MongoDB ────────────────────────────────────────────────
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017')
MONGO_DB = os.environ.get('MONGO_DB', 'synapse_db')

# ── Pipeline Tuning (optimized for 4-core CPU) ─────────────
CANON_BATCH_SIZE = 5     # questions per Ollama call (canonicalization)
META_BATCH_SIZE = 3      # topics per Ollama call (metadata generation)
COOLDOWN_SECONDS = 3     # pause between batches to reduce CPU pressure
REQUEST_TIMEOUT = 300    # 5 min HTTP timeout for slow CPU inference


if __name__ == '__main__':
    print(f"Project Root:    {PROJECT_ROOT}")
    print(f"Data Dir:        {DATA_DIR}")
    print(f"Output Dir:      {OUTPUT_DIR}")
    print(f"Raw JSON Dir:    {RAW_JSON_DIR}")
    print(f"Taxonomy Dir:    {TAXONOMY_DIR}")
    print(f"Ollama URL:      {OLLAMA_URL}")
    print(f"Ollama Model:    {OLLAMA_MODEL}")
    print(f"Mongo URI:       {MONGO_URI[:30]}...")
    print(f"Mongo DB:        {MONGO_DB}")
