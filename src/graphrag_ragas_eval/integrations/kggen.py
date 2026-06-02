from __future__ import annotations

from pathlib import Path

from ..eval import EvaluationRun
from ..kggen import KGGenMinePlan, evaluate_mine


def evaluate_kggen_mine(
    *,
    benchmark: Path,
    search_results: Path,
    output: Path,
    provider: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    max_tokens: int | None = None,
) -> EvaluationRun:
    plan = KGGenMinePlan(
        benchmark=benchmark,
        search_results=search_results,
        output=output,
        provider=provider,
        model=model,
        base_url=base_url,
        api_key=api_key,
        max_tokens=max_tokens,
    )
    return evaluate_mine(plan)
