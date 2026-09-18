# Vercel Setup

The UI and the query API both deploy from `apps/web`. There is no separate Render service.

## Project Configuration

- Framework preset: Next.js
- Root directory: `apps/web`
- Install command: `npm install`
- Build command: `npm run build`

## Environment Variables

Set these as **server** environment variables. Do not prefix them with `NEXT_PUBLIC_`:

- `OPENAI_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

Optional:

- `OPENAI_CHAT_MODEL` (defaults to `gpt-4.1-nano`)

## Verification

1. Open `/api/health` and confirm `{"status":"ok"}`.
2. Open the homepage and confirm API status shows online.
3. Run a sample question.
4. Verify the answer and citation excerpt cards render.
5. In the browser network panel, confirm `POST /api/query` is same-origin.
