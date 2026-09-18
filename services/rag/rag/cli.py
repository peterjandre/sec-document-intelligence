from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from rag.pipeline import index_extracted_json, is_extracted_filing

_THIS_FILE = Path(__file__).resolve()
_RAG_SERVICE_DIR = _THIS_FILE.parents[1]
_REPO_ROOT = _THIS_FILE.parents[3]


def _default_env_file() -> Path | None:
    for candidate in (
        Path.cwd() / ".env",
        _RAG_SERVICE_DIR / ".env",
        _REPO_ROOT / ".env",
        _REPO_ROOT / "services" / "api" / ".env",
    ):
        if candidate.is_file():
            return candidate
    return None


def _load_env_file(path: Path) -> None:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Env file not found: {resolved}")
    load_dotenv(resolved, override=False)
    print(f"Loaded environment from {resolved}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Index extracted SEC JSON into pgvector.")
    parser.add_argument("--input-dir", required=True, help="Directory with extracted JSON files.")
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help=(
            "Path to a .env file with OPENAI_API_KEY, SUPABASE_URL, and "
            "SUPABASE_SERVICE_ROLE_KEY. If omitted, uses the first existing of "
            "./.env, services/rag/.env, repo-root .env, or services/api/.env."
        ),
    )
    args = parser.parse_args()

    env_file = args.env_file if args.env_file is not None else _default_env_file()
    if env_file is not None:
        try:
            _load_env_file(env_file)
        except FileNotFoundError as exc:
            print(exc, file=sys.stderr)
            return 1
    else:
        print("No .env file found; using existing process environment variables.")

    input_dir = Path(args.input_dir)
    paths = [
        str(path)
        for path in sorted(input_dir.glob("*.json"))
        if is_extracted_filing(path)
    ]
    count = index_extracted_json(paths)
    print(f"Indexed {count} chunks from {len(paths)} extracted files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
