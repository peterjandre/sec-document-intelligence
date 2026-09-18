# SEC 10-K Document Intelligence MVP

Monorepo for a portfolio MVP that ingests SEC 10-K HTML filings, extracts structured content with C# regex, indexes chunks for retrieval, and serves grounded Q&A.

## Project Structure

- `apps/web` - Next.js UI (deploy to Vercel)
- `services/api` - FastAPI orchestrator (deploy to Render)
- `services/extractor-csharp` - C# regex extraction CLI
- `services/rag` - Python chunking and retrieval helpers
- `shared/schemas` - JSON schema contracts
- `docs` - architecture and deployment notes

## Local Development (No Docker)

1. Copy `.env.example` values into service-level env files.
2. Start API:
   - `cd services/api`
   - `python -m venv .venv && source .venv/bin/activate`
   - `pip install -r requirements.txt`
   - `uvicorn app.main:app --reload`
3. Start web:
   - `cd apps/web`
   - `npm install`
   - `npm run dev`
4. Build extractor:
   - `cd services/extractor-csharp`
   - `dotnet build -c Release`

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

- `POST /ingest/run`
- `GET /ingest/status/{job_id}`
- `POST /query`
- `GET /health`

## Deployment

- Vercel: deploy `apps/web` with `NEXT_PUBLIC_API_BASE_URL` pointing to Render API.
- Render: deploy `services/api`, set secrets (`OPENAI_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`) and extractor path.
