from __future__ import annotations

import json
from pathlib import Path

from graphrag_ragas_eval.reporting import (
    render_assertion_report,
    render_retrieval_smoke_report,
    render_smoke_report,
)


def test_render_smoke_report(tmp_path: Path) -> None:
    evaluation = tmp_path / "evaluation.json"
    generated_questions = tmp_path / "generated.json"
    autod_summary = tmp_path / "autod.json"
    autoq_questions = tmp_path / "autoq.json"
    assertion_prep = tmp_path / "assertions.json"
    assertion_scores = tmp_path / "assertion-scores.json"
    retrieval_results = tmp_path / "retrieval.json"
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
    assertion_scores.write_text(
        json.dumps(
            {
                "metadata": {"component": "AssertionEvaluation", "backend": "benchmark-qed"},
                "scores": [
                    {
                        "question_id": "q1",
                        "question": "Who is Scrooge?",
                        "assertion": "The answer should mention Scrooge.",
                        "score": 1.0,
                        "reason": "Pass",
                    }
                ],
                "summary_by_assertion": [{"assertion": "The answer should mention Scrooge."}],
                "summary_by_question": [{"question_id": "q1"}],
                "aggregate": {"overall_accuracy": 1.0},
            }
        ),
        encoding="utf-8",
    )
    retrieval_results.write_text(
        json.dumps(
            {
                "metadata": {"component": "RetrievalPrep"},
                "results": [
                    {
                        "question_id": "scrooge-1",
                        "question_text": "Who is Scrooge?",
                        "context": [
                            {"chunk_id": "text-unit-1", "text": "Scrooge is a miser."},
                        ],
                    }
                ],
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
        assertion_scores=assertion_scores,
        retrieval_results=retrieval_results,
        title="Smoke",
    )

    assert output.exists()
    assert "Smoke" in html
    assert "Overview" in html
    assert "AI 설명" in html
    assert "BenchmarkQED" in html
    assert "Ragas" in html
    assert "Ragas provides the metric vocabulary used by this repo" in html
    assert "<details" in html
    assert "Assertion Prep" in html
    assert "Assertion Scores" in html
    assert "Retrieval Prep" in html
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


def test_render_retrieval_smoke_report(tmp_path: Path) -> None:
    retrieval_reference = tmp_path / "reference.json"
    retrieval_results = tmp_path / "retrieval-results.json"
    retrieval_evaluation = tmp_path / "retrieval-evaluation.json"
    output = tmp_path / "retrieval-report.html"

    retrieval_reference.write_text(
        json.dumps(
            {
                "metadata": {"component": "RetrievalReference"},
                "references": [
                    {
                        "question_id": "scrooge-1",
                        "question_text": "Who is Scrooge?",
                        "cluster_ids": ["community-1"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    retrieval_results.write_text(
        json.dumps(
            {
                "metadata": {"component": "RetrievalPrep"},
                "results": [
                    {
                        "question_id": "scrooge-1",
                        "question_text": "Who is Scrooge?",
                        "context": [
                            {"chunk_id": "text-unit-1", "text": "Scrooge is a miser."},
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    retrieval_evaluation.write_text(
        json.dumps(
            {
                "metadata": {"component": "RetrievalEvaluation"},
                "summary": [
                    {
                        "rag_method_name": "benchmark-qed",
                        "context_precision": 1.0,
                        "context_recall": 1.0,
                    }
                ],
                "aggregate": {"context_precision": 1.0, "context_recall": 1.0},
            }
        ),
        encoding="utf-8",
    )

    html = render_retrieval_smoke_report(
        retrieval_reference=retrieval_reference,
        retrieval_results=retrieval_results,
        retrieval_evaluation=retrieval_evaluation,
        output=output,
        title="Retrieval Smoke",
    )

    assert output.exists()
    assert "Retrieval Smoke" in html
    assert "BenchmarkQED Retrieval" in html
    assert "Retrieval Reference" in html
    assert "Retrieval Prep" in html
    assert "Retrieval Evaluation" in html
    assert "context_precision" in html
    assert "BenchmarkQED-only retrieval report" in html


def test_render_assertion_report(tmp_path: Path) -> None:
    assertion_scores = tmp_path / "assertion-scores.json"
    output = tmp_path / "assertion-report.html"

    assertion_scores.write_text(
        json.dumps(
            {
                "metadata": {"component": "AssertionEvaluation", "backend": "benchmark-qed"},
                "scores": [
                    {
                        "question_id": "q1",
                        "question": "Who is Scrooge?",
                        "assertion": "The answer should mention Scrooge.",
                        "score": 1.0,
                        "reason": "Pass",
                    }
                ],
                "summary_by_assertion": [{"assertion": "The answer should mention Scrooge."}],
                "summary_by_question": [{"question_id": "q1"}],
                "aggregate": {"overall_accuracy": 1.0},
            }
        ),
        encoding="utf-8",
    )

    html = render_assertion_report(
        assertion_scores=assertion_scores,
        output=output,
        title="Assertion Report",
    )

    assert output.exists()
    assert "Assertion Report" in html
    assert "BenchmarkQED Assertion" in html
    assert "Assertion Scores" in html
    assert "overall_accuracy" in html
    assert "Who is Scrooge?" in html
    assert "The answer should mention Scrooge." in html
