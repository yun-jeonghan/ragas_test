from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
import shutil
from typing import Any

import yaml

from ..ragas import DEFAULT_RAGAS_METRICS
from ..reporting import render_smoke_report
from ..llm import load_llm_runtime_config
from ..upstream_benchmark_qed import build_vendor_model_factory_runtime, ensure_vendor_path
from .autod import AutoDPlan, summarize_dataset
from .autoe import AutoEPlan, evaluate_answers
from .autoq import AutoQPlan, generate_queries
from .retrieval import RetrievalPrepPlan, prepare_retrieval_results


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


@dataclass(frozen=True, slots=True)
class BenchmarkQEDSmokePlan:
    source: Path = Path("examples/sample_docs")
    benchmark: Path = Path("data/benchmarks/sample_benchmark.json")
    search_results: Path = Path("data/results/sample_search_results.json")
    assertion_scores: Path | None = None
    output_dir: Path = Path("/tmp/grev-benchmark-qed-smoke")
    report_output: Path = _repo_root() / "reports" / "benchmark-qed-smoke.html"
    target_size: int = 1
    num_questions: int = 1
    modes: tuple[str, ...] = ("local",)
    metrics: tuple[str, ...] = DEFAULT_RAGAS_METRICS
    assertion_min_validation_score: int = 1
    assertion_validation_enabled: bool = False
    report_title: str = "BenchmarkQED Smoke Report"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BenchmarkQEDSmokeResult:
    autod_summary: Path
    autoq_questions: Path
    assertion_prep: Path
    autoe_evaluation: Path
    retrieval_results: Path
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


def _autoq_workdir(output_path: Path) -> Path:
    return output_path.parent / f".{output_path.stem}.benchmark-qed"


def _mode_to_assertion_type(mode: str) -> str:
    mode_name = str(mode)
    if mode_name == "global":
        return "global"
    if mode_name == "multi-hop":
        return "linked"
    return "local"


def _prepare_assertion_config(
    settings_path: Path,
    output_path: Path,
    *,
    assertion_type: str,
    validation_enabled: bool,
    min_validation_score: int,
) -> Path:
    payload = yaml.safe_load(settings_path.read_text(encoding="utf-8"))
    assertions = payload.setdefault("assertions", {})
    assertion_cfg = assertions.get(assertion_type, {})
    if isinstance(assertion_cfg, dict):
        assertion_cfg["enable_validation"] = validation_enabled
        assertion_cfg["min_validation_score"] = min_validation_score
        assertions[assertion_type] = assertion_cfg
    raw_settings_path = output_path.parent / f"{settings_path.stem}.raw.yaml"
    raw_settings_path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return raw_settings_path


