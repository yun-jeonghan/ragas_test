from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from openai import AsyncOpenAI

from ..adapters import load_benchmark_samples, load_search_results
from ..eval import EvaluationRun
from ..llm import load_llm_runtime_config
from ..schemas import BenchmarkSample, EvaluationScore, GraphRAGSearchResult

_METRIC_NAME = "correctness"
_PREFIX = "GREV_KGGEN_MINE"


@dataclass(frozen=True, slots=True)
class KGGenMinePlan:
    benchmark: Path
    search_results: Path
    output: Path
    provider: str | None = None
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    max_tokens: int | None = None
    temperature: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


def _openai_client(base_url: str | None, api_key: str | None) -> AsyncOpenAI:
    kwargs: dict[str, Any] = {}
    if base_url:
        kwargs["base_url"] = base_url
        kwargs["api_key"] = api_key or "EMPTY"
    else:
        kwargs["api_key"] = api_key
    return AsyncOpenAI(**kwargs)


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def _coerce_binary(value: Any) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return 1.0 if float(value) >= 0.5 else 0.0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "correct", "pass"}:
            return 1.0
        if normalized in {"0", "false", "no", "n", "incorrect", "fail"}:
            return 0.0
        try:
            return 1.0 if float(normalized) >= 0.5 else 0.0
        except ValueError:
            return 0.0
    return 0.0


def _parse_judge_response(raw_text: str) -> tuple[float, str | None]:
    stripped = _strip_code_fences(raw_text)
    parsed: dict[str, Any] | None = None

    try:
        candidate = json.loads(stripped)
        if isinstance(candidate, dict):
            parsed = candidate
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
        if match:
            try:
                candidate = json.loads(match.group(0))
            except json.JSONDecodeError:
                candidate = None
            if isinstance(candidate, dict):
                parsed = candidate

    if parsed is not None:
        for key in ("correctness", "evaluation", "score", "value"):
            if key in parsed:
                reason = parsed.get("reason") or parsed.get("explanation") or stripped
                return _coerce_binary(parsed[key]), str(reason)

    digit_match = re.search(r"\b([01])\b", stripped)
    if digit_match:
        return float(int(digit_match.group(1))), stripped

    lowered = stripped.lower()
    if "yes" in lowered and "no" not in lowered:
        return 1.0, stripped
    if "no" in lowered and "yes" not in lowered:
        return 0.0, stripped
    return 0.0, stripped


def _retrieved_context_text(result: GraphRAGSearchResult) -> str:
    if not result.retrieved_contexts:
        return "(no retrieved contexts)"
    lines = []
    for index, context in enumerate(result.retrieved_contexts, start=1):
        label = f"[{index}]"
        if context.source:
            label += f" {context.source}"
        lines.append(f"{label}\n{context.text}")
    return "\n\n".join(lines)


def _build_messages(sample: BenchmarkSample, result: GraphRAGSearchResult) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are evaluating knowledge-graph retrieval correctness. "
                "Decide whether the retrieved context contains enough evidence to support the reference answer. "
                "Use only the retrieved context. Return JSON only."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Question:\n{sample.question}\n\n"
                f"Reference answer:\n{sample.reference_answer}\n\n"
                f"Retrieved context:\n{_retrieved_context_text(result)}\n\n"
                "Task:\n"
                'Return a JSON object with keys "correctness" and "reason". '
                '"correctness" must be 1 if the context clearly contains the information in the reference answer, '
                'otherwise 0. "reason" should be a short explanation.'
            ),
        },
    ]


@dataclass(frozen=True, slots=True)
class KGGenMineRunner:
    client: AsyncOpenAI
    model: str
    max_tokens: int = 256
    temperature: float = 0.0
    extra_body: dict[str, Any] | None = None
    max_concurrency: int = 4

    async def aevaluate_sample(
        self,
        sample: BenchmarkSample,
        result: GraphRAGSearchResult,
    ) -> EvaluationScore:
        completion = await self.client.chat.completions.create(
            model=self.model,
            messages=_build_messages(sample, result),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            extra_body=dict(self.extra_body or {}) or None,
        )
        raw_text = completion.choices[0].message.content or ""
        value, reason = _parse_judge_response(raw_text)
        return EvaluationScore(
            sample_id=sample.sample_id,
            metric_name=_METRIC_NAME,
            value=value,
            reason=reason,
            metadata={
                "question": sample.question,
                "reference_answer": sample.reference_answer,
                "search_mode": sample.search_mode.value,
                "answer": result.answer,
                "retrieved_context_count": len(result.retrieved_contexts),
                "raw_response": raw_text,
            },
        )

    async def aevaluate_results(
        self,
        samples: Sequence[BenchmarkSample],
        search_results: Sequence[GraphRAGSearchResult],
    ) -> EvaluationRun:
        by_sample_id = {result.sample_id: result for result in search_results}
        ordered_pairs: list[tuple[BenchmarkSample, GraphRAGSearchResult]] = []
        for sample in samples:
            try:
                ordered_pairs.append((sample, by_sample_id[sample.sample_id]))
            except KeyError as exc:
                raise KeyError(f"Missing search result for sample_id={sample.sample_id}") from exc

        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def _guarded(sample: BenchmarkSample, result: GraphRAGSearchResult) -> EvaluationScore:
            async with semaphore:
                return await self.aevaluate_sample(sample, result)

        scores = await asyncio.gather(*[_guarded(sample, result) for sample, result in ordered_pairs])
        return EvaluationRun(scores=tuple(scores), results=tuple(result for _, result in ordered_pairs))

    def evaluate_results(
        self,
        samples: Sequence[BenchmarkSample],
        search_results: Sequence[GraphRAGSearchResult],
    ) -> EvaluationRun:
        return asyncio.run(self.aevaluate_results(samples, search_results))


def evaluate_mine(plan: KGGenMinePlan) -> EvaluationRun:
    samples = load_benchmark_samples(plan.benchmark)
    search_results = load_search_results(plan.search_results)
    runtime_env = dict(os.environ)
    if plan.provider is not None:
        runtime_env[f"{_PREFIX}_PROVIDER"] = plan.provider
    if plan.model is not None:
        runtime_env[f"{_PREFIX}_MODEL"] = plan.model
    if plan.base_url is not None:
        runtime_env[f"{_PREFIX}_BASE_URL"] = plan.base_url
    if plan.api_key is not None:
        runtime_env[f"{_PREFIX}_API_KEY"] = plan.api_key
    if plan.max_tokens is not None:
        runtime_env[f"{_PREFIX}_MAX_TOKENS"] = str(plan.max_tokens)

    runtime = load_llm_runtime_config(runtime_env, prefix=_PREFIX)
    client = _openai_client(runtime.base_url, runtime.api_key)
    runner = KGGenMineRunner(
        client=client,
        model=runtime.model,
        max_tokens=runtime.max_tokens or plan.max_tokens or 256,
        temperature=plan.temperature,
        extra_body=runtime.extra_body,
    )
    run = runner.evaluate_results(samples, search_results)
    run.write_json(plan.output)
    return run
