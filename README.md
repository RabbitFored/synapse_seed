# Synapse Seed — Medical PYQ Data Pipeline

Automated pipeline to scrape, process, canonicalize, and seed MBBS exam questions (PYQs) into the **Synapse** Flutter app's MongoDB database.

Uses local AI (Ollama + `qwen3:8b`) to cluster raw exam questions into structured, syllabus-compliant study topics.

## Project Structure

```
synapse_seed/
├── .env                          # Secrets & config (gitignored)
├── .env.example                  # Template for collaborators
├── .gitignore
├── README.md
│
├── scraping/                     # Data acquisition scripts
│   ├── scrape_pyq.py             # Download PDFs from TNMGRMU website
│   ├── analyze_pdfs.py           # Classify PDFs (digital/scanned/mixed)
│   ├── split_pyq.py              # Split year-range PDFs → individual years
│   └── extract_to_json.py        # Parse PDFs → structured JSON
│
├── pipeline/                     # AI-powered processing pipeline
│   ├── config.py                 # Central config (reads .env, exposes all paths/settings)
│   ├── ollama_client.py          # Ollama API client (retry, timeout, /no_think)
│   ├── flatten.py                # Stage 1: Raw JSON → flat question list
│   ├── canonicalize.py           # Stage 2-4: Topic assignment, clustering, metadata
│   ├── seed_mongo.py             # Stage 5: Push to MongoDB Atlas
│   ├── export_to_app.py          # Export to Flutter app JSON schema
│   ├── run_pipeline.sh           # Full pipeline runner (flatten → seed)
│   └── taxonomy_keys/            # Subject-Paper-Chapter definitions
│       ├── yr1_subject_paper_chapters.json  (Anatomy, Physiology, Biochemistry)
│       └── yr2_subject_paper_chapters.json  (Pathology, Pharmacology, Microbiology)
│
├── data/                         # (gitignored) Raw PDFs, processed JSONs, pipeline output
└── venv/                         # (gitignored) Python virtual environment
```

## Quick Start

```bash
# 1. Setup
cp .env.example .env              # Fill in your Ollama URL & MongoDB URI
python3 -m venv venv
source venv/bin/activate
pip install requests python-dotenv tqdm pymongo

# 2. Run the full pipeline for a subject
cd pipeline
python flatten.py Pathology        # Stage 1: Flatten raw data
python canonicalize.py Pathology   # Stage 2-4: AI canonicalization (~25 min)
python seed_mongo.py Pathology     # Stage 5: Push to MongoDB

# Or use the shell script:
./run_pipeline.sh Pathology
```

## Taxonomy Standards

Chapter classification follows standard Indian medical textbooks:

| Subject | Textbook | Year |
|---------|----------|------|
| Anatomy | BD Chaurasia | 1st |
| Physiology | GK Pal | 1st |
| Biochemistry | DM Vasudevan | 1st |
| Pathology | Robbins | 2nd |
| Pharmacology | KD Tripathi | 2nd |
| Microbiology | Apurba Sastry | 2nd |

## Pipeline Configuration

All settings are in `pipeline/config.py` (loaded from `.env`):

| Setting | Default | Description |
|---------|---------|-------------|
| `CANON_BATCH_SIZE` | 10 | Questions per Ollama call |
| `META_BATCH_SIZE` | 5 | Topics per metadata call |
| `COOLDOWN_SECONDS` | 3 | Pause between batches |
| `REQUEST_TIMEOUT` | 300s | HTTP timeout for Ollama |

Tuned for 4-core CPU instances (Oracle Cloud free tier).
