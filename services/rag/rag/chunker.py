from __future__ import annotations

import re
from typing import Any, Literal

BlockKind = Literal["heading", "text", "noise", "table"]

TABLE_START = "[TABLE]"
TABLE_END = "[/TABLE]"
_TABLE_BLOCK = re.compile(
    re.escape(TABLE_START) + r".*?" + re.escape(TABLE_END),
    re.DOTALL,
)

# Page chrome left by many 10-K cleaners, e.g. "Apple Inc. | 2024 Form 10-K | 5"
_PAGE_HEADER = re.compile(
    r"^.+\|\s*\d{4}\s+Form\s+10-K\s*\|\s*\d+\s*$",
    re.IGNORECASE,
)
_BULLET_START = re.compile(r"^[•\-\*\u2022●▪◦]\s*")
_ONLY_DIGITS = re.compile(r"^\d+$")
# Standalone page markers left after HTML cleaning, e.g. "4." or "Page 32"
_PAGE_NUMBER = re.compile(r"^(?:page\s+)?\d{1,4}\.?$", re.IGNORECASE)
_SEPARATOR = re.compile(r"^[-–—_=.*•·]{1,12}$")

_MDA_FULL = (
    "Management's Discussion and Analysis of Financial Condition and Results of Operations"
)
_MDA_HEAD = re.compile(
    r"^management['’′`]?s\s+discussion\s+and\s+analysis$",
    re.IGNORECASE,
)
_MDA_TAIL = re.compile(
    r"^of\s+financial\s+condition\s+and\s+results\s+of\s+operations\.?$",
    re.IGNORECASE,
)
_MDA_FULL_RE = re.compile(
    r"^management['’′`]?s\s+discussion\s+and\s+analysis\s+"
    r"of\s+financial\s+condition\s+and\s+results\s+of\s+operations\.?$",
    re.IGNORECASE,
)


