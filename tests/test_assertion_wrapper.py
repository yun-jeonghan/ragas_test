from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
from typer.testing import CliRunner

from graphrag_ragas_eval.benchmark_qed.assertion import (
    AssertionEvaluationPlan,
    evaluate_assertion_scores,
)
from graphrag_ragas_eval.cli import app
from graphrag_ragas_eval.upstream_benchmark_qed import (
    ensure_autoe_import_shim,
    ensure_vendor_path,
)


def test_evaluate_assertion_scores_joins_by_question_id(monkeypatch, tmp_path: Path) -> None:
    assertion_prep = tmp_path / "assertion-prep.json"
    answers = tmp_path / "answers.json"
    output = tmp_path / "assertion-scores.json"

    assertion_prep.write_text(
        json.dumps(
            {
                "questions": [
                    {
                        "question_id": "q1",
                        "question_text": "Who is Scrooge?",
                        "assertions": [
                            {"statement": "The answer should mention Scrooge.", "rank": 1},
                            {"statement": "The answer should describe him as a miser.", "rank": 2},
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    answers.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "sample_id": "q1",
                        "question": "Who is Scrooge?",
                        "answer": "Scrooge is a miser.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    captured: dict[str, object] = {}

    ensure_vendor_path()
    ensure_autoe_import_shim()

    def _fake_get_assertion_scores(**kwargs):  # type: ignore[no-untyped-def]
        captured["answers"] = kwargs["answers"]
        captured["assertions"] = kwargs["assertions"]
        return pd.DataFrame(
            [
                {"question": "Who is Scrooge?", "assertion": "The answer should mention Scrooge.", "score": 1},
                {"question": "Who is Scrooge?", "assertion": "The answer should describe him as a miser.", "score": 1},
            ]
        )

    monkeypatch.setattr(
        "graphrag_ragas_eval.benchmark_qed.assertion.build_vendor_model_factory_runtime",
        lambda runtime: (SimpleNamespace(), SimpleNamespace()),
    )
    monkeypatch.setattr(
        "benchmark_qed.autoe.assertion.standard.get_assertion_scores",
        _fake_get_assertion_scores,
    )

    payload = evaluate_assertion_scores(
        AssertionEvaluationPlan(
            assertion_prep=assertion_prep,
            answers=answers,
            output=output,
        )
    )

    assert output.exists()
    assert payload["metadata"]["component"] == "AssertionEvaluation"
    assert payload["aggregate"]["overall_accuracy"] == 1.0
    assert len(payload["scores"]) == 2
    assert list(captured["answers"]["question_id"]) == ["q1"]
    assert list(captured["assertions"]["question_id"]) == ["q1", "q1"]


def test_benchmark_qed_assertion_score_cli_dispatch(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}
    (tmp_path / "assertion-prep.json").write_text("{}", encoding="utf-8")
    (tmp_path / "answers.json").write_text("{}", encoding="utf-8")

    def _fake_run(plan):
        captured["plan"] = plan
        result = {"scores": [1, 2]}
        Path(plan.output).write_text("{}", encoding="utf-8")
        return result

    monkeypatch.setattr("graphrag_ragas_eval.cli.evaluate_assertion_scores", _fake_run)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "benchmark-qed",
            "assertion-score",
            "--assertion-prep",
            str(tmp_path / "assertion-prep.json"),
            "--answers",
            str(tmp_path / "answers.json"),
            "--output",
            str(tmp_path / "assertion-scores.json"),
        ],
    )

    assert result.exit_code == 0
    assert "wrote assertion scores" in result.output
    assert captured["plan"].assertion_prep == tmp_path / "assertion-prep.json"


def test_benchmark_qed_assertion_report_cli_dispatch(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}
    assertion_scores = tmp_path / "assertion-scores.json"
    assertion_scores.write_text(
        json.dumps(
            {
                "metadata": {"component": "AssertionEvaluation", "backend": "benchmark-qed"},
                "scores": [],
                "summary_by_assertion": [],
                "summary_by_question": [],
                "aggregate": {},
            }
        ),
        encoding="utf-8",
    )

    def _fake_render(**kwargs):  # type: ignore[no-untyped-def]
        captured["kwargs"] = kwargs
        Path(kwargs["output"]).write_text("{}", encoding="utf-8")
        return "{}"

    monkeypatch.setattr("graphrag_ragas_eval.cli.render_assertion_report", _fake_render)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "benchmark-qed",
            "assertion-report",
            "--assertion-scores",
            str(assertion_scores),
            "--output",
            str(tmp_path / "assertion-report.html"),
        ],
    )

    assert result.exit_code == 0
    assert "wrote assertion report" in result.output
    assert captured["kwargs"]["assertion_scores"] == assertion_scores
