from __future__ import annotations

import asyncio
import inspect
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from ..schemas import BenchmarkSample, EvaluationScore, GraphRAGSearchResult, RetrievedContext


MetricObject = Any


@dataclass(frozen=True, slots=True)
class EvaluationRun:
    scores: tuple[EvaluationScore, ...]
    results: tuple[GraphRAGSearchResult, ...]

    def aggregate(self) -> dict[str, float]:
        totals: dict[str, list[float]] = {}
        for score in self.scores:
            totals.setdefault(score.metric_name, []).append(score.value)
        return {
            metric_name: sum(values) / len(values)
            for metric_name, values in totals.items()
            if values
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "scores": [
                {
                    "sample_id": score.sample_id,
                    "metric_name": score.metric_name,
                    "value": score.value,
                    "reason": score.reason,
                    "metadata": score.metadata,
                }
                for score in self.scores
            ],
            "results": [
                {
                    "sample_id": result.sample_id,
                    "question": result.question,
                    "search_mode": result.search_mode.value,
                    "answer": result.answer,
                    "retrieved_contexts": [
                        {
                            "text": context.text,
                            "source": context.source,
                            "score": context.score,
                            "metadata": context.metadata,
                        }
                        for context in result.retrieved_contexts
                    ],
                    "citations": list(result.citations),
                    "metadata": result.metadata,
                }
                for result in self.results
            ],
            "aggregate": self.aggregate(),
        }

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def _context_texts(contexts: Sequence[RetrievedContext]) -> list[str]:
    return [context.text for context in contexts if context.text]


def _metric_kwargs(sample: BenchmarkSample, result: GraphRAGSearchResult) -> dict[str, Any]:
    contexts = _context_texts(result.retrieved_contexts)
    references = list(sample.reference_contexts)
    payload = {
        "user_input": sample.question,
        "question": sample.question,
        "response": result.answer,
        "answer": result.answer,
        "reference": sample.reference_answer,
        "ground_truth": sample.reference_answer,
        "retrieved_contexts": contexts,
        "contexts": contexts,
        "reference_contexts": references,
    }
    return payload


def _filter_kwargs(func: Callable[..., Any], kwargs: dict[str, Any]) -> dict[str, Any]:
    signature = inspect.signature(func)
    accepted = set(signature.parameters)
    return {key: value for key, value in kwargs.items() if key in accepted}


def _try_instantiate_metric(metric_cls: type[Any], llm: Any, embeddings: Any | None = None) -> Any:
    candidate_kwargs_list: list[dict[str, Any]] = []
    if llm is not None and embeddings is not None:
        candidate_kwargs_list.append({"llm": llm, "embeddings": embeddings})
    if llm is not None:
        candidate_kwargs_list.append({"llm": llm})
    if embeddings is not None:
        candidate_kwargs_list.append({"embeddings": embeddings})
    candidate_kwargs_list.append({})

    for candidate_kwargs in candidate_kwargs_list:
        try:
            return metric_cls(**candidate_kwargs)
        except TypeError:
            continue
    return metric_cls()


def _resolve_metric_class(metric_name: str) -> type[Any]:
    candidates: dict[str, list[tuple[str, str]]] = {
        "context_precision": [
            ("ragas.metrics.collections", "ContextPrecision"),
            ("ragas.metrics", "ContextPrecision"),
            ("ragas.metrics", "LLMContextPrecisionWithReference"),
        ],
        "context_recall": [
            ("ragas.metrics.collections", "ContextRecall"),
            ("ragas.metrics", "ContextRecall"),
            ("ragas.metrics", "LLMContextRecall"),
        ],
        "faithfulness": [
            ("ragas.metrics.collections", "Faithfulness"),
            ("ragas.metrics", "Faithfulness"),
        ],
        "answer_relevancy": [
            ("ragas.metrics.collections", "ResponseRelevancy"),
            ("ragas.metrics.collections", "AnswerRelevancy"),
            ("ragas.metrics", "ResponseRelevancy"),
            ("ragas.metrics", "AnswerRelevancy"),
        ],
    }
    for module_name, class_name in candidates.get(metric_name, []):
        try:
            module = __import__(module_name, fromlist=[class_name])
            return getattr(module, class_name)
        except (ImportError, AttributeError):
            continue
    raise ValueError(f"Unsupported or unavailable Ragas metric: {metric_name}")


@dataclass(frozen=True, slots=True)
class RagasRunner:
    llm: Any
    metrics: tuple[str, ...]
    embeddings: Any | None = None

    def build_metric_objects(self) -> tuple[Any, ...]:
        metric_objects: list[Any] = []
        for metric_name in self.metrics:
            metric_cls = _resolve_metric_class(metric_name)
            metric_objects.append(_try_instantiate_metric(metric_cls, self.llm, self.embeddings))
        return tuple(metric_objects)

    async def aevaluate_sample(
        self,
        sample: BenchmarkSample,
        result: GraphRAGSearchResult,
        metric_objects: Sequence[Any],
    ) -> list[EvaluationScore]:
        payload = _metric_kwargs(sample, result)
        scores: list[EvaluationScore] = []
        for metric_name, metric in zip(self.metrics, metric_objects, strict=True):
            score_value = await self._call_metric(metric, payload)
            scores.append(
                EvaluationScore(
                    sample_id=sample.sample_id,
                    metric_name=metric_name,
                    value=float(score_value),
                    reason=None,
                    metadata={
                        "question": sample.question,
                        "search_mode": sample.search_mode.value,
                        "answer": result.answer,
                    },
                )
            )
        return scores

    async def aevaluate_results(
        self,
        samples: Sequence[BenchmarkSample],
        search_results: Sequence[GraphRAGSearchResult],
    ) -> EvaluationRun:
        by_sample_id = {result.sample_id: result for result in search_results}
        all_scores: list[EvaluationScore] = []
        ordered_results: list[GraphRAGSearchResult] = []
        metric_objects = self.build_metric_objects()
        for sample in samples:
            try:
                result = by_sample_id[sample.sample_id]
            except KeyError as exc:
                raise KeyError(f"Missing search result for sample_id={sample.sample_id}") from exc
            ordered_results.append(result)
            all_scores.extend(await self.aevaluate_sample(sample, result, metric_objects))
        return EvaluationRun(scores=tuple(all_scores), results=tuple(ordered_results))

    def evaluate_results(
        self,
        samples: Sequence[BenchmarkSample],
        search_results: Sequence[GraphRAGSearchResult],
    ) -> EvaluationRun:
        return asyncio.run(self.aevaluate_results(samples, search_results))

    async def _call_metric(self, metric: Any, payload: dict[str, Any]) -> float:
        ascore = getattr(metric, "ascore", None)
        if ascore is None:
            raise TypeError(f"Metric object does not expose ascore(): {metric!r}")
        kwargs = _filter_kwargs(ascore, payload)
        result = ascore(**kwargs)
        if inspect.isawaitable(result):
            result = await result
        value = getattr(result, "value", result)
        return float(value)


def evaluate_sample_set(
    samples: Sequence[BenchmarkSample],
    search_results: Sequence[GraphRAGSearchResult],
    *,
    llm: Any,
    metrics: tuple[str, ...],
) -> EvaluationRun:
    runner = RagasRunner(llm=llm, metrics=metrics)
    return runner.evaluate_results(samples, search_results)
