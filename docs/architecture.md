# Architecture Notes

## Request Flow

1. User asks a question in Next.js app.
2. Frontend calls Render-hosted FastAPI `/query`.
3. FastAPI retrieves relevant chunks from Supabase pgvector via RAG pipeline.
4. If chunks pass the similarity threshold, OpenAI `gpt-4.1-nano` answers from those excerpts only; citations stay the retrieved chunks.

## Ingestion Flow

1. `POST /ingest/run` accepts a local dataset path.
2. FastAPI invokes C# extractor CLI for HTML section and field extraction.
3. Extracted JSON is uploaded to Supabase object storage.
4. RAG pipeline chunks text, embeds with OpenAI, and indexes to pgvector tables.
