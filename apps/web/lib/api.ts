export const MODEL_BUSY_MESSAGE =
  "The answer model is busy right now. Please try again in a moment. The retrieved excerpts are shown below.";

export type QueryResponse = {
  answer: string;
  citations: Array<{
    document_id: string;
    section: string;
    excerpt: string;
    similarity: number;
  }>;
  routed_ticker?: string | null;
  routed_tickers?: string[];
};

export function displayAnswer(answer: string): string {
  if (/503\s+UNAVAILABLE/i.test(answer) || /^Answer generation failed/i.test(answer)) {
    return MODEL_BUSY_MESSAGE;
  }
  return answer;
}

export function isAnswerWarning(answer: string): boolean {
  const shown = displayAnswer(answer);
  return (
    shown === MODEL_BUSY_MESSAGE ||
    shown.startsWith("Answer generation is temporarily unavailable") ||
    shown.startsWith("The answer model is busy")
  );
}

export async function runQuery(
  question: string,
  options?: { filingYear?: number }
): Promise<QueryResponse> {
  const response = await fetch("/api/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      ...(options?.filingYear != null ? { filing_year: options.filingYear } : {}),
    }),
  });
  if (!response.ok) throw new Error("Failed to query filings");
  return response.json();
}

export async function getHealth(): Promise<{ status: string }> {
  const response = await fetch("/api/health", { cache: "no-store" });
  if (!response.ok) throw new Error("API health check failed");
  return response.json();
}
