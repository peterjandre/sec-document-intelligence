const TICKER_ALIASES: Record<string, string> = {
  aapl: "AAPL",
  apple: "AAPL",
  amzn: "AMZN",
  amazon: "AMZN",
  goog: "GOOG",
  googl: "GOOG",
  google: "GOOG",
  alphabet: "GOOG",
  meta: "META",
  facebook: "META",
  nflx: "NFLX",
  netflix: "NFLX",
  nvda: "NVDA",
  nvidia: "NVDA",
};

const ALIAS_PATTERN = new RegExp(
  `\\b(${Object.keys(TICKER_ALIASES)
    .sort((a, b) => b.length - a.length)
    .map((alias) => alias.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
    .join("|")})(?:['\u2019]s)?\\b`,
  "gi"
);

export function detectTickers(question: string): string[] {
  const found: string[] = [];
  const seen = new Set<string>();
  ALIAS_PATTERN.lastIndex = 0;
  for (const match of question.matchAll(ALIAS_PATTERN)) {
    const ticker = TICKER_ALIASES[match[1].toLowerCase()];
    if (ticker && !seen.has(ticker)) {
      seen.add(ticker);
      found.push(ticker);
    }
  }
  return found;
}

export function resolveQueryTickers(
  question: string,
  options?: { ticker?: string | null; tickers?: string[] | null }
): string[] {
  if (options?.tickers?.length) {
    return options.tickers.map((item) => item.trim().toUpperCase()).filter(Boolean);
  }
  if (options?.ticker?.trim()) {
    return [options.ticker.trim().toUpperCase()];
  }
  return detectTickers(question);
}
