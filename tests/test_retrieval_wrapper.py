from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from graphrag_ragas_eval.benchmark_qed.retrieval import (
    RetrievalEvaluationPlan,
    RetrievalReferencePlan,
    evaluate_retrieval_results,
    generate_retrieval_reference,
)
from graphrag_ragas_eval.upstream_benchmark_qed import (
    ensure_autoe_import_shim,
    ensure_vendor_path,
)


class _FakeReferenceResult:
    def __init__(self, question_id: str, question_text: str) -> None:
        self.question_id = question_id
        self.question_text = question_text

    def model_dump(self) -> dict[str, object]:
        return {
            "question_id": self.question_id,
            "question_text": self.question_text,
            "cluster_results": [],
        }


def test_generate_retrieval_reference_writes_payload(monkeypatch, tmp_path: Path) -> None:
    ensure_vendor_path()
    ensure_autoe_import_shim()
    questions = tmp_path / "questions.json"
    questions.write_text(
        json.dumps(
            {
                "questions": [
                    {"question_id": "q1", "question": "Who is Scrooge?"},
                    {"question_id": "q2", "question_text": "What is wealth?"},
                ]
            }
        ),
        encoding="utf-8",
    )
    clusters = tmp_path / "clusters.json"
    clusters.write_text("[]", encoding="utf-8")
    output = tmp_path / "retrieval-reference.json"

    fake_cluster = SimpleNamespace(id="cluster-1", text_units=[])
    captured: dict[str, object] = {}

    class _FakeClusterRater:
        def __init__(self, **kwargs):  # type: ignore[no-untyped-def]
            captured["cluster_rater_kwargs"] = kwargs
            self.clusters = kwargs["corpus"]

        async def assess_batch(self, queries):  # type: ignore[no-untyped-def]
            captured["queries"] = [(query.id, query.text) for query in queries]
            return [
                _FakeReferenceResult(question_id=query.id, question_text=query.text)
                for query in queries
            ]

    async def _fake_embed_clusters(clusters, embedder):  # type: ignore[no-untyped-def]
        captured["embedder"] = embedder
        return clusters

    monkeypatch.setattr(
        "graphrag_ragas_eval.benchmark_qed.retrieval._build_relevance_rater",
        lambda runtime, **kwargs: (object(), object()),
    )
    monkeypatch.setattr(
        "graphrag_ragas_eval.benchmark_qed.retrieval._load_clusters_with_embeddings",
        lambda *args, **kwargs: [fake_cluster],
    )
    monkeypatch.setattr(
        "graphrag_ragas_eval.benchmark_qed.retrieval._load_questions",
        lambda *args, **kwargs: [
            SimpleNamespace(id="q1", text="Who is Scrooge?"),
            SimpleNamespace(id="q2", text="What is wealth?"),
        ],
    )
    monkeypatch.setattr(
        "graphrag_ragas_eval.benchmark_qed.retrieval._ensure_embeddings_on_clusters",
        _fake_embed_clusters,
    )
    monkeypatch.setattr(
        "benchmark_qed.autoe.retrieval_metrics.reference_gen.cluster_relevance.ClusterRelevanceRater",
        _FakeClusterRater,
    )

    payload = generate_retrieval_reference(
        RetrievalReferencePlan(
            questions=questions,
            clusters=clusters,
            output=output,
            metadata={"suite": "benchmark-qed"},
        )
    )

    assert output.exists()
    assert payload["metadata"]["component"] == "RetrievalReference"
    assert payload["metadata"]["suite"] == "benchmark-qed"
    assert payload["references"][0]["question_id"] == "q1"
    assert captured["queries"] == [("q1", "Who is Scrooge?"), ("q2", "What is wealth?")]
    assert captured["cluster_rater_kwargs"]["semantic_neighbors"] == 10
    assert captured["cluster_rater_kwargs"]["centroid_neighbors"] == 5


def test_evaluate_retrieval_results_writes_summary(monkeypatch, tmp_path: Path) -> None:
    ensure_vendor_path()
    ensure_autoe_import_shim()
    reference_dir = tmp_path / "reference"
    reference_dir.mkdir()
    (reference_dir / "reference.json").write_text(
        json.dumps(
            {
                "references": [
                    {
                        "question_id": "q1",
                        "question_text": "Who is Scrooge?",
                        "cluster_results": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    clusters = tmp_path / "clusters.json"
    clusters.write_text("[]", encoding="utf-8")
    retrieval_results = tmp_path / "retrieval-results.json"
    retrieval_results.write_text("[]", encoding="utf-8")
    output = tmp_path / "retrieval-evaluation.json"

    captured: dict[str, object] = {}

    async def _fake_run_retrieval_evaluation(**kwargs):  # type: ignore[no-untyped-def]
        captured["kwargs"] = kwargs
        return pd.DataFrame(
            [
                {
                    "question_set": "default",
                    "rag_method": "benchmark-qed",
                    "binary_precision": 1.0,
                    "recall": 0.5,
                    "fidelity": 0.75,
                }
            ]
        )

    monkeypatch.setattr(
        "graphrag_ragas_eval.benchmark_qed.retrieval._build_relevance_rater",
        lambda runtime, **kwargs: (object(), object()),
    )
    monkeypatch.setattr(
        "graphrag_ragas_eval.benchmark_qed.retrieval._load_clusters_with_embeddings",
        lambda *args, **kwargs: [SimpleNamespace(id="cluster-1", text_units=[])],
    )
    monkeypatch.setattr(
        "benchmark_qed.autoe.retrieval.run_retrieval_evaluation",
        _fake_run_retrieval_evaluation,
    )

    payload = evaluate_retrieval_results(
        RetrievalEvaluationPlan(
            reference_dir=reference_dir,
            clusters=clusters,
            retrieval_results=retrieval_results,
            output=output,
            question_sets=("default",),
            metadata={"suite": "benchmark-qed"},
        )
    )

    assert output.exists()
    assert payload["metadata"]["component"] == "RetrievalEvaluation"
    assert payload["metadata"]["suite"] == "benchmark-qed"
    assert payload["rows"] == 1
    assert payload["summary"][0]["rag_method"] == "benchmark-qed"
    assert captured["kwargs"]["question_sets"] == ["default"]
    assert captured["kwargs"]["rag_methods"][0]["retrieval_results_path"] == retrieval_results
