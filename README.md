# Synapse Data Seeder Pipeline

This directory contains the automated data pipeline tools to scrape, process, canonicalize, and seed medical exam questions (PYQs) into the Synapse app's MongoDB database.

## Architecture

The pipeline uses local AI (Ollama + `qwen3:8b`) to canonicalize unorganized raw exam questions into structured, syllabus-compliant Study Topics.

```text
synapse_seed/
├── data/                    # (Git ignored) Raw pyq PDFs, flattened JSONs, and final pipeline outputs
├── venv/                    # (Git ignored) Python virtual environment
├── pipeline/                # The main pipeline scripts
│   ├── flatten.py           # Stage 1: Flattens hierarchical JSON into a flat list of questions
│   ├── canonicalize.py      # Stage 2-4: Assigns topics, clusters questions, generates metadata (uses Ollama)
│   ├── ollama_client.py     # Custom Ollama API integration with progress/retry logic
│   ├── seed_mongo.py        # Stage 5: Seeds the processed `clustered_topics.json` into MongoDB
│   ├── export_to_app.py     # Legacy export script
│   └── taxonomy_keys/       # Strict subject-paper-chapter JSON definitions based on standard textbooks
└── *.py (Root)              # Initial scraping & splitting scripts (scrape_pyq, split_pyq, etc.)
```

## How to Run

1. **Activate the Virtual Environment:**
   Make sure you activate the python environment to use the `tqdm` and `requests` libraries.
   ```bash
   source venv/bin/activate
   ```

2. **Step 1: Flatten the Data**
   Prepare the raw JSONs for the AI model:
   ```bash
   cd pipeline
   python flatten.py Pathology
   ```

3. **Step 2-4: Canonicalize & Cluster**
   This script calls the local Ollama instance. It is highly optimized for lower-resource 4-core CPUs (batch sizes of 10, `/no_think` model behavior, 5-minute timeout tolerances). It supports automatic resuming if interrupted.
   ```bash
   python canonicalize.py Pathology
   ```

4. **Step 5: Seed MongoDB**
   Verify the `.env` MongoDB URI in the parent `synapse/` folder, then push the data to production:
   ```bash
   python seed_mongo.py Pathology
   ```

## Taxonomy Standards

The app's navigation strictly adheres to proper medical textbook standards:
- **Anatomy:** BD Chaurasia Units
- **Physiology:** GK Pal Units
- **Biochemistry:** DM Vasudevan Units
- **Pathology:** Robbins Units
- **Pharmacology:** KD Tripathi Sections
- **Microbiology:** Apurba Sastry Sections

The `taxonomy_keys/` folder controls this. The AI guarantees that every clustered topic maps cleanly to exactly one of these pre-defined chapters.
