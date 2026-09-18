#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXTRACTOR_DIR="$ROOT_DIR/services/extractor-csharp"
OUTPUT_DIR="$ROOT_DIR/data/sec-filings/extracted"
REPORT_PATH="$OUTPUT_DIR/validation-report.json"

echo "Building C# extractor..."
dotnet build "$EXTRACTOR_DIR/extractor-csharp.csproj" -c Release >/dev/null

echo "Running extractor on sample fixture..."
mkdir -p "$OUTPUT_DIR"
dotnet run --project "$EXTRACTOR_DIR/extractor-csharp.csproj" -- \
  --input "$EXTRACTOR_DIR/fixtures" \
  --output "$OUTPUT_DIR" \
  --report "$REPORT_PATH" >/dev/null

echo "Running RAG indexing in local fallback mode..."
python3 - <<'PY'
import sys
from pathlib import Path
root = Path.cwd()
sys.path.append(str(root / "services" / "rag"))
from rag.pipeline import index_extracted_json, retrieve_answer

paths = [
    str(p)
    for p in (root / "data" / "sec-filings" / "extracted").glob("*.json")
    if p.name != "validation-report.json"
]
count = index_extracted_json(paths)
print(f"Indexed chunks: {count}")
result = retrieve_answer("What are the key risk factors?", top_k=3)
print("Answer:", result["answer"])
print("Citations:", len(result["citations"]))
PY

echo "E2E local script completed."
