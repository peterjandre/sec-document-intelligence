from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[4] / "rag"))
from rag.pipeline import retrieve_answer, DEFAULT_MIN_SIMILARITY  # type: ignore  # noqa: E402


def query_rag(
    question: str,
    top_k: int,
    *,
    min_similarity: float = DEFAULT_MIN_SIMILARITY,
    filing_year: int | None = None,
    filing_years: list[int] | None = None,
    ticker: str | None = None,
    tickers: list[str] | None = None,
) -> dict:
    return retrieve_answer(
        question=question,
        top_k=top_k,
        min_similarity=min_similarity,
        filing_year=filing_year,
        filing_years=filing_years,
        ticker=ticker,
        tickers=tickers,
    )
