import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const ready = Boolean(
    process.env.OPENAI_API_KEY &&
      process.env.SUPABASE_URL &&
      process.env.SUPABASE_SERVICE_ROLE_KEY
  );
  return NextResponse.json(
    { status: ready ? "ok" : "misconfigured" },
    { status: ready ? 200 : 503 }
  );
}
