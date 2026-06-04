from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from ..ragas import DEFAULT_RAGAS_METRICS
from ..ragas.runner import EvaluationRun
from ..schemas import BenchmarkSample, EvaluationScore, GraphRAGSearchResult, SearchMode
from ..upstream_benchmark_qed import (
    build_vendor_model_factory_runtime,
    ensure_autoe_import_shim,
)
from ..llm import load_llm_runtime_config


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


def _load_benchmark_rows(samples: list[BenchmarkSample]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "question_id": sample.sample_id,
                "question_text": sample.question,
                "answer": sample.reference_answer,
            }
            for sample in samples
        ]
    )


def _load_answer_rows(results: list[GraphRAGSearchResult]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "question_id": result.sample_id,
                "question_text": result.question,
                "answer": result.answer,
            }
            for result in results
        ]
    )


def evaluate_answers(plan: AutoEPlan) -> EvaluationRun:
    ensure_autoe_import_shim()
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
    chat_model, _ = build_vendor_model_factory_runtime(runtime)

    from benchmark_qed.autoe.reference.scores import get_reference_scores
    from benchmark_qed.config.model.score import Criteria
    from benchmark_qed.config.llm_config import LLMConfig, LLMProvider

    def _coerce_items(payload: object, *, key: str) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            items = payload.get(key, [])
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]
        return []

    def _load_samples(path: Path) -> list[BenchmarkSample]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        items = _coerce_items(payload, key="questions")
        samples: list[BenchmarkSample] = []
        for item in items:
            samples.append(
                BenchmarkSample(
                    sample_id=str(item.get("sample_id") or item.get("question_id")),
                    question=str(item.get("question") or item.get("question_text") or ""),
                    query_type=str(item.get("query_type") or item.get("mode") or "local"),
                    search_mode=SearchMode(
                        item.get("search_mode")
                        if isinstance(item.get("search_mode"), str)
                        else "local"
                    ),
                    reference_answer=str(item.get("reference_answer") or item.get("answer") or ""),
                )
            )
        return samples

    def _load_results(path: Path) -> list[GraphRAGSearchResult]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        items = _coerce_items(payload, key="results")
        results: list[GraphRAGSearchResult] = []
        for item in items:
            results.append(
                GraphRAGSearchResult(
                    sample_id=str(item.get("sample_id") or item.get("question_id")),
                    question=str(item.get("question") or item.get("question_text") or ""),
                    search_mode=SearchMode(
                        item.get("search_mode")
                        if isinstance(item.get("search_mode"), str)
                        else "local"
                    ),
                    answer=str(item.get("answer") or item.get("generated_answer") or ""),
                    retrieved_contexts=tuple(),
                )
            )
        return results

    samples = _load_samples(plan.benchmark)
    results = _load_results(plan.search_results)
    question_id_by_text = {sample.question: sample.sample_id for sample in samples}

    criteria = [Criteria(name=metric, description=metric) for metric in plan.metrics]
    generated_answers = _load_answer_rows(results)
    reference_answers = _load_benchmark_rows(samples)
    llm_config = LLMConfig(
        model=runtime.model,
        api_key=runtime.api_key or "EMPTY",
        llm_provider=LLMProvider.OpenAIChat,
        init_args={"api_base": runtime.base_url or ""},
        call_args={
            "temperature": 0.0,
            "seed": 42,
            **({"max_tokens": runtime.max_tokens} if runtime.max_tokens is not None else {}),
        },
    )
    scored = get_reference_scores(
        llm_client=chat_model,
        llm_config=llm_config,
        generated_answers=generated_answers,
        reference_answers=reference_answers,
        criteria=criteria,
        assessment_user_prompt=None,
        assessment_system_prompt=None,
        trials=1,
        question_id_key="question_id",
        question_text_key="question_text",
    )

    scores = tuple(
        EvaluationScore(
            sample_id=str(row.get("question_id") or question_id_by_text.get(str(row.get("question", "")), "")),
            metric_name=str(row["criteria"]),
            value=float(row["score"]),
            reason=str(row.get("reasoning", "")) or None,
            metadata={
                "trial": row.get("trial"),
                "question_text": row.get("question_text") or row.get("question"),
                "reference_answer": row.get("reference_answer"),
                "generated_answer": row.get("generated_answer"),
                "backend": "benchmark-qed",
            },
        )
        for _, row in scored.iterrows()
    )
    run = EvaluationRun(scores=scores, results=tuple(results))
    run.write_json(plan.output)
    return run
