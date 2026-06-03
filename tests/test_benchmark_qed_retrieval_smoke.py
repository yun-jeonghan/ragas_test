from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
from typer.testing import CliRunner

from graphrag_ragas_eval.cli import app
from graphrag_ragas_eval.benchmark_qed.retrieval import RetrievalSmokePlan, run_benchmark_qed_retrieval_smoke


def test_run_benchmark_qed_retrieval_smoke_orchestrates_retrieval_steps(monkeypatch, tmp_path: Path) -> None:
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
                    "retrieved_contexts": [
                        {
                            "text": "Scrooge is a miser.",
                            "source": "scrooge.txt",
                            "score": 1.0,
                            "metadata": {},
                        }
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )

    communities = pd.DataFrame(
        [
            {
                "id": "community-1",
                "human_readable_id": 1,
                "community": 1,
                "level": 0,
                "parent": -1,
                "children": [],
                "title": "Community 1",
                "entity_ids": [],
                "relationship_ids": [],
                "text_unit_ids": ["text-unit-1"],
                "period": "2026-06-01",
                "size": 1,
            }
        ]
    )
    text_units = pd.DataFrame(
        [
            {
                "id": "text-unit-1",
                "human_readable_id": 1,
                "text": "Scrooge is a miser.",
                "n_tokens": 4,
                "document_id": "doc-1",
                "entity_ids": [],
                "relationship_ids": [],
                "covariate_ids": [],
            }
        ]
    )

    calls: list[tuple[str, dict[str, object]]] = []

    def _fake_load_graphrag_tables(table_set):  # type: ignore[no-untyped-def]
        calls.append(("load_graphrag_tables", {"root": table_set.root}))
        return SimpleNamespace(communities=communities, text_units=text_units)

    def _record(name: str):
        def _inner(*args, **kwargs):
            calls.append((name, {"args": args, "kwargs": kwargs}))
            plan = args[0]
            if name == "generate_retrieval_reference":
                payload = {"metadata": {"component": "RetrievalReference"}, "references": []}
                plan.output.parent.mkdir(parents=True, exist_ok=True)
                plan.output.write_text(json.dumps(payload), encoding="utf-8")
                return payload
            if name == "prepare_retrieval_results":
                payload = {"metadata": {"component": "RetrievalPrep"}, "results": []}
                plan.output.parent.mkdir(parents=True, exist_ok=True)
                plan.output.write_text(json.dumps(payload), encoding="utf-8")
                return payload
            if name == "evaluate_retrieval_results":
                payload = {"metadata": {"component": "RetrievalEvaluation"}, "rows": 1}
                plan.output.parent.mkdir(parents=True, exist_ok=True)
                plan.output.write_text(json.dumps(payload), encoding="utf-8")
                return payload
            raise AssertionError(name)

        return _inner

    monkeypatch.setattr("graphrag_ragas_eval.benchmark_qed.retrieval.load_graphrag_tables", _fake_load_graphrag_tables)
    monkeypatch.setattr("graphrag_ragas_eval.benchmark_qed.retrieval.generate_retrieval_reference", _record("generate_retrieval_reference"))
    monkeypatch.setattr("graphrag_ragas_eval.benchmark_qed.retrieval.prepare_retrieval_results", _record("prepare_retrieval_results"))
    monkeypatch.setattr("graphrag_ragas_eval.benchmark_qed.retrieval.evaluate_retrieval_results", _record("evaluate_retrieval_results"))

    output_dir = tmp_path / "retrieval-smoke"
    result = run_benchmark_qed_retrieval_smoke(
        RetrievalSmokePlan(
            benchmark=benchmark,
            search_results=search_results,
            graphrag_root=tmp_path / "graphrag-output",
            output_dir=output_dir,
            metadata={"suite": "benchmark-qed"},
        )
    )

    assert result.clusters == output_dir / "clusters.json"
    assert result.retrieval_reference == output_dir / "retrieval-reference" / "reference.json"
    assert result.retrieval_results == output_dir / "retrieval-results.json"
    assert result.retrieval_evaluation == output_dir / "retrieval-evaluation.json"
    assert result.clusters.exists()
    assert result.retrieval_reference.exists()
    assert result.retrieval_results.exists()
    assert result.retrieval_evaluation.exists()
    assert [name for name, _ in calls] == [
        "load_graphrag_tables",
        "generate_retrieval_reference",
        "prepare_retrieval_results",
        "evaluate_retrieval_results",
    ]
    clusters_payload = json.loads(result.clusters.read_text(encoding="utf-8"))
    assert clusters_payload[0]["cluster_id"] == "community-1"
    assert clusters_payload[0]["text_unit_ids"] == ["text-unit-1"]
    assert calls[0][1]["root"] == tmp_path / "graphrag-output"
    assert calls[1][1]["args"][0].questions == benchmark
    assert calls[1][1]["args"][0].clusters == result.clusters
    assert calls[2][1]["args"][0].output == result.retrieval_results
    assert calls[3][1]["args"][0].reference_dir == output_dir / "retrieval-reference"


def test_benchmark_qed_retrieval_smoke_cli_dispatch(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}
    (tmp_path / "benchmark.json").write_text("[]", encoding="utf-8")
    (tmp_path / "search_results.json").write_text("[]", encoding="utf-8")
    (tmp_path / "graphrag-output").mkdir()

    def _fake_run(plan):
        captured["plan"] = plan
        result = SimpleNamespace(
            clusters=tmp_path / "clusters.json",
            retrieval_reference=tmp_path / "reference.json",
            retrieval_results=tmp_path / "retrieval-results.json",
            retrieval_evaluation=tmp_path / "retrieval-evaluation.json",
        )
        for path in [
            result.clusters,
            result.retrieval_reference,
            result.retrieval_results,
            result.retrieval_evaluation,
        ]:
            Path(path).write_text("{}", encoding="utf-8")
        return result

    monkeypatch.setattr("graphrag_ragas_eval.cli.run_benchmark_qed_retrieval_smoke", _fake_run)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "benchmark-qed",
            "retrieval-smoke",
            "--benchmark",
            str(tmp_path / "benchmark.json"),
            "--search-results",
            str(tmp_path / "search_results.json"),
            "--graphrag-root",
            str(tmp_path / "graphrag-output"),
            "--output-dir",
            str(tmp_path / "out"),
        ],
    )

    assert result.exit_code == 0
    assert "wrote retrieval reference" in result.output
    assert captured["plan"].benchmark == tmp_path / "benchmark.json"
