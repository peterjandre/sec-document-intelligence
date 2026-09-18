# Architecture Notes

## Request Flow

1. User asks a question in the Next.js app.
2. The browser calls same-origin `POST /api/query` (Vercel or `next dev`).
3. The route embeds the question with OpenAI, retrieves chunks from Supabase pgvector, and applies ticker routing plus a similarity threshold.
4. If chunks pass the threshold, OpenAI `gpt-4.1-nano` answers from those excerpts only; citations stay the retrieved chunks.

Secrets (`OPENAI_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`) live only in the Next.js server environment. They are never sent to the browser.

## Ingestion Flow (local)

1. The C# extractor CLI reads 10-K HTML and writes structured JSON.
2. The Python RAG CLI chunks that JSON, embeds with OpenAI, and upserts into Supabase pgvector.
3. Optional local FastAPI `POST /ingest/run` can wrap those same steps.

The hosted Vercel app does not run extraction or ingest.
