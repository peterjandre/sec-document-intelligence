import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import OpenAI, { APIError } from "openai";
import { resolveQueryTickers } from "./tickers";

const TABLE_MATCH_RPC = "sec_document_intelligence_match_chunks";
const DEFAULT_MIN_SIMILARITY = 0.5;
const CITATION_EXCERPT_CHARS = 500;
const CHAT_MODEL = "gpt-4.1-nano";
const EMBEDDING_MODEL = "text-embedding-3-small";
const DOC_ID = /^([a-z]+)-(\d{8})$/i;

export const NO_EVIDENCE_ANSWER =
  "I could not find strong supporting evidence in the indexed filings. Try a more specific question.";
export const GENERATION_UNAVAILABLE_ANSWER =
  "The answer model is busy right now. Please try again in a moment. The retrieved excerpts are shown below.";

export const ANSWER_SYSTEM_INSTRUCTION = `You answer questions about SEC Form 10-K filings using only the numbered excerpts in the user message.

Rules:
- Answer only from those excerpts. Do not use outside knowledge or guess.
- Cite supporting excerpts as [n] immediately after the claims they support.
- If the excerpts do not support an answer, say so.
- Never invent numbers, dates, percentages, or dollar amounts that are not in the excerpts. Prefer quoting figures over paraphrasing them.
- Never mix companies unless the question asks for a comparison.
- Do not invent sources. The numbered excerpts are the only evidence.
`;

export type QueryInput = {
  question: string;
  topK?: number;
  minSimilarity?: number;
  filingYear?: number | null;
  filingYears?: number[] | null;
  ticker?: string | null;
  tickers?: string[] | null;
};

export type Citation = {
  document_id: string;
  section: string;
  excerpt: string;
  similarity: number;
};

export type QueryResult = {
  answer: string;
  citations: Citation[];
  routed_ticker: string | null;
  routed_tickers: string[];
};

type MatchRow = {
  chunk_id?: string;
  document_id?: string;
  section?: string;
  text?: string;
  similarity?: number;
};

type Evidence = {
  document_id: string;
  section: string;
  text: string;
};

const FALLBACK_CITATION: Citation = {
  document_id: "unavailable",
  section: "N/A",
  excerpt: "No indexed document excerpts were found.",
  similarity: 0,
};

function reportingYear(year: number, month: number): number {
  return month === 1 ? year - 1 : year;
}

export function documentMeta(documentId: string): { ticker: string; year: number } {
  const match = DOC_ID.exec(documentId);
  if (match) {
    const raw = match[2];
    const year = Number(raw.slice(0, 4));
    const month = Number(raw.slice(4, 6));
    return {
      ticker: match[1].toUpperCase(),
      year: reportingYear(year, month),
    };
  }
  return {
    ticker: documentId.split("-", 1)[0]?.toUpperCase() || "UNKNOWN",
    year: 2025,
  };
}

function requestedYears(
  filingYear?: number | null,
  filingYears?: number[] | null
): Set<number> {
  if (filingYears?.length) {
    return new Set(filingYears.map((year) => Number(year)));
  }
  if (filingYear != null) {
    return new Set([Number(filingYear)]);
  }
  return new Set();
}

function expandStoredFilingYears(requested: Set<number>): number[] {
  const years = new Set<number>();
  for (const year of requested) {
    years.add(year);
    years.add(year + 1);
  }
  return [...years].sort((a, b) => a - b);
}

function rpcFilter(options: {
  filingYears?: number[] | null;
  ticker?: string | null;
  tickers?: string[] | null;
}): Record<string, unknown> {
  const payload: Record<string, unknown> = {};
  if (options.filingYears?.length) {
    payload.filing_years = options.filingYears;
  }
  if (options.tickers?.length) {
    payload.tickers = options.tickers.map((item) => item.toUpperCase());
  } else if (options.ticker) {
    payload.ticker = options.ticker.toUpperCase();
  }
  return payload;
}

function formatNumberedExcerpts(evidence: Evidence[]): string {
  return evidence
    .map(
      (item, index) =>
        `[${index + 1}] ${item.document_id} / ${item.section}\n${item.text}`
    )
    .join("\n\n");
}

export function buildAnswerPrompt(question: string, evidence: Evidence[]): string {
  return `Question:\n${question.trim()}\n\nExcerpts:\n${formatNumberedExcerpts(evidence)}`;
}

function isModelUnavailable(error: unknown): boolean {
  if (error instanceof APIError && (error.status === 429 || error.status === 503)) {
    return true;
  }
  const text = String(error).toUpperCase();
  return (text.includes("503") && text.includes("UNAVAILABLE")) || text.includes("429");
}

