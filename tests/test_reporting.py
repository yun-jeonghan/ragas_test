from __future__ import annotations

import json
from pathlib import Path

from graphrag_ragas_eval.reporting import render_smoke_report


def test_render_smoke_report(tmp_path: Path) -> None:
    evaluation = tmp_path / "evaluation.json"
    generated_questions = tmp_path / "generated.json"
    autod_summary = tmp_path / "autod.json"
    autoq_questions = tmp_path / "autoq.json"
    assertion_prep = tmp_path / "assertions.json"
    output = tmp_path / "report.html"

    evaluation.write_text(
        json.dumps(
            {
                "scores": [
                    {
                        "sample_id": "scrooge-1",
                        "metric_name": "context_precision",
                        "value": 1.0,
                        "metadata": {"question": "Who is Scrooge?", "search_mode": "local"},
                    }
                ],
                "results": [
                    {
                        "sample_id": "scrooge-1",
                        "question": "Who is Scrooge?",
                        "search_mode": "local",
                        "answer": "Scrooge is a miser.",
                        "retrieved_contexts": [
                            {"text": "Scrooge is a miser.", "source": "scrooge.txt", "score": 1.0},
                        ],
                    }
                ],
                "aggregate": {"context_precision": 1.0},
            }
        ),
        encoding="utf-8",
    )
    generated_questions.write_text(json.dumps({"questions": []}), encoding="utf-8")
    autod_summary.write_text(json.dumps({"documents": []}), encoding="utf-8")
    autoq_questions.write_text(json.dumps({"questions": []}), encoding="utf-8")
    assertion_prep.write_text(
        json.dumps(
            {
                "metadata": {
                    "component": "AssertionPrep",
                    "validation_enabled": False,
                    "min_validation_score": 1,
                },
                "questions": [
                    {"question_id": "q1", "assertions": [{"statement": "A"}]},
                ],
                "stats": {"total_assertions": 1, "valid_assertions": 1},
            }
        ),
        encoding="utf-8",
    )

    html = render_smoke_report(
        evaluation=evaluation,
        output=output,
        generated_questions=generated_questions,
        autod_summary=autod_summary,
        autoq_questions=autoq_questions,
        assertion_prep=assertion_prep,
        title="Smoke",
    )

    assert output.exists()
    assert "Smoke" in html
    assert "BenchmarkQED Results" in html
    assert "Metric Guide" in html
    assert "<details" in html
    assert "Interpretation" in html
    assert "Assertion Prep" in html
    assert "context_precision" in html
    assert "검색된 컨텍스트 중 답변에 실제로 도움이 되는 비율" in html
    assert "Scrooge is a miser." in html
    assert "Validation: off" in html


def test_render_smoke_report_shows_autoq_assertion_status(tmp_path: Path) -> None:
    evaluation = tmp_path / "evaluation.json"
    autoq_questions = tmp_path / "autoq.json"
    output = tmp_path / "report.html"

    evaluation.write_text(
        json.dumps(
            {
                "scores": [],
                "results": [],
                "aggregate": {},
            }
        ),
        encoding="utf-8",
    )
    autoq_questions.write_text(
        json.dumps(
            {
                "questions": [
                    {
                        "question": "What happened?",
                        "attributes": {
                            "claim_count": 1,
                            "assertion_count": 0,
                            "assertions": [],
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    html = render_smoke_report(
        evaluation=evaluation,
        output=output,
        autoq_questions=autoq_questions,
        title="Smoke",
    )

    assert output.exists()
    assert "Claims: 1; assertions: 0." in html
    assert "Assertions were not populated for this run" in html
