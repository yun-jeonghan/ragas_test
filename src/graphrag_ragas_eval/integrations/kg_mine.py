from __future__ import annotations

from pathlib import Path

from ..ragas.runner import EvaluationRun
from .kggen import evaluate_kggen_mine


def evaluate_kg_correctness(
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
    return evaluate_kggen_mine(
        benchmark=benchmark,
        search_results=search_results,
        output=output,
        provider=provider,
        model=model,
        base_url=base_url,
        api_key=api_key,
        max_tokens=max_tokens,
    )
