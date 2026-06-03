from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from graphrag_ragas_eval.benchmark_qed.retrieval import RetrievalPrepPlan, prepare_retrieval_results


def test_prepare_retrieval_results_normalizes_search_results(tmp_path: Path) -> None:
    search_results = tmp_path / "search_results.json"
    output = tmp_path / "retrieval-results.json"
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
                        }
                    ],
                    "metadata": {"backend": "sample"},
                }
            ]
        ),
        encoding="utf-8",
    )

    payload = prepare_retrieval_results(
        RetrievalPrepPlan(search_results=search_results, output=output)
    )

    assert output.exists()
    assert payload["metadata"]["component"] == "RetrievalPrep"
    assert payload["results"][0]["question_id"] == "scrooge-1"
    assert payload["results"][0]["context"][0]["chunk_id"] == "scrooge.txt"
    assert payload["results"][0]["context"][0]["text"] == "Scrooge is a miser."


def test_prepare_retrieval_results_uses_text_unit_ids_when_available(
    monkeypatch, tmp_path: Path
) -> None:
    search_results = tmp_path / "search_results.json"
    output = tmp_path / "retrieval-results.json"
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
                        }
                    ],
                    "metadata": {"backend": "sample"},
                }
            ]
        ),
        encoding="utf-8",
    )
    text_units = tmp_path / "text_units.parquet"
    text_units.write_text("placeholder", encoding="utf-8")
    text_units_df = pd.DataFrame(
        [
            {
                "id": "text-unit-1",
                "text": "Scrooge is a miser. He hates spending money.",
            }
        ]
    )

    monkeypatch.setattr(
        "graphrag_ragas_eval.benchmark_qed.retrieval._load_dataframe",
        lambda path: text_units_df,
    )

    payload = prepare_retrieval_results(
        RetrievalPrepPlan(search_results=search_results, output=output, text_units=text_units)
    )

    assert output.exists()
    assert payload["results"][0]["context"][0]["chunk_id"] == "text-unit-1"
    assert payload["results"][0]["context"][0]["text"] == "Scrooge is a miser."
