# UniMate

UniMate is a Python-based pipeline for scraping Pakistani university admissions pages, parsing and normalizing content, and ingesting the data into both structured and semantic retrieval stores.

## What it does

- Scrapes admissions and program pages for: `FAST University`, `NED University`, `Habib University`, `IBA`, `SZABIST`, and `DHA Suffa`
- Extracts page content, tables, and panels
- Normalizes admissions data into canonical JSON
- Builds semantic chunks from canonical fields
- Persists structured records into SQLite
- Uploads embeddings into a Chroma vector store via Gemini/OpenAI

## Repo structure

- `requirements.txt` - Python dependencies
- `university_scraper.py` - scraping entrypoint
- `src/` - pipeline modules
  - `src/config.py` - centralized configuration
  - `src/ingest.py` - SQLite ingestion
  - `src/chunker.py` - semantic chunk generation
  - `src/vector_store.py` - Chroma + embedding helper
  - `src/normalize_parsed_json.py` - normalize raw parsed JSON
  - `src/parse_scraped_json.py` - parse scraped JSON into structured records
  - `src/download_and_parse.py` - download and parse PDFs
  - `src/parsers.py` - parser helpers
  - `src/normalizer.py` - normalization helpers
  - `src/schema.py` - pydantic schema definitions

## Setup

1. Create and activate a Python virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set your Gemini or Google API key:

```bash
export GEMINI_API_KEY="your_gemini_api_key"
```

If you want to use OpenAI instead, set `OPENAI_API_KEY`.

## Configuration

- `src/config.py` centralizes paths and API environment variables.
- `GEMINI_API_KEY`, `GOOGLE_API_KEY`, or `OPENAI_API_KEY` is used for embeddings.
- `EMBEDDING_MODEL` defaults to `text-embedding-3-small`.
- `REQUEST_DELAY_SECONDS` defaults to `2` for polite scraping.

## Run the pipeline

1. Scrape pages:

```bash
python university_scraper.py
```

2. Parse scraped JSON and normalize:

```bash
python src/parse_scraped_json.py
python src/normalize_parsed_json.py
```

3. Build the ingestion pipeline and vector store:

```bash
python src/ingest_and_vectorize.py
```

## Notes

- The current vector store helper uses `chromadb` with `duckdb+parquet` persistence.
- If Gemini embedding support is not available, install and configure the correct `google-genai` package and API key.
- The data files are stored under `data/` and `output_json/`.
