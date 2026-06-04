from __future__ import annotations

from pathlib import Path
from typing import Sequence

from ..llm import build_ragas_embeddings, build_ragas_llm, load_llm_runtime_config
from ..adapters import load_benchmark_samples, load_search_results
from .runner import EvaluationRun, RagasRunner


def evaluate_ragas(
    *,
    benchmark: Path,
    search_results: Path,
    provider: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    metrics: Sequence[str],
    prefix: str = "GREV_RAGAS",
) -> EvaluationRun:
    runtime_env = {}
    if provider is not None:
        runtime_env[f"{prefix}_PROVIDER"] = provider
    if model is not None:
        runtime_env[f"{prefix}_MODEL"] = model
    if base_url is not None:
        runtime_env[f"{prefix}_BASE_URL"] = base_url
    if api_key is not None:
        runtime_env[f"{prefix}_API_KEY"] = api_key
    runtime = load_llm_runtime_config(runtime_env or None, prefix=prefix)
    samples = load_benchmark_samples(benchmark)
    results = load_search_results(search_results)
    llm = build_ragas_llm(runtime)
    embeddings = build_ragas_embeddings(runtime)
    runner = RagasRunner(llm=llm, embeddings=embeddings, metrics=tuple(metrics))
    return runner.evaluate_results(samples, results)
