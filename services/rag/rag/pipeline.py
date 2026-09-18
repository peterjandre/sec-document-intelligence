from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from openai import OpenAI
from supabase import create_client

from rag.chunker import chunk_section_text
from rag.tickers import resolve_query_tickers

TABLE_DOCUMENTS = "sec_document_intelligence_documents"
TABLE_CHUNKS = "sec_document_intelligence_chunks"
TABLE_CHUNK_EMBEDDINGS = "sec_document_intelligence_chunk_embeddings"
RPC_MATCH_CHUNKS = "sec_document_intelligence_match_chunks"

DEFAULT_MIN_SIMILARITY = 0.5
CITATION_EXCERPT_CHARS = 500
CHAT_MODEL = "gpt-4.1-nano"
NO_EVIDENCE_ANSWER = (
    "I could not find strong supporting evidence in the indexed filings. "
    "Try a more specific question."
)
GENERATION_UNAVAILABLE_ANSWER = (
    "The answer model is busy right now. Please try again in a moment. "
    "The retrieved excerpts are shown below."
)
ANSWER_SYSTEM_INSTRUCTION = """You answer questions about SEC Form 10-K filings using only the numbered excerpts in the user message.

Rules:
- Answer only from those excerpts. Do not use outside knowledge or guess.
- Cite supporting excerpts as [n] immediately after the claims they support.
- If the excerpts do not support an answer, say so.
- Never invent numbers, dates, percentages, or dollar amounts that are not in the excerpts. Prefer quoting figures over paraphrasing them.
- Never mix companies unless the question asks for a comparison.
- Do not invent sources. The numbered excerpts are the only evidence.
"""
_SKIP_JSON_NAMES = frozenset({"validation-report.json"})


def is_extracted_filing(path: Path) -> bool:
    return path.suffix.lower() == ".json" and path.name not in _SKIP_JSON_NAMES


_DOC_ID = re.compile(r"^(?P<ticker>[a-z]+)-(?P<date>\d{8})$", re.I)
_YEAR = re.compile(r"(?:19|20)\d{2}")


def _reporting_year(year: int, month: int) -> int:
    """January fiscal year-ends mostly cover the prior calendar year.

    NVIDIA's FY ending 2026-01-25 lines up with Apple's 2025 10-K, not 2026.
    """
    if month == 1:
        return year - 1
    return year


def _document_meta(document_id: str, parsed: dict[str, Any]) -> tuple[str, int]:
    """Ticker and reporting year from ids like aapl-20240928, else extracted fields."""
    match = _DOC_ID.match(document_id)
    if match:
        ticker = match.group("ticker").upper()
        raw = match.group("date")
        year = int(raw[:4])
        month = int(raw[4:6])
        return ticker, _reporting_year(year, month)

    ticker = document_id.split("-", 1)[0].upper()
    fields = parsed.get("fields") or {}
    ended = str(fields.get("fiscal_year_ended") or "")
    year_match = _YEAR.search(ended)
    year = int(year_match.group(0)) if year_match else 2025
    if re.search(r"\bjan(?:uary)?\b", ended, re.I):
        year = _reporting_year(year, 1)
    return ticker, year


def _openai_client() -> OpenAI | None:
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def format_numbered_excerpts(evidence: list[dict[str, Any]]) -> str:
    """Number retrieved chunks as [1] document_id / section followed by the text."""
    blocks: list[str] = []
    for index, item in enumerate(evidence, start=1):
        document_id = item.get("document_id", "unknown")
        section = item.get("section", "unknown")
        text = item.get("text") or item.get("excerpt") or ""
        blocks.append(f"[{index}] {document_id} / {section}\n{text}")
    return "\n\n".join(blocks)


def build_answer_prompt(question: str, evidence: list[dict[str, Any]]) -> str:
    return f"Question:\n{question.strip()}\n\nExcerpts:\n{format_numbered_excerpts(evidence)}"


def _is_model_unavailable(exc: BaseException) -> bool:
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if code in {429, 503}:
        return True
    text = str(exc).upper()
    return ("503" in text and "UNAVAILABLE" in text) or "429" in text


def complete_answer(question: str, evidence: list[dict[str, Any]]) -> str:
    """One chat completion grounded in already-retrieved excerpts. Does not search."""
    client = _openai_client()
    if client is None:
        return "Answer generation is configured but OPENAI_API_KEY is missing."

    model = os.getenv("OPENAI_CHAT_MODEL", CHAT_MODEL)
    try:
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            messages=[
                {"role": "system", "content": ANSWER_SYSTEM_INSTRUCTION},
                {"role": "user", "content": build_answer_prompt(question, evidence)},
            ],
        )
    except Exception as exc:  # noqa: BLE001
        if _is_model_unavailable(exc):
            return GENERATION_UNAVAILABLE_ANSWER
        return (
            "Answer generation is temporarily unavailable. "
            "The retrieved excerpts are shown below."
        )

    choice = response.choices[0] if response.choices else None
    text = (getattr(getattr(choice, "message", None), "content", None) or "").strip()
    if not text:
        return "The model returned an empty answer. See the retrieved excerpts below."
    return text


def _supabase_client():
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        return None
    return create_client(url, key)


def _embedding_for_text(text: str) -> list[float]:
    client = _openai_client()
    if client is None:
        return [0.0] * 8
    response = client.embeddings.create(model="text-embedding-3-small", input=text)
    return response.data[0].embedding