def normalize_whitespace(text: str) -> str:
    """Collapse runs of horizontal whitespace; preserve paragraph breaks."""
    text = re.sub(r"[ \t\f\v\u00A0]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_paragraph_blocks(text: str) -> list[tuple[int, int, str]]:
    """Split cleaned section text on blank lines; keep [TABLE] spans intact."""
    clean = normalize_whitespace(text)
    if not clean:
        return []

    blocks: list[tuple[int, int, str]] = []
    pos = 0
    for match in _TABLE_BLOCK.finditer(clean):
        blocks.extend(_split_prose_region(clean, pos, match.start()))
        blocks.append((match.start(), match.end(), match.group(0).strip()))
        pos = match.end()
    blocks.extend(_split_prose_region(clean, pos, len(clean)))
    return [(s, e, b) for s, e, b in blocks if b]


def _split_prose_region(
    clean: str, start: int, end: int
) -> list[tuple[int, int, str]]:
    if start >= end:
        return []
    region = clean[start:end]
    blocks: list[tuple[int, int, str]] = []
    offset = 0
    for part in region.split("\n\n"):
        loc = region.find(part, offset)
        abs_start = start + loc
        abs_end = abs_start + len(part)
        blocks.append((abs_start, abs_end, part.strip()))
        offset = loc + len(part)
    return blocks


def is_table_block(block: str) -> bool:
    text = block.strip()
    return text.startswith(TABLE_START) and text.endswith(TABLE_END)


def table_embed_text(block: str) -> str:
    """Strip [TABLE] markers; keep linearized fact lines for embedding."""
    text = block.strip()
    if text.startswith(TABLE_START):
        text = text[len(TABLE_START) :].lstrip("\n")
    if text.endswith(TABLE_END):
        text = text[: -len(TABLE_END)].rstrip("\n")
    return text.strip()


def normalize_heading_text(block: str) -> str:
    """Canonicalize known split/partial MD&A titles."""
    text = block.strip()
    if _MDA_FULL_RE.match(text) or _MDA_HEAD.match(text) or _MDA_TAIL.match(text):
        return _MDA_FULL
    return text


def merge_mda_title_blocks(
    blocks: list[tuple[int, int, str]],
) -> list[tuple[int, int, str]]:
    """Join 'Management's Discussion...' + 'of Financial Condition...' into one heading."""
    if not blocks:
        return []

    merged: list[tuple[int, int, str]] = []
    i = 0
    while i < len(blocks):
        start, end, text = blocks[i]
        if (
            i + 1 < len(blocks)
            and _MDA_HEAD.match(text)
            and _MDA_TAIL.match(blocks[i + 1][2])
        ):
            merged.append((start, blocks[i + 1][1], _MDA_FULL))
            i += 2
            continue
        merged.append((start, end, normalize_heading_text(text)))
        i += 1
    return merged


def _looks_title_case(text: str) -> bool:
    words = re.findall(r"[A-Za-z0-9&]+", text)
    if not words:
        return False
    small = {"a", "an", "and", "as", "at", "for", "in", "of", "on", "or", "the", "to", "with"}
    titled = 0
    for word in words:
        if word.lower() in small or word[0].isupper():
            titled += 1
    return titled / len(words) >= 0.7


def is_unembeddable(text: str) -> bool:
    """Page numbers, separators, and other fragments that should not be embedded."""
    value = text.strip()
    if not value:
        return True
    if _PAGE_HEADER.match(value) or value.lower() == "table of contents":
        return True
    if _ONLY_DIGITS.match(value) or _PAGE_NUMBER.match(value) or _SEPARATOR.match(value):
        return True
    return False


def classify_block(block: str) -> BlockKind:
    """Heuristic heading vs body vs noise for cleaned 10-K paragraphs."""
    text = block.strip()
    if not text:
        return "noise"

    if is_table_block(text):
        return "table"

    if _MDA_FULL_RE.match(text) or _MDA_HEAD.match(text) or _MDA_TAIL.match(text):
        return "heading"

    if is_unembeddable(text):
        return "noise"

    if _BULLET_START.match(text):
        return "text"

    word_count = len(text.split())
    if len(text) > 100 or word_count > 14:
        return "text"

    # Prose sentences end with a period; short headings usually do not.
    if text.endswith(".") and word_count > 4:
        return "text"

    if text.endswith(":") or text.isupper() or _looks_title_case(text):
        return "heading"

    # Short fragments without sentence punctuation (e.g. "iPhone", "Products").
    if not re.search(r"[.!?]$", text) and word_count <= 8:
        return "heading"

    return "text"


def semantic_heading_level(text: str) -> int:
    """Smaller number = higher in the outline (1 = major section)."""
    words = text.split()
    if _MDA_FULL_RE.match(text) or text == _MDA_FULL:
        return 1
    if text.isupper() and len(words) >= 2:
        return 1
    if len(words) >= 4:
        return 1
    if len(words) >= 2:
        return 2
    return 3


def is_major_heading(text: str) -> bool:
    """Headings that should outdent to the top of the section outline."""
    if text == _MDA_FULL or _MDA_FULL_RE.match(text):
        return True
    words = text.split()
    if text.isupper() and len(words) >= 2:
        return True
    if re.search(r"\brisks?\b", text, re.IGNORECASE) and len(words) >= 3:
        return True
    return False


def update_heading_stack(
    stack: list[tuple[int, str]],
    heading: str,
    *,
    nested_under_previous: bool,
) -> list[tuple[int, str]]:
    """
    Maintain an outline stack for nested heading paths.

    Consecutive headings nest (Products then iPhone → Products > iPhone).
    A heading after body text becomes a sibling of the previous leaf.
    Major headings outdent to the top. A short heading after a long leaf
    (e.g. Services after Wearables, Home and Accessories) outdents to the
    root section level so it becomes a peer of Products, not a child.
    """
    heading = normalize_heading_text(heading)
    if nested_under_previous and stack:
        level = stack[-1][0] + 1
        return stack + [(level, heading)]

    if not stack:
        return [(semantic_heading_level(heading), heading)]

    leaf_level, leaf_title = stack[-1]
    if is_major_heading(heading):
        level = 1
    elif len(leaf_title.split()) >= 4 and len(heading.split()) <= 2:
        level = stack[0][0]
    else:
        level = leaf_level

    next_stack = list(stack)
    while next_stack and next_stack[-1][0] >= level:
        next_stack.pop()
    next_stack.append((level, heading))
    return next_stack


def heading_path(stack: list[tuple[int, str]]) -> str | None:
    if not stack:
        return None
    return " > ".join(title for _, title in stack)


def chunk_section_text(
    document_id: str,
    section: str,
    text: str,
    size: int = 1200,
    *,
    include_heading_prefix: bool = True,
) -> list[dict[str, Any]]:
    """
    Chunk a cleaned section on blank lines (\\n\\n).

    Headings and page-number fragments are not emitted as chunks.
    Headings only update the outline; each body/table chunk inherits a nested
    heading path in metadata (and optionally as a text prefix).
    ``[TABLE]...[/TABLE]`` spans stay one chunk (not sliced, not headings).
    Oversized prose blocks are sliced near ``size`` characters, backing off to
    the last sentence punctuation or whitespace in the final quarter of the
    window when possible.
    """
    chunks: list[dict[str, Any]] = []
    chunk_index = 0
    stack: list[tuple[int, str]] = []
    last_was_heading = False

    blocks = merge_mda_title_blocks(split_paragraph_blocks(text))
    for start, end, block in blocks:
        kind = classify_block(block)
        if kind == "noise":
            last_was_heading = False
            continue
        if kind == "heading":
            stack = update_heading_stack(
                stack,
                block,
                nested_under_previous=last_was_heading,
            )
            last_was_heading = True
            continue

        last_was_heading = False
        path = heading_path(stack)
        if kind == "table":
            pieces = [table_embed_text(block)]
            block_type = "table"
        else:
            pieces = _slice_text(block, size)
            block_type = "text"
        cursor = start
        for piece in pieces:
            piece_end = end if kind == "table" else cursor + len(piece)
            if kind != "table" and is_unembeddable(piece):
                cursor = piece_end
                continue
            embed_text = f"{path}\n\n{piece}" if include_heading_prefix and path else piece
            chunks.append(
                {
                    "chunk_id": f"{document_id}:{section}:{chunk_index}",
                    "source_doc_id": document_id,
                    "section": section,
                    "text": embed_text,
                    "char_range": [start if kind == "table" else cursor, piece_end],
                    "token_count": max(1, len(embed_text.split())),
                    "metadata": {
                        "section": section,
                        "block_type": block_type,
                        "heading": stack[-1][1] if stack else None,
                        "heading_path": path,
                        "heading_stack": [title for _, title in stack],
                    },
                    "citation_locator": {
                        "document_id": document_id,
                        "section": section,
                        "heading": stack[-1][1] if stack else None,
                        "heading_path": path,
                    },
                }
            )
            chunk_index += 1
            cursor = piece_end

    return chunks


_SENTENCE_END = ".!?"


def _slice_text(text: str, size: int) -> list[str]:
    """Slice oversized prose near ``size``, preferring sentence then whitespace."""
    if len(text) <= size:
        return [text]
    if size <= 0:
        raise ValueError("size must be positive")

    pieces: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        remaining = n - start
        if remaining <= size:
            pieces.append(text[start:])
            break
        cut = _boundary_cut(text[start : start + size])
        pieces.append(text[start : start + cut])
        start += cut
    return pieces


def _boundary_cut(window: str) -> int:
    """Exclusive cut index within a full-size window. Always at least 1."""
    lookback_start = len(window) - max(len(window) // 4, 1)
    best_punct = -1
    for mark in _SENTENCE_END:
        idx = window.rfind(mark)
        if idx >= lookback_start:
            best_punct = max(best_punct, idx)
    if best_punct >= lookback_start:
        return best_punct + 1
    for idx in range(len(window) - 1, lookback_start - 1, -1):
        if window[idx].isspace():
            return idx + 1
    return len(window)
