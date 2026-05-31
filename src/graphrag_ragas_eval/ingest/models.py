from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class CanonicalDocument:
    """A normalized text document that downstream code can read directly."""

    id: str
    title: str
    text: str
    source_path: Path
    canonical_path: Path
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class NormalizedDocument:
    """A document record produced during source normalization."""

    id: str
    title: str
    text: str
    source_path: Path
    canonical_path: Path
    kind: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ExtractionManifestEntry:
    """Per-document provenance for text extraction and OCR fallback."""

    source_path: Path
    canonical_path: Path
    kind: str
    strategy: str
    page_count: int
    text_page_count: int
    ocr_page_count: int
    text_chars: int
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
