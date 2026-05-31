from __future__ import annotations

import importlib
import json
import os
import shutil
import subprocess
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


def _load_pdf_reader() -> type[Any]:
    """Import PdfReader lazily so the package stays importable without pypdf."""

    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - runtime dependency error path
        raise RuntimeError(
            "pypdf is required for PDF extraction. Install it with `pip install pypdf`."
        ) from exc
    return PdfReader


class PdfExtractionMode(str, Enum):
    """Supported PDF extraction strategies."""

    CHANDRA_ONLY = "chandra_only"
    MINERU_HYBRID = "mineru_hybrid"


@runtime_checkable
class PdfTextBackend(Protocol):
    """Backend interface for page-level text extraction."""

    name: str

    def extract_page_text(self, pdf_path: Path, page_number: int, page_count: int) -> str:
        """Extract text for a single 1-based page number."""


@runtime_checkable
class PdfBlockDescriptionBackend(Protocol):
    """Backend interface for describing structural blocks such as images or graphs."""

    name: str

    def describe_block(
        self,
        pdf_path: Path,
        block: "PdfContentBlock",
        *,
        page_number: int,
        page_count: int,
        page_text: str = "",
    ) -> str:
        """Describe a structural block with optional surrounding page text."""


@dataclass(frozen=True, slots=True)
class ChandraPdfOcrBackend:
    """Adapter around a chandra-style OCR or description module.

    The exact chandra API may differ by deployment, so this adapter tries a small set
    of conventional function names. The same backend is used for both page OCR and
    structural block descriptions in the hybrid MinerU flow.
    """

    module_name: str = "chandra"
    entrypoint_names: tuple[str, ...] = ("extract_page_text", "ocr_page", "extract_text")
    description_entrypoint_names: tuple[str, ...] = (
        "describe_block",
        "describe_image",
        "describe_page_element",
        "describe_region",
    )
    name: str = "chandra"

    def extract_page_text(self, pdf_path: Path, page_number: int, page_count: int) -> str:
        module = importlib.import_module(self.module_name)
        for entrypoint_name in self.entrypoint_names:
            entrypoint = getattr(module, entrypoint_name, None)
            if callable(entrypoint):
                for call in (
                    lambda: entrypoint(pdf_path=pdf_path, page_number=page_number, page_count=page_count),
                    lambda: entrypoint(str(pdf_path), page_number, page_count),
                    lambda: entrypoint(str(pdf_path), page_number),
                ):
                    try:
                        result = call()
                    except TypeError:
                        continue
                    if result is not None:
                        return str(result)
        raise RuntimeError(
            f"Unable to find a supported OCR entrypoint in module {self.module_name!r}."
        )

    def describe_block(
        self,
        pdf_path: Path,
        block: "PdfContentBlock",
        *,
        page_number: int,
        page_count: int,
        page_text: str = "",
    ) -> str:
        module = importlib.import_module(self.module_name)
        for entrypoint_name in self.description_entrypoint_names:
            entrypoint = getattr(module, entrypoint_name, None)
            if not callable(entrypoint):
                continue
            for call in (
                lambda: entrypoint(
                    pdf_path=pdf_path,
                    block=block,
                    page_number=page_number,
                    page_count=page_count,
                    page_text=page_text,
                ),
                lambda: entrypoint(
                    str(pdf_path),
                    block.kind,
                    block.text,
                    page_number,
                    page_count,
                    page_text,
                    block.metadata,
                ),
                lambda: entrypoint(str(pdf_path), page_number, page_text),
            ):
                try:
                    result = call()
                except TypeError:
                    continue
                if result is not None:
                    return str(result)
        return _fallback_block_description(block, page_number=page_number)


def load_pdf_ocr_backend(spec: str | None) -> PdfTextBackend | None:
    """Load a page OCR backend from a simple string spec."""

    if spec is None or not str(spec).strip():
        return None
    normalized = str(spec).strip()
    if normalized == "chandra":
        return ChandraPdfOcrBackend()
    return ChandraPdfOcrBackend(module_name=normalized, name=normalized)


