from __future__ import annotations

from dataclasses import dataclass


DEFAULT_RAGAS_METRICS: tuple[str, ...] = (
    "context_precision",
    "context_recall",
    "faithfulness",
    "answer_relevancy",
)

GRAPH_METRICS: tuple[str, ...] = (
    "graph_path_accuracy",
    "community_coverage",
    "entity_coverage",
    "citation_consistency",
    "mode_match",
)


@dataclass(frozen=True, slots=True)
class MetricPlan:
    ragas_metrics: tuple[str, ...] = DEFAULT_RAGAS_METRICS
    graph_metrics: tuple[str, ...] = GRAPH_METRICS
