from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ProjectPaths:
    root: Path

    @property
    def graphrag_output(self) -> Path:
        return self.root / "data" / "raw" / "graphrag"

    @property
    def benchmarks(self) -> Path:
        return self.root / "data" / "benchmarks"

    @property
    def results(self) -> Path:
        return self.root / "data" / "results"

    @property
    def reports(self) -> Path:
        return self.root / "reports"


@dataclass(frozen=True, slots=True)
class SearchConfig:
    community_level: int = 2
    max_contexts: int = 8
    response_type: str = "Multiple Paragraphs"


@dataclass(frozen=True, slots=True)
class EvalConfig:
    metrics: tuple[str, ...] = (
        "context_precision",
        "context_recall",
        "faithfulness",
        "answer_relevancy",
    )
    include_graph_metrics: bool = True

