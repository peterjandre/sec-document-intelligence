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

## MVP Dataset Validation Procedure (8 companies, 2025 filings)

1. Place all 2025 filing HTML files under `data/sec-filings/<ticker>/`.
2. For each ticker, run API `POST /ingest/run` with `input_dir` for that ticker.
3. Record `job_id`, poll `GET /ingest/status/{job_id}`, and capture validation warnings.
4. Run a query suite from web UI and verify:
   - answer text is returned
   - at least one citation appears
   - excerpt maps to relevant filing section

## Deployment Validation (Vercel + Render)

- Vercel `NEXT_PUBLIC_API_BASE_URL` points to Render service URL.
- Render CORS allowlist includes Vercel domain(s).
- Render logs confirm successful extractor invocation and ingest job completion.