def _load_assertion_prep_summary(summary_dir: Path, *, settings_path: Path, validation_enabled: bool, min_validation_score: int, assertion_type: str) -> Path:
    questions_path = summary_dir / "assertions.json"
    stats_path = summary_dir / "assertions_stats.json"
    sources_path = summary_dir / "assertion_sources.json"
    map_questions_path = summary_dir / "map_assertions.json"
    map_stats_path = summary_dir / "map_assertions_stats.json"

    summary_payload: dict[str, Any] = {
        "metadata": {
            "component": "AssertionPrep",
            "backend": "benchmark-qed",
            "assertion_type": assertion_type,
            "validation_enabled": validation_enabled,
            "min_validation_score": min_validation_score,
            "settings_path": str(settings_path),
        }
    }

    if questions_path.exists():
        summary_payload["questions"] = json.loads(questions_path.read_text(encoding="utf-8"))
    if stats_path.exists():
        summary_payload["stats"] = json.loads(stats_path.read_text(encoding="utf-8"))
    if sources_path.exists():
        summary_payload["sources"] = json.loads(sources_path.read_text(encoding="utf-8"))
    if map_questions_path.exists():
        summary_payload["map_questions"] = json.loads(map_questions_path.read_text(encoding="utf-8"))
    if map_stats_path.exists():
        summary_payload["map_stats"] = json.loads(map_stats_path.read_text(encoding="utf-8"))

    combined_path = summary_dir.parent / "assertion-prep.json"
    combined_path.write_text(
        json.dumps(summary_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return combined_path


def _generate_assertion_prep(
    *,
    autoq_workdir: Path,
    output_dir: Path,
    assertion_type: str,
    validation_enabled: bool,
    min_validation_score: int,
) -> Path:
    ensure_vendor_path()
    from benchmark_qed.autoq.cli import AssertionType, generate_assertions as vendor_generate_assertions

    settings_path = autoq_workdir / "settings.yaml"
    questions_path = autoq_workdir / "output" / f"data_{assertion_type}_questions" / "candidate_questions.json"
    if not questions_path.exists():
        raise FileNotFoundError(f"Missing candidate questions file: {questions_path}")

    assertion_output_dir = output_dir / f"{assertion_type}-assertions-raw.benchmark-qed"
    assertion_output_dir.mkdir(parents=True, exist_ok=True)
    raw_settings_path = _prepare_assertion_config(
        settings_path,
        assertion_output_dir,
        assertion_type=assertion_type,
        validation_enabled=validation_enabled,
        min_validation_score=min_validation_score,
    )
    vendor_generate_assertions(
        configuration_path=raw_settings_path,
        questions_path=questions_path,
        output_path=assertion_output_dir,
        assertion_type=AssertionType(assertion_type),
        print_model_usage=False,
    )
    return _load_assertion_prep_summary(
        assertion_output_dir,
        settings_path=raw_settings_path,
        validation_enabled=validation_enabled,
        min_validation_score=min_validation_score,
        assertion_type=assertion_type,
    )


def _build_interpretation(
    runtime: Any,
    autod_summary: Path,
    autoq_questions: Path,
    assertion_prep: Path,
    autoe_evaluation: Path,
    assertion_scores: Path | None = None,
) -> str:
    autod_data = json.loads(autod_summary.read_text(encoding="utf-8"))
    autoq_data = json.loads(autoq_questions.read_text(encoding="utf-8"))
    assertion_data = json.loads(assertion_prep.read_text(encoding="utf-8"))
    evaluation_data = json.loads(autoe_evaluation.read_text(encoding="utf-8"))
    assertion_scores_data = (
        json.loads(assertion_scores.read_text(encoding="utf-8")) if assertion_scores else None
    )

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
        "assertions": {
            "questions": len(assertion_data.get("questions", [])),
            "stats": assertion_data.get("stats", {}),
            "validation_enabled": assertion_data.get("metadata", {}).get("validation_enabled"),
            "min_validation_score": assertion_data.get("metadata", {}).get("min_validation_score"),
        },
        "assertion_scores": {
            "score_rows": len((assertion_scores_data or {}).get("scores", [])),
            "summary_by_assertion": len((assertion_scores_data or {}).get("summary_by_assertion", [])),
            "summary_by_question": len((assertion_scores_data or {}).get("summary_by_question", [])),
            "aggregate": (assertion_scores_data or {}).get("aggregate", {}),
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
    if assertion_scores_data is not None:
        lines.append(
            f"Assertion scoring produced {len(assertion_scores_data.get('scores', []))} score row(s) and {len(assertion_scores_data.get('aggregate', {}))} aggregate metric(s)."
        )
    return "\n".join(lines)


def run_benchmark_qed_smoke(plan: BenchmarkQEDSmokePlan) -> BenchmarkQEDSmokeResult:
    if plan.output_dir.exists():
        shutil.rmtree(plan.output_dir)
    plan.output_dir.mkdir(parents=True, exist_ok=True)
    plan.report_output.parent.mkdir(parents=True, exist_ok=True)

    runtime = load_llm_runtime_config(dict(os.environ), prefix="GREV_BENCHMARKQED")

    autod_summary = plan.output_dir / "autod-summary.json"
    autoq_questions = plan.output_dir / "autoq-questions.json"
    assertion_prep = plan.output_dir / "assertion-prep.json"
    assertion_scores = plan.assertion_scores
    autoe_evaluation = plan.output_dir / "autoe-evaluation.json"
    retrieval_results = plan.output_dir / "retrieval-results.json"

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
    assertion_type = _mode_to_assertion_type(plan.modes[0] if plan.modes else "local")
    assertion_prep = _generate_assertion_prep(
        autoq_workdir=_autoq_workdir(autoq_questions),
        output_dir=plan.output_dir,
        assertion_type=assertion_type,
        validation_enabled=plan.assertion_validation_enabled,
        min_validation_score=plan.assertion_min_validation_score,
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
    prepare_retrieval_results(
        RetrievalPrepPlan(
            search_results=plan.search_results,
            output=retrieval_results,
            metadata={"smoke": True, **plan.metadata},
        )
    )

    interpretation = _build_interpretation(
        runtime,
        autod_summary,
        autoq_questions,
        assertion_prep,
        autoe_evaluation,
        assertion_scores=assertion_scores,
    )

    render_smoke_report(
        evaluation=autoe_evaluation,
        output=plan.report_output,
        generated_questions=autoq_questions,
        autod_summary=autod_summary,
        autoq_questions=autoq_questions,
        assertion_prep=assertion_prep,
        assertion_scores=assertion_scores,
        title=plan.report_title,
        retrieval_results=retrieval_results,
        report_metadata={
            "chat_model": runtime.model,
            "provider": runtime.provider,
            "base_url": runtime.base_url,
            "embeddings_model": runtime.embeddings_model,
            "assertion_validation_enabled": plan.assertion_validation_enabled,
            "assertion_min_validation_score": plan.assertion_min_validation_score,
        },
        interpretation=interpretation,
    )

    return BenchmarkQEDSmokeResult(
        autod_summary=autod_summary,
        autoq_questions=autoq_questions,
        assertion_prep=assertion_prep,
        autoe_evaluation=autoe_evaluation,
        retrieval_results=retrieval_results,
        report=plan.report_output,
    )
