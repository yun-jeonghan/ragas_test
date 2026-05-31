from pathlib import Path

from graphrag_ragas_eval.ingest.normalizer import normalize_source_tree
from graphrag_ragas_eval.ingest.pdf import PdfExtractionMode, PdfExtractionPolicy, extract_pdf_document, extract_pdf_text


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


class _FakeDescriptionBackend:
    name = "fake-desc"

    def describe_block(
        self,
        pdf_path: Path,
        block,
        *,
        page_number: int,
        page_count: int,
        page_text: str = "",
    ) -> str:
        return f"DESC {block.kind} on page {page_number}"


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


def test_mineru_hybrid_renders_structure_and_descriptions(monkeypatch, tmp_path: Path) -> None:
    from graphrag_ragas_eval.ingest import pdf as pdf_module

    monkeypatch.setattr(pdf_module, "_load_pdf_reader", lambda: _FakeReader)

    def fake_run_mineru_cli(pdf_path: Path, output_dir: Path, *, command: str) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "sample_content_list.json").write_text(
            """
            [
              {"type": "text", "text": "MinerU intro", "page_idx": 0, "bbox": [0, 0, 10, 10]},
              {"type": "figure", "text": "", "page_idx": 0, "bbox": [1, 1, 5, 5]},
              {"type": "text", "text": "MinerU page 2", "page_idx": 1, "bbox": [0, 0, 10, 10]}
            ]
            """,
            encoding="utf-8",
        )

    monkeypatch.setattr(pdf_module, "_run_mineru_cli", fake_run_mineru_cli)

    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    result = extract_pdf_document(
        pdf_path,
        PdfExtractionPolicy(
            mode=PdfExtractionMode.MINERU_HYBRID,
            block_description_backend=_FakeDescriptionBackend(),
        ),
    )

    assert result.strategy == "mineru_hybrid"
    assert "MinerU intro" in result.text
    assert "DESC figure on page 1" in result.text
    assert result.pages[0].source == "mineru"
