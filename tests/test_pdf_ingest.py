from pathlib import Path

from graphrag_ragas_eval.ingest.normalizer import normalize_source_tree
from graphrag_ragas_eval.ingest.pdf import PdfExtractionPolicy, extract_pdf_text


class _FakePage:
    def __init__(self, text: str) -> None:
        self._text = text

    def extract_text(self, *args, **kwargs) -> str:
        return self._text


class _FakeReader:
    def __init__(self, path: str) -> None:
        self.pages = [
            _FakePage("This page has a text layer."),
            _FakePage(" "),
        ]


class _FakeOcrBackend:
    name = "fake-ocr"

    def extract_page_text(self, pdf_path: Path, page_number: int, page_count: int) -> str:
        return f"OCR page {page_number} of {page_count} from {pdf_path.name}"


def test_extract_pdf_text_uses_page_level_ocr(monkeypatch, tmp_path: Path) -> None:
    from graphrag_ragas_eval.ingest import pdf as pdf_module

    monkeypatch.setattr(pdf_module, "_load_pdf_reader", lambda: _FakeReader)
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    result = extract_pdf_text(
        pdf_path,
        PdfExtractionPolicy(min_text_chars=5, ocr_backend=_FakeOcrBackend()),
    )

    assert result.page_count == 2
    assert result.text_page_count == 1
    assert result.ocr_page_count == 1
    assert any(page.source == "fake-ocr" for page in result.pages)
    assert "OCR page 2 of 2" in result.text


def test_normalize_source_tree_writes_canonical_txt_for_pdf(monkeypatch, tmp_path: Path) -> None:
    from graphrag_ragas_eval.ingest import pdf as pdf_module

    monkeypatch.setattr(pdf_module, "_load_pdf_reader", lambda: _FakeReader)
    source = tmp_path / "source"
    source.mkdir()
    pdf_path = source / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    canonical = tmp_path / "canonical"
    manifest = tmp_path / "manifests" / "extraction.jsonl"
    documents = normalize_source_tree(
        source,
        canonical,
        manifest,
        pdf_policy=PdfExtractionPolicy(min_text_chars=5, ocr_backend=_FakeOcrBackend()),
    )

    assert len(documents) == 1
    canonical_txt = canonical / "sample.txt"
    assert canonical_txt.exists()
    assert "OCR page 2 of 2" in canonical_txt.read_text(encoding="utf-8")
    assert manifest.exists()
