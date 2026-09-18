# SEC 10-K Document Intelligence MVP

Monorepo for a portfolio MVP that ingests SEC 10-K HTML filings, extracts structured content with C# regex, indexes chunks for retrieval, and serves grounded Q&A.

The public demo is **Vercel-only**. A Next.js route (`/api/query`) embeds the question, retrieves chunks from Supabase pgvector, and asks OpenAI `gpt-4.1-nano` to answer from those excerpts. C# extraction and Python indexing stay local tools for rebuilding the corpus.

## Project Structure

- `apps/web` - Next.js UI and query API (deploy to Vercel)
- `services/api` - Optional FastAPI ingest orchestrator for local runs
- `services/extractor-csharp` - C# regex extraction CLI (local)
- `services/rag` - Python chunking and indexing helpers (local)
- `shared/schemas` - JSON schema contracts
- `docs` - architecture and deployment notes

## Local Development (No Docker)

1. Copy `apps/web/.env.example` to `apps/web/.env.local` and set:
   - `OPENAI_API_KEY`
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
2. Start the app:
   - `cd apps/web`
   - `npm install`
   - `npm run dev`
3. Open `http://localhost:3000` and ask a question. Query traffic stays on the Next.js server; secrets never go to the browser.

### Optional: rebuild the indexed corpus

1. Build the extractor:
   - `cd services/extractor-csharp`
   - `dotnet build -c Release`
2. Extract and index (see `services/rag/README.md`):
   - `cd services/rag`
   - `python -m rag.cli --input-dir ../../data/sec-filings/extracted --env-file ../api/.env`

## Evaluate regex against real filings

Run the extractor on every `.htm` / `.html` file in `data/sec-filings` and print a section/field scorecard:

```bash
./scripts/eval_regex.sh
```

Optional custom paths:

```bash
./scripts/eval_regex.sh /path/to/filings /path/to/extracted-json
```

Use the scorecard (`HIT` vs `MISS`, extracted character counts, and text previews) to refine patterns in `services/extractor-csharp/Program.cs`, then rerun the script.

## API Endpoints

Hosted on the Next.js app (locally and on Vercel):

- `POST /api/query`
- `GET /api/health`

Optional local FastAPI ingest service (`services/api`):

- `POST /ingest/run`
- `GET /ingest/status/{job_id}`
- `GET /health`

## Deployment

- Vercel: deploy `apps/web` with `OPENAI_API_KEY`, `SUPABASE_URL`, and `SUPABASE_SERVICE_ROLE_KEY`. Do not prefix those with `NEXT_PUBLIC_`.
- Re-indexing stays a local Python/C# workflow; the live site only reads chunks already stored in Supabase.
