# Render Backend Setup

## Service Configuration

- Service type: Web Service
- Root directory: `services/api`
- Runtime: Python
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check path: `/health`

## Environment Variables

- `OPENAI_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `ALLOWED_ORIGINS` (include your Vercel app URL)
- `EXTRACTOR_CLI_PATH` (runtime path to extractor binary)

## C# Extractor Runtime Notes

Render must have access to the C# binary used by FastAPI subprocess calls.
Recommended MVP options:

1. Build extractor during CI and commit binary artifact for MVP experimentation.
2. Use a Render native environment with .NET runtime available.
3. Run extractor in a dedicated worker service and call it from API.
