from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


def _load_pdf_reader() -> type[Any]:
    """Import PdfReader lazily so the rest of the package still imports without pypdf."""

    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - exercised in environments without pypdf
        raise RuntimeError(
            "pypdf is required for PDF extraction. Install it with `pip install pypdf`."
        ) from exc
    return PdfReader


@runtime_checkable
class PdfOcrBackend(Protocol):
    """Backend interface for page-level OCR fallbacks.

    The concrete OCR engine is intentionally abstracted so the pipeline can swap in
    chandra today and a different OCR engine later without changing the rest of the
    ingestion flow.
    """

    name: str

    def extract_page_text(self, pdf_path: Path, page_number: int, page_count: int) -> str:
        """Extract OCR text for a single 1-based page number."""


@dataclass(frozen=True, slots=True)
class ChandraPdfOcrBackend:
    """Thin adapter around a chandra OCR implementation.

    The chandra API is intentionally discovered at runtime because deployments may
    expose it as a module, a helper function, or a CLI-backed shim. We try a small set
    of conventional entry points so the ingestion code stays stable even if the OCR
    implementation changes.
    """

    module_name: str = "chandra"
    entrypoint_names: tuple[str, ...] = ("extract_page_text", "ocr_page", "extract_text")
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


def load_pdf_ocr_backend(spec: str | None) -> PdfOcrBackend | None:
    """Load an OCR backend from a simple string spec.

    - ``None`` disables OCR fallback.
    - ``chandra`` loads the built-in chandra adapter.
    - any other value is treated as a module name exposing a compatible API.
    """

    if spec is None or not str(spec).strip():
        return None
    normalized = str(spec).strip()
    if normalized == "chandra":
        return ChandraPdfOcrBackend()
    return ChandraPdfOcrBackend(module_name=normalized, name=normalized)


@dataclass(frozen=True, slots=True)
class PdfPageExtraction:
    page_number: int
    text: str
    source: str


@dataclass(frozen=True, slots=True)
class PdfExtractionPolicy:
    """Page-level PDF extraction policy.

    Pages with less than ``min_text_chars`` from the PDF text layer are treated as
    OCR candidates. This keeps scanned pages from disappearing while still preferring
    the text layer whenever it exists.
    """

    min_text_chars: int = 20
    preserve_layout: bool = False
    include_page_markers: bool = True
    ocr_backend: PdfOcrBackend | None = None


@dataclass(frozen=True, slots=True)
class PdfExtractionResult:
    source_path: Path
    text: str
    pages: tuple[PdfPageExtraction, ...]
    page_count: int
    text_page_count: int
    ocr_page_count: int
    warnings: tuple[str, ...] = ()

    @property
    def char_count(self) -> int:
        return len(self.text)


def _page_text(page: Any, *, preserve_layout: bool) -> str:
    if preserve_layout:
        return page.extract_text(extraction_mode="layout") or ""
    return page.extract_text() or ""


def extract_pdf_text(path: Path, policy: PdfExtractionPolicy) -> PdfExtractionResult:
    """Extract text from a PDF, falling back to OCR on a page-by-page basis."""

    reader_class = _load_pdf_reader()
    reader = reader_class(str(path))
    page_count = len(reader.pages)
    pages: list[PdfPageExtraction] = []
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

        if policy.include_page_markers:
            marker = f"[page: {index}]"
            page_payload = f"{marker}\n{page_text}".strip()
        else:
            page_payload = page_text
        pages.append(PdfPageExtraction(page_number=index, text=page_payload, source=page_source))

    combined_text = "\n\n".join(page.text for page in pages if page.text).strip()
    return PdfExtractionResult(
        source_path=path,
        text=combined_text,
        pages=tuple(pages),
        page_count=page_count,
        text_page_count=text_page_count,
        ocr_page_count=ocr_page_count,
        warnings=tuple(warnings),
    )
