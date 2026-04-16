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
├── scraping/                     # Phase 1: Data acquisition
│   ├── run_scraping.sh           # 🚀 Automates all 5 scraping steps
│   ├── scrape_pyq.py             # Step 1: Download PDFs from TNMGRMU
│   ├── organize_pyq.py           # Step 2: Organize by Subject/Year/Paper
│   ├── analyze_pdfs.py           # Step 3: Classify (digital/scanned/mixed)
│   ├── split_pyq.py              # Step 4: Split multi-year → individual year PDFs
│   └── extract_to_json.py        # Step 5: Parse PDFs → structured JSON
│
├── pipeline/                     # Phase 2: AI-powered processing
│   ├── run_pipeline.sh           # 🚀 Automates flatten → canonicalize → seed
│   ├── config.py                 # Central config (reads .env, exposes all paths/settings)
│   ├── ollama_client.py          # Ollama API client (retry, timeout, /no_think)
│   ├── flatten.py                # Stage 1: Raw JSON → flat question list
│   ├── canonicalize.py           # Stage 2-4: Topic assignment, clustering, metadata
│   ├── seed_mongo.py             # Stage 5: Push to MongoDB Atlas
│   ├── export_to_app.py          # Export to Flutter app JSON schema
│   └── taxonomy_keys/            # Subject-Paper-Chapter definitions
│       ├── yr1_subject_paper_chapters.json
│       └── yr2_subject_paper_chapters.json
│
├── data/                         # (gitignored) Raw PDFs, processed JSONs, pipeline output
└── venv/                         # (gitignored) Python virtual environment
```

## Quick Start

### 1. Setup
```bash
cp .env.example .env              # Fill in your Ollama URL & MongoDB URI
python3 -m venv venv
source venv/bin/activate
pip install requests python-dotenv tqdm pymongo beautifulsoup4 PyMuPDF
```

### 2. Scrape PYQs (one-time, ~10 min)
```bash
cd scraping
chmod +x run_scraping.sh
./run_scraping.sh
```

This runs all 5 steps automatically:
| Step | Script | What it does |
|------|--------|-------------|
| 1 | `scrape_pyq.py` | Downloads all PYQ PDFs from TNMGRMU website |
| 2 | `organize_pyq.py` | Copies and organizes by Subject → Year → Paper |
| 3 | `analyze_pdfs.py` | Identifies digital vs scanned PDFs |
| 4 | `split_pyq.py` | Splits combined year-range PDFs into individual years |
| 5 | `extract_to_json.py` | Parses PDFs into structured JSON question data |

### 3. Run the AI pipeline (~25 min per subject)
```bash
cd pipeline

# Run for each subject individually:
python flatten.py Pathology
python canonicalize.py Pathology
python seed_mongo.py Pathology

# Or use the automation script:
chmod +x run_pipeline.sh
./run_pipeline.sh Pathology
```

## Supported Subjects

| Year | Subject | Textbook Standard | Paper Split |
|------|---------|-------------------|-------------|
| 1st | Anatomy | BD Chaurasia | Upper/Lower Limb, Abdomen+Pelvis / Thorax, Head+Neck, Neuro |
| 1st | Physiology | GK Pal | General, Blood, GI, Renal, Endo, Repro / CVS, RS, CNS, ANS, Senses |
| 1st | Biochemistry | DM Vasudevan | Cell, Enzymes, CHO, Lipid, Oxidation, Vitamins / Protein, Nucleotide, MolBio, Clinical |
| 2nd | Pathology | Robbins | General Path + Hematology / Systemic Pathology |
| 2nd | Pharmacology | KD Tripathi | General, ANS, CNS, CVS, RS, Blood, Kidney / GI, Hormones, Antimicrobials, Chemo |
| 2nd | Microbiology | Apurba Sastry | General Micro, Immunology, Bacteriology / Virology, Parasitology, Mycology |

## Pipeline Configuration

All settings are in `pipeline/config.py` (loaded from `.env`):

| Setting | Default | Description |
|---------|---------|-------------|
| `CANON_BATCH_SIZE` | 10 | Questions per Ollama call |
| `META_BATCH_SIZE` | 5 | Topics per metadata call |
| `COOLDOWN_SECONDS` | 3 | Pause between batches |
| `REQUEST_TIMEOUT` | 300s | HTTP timeout for Ollama |

Tuned for 4-core CPU instances (Oracle Cloud free tier).
