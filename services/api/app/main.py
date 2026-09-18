from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.models import (
    IngestRunRequest,
    IngestRunResponse,
    IngestStatusResponse,
    QueryRequest,
    QueryResponse,
)
from app.services.extractor_runner import run_extractor
from app.services.storage_client import get_supabase_client, upload_file

# Allow importing shared RAG package from monorepo structure.
sys.path.append(str(Path(__file__).resolve().parents[3] / "services" / "rag"))
from rag.pipeline import index_extracted_json, retrieve_answer  # type: ignore  # noqa: E402

app = FastAPI(title="SEC Filing Intelligence API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.allowed_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

JOB_STATE: dict[str, IngestStatusResponse] = {}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ingest/run", response_model=IngestRunResponse)
def ingest_run(payload: IngestRunRequest) -> IngestRunResponse:
    job_id = str(uuid.uuid4())
    JOB_STATE[job_id] = IngestStatusResponse(
        job_id=job_id, status="running", message="Ingestion started."
    )

    output_dir = str(Path(payload.input_dir).parent / "extracted")
    report_path = str(Path(output_dir) / "validation-report.json")
    try:
        report = run_extractor(
            extractor_path=settings.extractor_cli_path,
            input_dir=payload.input_dir,
            output_dir=output_dir,
            report_path=report_path,
        )
        extracted_files = [
            path
            for path in Path(output_dir).glob("*.json")
            if path.name != "validation-report.json"
        ]
        supabase_client = get_supabase_client(
            settings.supabase_url, settings.supabase_service_role_key
        )
        for file_path in extracted_files:
            upload_file(
                supabase_client,
                "sec-structured-json",
                f"{payload.filing_year}/{file_path.name}",
                str(file_path),
            )
        index_extracted_json([str(path) for path in extracted_files])
        JOB_STATE[job_id] = IngestStatusResponse(
            job_id=job_id,
            status="completed",
            message="Ingestion completed successfully.",
            validation_warnings=report.get("warnings", []),
        )
        return IngestRunResponse(
            job_id=job_id,
            status="completed",
            files_processed=int(report.get("files_processed", len(extracted_files))),
        )
    except Exception as exc:  # noqa: BLE001
        JOB_STATE[job_id] = IngestStatusResponse(
            job_id=job_id,
            status="failed",
            message=str(exc),
            validation_warnings=[],
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/ingest/status/{job_id}", response_model=IngestStatusResponse)
def ingest_status(job_id: str) -> IngestStatusResponse:
    if job_id not in JOB_STATE:
        raise HTTPException(status_code=404, detail="Job not found")
    return JOB_STATE[job_id]


@app.post("/query", response_model=QueryResponse)
def query(payload: QueryRequest) -> QueryResponse:
    if len(payload.question.strip()) < 5:
        raise HTTPException(status_code=400, detail="Question is too short")
    result = retrieve_answer(
        payload.question,
        payload.top_k,
        min_similarity=payload.min_similarity,
        filing_year=payload.filing_year,
        filing_years=payload.filing_years,
        ticker=payload.ticker,
        tickers=payload.tickers,
    )
    return QueryResponse(**result)


@app.get("/debug/jobs")
def debug_jobs() -> str:
    return json.dumps({job_id: job.model_dump() for job_id, job in JOB_STATE.items()})