def index_extracted_json(paths: list[str]) -> int:
    supabase = _supabase_client()
    indexed = 0
    for path in paths:
        file_path = Path(path)
        if not is_extracted_filing(file_path):
            continue
        parsed = json.loads(file_path.read_text())
        document_id = parsed.get("documentId") or parsed.get("document_id") or file_path.stem
        ticker, filing_year = _document_meta(document_id, parsed)
        if supabase is not None:
            supabase.table(TABLE_DOCUMENTS).upsert(
                {
                    "document_id": document_id,
                    "ticker": ticker,
                    "filing_year": filing_year,
                }
            ).execute()
        for section in parsed.get("sections", []):
            chunks = chunk_section_text(
                document_id=document_id,
                section=section.get("name", "unknown"),
                text=section.get("text", ""),
            )
            for chunk in chunks:
                embedding = _embedding_for_text(chunk["text"])
                if supabase is not None:
                    supabase.table(TABLE_CHUNKS).upsert(
                        {
                            "chunk_id": chunk["chunk_id"],
                            "document_id": chunk["source_doc_id"],
                            "section": chunk["section"],
                            "text": chunk["text"],
                            "char_range_start": chunk["char_range"][0],
                            "char_range_end": chunk["char_range"][1],
                        }
                    ).execute()
                    supabase.table(TABLE_CHUNK_EMBEDDINGS).upsert(
                        {
                            "chunk_id": chunk["chunk_id"],
                            "embedding": embedding,
                            "metadata": chunk["metadata"],
                        }
                    ).execute()
                indexed += 1
    return indexed


def _rpc_filter(
    filing_year: int | None = None,
    filing_years: list[int] | None = None,
    ticker: str | None = None,
    tickers: list[str] | None = None,
) -> dict[str, Any]:
    """Build the jsonb filter the match RPC already understands."""
    payload: dict[str, Any] = {}
    if filing_years:
        payload["filing_years"] = filing_years
    elif filing_year is not None:
        payload["filing_year"] = filing_year
    if tickers:
        payload["tickers"] = [item.upper() for item in tickers]
    elif ticker:
        payload["ticker"] = ticker.upper()
    return payload


def _requested_years(
    filing_year: int | None,
    filing_years: list[int] | None,
) -> set[int]:
    if filing_years:
        return {int(year) for year in filing_years}
    if filing_year is not None:
        return {int(filing_year)}
    return set()


def _expand_stored_filing_years(requested: set[int]) -> list[int]:
    """Also fetch year+1 so January FYE rows stored under the later year are included."""
    return sorted({year for item in requested for year in (item, item + 1)})


def retrieve_answer(
    question: str,
    top_k: int = 5,
    *,
    min_similarity: float = DEFAULT_MIN_SIMILARITY,
    filing_year: int | None = None,
    filing_years: list[int] | None = None,
    ticker: str | None = None,
    tickers: list[str] | None = None,
) -> dict[str, Any]:
    supabase = _supabase_client()
    fallback_citation = {
        "document_id": "unavailable",
        "section": "N/A",
        "excerpt": "No indexed document excerpts were found.",
        "similarity": 0.0,
    }
    if supabase is None:
        return {
            "answer": "RAG backend is configured but Supabase credentials are missing.",
            "citations": [fallback_citation],
            "routed_ticker": None,
            "routed_tickers": [],
        }

    routed_tickers = resolve_query_tickers(question, ticker=ticker, tickers=tickers)
    query_embedding = _embedding_for_text(question)
    requested = _requested_years(filing_year, filing_years)
    rpc_years = _expand_stored_filing_years(requested) if requested else None
    match_count = max(top_k * 4, top_k) if requested else max(top_k * 3, top_k)
    matches = supabase.rpc(
        RPC_MATCH_CHUNKS,
        {
            "query_embedding": query_embedding,
            "match_count": match_count,
            "filter": _rpc_filter(
                filing_year=None,
                filing_years=rpc_years,
                ticker=routed_tickers[0] if len(routed_tickers) == 1 else None,
                tickers=routed_tickers if len(routed_tickers) > 1 else None,
            ),
        },
    ).execute()
    rows = [
        row
        for row in (matches.data or [])
        if float(row.get("similarity") or 0) >= min_similarity
    ]
    if requested:
        rows = [
            row
            for row in rows
            if _document_meta(str(row.get("document_id") or ""), {})[1] in requested
        ]
    rows = rows[:top_k]
    if not rows:
        return {
            "answer": NO_EVIDENCE_ANSWER,
            "citations": [fallback_citation],
            "routed_ticker": routed_tickers[0] if len(routed_tickers) == 1 else None,
            "routed_tickers": routed_tickers,
        }
    evidence = [
        {
            "document_id": row.get("document_id", "unknown"),
            "section": row.get("section", "unknown"),
            "text": row.get("text", ""),
        }
        for row in rows
    ]
    citations = [
        {
            "document_id": item["document_id"],
            "section": item["section"],
            "excerpt": (item["text"] or "")[:CITATION_EXCERPT_CHARS],
            "similarity": round(float(row.get("similarity") or 0), 4),
        }
        for item, row in zip(evidence, rows)
    ]
    return {
        "answer": complete_answer(question, evidence),
        "citations": citations,
        "routed_ticker": routed_tickers[0] if len(routed_tickers) == 1 else None,
        "routed_tickers": routed_tickers,
    }
