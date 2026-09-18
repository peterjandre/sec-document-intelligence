from typing import Literal

from pydantic import BaseModel, Field


class IngestRunRequest(BaseModel):
    input_dir: str = Field(description="Directory containing SEC filing HTML files.")
    ticker: str | None = None
    filing_year: int = 2025


class IngestRunResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "failed"]
    files_processed: int


class IngestStatusResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "failed"]
    message: str
    validation_warnings: list[str] = []


class QueryRequest(BaseModel):
    question: str
    top_k: int = Field(default=5, ge=1, le=50)
    min_similarity: float = Field(default=0.5, ge=0.0, le=1.0)
    filing_year: int | None = None
    filing_years: list[int] | None = None
    ticker: str | None = None
    tickers: list[str] | None = None


class Citation(BaseModel):
    document_id: str
    section: str
    excerpt: str
    similarity: float = 0.0


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    routed_ticker: str | None = None
    routed_tickers: list[str] = []