function openaiClient(): OpenAI | null {
  const apiKey = process.env.OPENAI_API_KEY ?? "";
  if (!apiKey) return null;
  return new OpenAI({ apiKey });
}

function supabaseClient(): SupabaseClient | null {
  const url = process.env.SUPABASE_URL ?? "";
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY ?? "";
  if (!url || !key) return null;
  return createClient(url, key, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
}

async function embeddingForText(text: string): Promise<number[] | null> {
  const client = openaiClient();
  if (!client) return null;
  const response = await client.embeddings.create({
    model: EMBEDDING_MODEL,
    input: text,
  });
  return response.data[0]?.embedding ?? null;
}

export async function completeAnswer(
  question: string,
  evidence: Evidence[]
): Promise<string> {
  const client = openaiClient();
  if (!client) {
    return "Answer generation is configured but OPENAI_API_KEY is missing.";
  }

  const model = process.env.OPENAI_CHAT_MODEL || CHAT_MODEL;
  try {
    const response = await client.chat.completions.create({
      model,
      temperature: 0,
      messages: [
        { role: "system", content: ANSWER_SYSTEM_INSTRUCTION },
        { role: "user", content: buildAnswerPrompt(question, evidence) },
      ],
    });
    const text = response.choices[0]?.message?.content?.trim() ?? "";
    if (!text) {
      return "The model returned an empty answer. See the retrieved excerpts below.";
    }
    return text;
  } catch (error) {
    if (isModelUnavailable(error)) {
      return GENERATION_UNAVAILABLE_ANSWER;
    }
    return "Answer generation is temporarily unavailable. The retrieved excerpts are shown below.";
  }
}

function routedResult(
  answer: string,
  citations: Citation[],
  routedTickers: string[]
): QueryResult {
  return {
    answer,
    citations,
    routed_ticker: routedTickers.length === 1 ? routedTickers[0] : null,
    routed_tickers: routedTickers,
  };
}

export async function retrieveAnswer(input: QueryInput): Promise<QueryResult> {
  const question = input.question.trim();
  const topK = input.topK ?? 5;
  const minSimilarity = input.minSimilarity ?? DEFAULT_MIN_SIMILARITY;
  const routedTickers = resolveQueryTickers(question, {
    ticker: input.ticker,
    tickers: input.tickers,
  });
  const supabase = supabaseClient();
  if (!supabase) {
    return routedResult(
      "RAG backend is configured but Supabase credentials are missing.",
      [FALLBACK_CITATION],
      routedTickers
    );
  }

  const queryEmbedding = await embeddingForText(question);
  if (!queryEmbedding) {
    return routedResult(
      "Answer generation is configured but OPENAI_API_KEY is missing.",
      [FALLBACK_CITATION],
      routedTickers
    );
  }

  const requested = requestedYears(input.filingYear, input.filingYears);
  const rpcYears = requested.size ? expandStoredFilingYears(requested) : null;
  const matchCount = requested.size ? Math.max(topK * 4, topK) : Math.max(topK * 3, topK);

  const { data, error } = await supabase.rpc(TABLE_MATCH_RPC, {
    query_embedding: queryEmbedding,
    match_count: matchCount,
    filter: rpcFilter({
      filingYears: rpcYears,
      ticker: routedTickers.length === 1 ? routedTickers[0] : null,
      tickers: routedTickers.length > 1 ? routedTickers : null,
    }),
  });
  if (error) {
    throw error;
  }

  let rows = ((data as MatchRow[] | null) ?? []).filter(
    (row) => Number(row.similarity ?? 0) >= minSimilarity
  );
  if (requested.size) {
    rows = rows.filter((row) =>
      requested.has(documentMeta(String(row.document_id ?? "")).year)
    );
  }
  rows = rows.slice(0, topK);
  if (!rows.length) {
    return routedResult(NO_EVIDENCE_ANSWER, [FALLBACK_CITATION], routedTickers);
  }

  const evidence: Evidence[] = rows.map((row) => ({
    document_id: row.document_id ?? "unknown",
    section: row.section ?? "unknown",
    text: row.text ?? "",
  }));
  const citations: Citation[] = evidence.map((item, index) => ({
    document_id: item.document_id,
    section: item.section,
    excerpt: item.text.slice(0, CITATION_EXCERPT_CHARS),
    similarity: Math.round(Number(rows[index]?.similarity ?? 0) * 10000) / 10000,
  }));

  return routedResult(await completeAnswer(question, evidence), citations, routedTickers);
}
