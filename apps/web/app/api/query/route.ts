import { NextResponse } from "next/server";
import { retrieveAnswer } from "../../../lib/rag";

export const runtime = "nodejs";
export const maxDuration = 60;

const MAX_QUESTION_CHARS = 1000;

type QueryBody = {
  question?: unknown;
  top_k?: unknown;
  min_similarity?: unknown;
  filing_year?: unknown;
  filing_years?: unknown;
  ticker?: unknown;
  tickers?: unknown;
};

function asString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function asStringList(value: unknown): string[] | null {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : null;
}

function asNumberList(value: unknown): number[] | null {
  return Array.isArray(value)
    ? value.filter((item): item is number => typeof item === "number" && Number.isFinite(item))
    : null;
}

export async function POST(request: Request) {
  let body: QueryBody;
  try {
    body = (await request.json()) as QueryBody;
  } catch {
    return NextResponse.json({ detail: "Invalid JSON body" }, { status: 400 });
  }

  const question = asString(body.question)?.slice(0, MAX_QUESTION_CHARS).trim() ?? "";
  if (question.length < 5) {
    return NextResponse.json({ detail: "Question is too short" }, { status: 400 });
  }

  const topK = asNumber(body.top_k) ?? 5;
  const minSimilarity = asNumber(body.min_similarity) ?? 0.5;
  if (topK < 1 || topK > 50 || minSimilarity < 0 || minSimilarity > 1) {
    return NextResponse.json({ detail: "Invalid retrieval options" }, { status: 400 });
  }

  try {
    const result = await retrieveAnswer({
      question,
      topK,
      minSimilarity,
      filingYear: asNumber(body.filing_year),
      filingYears: asNumberList(body.filing_years),
      ticker: asString(body.ticker),
      tickers: asStringList(body.tickers),
    });
    return NextResponse.json(result);
  } catch {
    return NextResponse.json({ detail: "Query failed" }, { status: 500 });
  }
}
