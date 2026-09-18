#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REQUIRED_SECTIONS = ["Business", "Risk Factors", "MD&A", "Signatures"]
REQUIRED_FIELDS = ["fiscal_year_ended", "company_name"]
TABLE_START = "[TABLE]"
TABLE_END = "[/TABLE]"
TABLE_BLOCK = re.compile(
    re.escape(TABLE_START) + r"(.*?)" + re.escape(TABLE_END),
    re.DOTALL,
)


def preview(text: str, limit: int = 90) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


FIELD_ORDER = (
    "documentId",
    "sourcePath",
    "fields",
    "sections",
    "validationStatus",
    "warnings",
    "regexMatches",
)


def reorder_extraction(data: dict) -> dict:
    """Put fields above sections for easier eval inspection; preserve other keys."""
    ordered: dict = {}
    for key in FIELD_ORDER:
        if key in data:
            ordered[key] = data[key]
    for key, value in data.items():
        if key not in ordered:
            ordered[key] = value
    return ordered


def load_extractions(output_dir: Path) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(output_dir.glob("*.json")):
        if path.name == "validation-report.json":
            continue
        data = reorder_extraction(json.loads(path.read_text()))
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        rows.append(data)
    return rows


def extract_tables(text: str) -> list[str]:
    return [block.strip() for block in TABLE_BLOCK.findall(text or "")]


def table_preview_line(block: str) -> str:
    """Prefer a fact line (label: values) over a section caption ending in ':'."""
    first = ""
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if not first:
            first = stripped
        if ":" in stripped and not stripped.endswith(":"):
            return stripped
    return first


def section_tables(row: dict) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for item in row.get("sections", []):
        found[item.get("name", "unknown")] = extract_tables(item.get("text", ""))
    return found


def table_count(row: dict) -> int:
    return sum(len(blocks) for blocks in section_tables(row).values())


def cell(ok: bool, extra: str = "") -> str:
    if ok:
        return extra or "HIT"
    return "MISS"


def print_table(rows: list[dict]) -> None:
    headers = ["Filing", "Status", *REQUIRED_SECTIONS, *REQUIRED_FIELDS, "Tables"]
    table: list[list[str]] = [headers]
    for row in rows:
        sections = {item["name"]: item for item in row.get("sections", [])}
        fields = row.get("fields", {})
        by_section = section_tables(row)
        line = [row.get("documentId", "unknown"), row.get("validationStatus", "unknown")]
        for name in REQUIRED_SECTIONS:
            section = sections.get(name)
            if section:
                chars = len(section.get("text", ""))
                n_tables = len(by_section.get(name, []))
                cell_text = f"HIT/{chars}"
                if n_tables:
                    cell_text += f" t={n_tables}"
                line.append(cell_text)
            else:
                line.append("MISS")
        for name in REQUIRED_FIELDS:
            value = fields.get(name)
            line.append(preview(value, 24) if value else "MISS")
        line.append(str(table_count(row)))
        table.append(line)

    widths = [max(len(row[i]) for row in table) for i in range(len(headers))]
    for index, row in enumerate(table):
        rendered = "  ".join(value.ljust(widths[i]) for i, value in enumerate(row))
        print(rendered)
        if index == 0:
            print("  ".join("-" * width for width in widths))


