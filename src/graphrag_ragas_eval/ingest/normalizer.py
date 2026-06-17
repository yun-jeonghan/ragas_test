from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import re

from .models import ExtractionManifestEntry, NormalizedDocument
from .markdown import preprocess_markdown_text
from .pdf import PdfExtractionPolicy, extract_pdf_document


SUPPORTED_SOURCE_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".pdf"}


@dataclass(frozen=True, slots=True)
class DocumentNormalizer:
    """Normalize mixed source inputs into canonical TXT files.

    The normalizer is intentionally the only place that knows how to turn PDFs or other
    structured inputs into downstream-safe text. GraphRAG, Ragas, and BenchmarkQED read
    the canonical TXT tree that this class writes.
    """

    source_root: Path
    canonical_root: Path
    manifest_path: Path
    pdf_policy: PdfExtractionPolicy = field(default_factory=PdfExtractionPolicy)

    def normalize(self, *, clean: bool = False) -> list[NormalizedDocument]:
        if not self.source_root.exists():
            raise FileNotFoundError(self.source_root)
        if clean:
            shutil.rmtree(self.canonical_root, ignore_errors=True)
            shutil.rmtree(self.manifest_path.parent, ignore_errors=True)
        self.canonical_root.mkdir(parents=True, exist_ok=True)
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)

        documents: list[NormalizedDocument] = []
        manifest_entries: list[ExtractionManifestEntry] = []
        for source_path in sorted(self.source_root.rglob("*")):
            if not source_path.is_file() or source_path.suffix.lower() not in SUPPORTED_SOURCE_EXTENSIONS:
                continue
            normalized_documents, manifest_entry = self._normalize_file(source_path)
            documents.extend(normalized_documents)
            manifest_entries.extend(manifest_entry)

        self._write_manifest(manifest_entries)
        return documents

    def _normalize_file(self, source_path: Path) -> tuple[list[NormalizedDocument], list[ExtractionManifestEntry]]:
        suffix = source_path.suffix.lower()
        if suffix == ".pdf":
            return self._normalize_pdf(source_path)
        if suffix == ".json":
            return self._normalize_json(source_path)
        return self._normalize_plain_text(source_path)

    def _normalize_plain_text(
        self, source_path: Path
    ) -> tuple[list[NormalizedDocument], list[ExtractionManifestEntry]]:
        raw_text = source_path.read_text(encoding="utf-8")
        metadata: dict[str, Any] = {"extraction": "direct"}
        kind = source_path.suffix.lower().lstrip(".")
        title = source_path.stem
        text = raw_text
        if source_path.suffix.lower() == ".md":
            result = preprocess_markdown_text(raw_text)
            text = result.text
            kind = "markdown"
            metadata.update(result.metadata)
            metadata["extraction"] = "markdown"
            if result.title:
                title = result.title
        canonical_path = self._canonical_path(source_path).with_suffix(".txt")
        self._write_text(canonical_path, text)
        document = NormalizedDocument(
            id=canonical_path.stem,
            title=title,
            text=text,
            source_path=source_path,
            canonical_path=canonical_path,
            kind=kind,
            metadata=metadata,
        )
        entry = ExtractionManifestEntry(
            source_path=source_path,
            canonical_path=canonical_path,
            kind=document.kind,
            strategy=metadata.get("extraction", "direct"),
            page_count=0,
            text_page_count=0,
            ocr_page_count=0,
            text_chars=len(text),
            metadata=metadata,
        )
        return [document], [entry]

    def _normalize_json(
        self, source_path: Path
    ) -> tuple[list[NormalizedDocument], list[ExtractionManifestEntry]]:
        payload = json.loads(source_path.read_text(encoding="utf-8"))
        rows: list[dict[str, Any]]
        if isinstance(payload, list):
            rows = [row for row in payload if isinstance(row, dict)]
        elif isinstance(payload, dict):
            rows = [row for row in payload.get("documents", []) if isinstance(row, dict)]
            if not rows:
                rows = [payload]
        else:
            rows = [
                {
                    "id": source_path.stem,
                    "title": source_path.stem,
                    "text": json.dumps(payload, ensure_ascii=False, indent=2),
                }
            ]

        documents: list[NormalizedDocument] = []
        manifest_entries: list[ExtractionManifestEntry] = []
        for index, row in enumerate(rows, start=1):
            row_id = str(row.get("id") or f"row-{index}")
            title = str(row.get("title") or source_path.stem)
            text = str(row.get("text") or json.dumps(row, ensure_ascii=False, indent=2))
            canonical_path = self._canonical_path(
                source_path, suffix=f"__{index:04d}__{self._safe_token(row_id)}"
            ).with_suffix(".txt")
            self._write_text(canonical_path, text)
            documents.append(
                NormalizedDocument(
                    id=row_id,
                    title=title,
                    text=text,
                    source_path=source_path,
                    canonical_path=canonical_path,
                    kind="json",
                    metadata={"row_index": index},
                )
            )
            manifest_entries.append(
                ExtractionManifestEntry(
                    source_path=source_path,
                    canonical_path=canonical_path,
                    kind="json",
                    strategy="json-row",
                    page_count=0,
                    text_page_count=0,
                    ocr_page_count=0,
                    text_chars=len(text),
                    metadata={"row_index": index},
                )
            )
        return documents, manifest_entries

    def _normalize_pdf(
        self, source_path: Path
    ) -> tuple[list[NormalizedDocument], list[ExtractionManifestEntry]]:
        result = extract_pdf_document(source_path, self.pdf_policy)
        canonical_path = self._canonical_path(source_path).with_suffix(".txt")
        self._write_text(canonical_path, result.text)
        document = NormalizedDocument(
            id=canonical_path.stem,
            title=canonical_path.stem,
            text=result.text,
            source_path=source_path,
            canonical_path=canonical_path,
            kind="pdf",
            metadata={
                "strategy": result.strategy,
                "page_count": result.page_count,
                "text_page_count": result.text_page_count,
                "ocr_page_count": result.ocr_page_count,
                "warnings": list(result.warnings),
            },
        )
        entry = ExtractionManifestEntry(
            source_path=source_path,
            canonical_path=canonical_path,
            kind="pdf",
            strategy=result.strategy,
            page_count=result.page_count,
            text_page_count=result.text_page_count,
            ocr_page_count=result.ocr_page_count,
            text_chars=result.char_count,
            warnings=result.warnings,
            metadata={
                "strategy": result.strategy,
                "pages": [
                    {
                        "page_number": page.page_number,
                        "text": page.text,
                        "source": page.source,
                    }
                    for page in result.pages
                ],
                "blocks": [
                    {
                        "kind": block.kind,
                        "text": block.text,
                        "page_index": block.page_index,
                        "bbox": list(block.bbox) if block.bbox is not None else None,
                        "metadata": block.metadata,
                    }
                    for block in result.blocks
                ],
            },
        )
        return [document], [entry]

    def _canonical_path(self, source_path: Path, *, suffix: str = "") -> Path:
        relative = source_path.relative_to(self.source_root)
        parts = list(relative.parts)
        if not parts:
            parts = [source_path.stem]
        *parents, filename = parts
        stem = Path(filename).stem + suffix
        return self.canonical_root.joinpath(*parents, f"{stem}.txt")

    def _safe_token(self, value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
        return cleaned or "item"

    def _write_text(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def _write_manifest(self, entries: list[ExtractionManifestEntry]) -> None:
        lines = []
        for entry in entries:
            lines.append(
                json.dumps(
                    {
                        "source_path": str(entry.source_path),
                        "canonical_path": str(entry.canonical_path),
                        "kind": entry.kind,
                        "strategy": entry.strategy,
                        "page_count": entry.page_count,
                        "text_page_count": entry.text_page_count,
                        "ocr_page_count": entry.ocr_page_count,
                        "text_chars": entry.text_chars,
                        "warnings": list(entry.warnings),
                        "metadata": entry.metadata,
                    },
                    ensure_ascii=False,
                )
            )
        self.manifest_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def normalize_source_tree(
    source_root: Path,
    canonical_root: Path,
    manifest_path: Path,
    *,
    clean: bool = False,
    pdf_policy: PdfExtractionPolicy | None = None,
) -> list[NormalizedDocument]:
    """Normalize a source tree into canonical TXT files.

    This helper exists so CLI and GraphRAG staging can share one implementation.
    """

    normalizer = DocumentNormalizer(
        source_root=source_root,
        canonical_root=canonical_root,
        manifest_path=manifest_path,
        pdf_policy=pdf_policy or PdfExtractionPolicy(),
    )
    return normalizer.normalize(clean=clean)
