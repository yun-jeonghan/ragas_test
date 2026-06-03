from __future__ import annotations

import json
from pathlib import Path

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
