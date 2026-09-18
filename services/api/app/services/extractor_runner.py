import json
import subprocess
from pathlib import Path


def run_extractor(
    extractor_path: str, input_dir: str, output_dir: str, report_path: str
) -> dict:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    command = [
        extractor_path,
        "--input",
        input_dir,
        "--output",
        output_dir,
        "--report",
        report_path,
    ]
    process = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if process.returncode != 0:
        raise RuntimeError(
            f"Extractor failed ({process.returncode}): {process.stderr.strip()}"
        )
    report = Path(report_path)
    if report.exists():
        return json.loads(report.read_text())
    return {"status": "completed", "warnings": [], "files_processed": 0}
