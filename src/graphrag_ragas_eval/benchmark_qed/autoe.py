from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..eval import DEFAULT_RAGAS_METRICS
from ..integrations import evaluate_ragas


@dataclass(frozen=True, slots=True)
class AutoEPlan:
    benchmark: Path
    search_results: Path
    output: Path
    provider: str | None = None
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    metrics: tuple[str, ...] = DEFAULT_RAGAS_METRICS
    metadata: dict[str, Any] = field(default_factory=dict)


def evaluate_answers(plan: AutoEPlan):
    run = evaluate_ragas(
        benchmark=plan.benchmark,
        search_results=plan.search_results,
        provider=plan.provider,
        model=plan.model,
        base_url=plan.base_url,
        api_key=plan.api_key,
        metrics=plan.metrics,
        prefix="GREV_BENCHMARKQED",
    )
    run.write_json(plan.output)
    return run
