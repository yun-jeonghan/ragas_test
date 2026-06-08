from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from graphrag_storage.storage_config import StorageConfig
from pydantic import BaseModel, SecretStr

from ..documents import load_documents
from ..llm import load_llm_runtime_config
from ..upstream_benchmark_qed import (
    build_vendor_llm_config,
    ensure_vendor_path,
    model_dump_json_safe,
)


@dataclass(frozen=True, slots=True)
class AutoQPlan:
    source: Path
    output: Path
    num_questions: int = 10
    modes: tuple[str, ...] = ("local",)
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


def _yaml_safe_value(value: Any) -> Any:
    if isinstance(value, SecretStr):
        return value.get_secret_value()
    if isinstance(value, BaseModel):
        return {key: _yaml_safe_value(item) for key, item in value.model_dump(mode="python", by_alias=True).items()}
    if isinstance(value, dict):
        return {key: _yaml_safe_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_yaml_safe_value(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    return value


def _mode_name(mode: Any) -> str:
    return str(getattr(mode, "value", mode))


def _normalize_question(item: dict[str, Any], *, source: str) -> dict[str, Any]:
    normalized = dict(item)
    if "question" not in normalized and "text" in normalized:
        normalized["question"] = normalized.get("text")
    normalized["source"] = source
    return normalized


def _stage_text_inputs(source: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    files = [source] if source.is_file() else [path for path in sorted(source.rglob("*")) if path.is_file()]
    for path in files:
        if path.suffix.lower() != ".txt":
            continue
        target = dest / path.relative_to(source if source.is_dir() else source.parent)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def generate_queries(plan: AutoQPlan):
    ensure_vendor_path()
    documents = load_documents(plan.source)
    workdir = plan.output.parent / f".{plan.output.stem}.benchmark-qed"
    input_dir = workdir / "input"
    # benchmark-qed expects its input storage to be rooted at "input/" inside the workdir.
    _stage_text_inputs(plan.source, input_dir)
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
        input=InputConfig(
            dataset_path=Path("."),
            input_type="text",
            storage=StorageConfig(type="file", base_dir="input"),
        ),
        concurrent_requests=1,
        encoding=EncodingModelConfig(
            # BenchmarkQED expects a tiktoken encoding name here, not the embedding model id.
            model_name="o200k_base",
            chunk_size=600,
            chunk_overlap=100,
        ),
        sampling=SamplingConfig(
            num_clusters=max(1, min(len(documents) or 1, plan.num_questions)),
            num_samples_per_cluster=1,
            random_seed=42,
        ),
        chat_model=build_vendor_llm_config(runtime, embeddings=False),
        embedding_model=build_vendor_llm_config(runtime, embeddings=True),
    )

    config_path = workdir / "settings.yaml"
    config_path.write_text(
        yaml.safe_dump(_yaml_safe_value(config), sort_keys=False, allow_unicode=True),
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
    ] or [GenerationType.data_local]

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