def print_summary(rows: list[dict]) -> None:
    total = len(rows)
    if total == 0:
        print("No extraction JSON files found.")
        return

    status_counts: dict[str, int] = {}
    section_hits = {name: 0 for name in REQUIRED_SECTIONS}
    field_hits = {name: 0 for name in REQUIRED_FIELDS}

    for row in rows:
        status = row.get("validationStatus", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        names = {item["name"] for item in row.get("sections", [])}
        fields = row.get("fields", {})
        for name in REQUIRED_SECTIONS:
            if name in names:
                section_hits[name] += 1
        for name in REQUIRED_FIELDS:
            if name in fields:
                field_hits[name] += 1

    print()
    print(f"Files: {total}")
    print("Status counts: " + ", ".join(f"{key}={value}" for key, value in sorted(status_counts.items())))
    print("Section hit rate:")
    for name in REQUIRED_SECTIONS:
        print(f"  {name}: {section_hits[name]}/{total}")
    print("Field hit rate:")
    for name in REQUIRED_FIELDS:
        print(f"  {name}: {field_hits[name]}/{total}")
    print("Tables identified ([TABLE] blocks):")
    for name in REQUIRED_SECTIONS:
        hits = sum(1 for row in rows if section_tables(row).get(name))
        total_tables = sum(len(section_tables(row).get(name, [])) for row in rows)
        print(f"  {name}: {hits}/{total} filings, {total_tables} tables")


def print_previews(rows: list[dict]) -> None:
    print()
    print("Section previews (first hit text):")
    for row in rows:
        print(f"\n# {row.get('documentId')}")
        sections = {item["name"]: item.get("text", "") for item in row.get("sections", [])}
        for name in REQUIRED_SECTIONS:
            text = sections.get(name)
            if text:
                print(f"  {name}: {preview(text, 140)}")
            else:
                print(f"  {name}: MISS")
        fields = row.get("fields", {})
        for name in REQUIRED_FIELDS:
            print(f"  {name}: {fields.get(name, 'MISS')}")
        warnings = row.get("warnings", [])
        if warnings:
            print(f"  warnings: {'; '.join(warnings)}")


def print_identified_tables(rows: list[dict], preview_limit: int = 3) -> None:
    print()
    print("Tables identified (linearized [TABLE] blocks):")
    for row in rows:
        by_section = section_tables(row)
        total = sum(len(blocks) for blocks in by_section.values())
        print(f"\n# {row.get('documentId')}  tables={total}")
        if total == 0:
            print("  (no [TABLE] blocks in extracted sections)")
            continue
        for name in REQUIRED_SECTIONS:
            blocks = by_section.get(name, [])
            print(f"  {name}: {len(blocks)}")
            for index, block in enumerate(blocks[:preview_limit]):
                print(f"    [{index}] {preview(table_preview_line(block), 120)}")
            if len(blocks) > preview_limit:
                print(f"    ... +{len(blocks) - preview_limit} more")
        extras = [
            (name, blocks)
            for name, blocks in by_section.items()
            if name not in REQUIRED_SECTIONS and blocks
        ]
        for name, blocks in extras:
            print(f"  {name}: {len(blocks)}")


def print_regex_matches(rows: list[dict]) -> None:
    print()
    print("Regex matches (all candidates):")
    for row in rows:
        print(f"\n# {row.get('documentId')}")
        matches = row.get("regexMatches", [])
        if not matches:
            print("  (no regex matches recorded)")
            continue
        for match in matches:
            status = "SELECTED" if match.get("selected") else "skipped"
            reason = match.get("skippedReason") or "-"
            print(
                "  "
                f"[{status}] {match.get('sectionName')} "
                f"#{match.get('matchIndex')} "
                f"start={match.get('startIndex')} "
                f"raw={match.get('rawBodyLength')} "
                f"clean={match.get('cleanedBodyLength')} "
                f"inToc={match.get('inToc')} "
                f"tocLike={match.get('looksLikeTocFragment')} "
                f"reason={reason}"
            )
            print(f"    preview: {preview(match.get('preview', ''), 160)}")


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: eval_regex_report.py <extracted-json-dir>", file=sys.stderr)
        return 2

    output_dir = Path(sys.argv[1])
    if not output_dir.is_dir():
        print(f"Directory not found: {output_dir}", file=sys.stderr)
        return 1

    rows = load_extractions(output_dir)
    print_table(rows)
    print_summary(rows)
    print_previews(rows)
    print_identified_tables(rows)
    print_regex_matches(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
