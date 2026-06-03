from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ..documents import load_documents
from ..llm import load_llm_runtime_config
from ..upstream_benchmark_qed import (
    build_vendor_llm_config,
    ensure_vendor_path,
    model_dump_json_safe,
    write_documents_csv,
)


@dataclass(frozen=True, slots=True)
class AutoQPlan:
    source: Path
    output: Path
    num_questions: int = 10
    modes: tuple[str, ...] = ("local", "global")
    metadata: dict[str, Any] = field(default_factory=dict)


def _vendor_generation_types(modes: tuple[str, ...]) -> list[str]:
    mode_map = {
        "local": "data_local",
        "global": "data_global",
        "multi-hop": "data_linked",
        "unanswerable": None,
    }
    selected = [mode_map[mode] for mode in modes if mode_map.get(mode)]
    return selected or ["data_local", "data_global"]


def _mode_name(mode: Any) -> str:
    return str(getattr(mode, "value", mode))


def _normalize_question(item: dict[str, Any], *, source: str) -> dict[str, Any]:
    normalized = dict(item)
    if "question" not in normalized and "text" in normalized:
        normalized["question"] = normalized.get("text")
    normalized["source"] = source
    return normalized


def generate_queries(plan: AutoQPlan):
    ensure_vendor_path()
    documents = load_documents(plan.source)
    source_rows = [
        {"id": document.id, "title": document.title, "text": document.text}
        for document in documents
    ]
    workdir = plan.output.parent / f".{plan.output.stem}.benchmark-qed"
    input_csv = write_documents_csv(source_rows, workdir / "input.csv")
    output_dir = workdir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    runtime = load_llm_runtime_config(prefix="GREV_BENCHMARKQED")
    from benchmark_qed.autoq.cli import GenerationType, autoq as upstream_autoq
    from benchmark_qed.autoq.config import (
        EncodingModelConfig,
        InputConfig,
        QuestionGenerationConfig,
        SamplingConfig,
    )

    config = QuestionGenerationConfig(
        input=InputConfig(dataset_path=input_csv),
        concurrent_requests=1,
        encoding=EncodingModelConfig(
            # BenchmarkQED expects a tiktoken encoding name here, not the embedding model id.
            model_name="o200k_base",
            chunk_size=600,
            chunk_overlap=100,
        ),
        sampling=SamplingConfig(
            num_clusters=max(1, min(len(source_rows) or 1, plan.num_questions)),
            num_samples_per_cluster=1,
            random_seed=42,
        ),
        chat_model=build_vendor_llm_config(runtime, embeddings=False),
        embedding_model=build_vendor_llm_config(runtime, embeddings=True),
    )

    config_path = workdir / "settings.yaml"
    config_path.write_text(
        yaml.safe_dump(
            config.model_dump(mode="json", by_alias=True),
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    generation_type_map = {
        "local": GenerationType.data_local,
        "global": GenerationType.data_global,
        "multi-hop": GenerationType.data_linked,
    }
    generation_types = [
        generation_type_map[mode_name]
        for mode in plan.modes
        if (mode_name := _mode_name(mode)) in generation_type_map
    ] or [GenerationType.data_local, GenerationType.data_global]

    upstream_autoq(
        configuration_path=config_path,
        output_data_path=output_dir,
        generation_types=generation_types,
        print_model_usage=False,
    )

    collected: list[dict[str, Any]] = []
    for generation_type in generation_types:
        question_dir = output_dir / f"{generation_type.value}_questions"
        selected_path = question_dir / "selected_questions.json"
        candidate_path = question_dir / "candidate_questions.json"
        if not selected_path.exists():
            continue
        questions = json.loads(selected_path.read_text(encoding="utf-8"))
        if isinstance(questions, list):
            selected = [_normalize_question(question, source="selected") for question in questions if isinstance(question, dict)]
            if selected:
                collected.extend(selected)
                continue
        if candidate_path.exists():
            candidates = json.loads(candidate_path.read_text(encoding="utf-8"))
            if isinstance(candidates, list):
                collected.extend(
                    _normalize_question(question, source="candidate")
                    for question in candidates
                    if isinstance(question, dict)
                )

    payload = {
        "metadata": {
            "component": "AutoQ",
            "num_questions": plan.num_questions,
            "modes": list(plan.modes),
            "backend": "benchmark-qed",
            **plan.metadata,
        },
        "questions": collected[: plan.num_questions],
    }
    plan.output.parent.mkdir(parents=True, exist_ok=True)
    plan.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload["questions"]
