from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import shutil
from typing import Any

from ..reporting import render_smoke_report
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


def run_benchmark_qed_smoke(plan: BenchmarkQEDSmokePlan) -> BenchmarkQEDSmokeResult:
    if plan.output_dir.exists():
        shutil.rmtree(plan.output_dir)
    plan.output_dir.mkdir(parents=True, exist_ok=True)
    plan.report_output.parent.mkdir(parents=True, exist_ok=True)

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

    render_smoke_report(
        evaluation=autoe_evaluation,
        output=plan.report_output,
        generated_questions=autoq_questions,
        autod_summary=autod_summary,
        autoq_questions=autoq_questions,
        title=plan.report_title,
    )

    return BenchmarkQEDSmokeResult(
        autod_summary=autod_summary,
        autoq_questions=autoq_questions,
        autoe_evaluation=autoe_evaluation,
        report=plan.report_output,
    )
