# Deployment Runbook (Vercel + Render)

## 1) Render API

- Create a new Render Web Service from this repo.
- Set root directory: `services/api`.
- Build command: `pip install -r requirements.txt`.
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- Configure env vars:
  - `OPENAI_API_KEY`
  - `SUPABASE_URL`
  - `SUPABASE_SERVICE_ROLE_KEY`
  - `ALLOWED_ORIGINS` (Vercel URL)
  - `EXTRACTOR_CLI_PATH` (binary path in runtime)

## 2) Vercel Web

- Import project and set root directory to `apps/web`.
- Add env var:
  - `NEXT_PUBLIC_API_BASE_URL=https://<render-service>.onrender.com`
- Deploy and verify the query UI can call `/health` and `/query`.

## 3) Post-Deploy Verification

- Trigger `POST /ingest/run` from API docs or curl.
- Confirm `GET /ingest/status/{job_id}` returns `completed`.
- Run web query and verify answer includes source excerpt cards.
