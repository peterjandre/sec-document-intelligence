# E2E Validation Notes

## Local Execution

Command run:

```bash
./scripts/e2e_local.sh
```

Observed output:

- C# extractor build succeeded.
- Extractor processed sample fixture input and produced structured JSON + report.
- RAG indexing processed extracted JSON and indexed 2 chunks in fallback mode.
- Query flow returned an answer payload with 1 citation when Supabase credentials were not configured.

## Live query (Vercel / `next dev`)

1. Set `OPENAI_API_KEY`, `SUPABASE_URL`, and `SUPABASE_SERVICE_ROLE_KEY` in `apps/web/.env.local` (or Vercel env).
2. `cd apps/web && npm run dev`
3. `GET /api/health` returns `ok`.
4. From the UI, run a query suite and verify:
   - answer text is returned
   - at least one citation appears
   - excerpt maps to a relevant filing section
   - browser calls `/api/query` on the same origin

## MVP Dataset Validation Procedure (local ingest)

1. Place filing HTML files under `data/sec-filings/`.
2. Run the C# extractor and Python RAG CLI (see `services/rag/README.md`).
3. Confirm chunks exist in the `sec_document_intelligence_*` tables.
4. Query from the Next.js UI.

## Deployment Validation (Vercel)

- Root directory is `apps/web`.
- Server env vars are set without `NEXT_PUBLIC_`.
- `/api/health` is `ok`.
- Homepage query returns an answer plus source excerpt cards.
