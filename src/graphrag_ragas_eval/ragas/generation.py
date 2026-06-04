from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..documents import load_documents
from ..llm import build_ragas_embeddings, build_ragas_llm, load_llm_runtime_config


@dataclass(frozen=True, slots=True)
class RagasQuestionGenerationPlan:
    source: Path
    output: Path
    testset_size: int = 10
    question_modes: tuple[str, ...] | None = None
    provider: str | None = None
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    prefix: str = "GREV_RAGAS"
    metadata: dict[str, Any] = field(default_factory=dict)


def _to_langchain_documents(documents: list[Any]) -> list[Any]:
    try:
        from langchain_core.documents import Document
    except ImportError:  # pragma: no cover - optional dependency fallback
        Document = None  # type: ignore[assignment]

    converted: list[Any] = []
    for document in documents:
        metadata = {
            "id": getattr(document, "id", None),
            "title": getattr(document, "title", None),
            "source_path": str(getattr(document, "source_path", "")) if getattr(document, "source_path", None) else None,
        }
        metadata = {key: value for key, value in metadata.items() if value is not None}
        if Document is not None:
            converted.append(Document(page_content=getattr(document, "text", ""), metadata=metadata))
        else:  # pragma: no cover - used only when langchain_core is unavailable
            converted.append(type("Document", (), {"page_content": getattr(document, "text", ""), "metadata": metadata})())
    return converted


def _dataset_to_records(dataset: Any) -> list[dict[str, Any]]:
    if hasattr(dataset, "to_pandas"):
        frame = dataset.to_pandas()
        if hasattr(frame, "to_dict"):
            records = frame.to_dict(orient="records")
            if isinstance(records, list):
                return [dict(record) for record in records]
    if hasattr(dataset, "to_dict"):
        payload = dataset.to_dict()
        if isinstance(payload, list):
            return [dict(record) for record in payload]
        if isinstance(payload, dict):
            return [dict(payload)]
    return [{"value": repr(dataset)}]


def _normalize_question_modes(question_modes: tuple[str, ...] | None) -> tuple[str, ...] | None:
    if not question_modes:
        return None

    normalized: list[str] = []
    for mode in question_modes:
        cleaned = mode.strip().lower().replace("_", "-")
        if not cleaned:
            continue
        if cleaned in {"default", "all"}:
            return None
        if cleaned not in normalized:
            normalized.append(cleaned)
    return tuple(normalized) or None


def _build_query_distribution(llm: Any, question_modes: tuple[str, ...] | None) -> list[tuple[Any, float]] | None:
    normalized_modes = _normalize_question_modes(question_modes)
    if normalized_modes is None:
        return None

    try:
        from ragas.testset.synthesizers.multi_hop import (
            MultiHopAbstractQuerySynthesizer,
            MultiHopSpecificQuerySynthesizer,
        )
        from ragas.testset.synthesizers.single_hop.specific import (
            SingleHopSpecificQuerySynthesizer,
        )
    except ImportError as exc:  # pragma: no cover - runtime dependency error path
        raise RuntimeError("openai or ragas is not installed") from exc

    synthesizers: list[Any] = []
    for mode in normalized_modes:
        if mode == "single-hop-specific":
            synthesizers.append(SingleHopSpecificQuerySynthesizer(llm=llm))
        elif mode == "multi-hop-abstract":
            synthesizers.append(MultiHopAbstractQuerySynthesizer(llm=llm))
        elif mode == "multi-hop-specific":
            synthesizers.append(MultiHopSpecificQuerySynthesizer(llm=llm))
        elif mode == "single-hop":
            synthesizers.append(SingleHopSpecificQuerySynthesizer(llm=llm))
        elif mode == "multi-hop":
            synthesizers.extend(
                [
                    MultiHopAbstractQuerySynthesizer(llm=llm),
                    MultiHopSpecificQuerySynthesizer(llm=llm),
                ]
            )
        else:
            raise ValueError(
                "Unsupported ragas question mode: "
                f"{mode}. Expected default, single-hop, multi-hop, "
                "single-hop-specific, multi-hop-abstract, or multi-hop-specific."
            )

    if not synthesizers:
        return None

    probability = 1 / len(synthesizers)
    return [(synthesizer, probability) for synthesizer in synthesizers]


def generate_ragas_questions(plan: RagasQuestionGenerationPlan) -> dict[str, Any]:
    runtime_env = {}
    if plan.provider is not None:
        runtime_env[f"{plan.prefix}_PROVIDER"] = plan.provider
    if plan.model is not None:
        runtime_env[f"{plan.prefix}_MODEL"] = plan.model
    if plan.base_url is not None:
        runtime_env[f"{plan.prefix}_BASE_URL"] = plan.base_url
    if plan.api_key is not None:
        runtime_env[f"{plan.prefix}_API_KEY"] = plan.api_key

    runtime = load_llm_runtime_config(runtime_env or None, prefix=plan.prefix)
    documents = load_documents(plan.source)
    if not documents:
        raise ValueError(f"No TXT documents found under {plan.source}")

    langchain_docs = _to_langchain_documents(documents)
    llm = build_ragas_llm(runtime)
    embeddings = build_ragas_embeddings(runtime)

    try:
        from ragas.testset import TestsetGenerator
    except ImportError as exc:  # pragma: no cover - runtime dependency error path
        raise RuntimeError("openai or ragas is not installed") from exc

    generator = TestsetGenerator(llm=llm, embedding_model=embeddings)
    query_distribution = _build_query_distribution(llm, plan.question_modes)
    if query_distribution is None:
        dataset = generator.generate_with_langchain_docs(langchain_docs, testset_size=plan.testset_size)
    else:
        dataset = generator.generate_with_langchain_docs(
            langchain_docs,
            testset_size=plan.testset_size,
            query_distribution=query_distribution,
        )
    questions = _dataset_to_records(dataset)

    payload = {
        "metadata": {
            "generator": "ragas",
            "source": str(plan.source),
            "output": str(plan.output),
            "testset_size": plan.testset_size,
            "question_modes": list(plan.question_modes) if plan.question_modes else None,
            **plan.metadata,
        },
        "questions": questions,
    }
    plan.output.parent.mkdir(parents=True, exist_ok=True)
    plan.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
