# FastAPI / Render (optional, local ingest only)

The hosted demo is Vercel-only. `POST /api/query` on Next.js talks to Supabase and OpenAI directly, so Render is not required.

Keep `services/api` for local ingest orchestration if you want a FastAPI wrapper around the C# extractor. That path is not used in production.

## Local FastAPI (ingest)

- Root directory: `services/api`
- Start: `uvicorn app.main:app --reload --port 8000`
- Health check path: `/health`

## Environment Variables

- `OPENAI_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `EXTRACTOR_CLI_PATH` (path to the local extractor binary)

## C# Extractor Runtime Notes

Ingest needs a .NET 8 extractor binary on the same machine as FastAPI. Render’s Python runtime does not include that toolchain, which is one reason ingest stays local.
