from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from graphrag_ragas_eval.cli import app, _load_ragas_question_generation_defaults
from graphrag_ragas_eval.ragas.generation import RagasQuestionGenerationPlan, generate_ragas_questions


def test_generate_ragas_questions_writes_payload(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "docs"
    source.mkdir()
    (source / "doc-1.txt").write_text("Alpha is first. Beta follows.", encoding="utf-8")
    (source / "doc-2.txt").write_text("Gamma is next. Delta follows.", encoding="utf-8")
    output = tmp_path / "ragas-questions.json"

    captured: dict[str, object] = {}

    class _FakeFrame:
        def to_dict(self, orient: str = "records") -> list[dict[str, object]]:
            assert orient == "records"
            return [{"question": "What is alpha?", "ground_truth": "Alpha is first."}]

    class _FakeDataset:
        def to_pandas(self) -> _FakeFrame:
            return _FakeFrame()

    class _FakeGenerator:
        def __init__(self, *, llm, embedding_model):  # type: ignore[no-untyped-def]
            captured["llm"] = llm
            captured["embeddings"] = embedding_model

        def generate_with_langchain_docs(self, docs, testset_size, **kwargs):  # type: ignore[no-untyped-def]
            captured["docs"] = docs
            captured["testset_size"] = testset_size
            captured["kwargs"] = kwargs
            return _FakeDataset()

    fake_testset = types.ModuleType("ragas.testset")
    fake_testset.TestsetGenerator = _FakeGenerator
    monkeypatch.setitem(sys.modules, "ragas", types.ModuleType("ragas"))
    monkeypatch.setitem(sys.modules, "ragas.testset", fake_testset)
    monkeypatch.setattr("graphrag_ragas_eval.ragas.generation.build_ragas_llm", lambda runtime: "fake-llm")
    monkeypatch.setattr(
        "graphrag_ragas_eval.ragas.generation.build_ragas_embeddings",
        lambda runtime: "fake-embeddings",
    )

    payload = generate_ragas_questions(
        RagasQuestionGenerationPlan(
            source=source,
            output=output,
            testset_size=2,
            provider="vllm",
            model="fake-model",
            base_url="http://localhost:8000/v1",
            api_key="fake-key",
            metadata={"suite": "ragas"},
        )
    )

    assert captured["llm"] == "fake-llm"
    assert captured["embeddings"] == "fake-embeddings"
    assert captured["testset_size"] == 2
    assert captured["kwargs"] == {}
    assert len(captured["docs"]) == 2
    assert payload["metadata"]["generator"] == "ragas"
    assert payload["metadata"]["suite"] == "ragas"
    assert payload["questions"][0]["question"] == "What is alpha?"
    assert output.exists()
    assert json.loads(output.read_text(encoding="utf-8"))["questions"][0]["question"] == "What is alpha?"


def test_ragas_generate_questions_cli_dispatch(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "docs"
    source.mkdir()
    (source / "doc.txt").write_text("Alpha is first.", encoding="utf-8")
    output = tmp_path / "ragas-questions.json"

    captured: dict[str, object] = {}

    def _fake_generate(plan):  # type: ignore[no-untyped-def]
        captured["plan"] = plan
        output.write_text(json.dumps({"questions": []}), encoding="utf-8")
        return {"questions": []}

    monkeypatch.setattr("graphrag_ragas_eval.cli.generate_ragas_questions", _fake_generate)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "ragas",
            "generate-questions",
            "--source",
            str(source),
            "--output",
            str(output),
            "--testset-size",
            "3",
        ],
    )

    assert result.exit_code == 0
    assert captured["plan"].source == source
    assert captured["plan"].output == output
    assert captured["plan"].testset_size == 3
    assert "wrote ragas testset to" in result.stdout


def test_ragas_generate_questions_env_defaults(monkeypatch) -> None:
    monkeypatch.setenv("GREV_RAGAS_TESTSET_SIZE", "7")
    monkeypatch.setenv("GREV_RAGAS_QUESTION_MODES", "single-hop-specific,multi-hop")

    testset_size, question_modes = _load_ragas_question_generation_defaults()

    assert testset_size == 7
    assert question_modes == ("single-hop-specific", "multi-hop")
