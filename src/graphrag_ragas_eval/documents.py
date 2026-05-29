from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class LoadedDocument:
    id: str
    title: str
    text: str
    source_path: Path | None = None


def load_documents(source: Path) -> list[LoadedDocument]:
    if not source.exists():
        raise FileNotFoundError(source)

    documents: list[LoadedDocument] = []
    files = [source] if source.is_file() else [path for path in sorted(source.rglob("*")) if path.is_file()]
    for path in files:
        suffix = path.suffix.lower()
        if suffix not in {".txt", ".md", ".json"}:
            continue
        if suffix == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            rows = payload if isinstance(payload, list) else payload.get("documents", [])
            for row in rows:
                documents.append(
                    LoadedDocument(
                        id=str(row.get("id") or path.name),
                        title=str(row.get("title") or path.stem),
                        text=str(row.get("text") or ""),
                        source_path=path,
                    )
                )
            continue
        documents.append(
            LoadedDocument(
                id=path.name,
                title=path.stem,
                text=path.read_text(encoding="utf-8"),
                source_path=path,
            )
        )
    return documents


def first_sentence(text: str) -> str:
    parts = re.split(r"[.!?]\s+", text.strip(), maxsplit=1)
    return parts[0].strip() if parts else ""


def summarize_document(text: str, max_sentences: int = 2) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(sentence for sentence in sentences[:max_sentences] if sentence).strip()


def summarize_documents(documents: list[LoadedDocument]) -> dict[str, Any]:
    summaries = [
        {
            "id": doc.id,
            "title": doc.title,
            "summary": summarize_document(doc.text),
            "source_path": str(doc.source_path) if doc.source_path else None,
        }
        for doc in documents
    ]
    corpus = " ".join(item["summary"] for item in summaries if item["summary"])
    themes = [theme.strip() for theme in re.split(r"[.;]\s*", corpus) if theme.strip()][:5]
    return {
        "documents": summaries,
        "corpus_summary": summarize_document(corpus, max_sentences=3),
        "themes": themes,
    }
