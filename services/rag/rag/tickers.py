from __future__ import annotations

import re

# Aliases for the six issuers currently indexed. Possessives are handled in the regex.
_TICKER_ALIASES: dict[str, str] = {
    "aapl": "AAPL",
    "apple": "AAPL",
    "amzn": "AMZN",
    "amazon": "AMZN",
    "goog": "GOOG",
    "googl": "GOOG",
    "google": "GOOG",
    "alphabet": "GOOG",
    "meta": "META",
    "facebook": "META",
    "nflx": "NFLX",
    "netflix": "NFLX",
    "nvda": "NVDA",
    "nvidia": "NVDA",
}

_ALIAS_PATTERN = re.compile(
    r"\b("
    + "|".join(re.escape(alias) for alias in sorted(_TICKER_ALIASES, key=len, reverse=True))
    + r")(?:['\u2019]s)?\b",
    re.IGNORECASE,
)


def detect_tickers(question: str) -> list[str]:
    """Return unique tickers named in the question, in first-mention order."""
    found: list[str] = []
    seen: set[str] = set()
    for match in _ALIAS_PATTERN.finditer(question):
        ticker = _TICKER_ALIASES[match.group(1).lower()]
        if ticker not in seen:
            seen.add(ticker)
            found.append(ticker)
    return found


def resolve_query_tickers(
    question: str,
    ticker: str | None = None,
    tickers: list[str] | None = None,
) -> list[str]:
    """Explicit API filters win; otherwise route to every issuer named in the question."""
    if tickers:
        return [item.upper() for item in tickers if item.strip()]
    if ticker and ticker.strip():
        return [ticker.strip().upper()]
    return detect_tickers(question)
