#!/usr/bin/env python3
"""Chunk extracted section JSON and write inspectable chunk preview files.

Reads C# extractor output (full section text) and runs the RAG chunker so you
can see heading_path / nested outlines without changing eval_regex.sh.

Examples:
  python3 scripts/preview_chunks.py
  python3 scripts/preview_chunks.py data/sec-filings/extracted/aapl-20240928.json
  python3 scripts/preview_chunks.py data/sec-filings/extracted --all
  python3 scripts/preview_chunks.py ... --section Business --limit 15
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "rag"))

from rag.chunker import (  # noqa: E402
    classify_block,
    chunk_section_text,
    merge_mda_title_blocks,
    split_paragraph_blocks,
)

DEFAULT_INPUT = ROOT / "data/sec-filings/extracted/aapl-20240928.json"
DEFAULT_OUT_DIR = ROOT / "data/sec-filings/chunked"


def load_extraction(path: Path) -> dict:
    return json.loads(path.read_text())


def document_id_for(data: dict, path: Path) -> str:
    return data.get("documentId") or data.get("document_id") or path.stem


def build_chunk_preview(data: dict, path: Path, section_filter: str | None = None) -> dict:
    doc_id = document_id_for(data, path)
    sections_out: list[dict] = []
    all_chunks: list[dict] = []

    for section in data.get("sections", []):
        name = section.get("name", "unknown")
        if section_filter and name != section_filter:
            continue

        text = section.get("text", "")
        blocks = merge_mda_title_blocks(split_paragraph_blocks(text))
        kinds = {"heading": 0, "text": 0, "noise": 0, "table": 0}
        block_rows: list[dict] = []
        for start, end, block in blocks:
            kind = classify_block(block)
            kinds[kind] += 1
            block_rows.append(
                {
                    "kind": kind,
                    "start": start,
                    "end": end,
                    "chars": len(block),
                    "preview": " ".join(block.split())[:120],
                }
            )

        chunks = chunk_section_text(doc_id, name, text)
        all_chunks.extend(chunks)
        heading_paths = []
        for chunk in chunks:
            path_value = chunk.get("metadata", {}).get("heading_path")
            if path_value and path_value not in heading_paths:
                heading_paths.append(path_value)

        sections_out.append(
            {
                "name": name,
                "blockCounts": kinds,
                "blockCount": len(blocks),
                "chunkCount": len(chunks),
                "headingPaths": heading_paths,
                "blocks": block_rows,
                "chunks": chunks,
            }
        )

    return {
        "documentId": doc_id,
        "sourcePath": str(path),
        "sectionCount": len(sections_out),
        "chunkCount": len(all_chunks),
        "sections": sections_out,
    }


def print_console_summary(preview: dict, limit: int) -> None:
    print(f"\n# {preview['documentId']}  chunks={preview['chunkCount']}")
    for section in preview["sections"]:
        print(
            f"\n=== {section['name']}  blocks={section['blockCount']}  "
            f"{section['blockCounts']}  embeddable={section['chunkCount']} ==="
        )
        if section["headingPaths"]:
            print("  heading paths:")
            for path_value in section["headingPaths"][:limit]:
                print(f"    - {path_value}")
            if len(section["headingPaths"]) > limit:
                print(f"    ... +{len(section['headingPaths']) - limit} more paths")

        print("  blocks:")
        for i, block in enumerate(section["blocks"][:limit]):
            print(f"    [{i:02d}] {block['kind']:7s}  {block['preview']}")
        if len(section["blocks"]) > limit:
            print(f"    ... +{len(section['blocks']) - limit} more blocks")

        print("  sample chunks:")
        for chunk in section["chunks"][: min(5, limit)]:
            heading_path = chunk.get("metadata", {}).get("heading_path")
            block_type = chunk.get("metadata", {}).get("block_type")
            text_preview = " ".join(chunk.get("text", "").split())[:100]
            print(f"    type={block_type} path={heading_path!r}")
            print(f"      text={text_preview!r}")


def write_preview(preview: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{preview['documentId']}.chunks.json"
    out_path.write_text(json.dumps(preview, indent=2, ensure_ascii=False) + "\n")
    return out_path


def iter_input_paths(raw: Path, all_files: bool) -> list[Path]:
    if raw.is_file():
        return [raw]
    if raw.is_dir():
        paths = sorted(
            p
            for p in raw.glob("*.json")
            if p.name != "validation-report.json" and not p.name.endswith(".chunks.json")
        )
        if not all_files and len(paths) > 1:
            # Default single-file mode when a dir is passed without --all:
            # prefer aapl sample if present, else first file.
            for preferred in paths:
                if preferred.name.startswith("aapl-"):
                    return [preferred]
            return paths[:1]
        return paths
    raise FileNotFoundError(raw)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input_path",
        nargs="?",
        default=str(DEFAULT_INPUT),
        help="Extracted JSON file or directory (default: aapl-20240928.json)",
    )
    parser.add_argument(
        "--out-dir",
        default=str(DEFAULT_OUT_DIR),
        help=f"Directory for *.chunks.json output (default: {DEFAULT_OUT_DIR})",
    )
    parser.add_argument("--all", action="store_true", help="Process every JSON in an input directory")
    parser.add_argument("--section", help="Only include one section name")
    parser.add_argument("--limit", type=int, default=20, help="Console preview line limit per section")
    parser.add_argument("--quiet", action="store_true", help="Write JSON only; skip console summary")
    args = parser.parse_args()

    input_path = Path(args.input_path)
    out_dir = Path(args.out_dir)
    try:
        paths = iter_input_paths(input_path, all_files=args.all)
    except FileNotFoundError:
        print(f"Input not found: {input_path}", file=sys.stderr)
        return 1

    written: list[Path] = []
    for path in paths:
        data = load_extraction(path)
        preview = build_chunk_preview(data, path, section_filter=args.section)
        out_path = write_preview(preview, out_dir)
        written.append(out_path)
        if not args.quiet:
            print_console_summary(preview, limit=args.limit)
            print(f"\nWrote {out_path}")

    if args.quiet:
        for path in written:
            print(path)
    elif len(written) > 1:
        print(f"\nWrote {len(written)} files under {out_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
