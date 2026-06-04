from pathlib import Path

from graphrag_ragas_eval.ragas.dataset import load_benchmark_samples, to_ragas_rows


def test_load_benchmark_samples_json(tmp_path: Path) -> None:
    path = tmp_path / "samples.json"
    path.write_text(
        """
        [
          {
            "sample_id": "q1",
            "question": "Who is Scrooge?",
            "query_type": "local",
            "search_mode": "local",
            "reference_answer": "Scrooge is a miser.",
            "reference_contexts": ["Scrooge is a miser."]
          }
        ]
        """,
        encoding="utf-8",
    )

    samples = load_benchmark_samples(path)
    assert samples[0].sample_id == "q1"
    assert samples[0].search_mode.value == "local"


def test_to_ragas_rows() -> None:
    samples = load_benchmark_samples(Path(__file__).parent / "fixtures" / "sample.json")
    rows = to_ragas_rows(samples)
    assert rows[0]["user_input"] == "Who is Scrooge?"
    assert rows[0]["reference"] == "Scrooge is a miser."
