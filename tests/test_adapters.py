from __future__ import annotations

import json

from graphrag_ragas_eval.adapters import (
    benchmark_sample_to_mine_payload,
    benchmark_sample_to_ragas_row,
    load_benchmark_samples,
    load_search_results,
    search_result_context_text,
    search_result_to_ragas_row,
)


def test_benchmark_and_search_result_adapters_round_trip(tmp_path) -> None:
    benchmark_path = tmp_path / "benchmark.json"
    search_path = tmp_path / "search.json"

    benchmark_path.write_text(
        json.dumps(
            {
                "samples": [
                    {
                        "sample_id": "sample-1",
                        "question": "Who founded OpenAI?",
                        "query_type": "local",
                        "search_mode": "local",
                        "reference_answer": "Sam Altman",
                        "reference_contexts": ["OpenAI was founded by Sam Altman."],
                        "expected_entities": ["OpenAI", "Sam Altman"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    search_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "sample_id": "sample-1",
                        "question": "Who founded OpenAI?",
                        "search_mode": "local",
                        "answer": "Sam Altman",
                        "retrieved_contexts": [
                            {
                                "text": "OpenAI was founded by Sam Altman.",
                                "source": "doc-1",
                            }
                        ],
                        "citations": ["doc-1"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    samples = load_benchmark_samples(benchmark_path)
    results = load_search_results(search_path)

    assert benchmark_sample_to_ragas_row(samples[0])["reference"] == "Sam Altman"
    assert benchmark_sample_to_mine_payload(samples[0])["question"] == "Who founded OpenAI?"
    assert search_result_to_ragas_row(results[0])["retrieved_contexts"] == [
        "OpenAI was founded by Sam Altman."
    ]
    assert search_result_context_text(results[0]) == "OpenAI was founded by Sam Altman."
