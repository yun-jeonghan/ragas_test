from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..schemas import BenchmarkSample, EvaluationScore, GraphRAGSearchResult


@dataclass(frozen=True, slots=True)
class RagasRunner:
    llm: Any
    metrics: tuple[str, ...]

    def score_sample(self, sample: BenchmarkSample, result: GraphRAGSearchResult) -> list[EvaluationScore]:
        scores: list[EvaluationScore] = []
        for metric_name in self.metrics:
            scores.append(
                EvaluationScore(
                    sample_id=sample.sample_id,
                    metric_name=metric_name,
                    value=0.0,
                    reason="Metric wiring not implemented yet.",
                    metadata={
                        "question": sample.question,
                        "search_mode": sample.search_mode.value,
                        "answer": result.answer,
                    },
                )
            )
        return scores

