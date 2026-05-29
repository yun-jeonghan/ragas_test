from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..eval import DEFAULT_RAGAS_METRICS, RagasRunner, load_benchmark_samples, load_search_results
from ..llm import build_ragas_llm, load_llm_runtime_config


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
    samples = load_benchmark_samples(plan.benchmark)
    results = load_search_results(plan.search_results)
    runtime_env = dict(os.environ)
    if plan.provider is not None:
        runtime_env["GREV_BENCHMARKQED_PROVIDER"] = plan.provider
    if plan.model is not None:
        runtime_env["GREV_BENCHMARKQED_MODEL"] = plan.model
    if plan.base_url is not None:
        runtime_env["GREV_BENCHMARKQED_BASE_URL"] = plan.base_url
    if plan.api_key is not None:
        runtime_env["GREV_BENCHMARKQED_API_KEY"] = plan.api_key
    runtime = load_llm_runtime_config(runtime_env, prefix="GREV_BENCHMARKQED")
    llm = build_ragas_llm(runtime)
    runner = RagasRunner(llm=llm, metrics=plan.metrics)
    run = runner.evaluate_results(samples, results)
    run.write_json(plan.output)
    return run
