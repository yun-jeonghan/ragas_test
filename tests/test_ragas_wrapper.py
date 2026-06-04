from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from graphrag_ragas_eval.cli import app


def test_ragas_evaluate_cli_dispatch(monkeypatch, tmp_path: Path) -> None:
    benchmark = tmp_path / "benchmark.json"
    search_results = tmp_path / "search_results.json"
    output = tmp_path / "evaluation.json"
    benchmark.write_text("[]", encoding="utf-8")
    search_results.write_text("[]", encoding="utf-8")

    captured: dict[str, object] = {}

    class _FakeRun:
        def write_json(self, path: Path) -> None:
            captured["write_json_path"] = path
            path.write_text('{"aggregate": {"faithfulness": 1.0}}', encoding="utf-8")

        def aggregate(self) -> dict[str, float]:
            return {"faithfulness": 1.0}

    def _fake_evaluate_ragas(**kwargs):  # type: ignore[no-untyped-def]
        captured["kwargs"] = kwargs
        return _FakeRun()

    monkeypatch.setattr("graphrag_ragas_eval.cli.evaluate_ragas", _fake_evaluate_ragas)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "ragas",
            "evaluate",
            "--benchmark",
            str(benchmark),
            "--search-results",
            str(search_results),
            "--output",
            str(output),
            "--metrics",
            "faithfulness",
        ],
    )

    assert result.exit_code == 0
    assert captured["kwargs"] == {
        "benchmark": benchmark,
        "search_results": search_results,
        "model": None,
        "provider": None,
        "base_url": None,
        "api_key": None,
        "metrics": ("faithfulness",),
        "prefix": "GREV_RAGAS",
    }
    assert captured["write_json_path"] == output
    assert output.exists()
    assert "wrote evaluation results to" in result.stdout
    assert "faithfulness" in result.stdout
