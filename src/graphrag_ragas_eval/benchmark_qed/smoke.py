from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
import shutil
from typing import Any

from ..reporting import render_smoke_report
from ..llm import load_llm_runtime_config
from ..upstream_benchmark_qed import build_vendor_model_factory_runtime
from .autod import AutoDPlan, summarize_dataset
from .autoe import AutoEPlan, evaluate_answers
from .autoq import AutoQPlan, generate_queries


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


@dataclass(frozen=True, slots=True)
class BenchmarkQEDSmokePlan:
    source: Path = Path("examples/sample_docs")
    benchmark: Path = Path("data/benchmarks/sample_benchmark.json")
    search_results: Path = Path("data/results/sample_search_results.json")
    output_dir: Path = Path("/tmp/grev-benchmark-qed-smoke")
    report_output: Path = _repo_root() / "reports" / "benchmark-qed-smoke.html"
    target_size: int = 1
    num_questions: int = 1
    modes: tuple[str, ...] = ("local",)
    metrics: tuple[str, ...] = ("context_precision",)
    report_title: str = "BenchmarkQED Smoke Report"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BenchmarkQEDSmokeResult:
    autod_summary: Path
    autoq_questions: Path
    autoe_evaluation: Path
    report: Path


def _extract_completion_text(response: Any) -> str:
    for attribute in ("content", "formatted_response"):
        value = getattr(response, attribute, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    output = getattr(response, "output", None)
    if output is not None:
        for attribute in ("content", "formatted_response"):
            value = getattr(output, attribute, None)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _build_interpretation(runtime: Any, autod_summary: Path, autoq_questions: Path, autoe_evaluation: Path) -> str:
    autod_data = json.loads(autod_summary.read_text(encoding="utf-8"))
    autoq_data = json.loads(autoq_questions.read_text(encoding="utf-8"))
    evaluation_data = json.loads(autoe_evaluation.read_text(encoding="utf-8"))

    prompt_payload = {
        "runtime": {
            "provider": getattr(runtime, "provider", None),
            "model": getattr(runtime, "model", None),
            "base_url": getattr(runtime, "base_url", None),
            "embeddings_model": getattr(runtime, "embeddings_model", None),
        },
        "autod": {
            "documents": len(autod_data.get("documents", [])),
            "themes": autod_data.get("themes", []),
            "corpus_summary": autod_data.get("corpus_summary"),
            "benchmark_qed_summary": autod_data.get("benchmark_qed", {}).get("summary"),
        },
        "autoq": {
            "questions": len(autoq_data.get("questions", [])),
            "modes": autoq_data.get("metadata", {}).get("modes", []),
            "first_question": (autoq_data.get("questions", [{}])[0] or {}).get("question")
            if autoq_data.get("questions")
            else None,
        },
        "autoe": {
            "aggregate": evaluation_data.get("aggregate", {}),
            "scores": len(evaluation_data.get("scores", [])),
            "results": len(evaluation_data.get("results", [])),
        },
    }

    try:
        chat_model, _ = build_vendor_model_factory_runtime(runtime)
        messages = [
            {
                "role": "system",
                "content": (
                    "You write concise smoke-test report commentary. "
                    "Be grounded in the numbers, mention caveats, and keep it to 4 short bullet points."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(prompt_payload, ensure_ascii=False, indent=2),
            },
        ]
        response = asyncio.run(chat_model.completion_async(messages=messages))
        text = _extract_completion_text(response)
        if text:
            return text
    except Exception:
        pass

    aggregate = evaluation_data.get("aggregate", {})
    lines = [
        f"Model lens: {getattr(runtime, 'model', 'qwen2.5:0.5b')} via {getattr(runtime, 'provider', 'ollama')}.",
        "This is a smoke run, so the numbers are mainly for wiring validation.",
    ]
    if aggregate:
        for metric_name, value in aggregate.items():
            lines.append(f"{metric_name} = {value}.")
    if not autoq_data.get("questions"):
        lines.append("AutoQ returned no selected questions in this run, so generation coverage is the main thing to inspect.")
    return "\n".join(lines)


def run_benchmark_qed_smoke(plan: BenchmarkQEDSmokePlan) -> BenchmarkQEDSmokeResult:
    if plan.output_dir.exists():
        shutil.rmtree(plan.output_dir)
    plan.output_dir.mkdir(parents=True, exist_ok=True)
    plan.report_output.parent.mkdir(parents=True, exist_ok=True)

    runtime = load_llm_runtime_config(dict(os.environ), prefix="GREV_BENCHMARKQED")

    autod_summary = plan.output_dir / "autod-summary.json"
    autoq_questions = plan.output_dir / "autoq-questions.json"
    autoe_evaluation = plan.output_dir / "autoe-evaluation.json"

    summarize_dataset(
        AutoDPlan(
            source=plan.source,
            output=autod_summary,
            target_size=plan.target_size,
            metadata={"smoke": True, **plan.metadata},
        )
    )
    generate_queries(
        AutoQPlan(
            source=plan.source,
            output=autoq_questions,
            num_questions=plan.num_questions,
            modes=plan.modes,
            metadata={"smoke": True, **plan.metadata},
        )
    )
    evaluate_answers(
        AutoEPlan(
            benchmark=plan.benchmark,
            search_results=plan.search_results,
            output=autoe_evaluation,
            metrics=plan.metrics,
            metadata={"smoke": True, **plan.metadata},
        )
    )

    interpretation = _build_interpretation(runtime, autod_summary, autoq_questions, autoe_evaluation)

    render_smoke_report(
        evaluation=autoe_evaluation,
        output=plan.report_output,
        generated_questions=autoq_questions,
        autod_summary=autod_summary,
        autoq_questions=autoq_questions,
        title=plan.report_title,
        report_metadata={
            "chat_model": runtime.model,
            "provider": runtime.provider,
            "base_url": runtime.base_url,
            "embeddings_model": runtime.embeddings_model,
        },
        interpretation=interpretation,
    )

    return BenchmarkQEDSmokeResult(
        autod_summary=autod_summary,
        autoq_questions=autoq_questions,
        autoe_evaluation=autoe_evaluation,
        report=plan.report_output,
    )
