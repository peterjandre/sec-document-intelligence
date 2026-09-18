# Deployment Runbook (Vercel)

The public demo is a single Next.js app. Query, retrieval, and answer generation run in `apps/web/app/api/query`.

## 1) Vercel

- Import `peterjandre/sec-document-intelligence`.
- Set root directory to `apps/web`.
- Framework preset: Next.js.
- Add server env vars (not `NEXT_PUBLIC_`):
  - `OPENAI_API_KEY`
  - `SUPABASE_URL`
  - `SUPABASE_SERVICE_ROLE_KEY`
- Deploy and open `/api/health` (should return `{"status":"ok"}`).
- Run a sample question on the homepage and confirm answer plus citation cards.

## 2) Local indexing (not part of Vercel)

Rebuilding chunks still happens on a machine with the C# extractor and Python RAG CLI. See `services/rag/README.md`. The live site only reads the tables those jobs write.

## 3) Post-Deploy Verification

- `GET https://<app>.vercel.app/api/health` returns `ok`.
- Ask a company-specific question and confirm ticker routing plus source excerpts.
- Confirm browser network requests go to `/api/query` on the same origin, not a separate backend host.