@dataclass(frozen=True, slots=True)
class PdfContentBlock:
    """A structured block extracted from a PDF."""

    kind: str
    text: str
    page_index: int
    bbox: tuple[float, float, float, float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def normalized_kind(self) -> str:
        return self.kind.strip().lower()


@dataclass(frozen=True, slots=True)
class PdfPageExtraction:
    page_number: int
    text: str
    source: str


@dataclass(frozen=True, slots=True)
class PdfExtractionPolicy:
    """Extraction policy for either direct OCR or MinerU hybrid parsing."""

    mode: PdfExtractionMode = PdfExtractionMode.CHANDRA_ONLY
    min_text_chars: int = 20
    preserve_layout: bool = False
    include_page_markers: bool = True
    ocr_backend: PdfTextBackend | None = None
    block_description_backend: PdfBlockDescriptionBackend | None = None
    mineru_command: str = "mineru"
    mineru_output_artifact: str = "*content_list*.json"


@dataclass(frozen=True, slots=True)
class PdfExtractionResult:
    source_path: Path
    strategy: str
    text: str
    blocks: tuple[PdfContentBlock, ...]
    pages: tuple[PdfPageExtraction, ...]
    page_count: int
    text_page_count: int
    ocr_page_count: int
    warnings: tuple[str, ...] = ()

    @property
    def char_count(self) -> int:
        return len(self.text)


@dataclass(frozen=True, slots=True)
class PdfMinerUParseResult:
    source_path: Path
    blocks: tuple[PdfContentBlock, ...]
    output_dir: Path
    page_count: int
    warnings: tuple[str, ...] = ()


def load_pdf_extraction_policy(env: dict[str, str] | None = None) -> PdfExtractionPolicy:
    """Build a policy from environment variables.

    Supported env vars:

    - ``GREV_PDF_EXTRACTOR_MODE``: ``chandra_only`` or ``mineru_hybrid``
    - ``GREV_PDF_OCR_BACKEND``: backend for page OCR and image/graph descriptions
    - ``GREV_PDF_MINERU_COMMAND``: CLI command used in hybrid mode
    - ``GREV_PDF_MINERU_OUTPUT_ARTIFACT``: glob used to locate MinerU content list JSON
    """

    source = os.environ if env is None else env

    mode_raw = (source.get("GREV_PDF_EXTRACTOR_MODE") or "").strip().lower()
    if mode_raw:
        try:
            mode = PdfExtractionMode(mode_raw)
        except ValueError as exc:
            raise ValueError(
                "GREV_PDF_EXTRACTOR_MODE must be one of: chandra_only, mineru_hybrid"
            ) from exc
    else:
        mode = PdfExtractionMode.CHANDRA_ONLY
    ocr_backend = load_pdf_ocr_backend(source.get("GREV_PDF_OCR_BACKEND"))
    description_backend = load_pdf_ocr_backend(source.get("GREV_PDF_DESCRIPTION_BACKEND"))
    if description_backend is None:
        description_backend = ocr_backend
    mineru_command = (source.get("GREV_PDF_MINERU_COMMAND") or "mineru").strip()
    mineru_output_artifact = (source.get("GREV_PDF_MINERU_OUTPUT_ARTIFACT") or "*content_list*.json").strip()

    return PdfExtractionPolicy(
        mode=mode,
        ocr_backend=ocr_backend,
        block_description_backend=description_backend,
        mineru_command=mineru_command,
        mineru_output_artifact=mineru_output_artifact,
    )


def extract_pdf_text(path: Path, policy: PdfExtractionPolicy) -> str:
    """Backward-compatible helper that returns only the rendered text."""

    return extract_pdf_document(path, policy).text


def extract_pdf_document(path: Path, policy: PdfExtractionPolicy) -> PdfExtractionResult:
    """Extract a PDF into canonical text with the configured strategy."""

    if policy.mode == PdfExtractionMode.MINERU_HYBRID:
        try:
            return _extract_pdf_document_mineru_hybrid(path, policy)
        except Exception as exc:
            fallback = _extract_pdf_document_chandra_only(path, policy)
            warnings = fallback.warnings + (
                f"mineru_hybrid fallback to chandra_only because: {exc}",
            )
            return PdfExtractionResult(
                source_path=fallback.source_path,
                strategy="mineru_hybrid->chandra_only",
                text=fallback.text,
                blocks=fallback.blocks,
                pages=fallback.pages,
                page_count=fallback.page_count,
                text_page_count=fallback.text_page_count,
                ocr_page_count=fallback.ocr_page_count,
                warnings=warnings,
            )
    return _extract_pdf_document_chandra_only(path, policy)


def _page_text(page: Any, *, preserve_layout: bool) -> str:
    if preserve_layout:
        return page.extract_text(extraction_mode="layout") or ""
    return page.extract_text() or ""


def _extract_pdf_document_chandra_only(path: Path, policy: PdfExtractionPolicy) -> PdfExtractionResult:
    reader_class = _load_pdf_reader()
    reader = reader_class(str(path))
    page_count = len(reader.pages)
    pages: list[PdfPageExtraction] = []
    blocks: list[PdfContentBlock] = []
    warnings: list[str] = []
    text_page_count = 0
    ocr_page_count = 0

    for index, page in enumerate(reader.pages, start=1):
        raw_text = _page_text(page, preserve_layout=policy.preserve_layout)
        normalized_text = raw_text.strip()
        use_ocr = len(normalized_text) < policy.min_text_chars
        page_source = "text"
        page_text = normalized_text

        if use_ocr:
            backend = policy.ocr_backend
            if backend is None:
                warnings.append(
                    f"page {index}: text layer produced only {len(normalized_text)} characters "
                    "and no OCR backend was configured"
                )
            else:
                ocr_text = backend.extract_page_text(path, index, page_count).strip()
                if ocr_text:
                    page_text = ocr_text
                    page_source = backend.name
                else:
                    warnings.append(f"page {index}: OCR backend {backend.name} returned no text")

        if page_source == "text" and page_text:
            text_page_count += 1
        elif page_source != "text" and page_text:
            ocr_page_count += 1

        page_blocks = [PdfContentBlock(kind="text", text=page_text, page_index=index - 1, metadata={"source": page_source})]
        blocks.extend(page_blocks)
        if policy.include_page_markers:
            marker = f"[page: {index}]"
            page_payload = f"{marker}\n{page_text}".strip()
        else:
            page_payload = page_text
        pages.append(PdfPageExtraction(page_number=index, text=page_payload, source=page_source))

    combined_text = "\n\n".join(page.text for page in pages if page.text).strip()
    return PdfExtractionResult(
        source_path=path,
        strategy="chandra_only",
        text=combined_text,
        blocks=tuple(blocks),
        pages=tuple(pages),
        page_count=page_count,
        text_page_count=text_page_count,
        ocr_page_count=ocr_page_count,
        warnings=tuple(warnings),
    )


def _extract_pdf_document_mineru_hybrid(path: Path, policy: PdfExtractionPolicy) -> PdfExtractionResult:
    parsed = _parse_pdf_with_mineru(path, policy)
    page_count = parsed.page_count
    page_blocks: dict[int, list[PdfContentBlock]] = defaultdict(list)
    for block in parsed.blocks:
        page_blocks[block.page_index].append(block)

    pages: list[PdfPageExtraction] = []
    rendered_blocks: list[PdfContentBlock] = []
    warnings = list(parsed.warnings)

    for page_index in range(page_count):
        blocks = sorted(page_blocks.get(page_index, []), key=_block_sort_key)
        rendered_lines: list[str] = []
        for block in blocks:
            rendered = _render_mineru_block(path, block, page_number=page_index + 1, page_count=page_count, policy=policy)
            if rendered.strip():
                rendered_lines.append(rendered.strip())
                rendered_blocks.append(
                    PdfContentBlock(
                        kind=block.kind,
                        text=rendered.strip(),
                        page_index=block.page_index,
                        bbox=block.bbox,
                        metadata=block.metadata,
                    )
                )
        page_text_body = "\n".join(rendered_lines).strip()
        if policy.include_page_markers:
            page_text = f"[page: {page_index + 1}]\n{page_text_body}".strip()
        else:
            page_text = page_text_body
        pages.append(PdfPageExtraction(page_number=page_index + 1, text=page_text, source="mineru"))

    combined_text = "\n\n".join(page.text for page in pages if page.text).strip()
    text_page_count = sum(1 for page in pages if page.text and page.text.replace(f"[page: {page.page_number}]", "").strip())
    return PdfExtractionResult(
        source_path=path,
        strategy="mineru_hybrid",
        text=combined_text,
        blocks=tuple(rendered_blocks),
        pages=tuple(pages),
        page_count=page_count,
        text_page_count=text_page_count,
        ocr_page_count=0,
        warnings=tuple(warnings),
    )


def _parse_pdf_with_mineru(path: Path, policy: PdfExtractionPolicy) -> PdfMinerUParseResult:
    reader_class = _load_pdf_reader()
    reader = reader_class(str(path))
    page_count = len(reader.pages)

    output_dir = Path(tempfile.mkdtemp(prefix=f"{path.stem}-mineru-"))
    _run_mineru_cli(path, output_dir, command=policy.mineru_command)
    content_list_path = _find_mineru_artifact(output_dir, policy.mineru_output_artifact)
    if content_list_path is None:
        raise RuntimeError(
            f"MinerU output did not contain an artifact matching {policy.mineru_output_artifact!r}"
        )
    blocks = _load_mineru_content_list(content_list_path)
    return PdfMinerUParseResult(
        source_path=path,
        blocks=tuple(blocks),
        output_dir=content_list_path.parent,
        page_count=page_count,
    )


def _run_mineru_cli(pdf_path: Path, output_dir: Path, *, command: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [command, "-p", str(pdf_path), "-o", str(output_dir), "--dump-content-list"]
    subprocess.run(cmd, check=True)


def _find_mineru_artifact(output_dir: Path, pattern: str) -> Path | None:
    matches = sorted(output_dir.rglob(pattern))
    if matches:
        return matches[0]
    return None


def _load_mineru_content_list(path: Path) -> list[PdfContentBlock]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]]
    if isinstance(payload, list):
        rows = [row for row in payload if isinstance(row, dict)]
    elif isinstance(payload, dict):
        rows = [row for row in payload.get("content_list", []) if isinstance(row, dict)]
        if not rows:
            rows = [payload]
    else:
        rows = []

    blocks: list[PdfContentBlock] = []
    for row in rows:
        page_index = int(row.get("page_idx") or row.get("page_index") or 0)
        bbox = _coerce_bbox(row.get("bbox"))
        metadata = {key: value for key, value in row.items() if key not in {"type", "text", "page_idx", "page_index", "bbox"}}
        blocks.append(
            PdfContentBlock(
                kind=str(row.get("type") or row.get("kind") or "text"),
                text=str(row.get("text") or ""),
                page_index=page_index,
                bbox=bbox,
                metadata=metadata or {},
            )
        )
    return blocks


