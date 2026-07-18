from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from langchain_text_splitters import Language, RecursiveCharacterTextSplitter

_ZERO_WIDTH_CHARS = ("\ufeff", "\u200b", "\u200c", "\u200d", "\u2060")
DEFAULT_MARKDOWN_CHUNK_SIZE = 1000
DEFAULT_MARKDOWN_CHUNK_OVERLAP = 200


@dataclass(frozen=True, slots=True)
class MarkdownPreprocessResult:
    text: str
    title: str | None = None
    frontmatter: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MarkdownChunk:
    text: str
    index: int
    total: int
    metadata: dict[str, Any] = field(default_factory=dict)


def preprocess_markdown_text(text: str) -> MarkdownPreprocessResult:
    """Normalize markdown into a stable text form for chunking and indexing.

    The goal is deliberately conservative:
    - keep markdown structure that helps retrieval
    - remove noise that hurts chunking
    - preserve code fences and tables as-is
    """

    normalized = _normalize_unicode(text)
    frontmatter, body = _split_frontmatter(normalized)
    lines = body.splitlines()

    cleaned_lines: list[str] = []
    in_code_block = False
    code_fence = ""
    heading_count = 0
    table_count = 0
    blank_run = 0
    title: str | None = None

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()

        if _is_fence_line(stripped):
            if in_code_block and stripped.startswith(code_fence):
                in_code_block = False
                code_fence = ""
            elif not in_code_block:
                in_code_block = True
                code_fence = stripped[:3]
            cleaned_lines.append(stripped)
            blank_run = 0
            continue

        if in_code_block:
            cleaned_lines.append(line)
            blank_run = 0
            continue

        if not stripped:
            blank_run += 1
            if blank_run <= 1:
                cleaned_lines.append("")
            continue
        blank_run = 0

        if stripped.startswith("#"):
            normalized_heading = _normalize_heading(stripped)
            heading_count += 1
            if title is None:
                title = normalized_heading.lstrip("#").strip() or None
            cleaned_lines.append(normalized_heading)
            continue

        if _looks_like_table_row(stripped):
            table_count += 1
            cleaned_lines.append(stripped)
            continue

        cleaned_lines.append(stripped)

    cleaned_text = "\n".join(cleaned_lines).strip()
    if cleaned_text:
        cleaned_text += "\n"

    metadata: dict[str, Any] = {
        "heading_count": heading_count,
        "table_row_count": table_count,
        "has_frontmatter": bool(frontmatter),
    }
    if frontmatter:
        metadata["frontmatter_keys"] = list(frontmatter.keys())
    if title is None and "title" in frontmatter:
        title = frontmatter["title"].strip() or None

    if title:
        metadata["title"] = title

    return MarkdownPreprocessResult(
        text=cleaned_text,
        title=title,
        frontmatter=frontmatter,
        metadata=metadata,
    )


def split_markdown_text(
    text: str,
    *,
    chunk_size: int = DEFAULT_MARKDOWN_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_MARKDOWN_CHUNK_OVERLAP,
) -> list[MarkdownChunk]:
    """Split markdown with LangChain's RecursiveCharacterTextSplitter.

    This keeps markdown structure-aware separators, but still defers the actual
    chunk sizing logic to the LangChain splitter as requested.
    """

    preprocessed = preprocess_markdown_text(text)
    if not preprocessed.text.strip():
        return []

    splitter = RecursiveCharacterTextSplitter.from_language(
        Language.MARKDOWN,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    chunks = [chunk.strip() for chunk in splitter.split_text(preprocessed.text) if chunk.strip()]
    total = len(chunks)
    return [
        MarkdownChunk(
            text=chunk,
            index=index,
            total=total,
            metadata={
                **preprocessed.metadata,
                "chunk_index": index,
                "chunk_count": total,
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
            },
        )
        for index, chunk in enumerate(chunks, start=1)
    ]


def _normalize_unicode(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    for char in _ZERO_WIDTH_CHARS:
        normalized = normalized.replace(char, "")
    return normalized.lstrip("\ufeff")


def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text

    frontmatter_lines: list[str] = []
    body_start = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            body_start = index + 1
            break
        frontmatter_lines.append(line)

    if body_start is None:
        return {}, text

    frontmatter: dict[str, str] = {}
    for line in frontmatter_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        frontmatter[key.strip()] = value.strip().strip('"').strip("'")
    body = "\n".join(lines[body_start:])
    return frontmatter, body


def _is_fence_line(line: str) -> bool:
    return line.startswith("```") or line.startswith("~~~")


def _normalize_heading(line: str) -> str:
    stripped = line.lstrip("#").strip()
    level = len(line) - len(line.lstrip("#"))
    level = max(1, min(level, 6))
    return f"{'#' * level} {stripped}".rstrip()


def _looks_like_table_row(line: str) -> bool:
    return line.startswith("|") and line.endswith("|") and "|" in line[1:-1]
