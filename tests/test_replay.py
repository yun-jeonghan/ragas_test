from pathlib import Path

from graphrag_ragas_eval.eval.ragas_runner import EvaluationRun
from graphrag_ragas_eval.eval.replay import load_search_results
from graphrag_ragas_eval.schemas import EvaluationScore


def test_load_search_results(tmp_path: Path) -> None:
    path = tmp_path / "results.json"
    path.write_text(
        """
        [
          {
            "sample_id": "q1",
            "question": "Who is Scrooge?",
            "search_mode": "local",
            "answer": "Scrooge is a miser.",
            "retrieved_contexts": [
              {
                "text": "Scrooge is a miser.",
                "source": "a.txt",
                "score": 1.0,
                "metadata": {}
              }
            ],
            "citations": ["a.txt"],
            "metadata": {"backend": "sample"}
          }
        ]
        """,
        encoding="utf-8",
    )

    results = load_search_results(path)
    assert results[0].sample_id == "q1"
    assert results[0].retrieved_contexts[0].text == "Scrooge is a miser."


def test_evaluation_run_aggregate() -> None:
    run = EvaluationRun(
        scores=(
            EvaluationScore(sample_id="q1", metric_name="faithfulness", value=1.0),
            EvaluationScore(sample_id="q2", metric_name="faithfulness", value=0.0),
            EvaluationScore(sample_id="q1", metric_name="answer_relevancy", value=1.0),
        ),
        results=(),
    )

    aggregate = run.aggregate()
    assert aggregate["faithfulness"] == 0.5
    assert aggregate["answer_relevancy"] == 1.0

