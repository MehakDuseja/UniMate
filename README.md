# UniMate

UniMate is a Pakistani university recommender: a scraping-to-vector-store data pipeline for nine Karachi
universities, feeding a LangGraph + Gemini conversational agent served through a Streamlit chat UI.

## What it does

- Scrapes admissions/program/fee/hostel pages for: `FAST University`, `NED University`, `Habib University`,
  `IBA`, `SZABIST`, `DHA Suffa`, `UIT University`, `Iqra University`, and `Sir Syed University` (all Karachi
  campuses)
- Extracts page content, tables, and panels; parses PDFs where needed
- Normalizes admissions data into a canonical schema, deriving fields like province, HEC recognition, minimum
  eligibility %, hostel availability, and verified tuition figures where the source states them unambiguously
- Chunks normalized fields for semantic retrieval and persists structured records into SQLite
- Embeds chunks locally (sentence-transformers) and stores them in a Chroma vector store
- Runs a LangGraph agent (Gemini) that profiles a student through conversation, applies hard eligibility/
  hostel/region filters, ranks eligible universities, and answers follow-up questions - served via a
  Streamlit chat UI
- Optional voice chat: speak a message via a mic button, and play any assistant reply back as speech (Fish
  Audio API - see Configuration)

## Repo structure

- `requirements.txt` - pinned Python dependencies
- `university_scraper.py` - scraping entrypoint
- `streamlit_app.py` - chat frontend for the agent
- `.streamlit/config.toml` - disables Streamlit's dev file watcher (see Notes)
- `src/` - data pipeline modules
  - `src/config.py` - centralized configuration (paths, API key, model names)
  - `src/parsers.py` - PDF/HTML extraction helpers (tables, fees, eligibility, hostel info, etc.)
  - `src/parse_scraped_json.py` - parse scraped JSON into structured records
  - `src/normalizer.py` - normalization + derived fields (province, tuition, coordinates, hostel availability)
  - `src/normalize_parsed_json.py` - driver for normalization
  - `src/chunker.py` - semantic chunk generation
  - `src/ingest.py` - SQLite ingestion (auto-migrates the schema if columns were added since the DB was created)
  - `src/vector_store.py` - Chroma + embedding helper (local or Gemini backend)
  - `src/ingest_and_vectorize.py` - runs the whole ingest+chunk+embed pipeline in one command
  - `src/schema.py` - pydantic schema definitions
  - `src/downloads.py`, `src/download_and_parse.py` - standalone PDF pre-fetch utility, not part of the main
    pipeline (`university_scraper.py`'s own PDF handling is what the pipeline actually uses)
- `agent/` - the LangGraph recommender agent
  - `agent/state.py` - student profile + graph state types
  - `agent/prompts.py` - every system prompt, as plain templates
  - `agent/llm.py` - thin Gemini chat wrapper with 429 retry/backoff
  - `agent/nodes.py` - node functions: profile building, ranking, presenting, refining, Q&A
  - `agent/retriever.py` - Chroma/SQLite retrieval, hard filtering, candidate building
  - `agent/geo.py` - Karachi-neighborhood geocoding for distance-based ranking
  - `agent/graph.py` - graph wiring
  - `agent/cli.py` - terminal test harness (`python3 -m agent.cli`)
  - `agent/voice.py` - Fish Audio wrapper for voice chat (text-to-speech and speech-to-text), used only by
    `streamlit_app.py`

## Setup

1. Create and activate a **Python 3.11** virtual environment (chromadb's `onnxruntime` dependency has no wheel
   for newer Python versions yet, so a generic/latest `python3 -m venv` may break the install):

```bash
python3.11 -m venv venv311
source venv311/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set your Gemini API key:

```bash
export GEMINI_API_KEY="your_gemini_api_key"
```

(or add it to a `.env` file - `src/config.py` loads one automatically.)

## Configuration

- `src/config.py` centralizes paths and API environment variables.
- `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) is used for the chat agent. There is no OpenAI integration - an
  `OPENAI_API_KEY` fallback exists only as an alternate key lookup and is never actually sent to OpenAI.
- Chunk embeddings run locally via `sentence-transformers` (`all-MiniLM-L6-v2`) by default, since the
  free-tier Gemini embedding API is rate-limited; `src/vector_store.py` also supports a Gemini embedding
  backend if you have quota for it.
- `GEMINI_CHAT_MODEL` defaults to `gemini-3.1-flash-lite`.
- `REQUEST_DELAY_SECONDS` defaults to `2` for polite scraping.
- `LANGSMITH_API_KEY` is optional - just setting it turns on tracing (see Tracing below).
- `FISH_API_KEY` is optional - only needed for voice chat (`agent/voice.py`). Get one at
  [fish.audio](https://fish.audio) - it's a separate paid account/quota from Gemini, not part of the free
  tier. Without it set, voice chat is unavailable (the mic button and "Play" buttons show an error) but the
  rest of the app works normally.

## Tracing

Set `LANGSMITH_API_KEY` in `.env` (get one at [smith.langchain.com](https://smith.langchain.com)) and every
graph run, plus every individual Gemini call (`agent/llm.py`'s `generate_text`/`generate_json`, decorated with
`@traceable`), shows up in your LangSmith project (defaults to `unimate`) - the exact system prompt, user
prompt, and raw response for each call, nested under the node/turn that made it. Useful for tracing exactly
which retrieved context or prompt produced a wrong answer. With no key set, tracing is a no-op with no
behavior change.

## Run the data pipeline

1. Scrape pages:

```bash
python university_scraper.py
```

2. Parse scraped JSON and normalize:

```bash
python3 -m src.parse_scraped_json
python3 -m src.normalize_parsed_json
```

3. Build the ingestion pipeline and vector store (SQLite + Chroma) in one step:

```bash
python3 -m src.ingest_and_vectorize
```

## Run the agent

Terminal test harness - conversations persist across restarts (see Notes below), so re-running with the same
thread_id resumes where you left off:

```bash
python3 -m agent.cli [thread_id]   # thread_id defaults to "cli-default"
```

Chat UI:

```bash
streamlit run streamlit_app.py
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Covers the parser/normalizer extraction logic, the deterministic guardrails in `agent/nodes.py` (eligibility
gate, region gate, input sanitizing), and graph routing. A few retriever tests need the data pipeline to have
been run first (`python3 -m src.ingest_and_vectorize`) and are skipped otherwise.

## Notes

- The vector store uses `chromadb`'s `PersistentClient` (chromadb 1.x API), stored under `data/chroma_db`.
- Structured fields (fees, eligibility %, hostel availability, coordinates) live in `data/university_ingest.db`
  (SQLite) and are used directly by the ranker for hard filtering and grounding - not just the semantic chunks.
- The corpus currently covers Karachi only; the agent explicitly tells a student asking about another city or
  province that it isn't designed for that yet, rather than silently trying to match it.
- Conversations are durable: `agent/graph.py` compiles with a `SqliteSaver` checkpointer
  (`data/agent_checkpoints.db`), keyed by `thread_id`. Streamlit generates a random `thread_id` per browser
  session and `agent/cli.py` accepts one as an argument - either way, a server restart can recover a
  conversation via `graph.get_state(config)` instead of only ever starting fresh.
- Streamlit's dev-mode file watcher is disabled (`.streamlit/config.toml`) because it otherwise spams
  `ModuleNotFoundError: No module named 'torchvision'` while introspecting `transformers`' optional vision
  submodules (pulled in transitively by `sentence-transformers`, unrelated to anything this project uses).
  This means code changes need a manual rerun/restart to take effect instead of auto-reloading.