def _coerce_bbox(raw: Any) -> tuple[float, float, float, float] | None:
    if not isinstance(raw, (list, tuple)) or len(raw) != 4:
        return None
    try:
        return (float(raw[0]), float(raw[1]), float(raw[2]), float(raw[3]))
    except (TypeError, ValueError):
        return None


def _block_sort_key(block: PdfContentBlock) -> tuple[float, float, str]:
    bbox = block.bbox
    if bbox is None:
        return (float("inf"), float("inf"), block.normalized_kind())
    return (bbox[1], bbox[0], block.normalized_kind())


def _render_mineru_block(
    pdf_path: Path,
    block: PdfContentBlock,
    *,
    page_number: int,
    page_count: int,
    policy: PdfExtractionPolicy,
) -> str:
    normalized_kind = block.normalized_kind()
    text_like_kinds = {"text", "title", "heading", "paragraph", "list", "caption"}
    if normalized_kind in text_like_kinds and block.text.strip():
        return block.text.strip()

    if normalized_kind in {"image", "figure", "graph", "chart", "table", "equation"}:
        backend = policy.block_description_backend
        if backend is not None:
            try:
                description = backend.describe_block(
                    pdf_path,
                    block,
                    page_number=page_number,
                    page_count=page_count,
                    page_text="",
                )
                if description.strip():
                    return description.strip()
            except Exception as exc:  # pragma: no cover - backend dependent
                return _fallback_block_description(block, page_number=page_number, extra=str(exc))

    if block.text.strip():
        return block.text.strip()
    return _fallback_block_description(block, page_number=page_number)


def _fallback_block_description(block: PdfContentBlock, *, page_number: int, extra: str | None = None) -> str:
    details: list[str] = [f"{block.kind} on page {page_number}"]
    if block.bbox is not None:
        details.append(f"bbox={list(block.bbox)}")
    if block.text.strip():
        details.append(f"text={block.text.strip()}")
    if extra:
        details.append(extra)
    return "[block: " + "; ".join(details) + "]"
