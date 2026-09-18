#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INPUT_DIR="${1:-$ROOT_DIR/data/sec-filings}"
OUTPUT_DIR="${2:-$ROOT_DIR/data/sec-filings/extracted}"
EXTRACTOR_DIR="$ROOT_DIR/services/extractor-csharp"
REPORT_PATH="$OUTPUT_DIR/validation-report.json"

if [[ ! -d "$INPUT_DIR" ]]; then
  echo "Input directory not found: $INPUT_DIR" >&2
  exit 1
fi

mkdir -p "$OUTPUT_DIR"
find "$OUTPUT_DIR" -maxdepth 1 -type f -name '*.json' -delete

echo "Building C# extractor..."
dotnet build "$EXTRACTOR_DIR/extractor-csharp.csproj" -c Release >/dev/null

echo "Extracting filings from: $INPUT_DIR"
dotnet run --project "$EXTRACTOR_DIR/extractor-csharp.csproj" -c Release --no-build -- \
  --input "$INPUT_DIR" \
  --output "$OUTPUT_DIR" \
  --report "$REPORT_PATH"

echo
python3 "$ROOT_DIR/scripts/eval_regex_report.py" "$OUTPUT_DIR"
echo
echo "JSON output: $OUTPUT_DIR"
echo "Validation report: $REPORT_PATH"
