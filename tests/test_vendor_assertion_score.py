from __future__ import annotations

from graphrag_ragas_eval.upstream_benchmark_qed import ensure_vendor_path


def test_vendor_assertion_score_normalization_and_parsing() -> None:
    ensure_vendor_path()

    from benchmark_qed.autoq.question_gen.data_questions.assertion_gen.base import (
        normalize_assertion_score,
    )
    from benchmark_qed.autoq.question_gen.data_questions.assertion_gen.local_claim_assertion_gen import (
        LocalClaimAssertionGenerator,
    )

    assert normalize_assertion_score(7) == 7
    assert normalize_assertion_score(85) == 9

    generator = LocalClaimAssertionGenerator(llm=object(), llm_params={})
    parsed = generator._parse_assertions(
        [
            {
                "statement": "Scrooge learns a lesson.",
                "score": 85,
                "sources": ["claim_1"],
            }
        ],
        claims=[
            {
                "statement": "Scrooge learns a lesson.",
                "sources": [{"text": "Scrooge learns a lesson."}],
            }
        ],
    )

    assert len(parsed) == 1
    assert parsed[0].score == 9
    assert parsed[0].statement == "Scrooge learns a lesson."
