# RAG Service Helpers

Python helpers that chunk extracted 10-K JSON, embed the chunks with OpenAI (`text-embedding-3-small`), upsert documents / chunks / embeddings into Supabase, and answer questions with OpenAI (`gpt-4.1-nano`) after retrieval.

The CLI reads **extracted** filings (`data/sec-filings/extracted/*.json`), not the inspectable `*.chunks.json` previews. It re-runs the chunker, then writes to the `sec_document_intelligence_*` tables.

## Prerequisites

1. Apply `services/api/sql/schema.sql` in Supabase (tables + match function). Defer the IVFFlat index until after the first load.
2. Install deps from this folder:

```bash
cd services/rag
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

3. Put `OPENAI_API_KEY`, `SUPABASE_URL`, and `SUPABASE_SERVICE_ROLE_KEY` in a `.env` file. Embeddings and the grounded answer step both use OpenAI (`text-embedding-3-small` and `gpt-4.1-nano`).

## Usage

If `services/api/.env` already has those three variables, you can run without copying another file:

```bash
cd services/rag
python -m rag.cli --input-dir ../../data/sec-filings/extracted --env-file ../api/.env
```

Or copy this service’s example and let auto-discovery find `services/rag/.env`:

```bash
cd services/rag
cp .env.example .env   # then fill in keys
python -m rag.cli --input-dir ../../data/sec-filings/extracted
```

If `--env-file` is omitted, the CLI loads the first existing of `./.env`, `services/rag/.env`, the repo-root `.env`, or `services/api/.env`. Existing process environment variables are not overwritten.

`validation-report.json` in the input directory is skipped. Expect one OpenAI call and two Supabase upserts per chunk; a full 12-filing run is thousands of chunks and can take several minutes. On success the CLI prints `Indexed <n> chunks from <m> extracted files`.
