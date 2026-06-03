from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from graphrag_ragas_eval.cli import app
from graphrag_ragas_eval.benchmark_qed.autoq import AutoQPlan, generate_queries
from graphrag_ragas_eval.benchmark_qed.autoe import AutoEPlan, evaluate_answers
from graphrag_ragas_eval.benchmark_qed.smoke import BenchmarkQEDSmokePlan, run_benchmark_qed_smoke
from graphrag_ragas_eval.upstream_benchmark_qed import ensure_vendor_path


def test_run_benchmark_qed_smoke_orchestrates_all_steps(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "docs"
    source.mkdir()
    (source / "sample.txt").write_text("Scrooge is a miser.", encoding="utf-8")
    benchmark = tmp_path / "benchmark.json"
    benchmark.write_text(
        json.dumps(
            [
                {
                    "sample_id": "scrooge-1",
                    "question": "Who is Scrooge?",
                    "query_type": "local",
                    "search_mode": "local",
                    "reference_answer": "Scrooge is a miser.",
                }
            ]
        ),
        encoding="utf-8",
    )
    search_results = tmp_path / "search_results.json"
    search_results.write_text(
        json.dumps(
            [
                {
                    "sample_id": "scrooge-1",
                    "question": "Who is Scrooge?",
                    "search_mode": "local",
                    "answer": "Scrooge is a miser.",
                    "retrieved_contexts": [],
                }
            ]
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "output"
    report_output = tmp_path / "report.html"
    calls: list[tuple[str, dict[str, object]]] = []

    def _record(name: str):
        def _inner(*args, **kwargs):
            calls.append((name, {"args": args, "kwargs": kwargs}))
            if name == "render_smoke_report":
                output = kwargs["output"]
                output.write_text("<html>smoke</html>", encoding="utf-8")
                return "<html>smoke</html>"

            plan = args[0]
            if name == "summarize_dataset":
                plan.output.write_text(json.dumps({"component": "AutoD"}), encoding="utf-8")
                return {"component": "AutoD"}
            if name == "generate_queries":
                plan.output.write_text(json.dumps({"component": "AutoQ"}), encoding="utf-8")
                return [{"question": "Who is Scrooge?"}]
            if name == "evaluate_answers":
                plan.output.write_text(json.dumps({"component": "AutoE"}), encoding="utf-8")
                return object()
            raise AssertionError(name)

        return _inner

    class _FakeChatModel:
        async def completion_async(self, messages, **kwargs):  # type: ignore[no-untyped-def]
            return type("Response", (), {"content": "Model lens: fake."})()

    def _fake_model_factory_runtime(runtime):  # type: ignore[no-untyped-def]
        return _FakeChatModel(), object()

    monkeypatch.setattr("graphrag_ragas_eval.benchmark_qed.smoke.summarize_dataset", _record("summarize_dataset"))
    monkeypatch.setattr("graphrag_ragas_eval.benchmark_qed.smoke.generate_queries", _record("generate_queries"))
    monkeypatch.setattr("graphrag_ragas_eval.benchmark_qed.smoke.evaluate_answers", _record("evaluate_answers"))
    monkeypatch.setattr("graphrag_ragas_eval.benchmark_qed.smoke.render_smoke_report", _record("render_smoke_report"))
    monkeypatch.setattr("graphrag_ragas_eval.benchmark_qed.smoke.build_vendor_model_factory_runtime", _fake_model_factory_runtime)

    result = run_benchmark_qed_smoke(
        BenchmarkQEDSmokePlan(
            source=source,
            benchmark=benchmark,
            search_results=search_results,
            output_dir=output_dir,
            report_output=report_output,
            target_size=1,
            num_questions=1,
            modes=("local",),
            metrics=("context_precision",),
            report_title="Smoke",
            metadata={"suite": "benchmark-qed"},
        )
    )

    assert result.autod_summary == output_dir / "autod-summary.json"
    assert result.autoq_questions == output_dir / "autoq-questions.json"
    assert result.autoe_evaluation == output_dir / "autoe-evaluation.json"
    assert result.report == report_output
    assert result.autod_summary.exists()
    assert result.autoq_questions.exists()
    assert result.autoe_evaluation.exists()
    assert result.report.exists()
    assert [name for name, _ in calls] == [
        "summarize_dataset",
        "generate_queries",
        "evaluate_answers",
        "render_smoke_report",
    ]
    assert calls[0][1]["args"][0].metadata == {"smoke": True, "suite": "benchmark-qed"}
    assert calls[1][1]["args"][0].metadata == {"smoke": True, "suite": "benchmark-qed"}
    assert calls[2][1]["args"][0].metadata == {"smoke": True, "suite": "benchmark-qed"}


def test_benchmark_qed_smoke_cli_dispatch(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}
    (tmp_path / "benchmark.json").write_text("[]", encoding="utf-8")
    (tmp_path / "search_results.json").write_text("[]", encoding="utf-8")

    def _fake_run(plan):
        captured["plan"] = plan
        result = type(
            "Result",
            (),
            {
                "autod_summary": tmp_path / "autod.json",
                "autoq_questions": tmp_path / "autoq.json",
                "autoe_evaluation": tmp_path / "autoe.json",
                "report": tmp_path / "report.html",
            },
        )()
        for path in [result.autod_summary, result.autoq_questions, result.autoe_evaluation, result.report]:
            path.write_text("{}", encoding="utf-8")
        return result

    monkeypatch.setattr("graphrag_ragas_eval.cli.run_benchmark_qed_smoke", _fake_run)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "benchmark-qed",
            "smoke",
            "--source",
            str(tmp_path),
            "--benchmark",
            str(tmp_path / "benchmark.json"),
            "--search-results",
            str(tmp_path / "search_results.json"),
            "--output-dir",
            str(tmp_path / "out"),
            "--report-output",
            str(tmp_path / "report.html"),
        ],
    )

    assert result.exit_code == 0
    assert "wrote smoke report" in result.output
    assert captured["plan"].source == tmp_path


def test_autoq_uses_tiktoken_encoding_name(monkeypatch, tmp_path: Path) -> None:
    import tiktoken

    source = tmp_path / "docs"
    source.mkdir()
    (source / "sample.txt").write_text("Scrooge is a miser.", encoding="utf-8")

    monkeypatch.setattr(tiktoken, "get_encoding", lambda name: object())
    ensure_vendor_path()
    import benchmark_qed.autoq.cli as vendor_autoq_cli

    monkeypatch.setattr(vendor_autoq_cli, "autoq", lambda **kwargs: None)

    output = tmp_path / "autoq.json"
    generate_queries(
        AutoQPlan(
            source=source,
            output=output,
            num_questions=1,
            modes=("local",),
        )
    )

    settings = (output.parent / ".autoq.benchmark-qed" / "settings.yaml").read_text(encoding="utf-8")
    assert "model_name: o200k_base" in settings


def test_autoe_accepts_list_inputs(monkeypatch, tmp_path: Path) -> None:
    import pandas as pd
    import sys
    import types

    ensure_vendor_path()

    benchmark = tmp_path / "benchmark.json"
    benchmark.write_text(
        json.dumps(
            [
                {
                    "sample_id": "scrooge-1",
                    "question": "Who is Scrooge?",
                    "query_type": "local",
                    "search_mode": "local",
                    "reference_answer": "Scrooge is a miser.",
                }
            ]
        ),
        encoding="utf-8",
    )
    search_results = tmp_path / "search_results.json"
    search_results.write_text(
        json.dumps(
            [
                {
                    "sample_id": "scrooge-1",
                    "question": "Who is Scrooge?",
                    "search_mode": "local",
                    "answer": "Scrooge is a miser.",
                    "retrieved_contexts": [],
                }
            ]
        ),
        encoding="utf-8",
    )
    output = tmp_path / "autoe.json"

    monkeypatch.setattr(
        "graphrag_ragas_eval.benchmark_qed.autoe.build_vendor_model_factory_runtime",
        lambda runtime: ("chat", "embeddings"),
    )

    def _fake_get_reference_scores(**kwargs):
        return pd.DataFrame(
            [
                {
                    "question_id": "scrooge-1",
                    "criteria": "context_precision",
                    "score": 1.0,
                    "reasoning": None,
                    "trial": 1,
                    "question_text": "Who is Scrooge?",
                    "reference_answer": "Scrooge is a miser.",
                    "generated_answer": "Scrooge is a miser.",
                }
            ]
        )

    fake_scores_module = types.ModuleType("benchmark_qed.autoe.reference.scores")
    fake_scores_module.get_reference_scores = _fake_get_reference_scores
    fake_reference_module = types.ModuleType("benchmark_qed.autoe.reference")
    fake_reference_module.scores = fake_scores_module
    monkeypatch.setitem(sys.modules, "benchmark_qed.autoe.reference", fake_reference_module)
    monkeypatch.setitem(sys.modules, "benchmark_qed.autoe.reference.scores", fake_scores_module)

    run = evaluate_answers(
        AutoEPlan(
            benchmark=benchmark,
            search_results=search_results,
            output=output,
            metrics=("context_precision",),
        )
    )

    assert output.exists()
    assert run.aggregate() == {"context_precision": 1.0}
