from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from ..documents import load_documents
from ..schemas import BenchmarkSample, SearchMode


class GenerationMode(str, Enum):
    LOCAL = "local"
    GLOBAL = "global"
    MULTI_HOP = "multi-hop"
    UNANSWERABLE = "unanswerable"


@dataclass(frozen=True, slots=True)
class QuestionGenerationPlan:
    source: Path
    output: Path
    num_questions: int = 10
    modes: tuple[GenerationMode, ...] = (GenerationMode.LOCAL, GenerationMode.GLOBAL)
    subrepo_name: str = "benchmark"
    metadata: dict[str, Any] = field(default_factory=dict)


def _load_documents(source: Path) -> list[dict[str, str]]:
    loaded = load_documents(source)
    return [
        {
            "id": document.id,
            "title": document.title,
            "text": document.text,
        }
        for document in loaded
    ]


def _first_sentence(text: str) -> str:
    parts = re.split(r"[.!?]\s+", text.strip(), maxsplit=1)
    return parts[0].strip() if parts else ""


def _local_sample(document: dict[str, str], index: int) -> BenchmarkSample:
    text = document.get("text", "").strip()
    title = document.get("title", "the topic")
    answer = _first_sentence(text) or "This document does not have a clear first sentence."
    return BenchmarkSample(
        sample_id=f"local-{index}",
        question=f"What does the document say about {title}?",
        query_type="local",
        search_mode=SearchMode.LOCAL,
        reference_answer=answer,
        reference_contexts=(text,) if text else (),
        source_doc_ids=(document.get("id", f"doc-{index}"),),
        difficulty="easy",
        metadata={"generator": "fallback", "mode": "local"},
    )


def _global_sample(documents: list[dict[str, str]]) -> BenchmarkSample | None:
    if not documents:
        return None
    context_texts = [doc.get("text", "") for doc in documents[:3] if doc.get("text")]
    source_doc_ids = [doc.get("id", "") for doc in documents[:3] if doc.get("id")]
    return BenchmarkSample(
        sample_id="global-1",
        question="What are the main themes across the documents?",
        query_type="global",
        search_mode=SearchMode.GLOBAL,
        reference_answer="The documents describe the main themes covered across the corpus.",
        reference_contexts=tuple(context_texts),
        source_doc_ids=tuple(source_doc_ids),
        difficulty="medium",
        metadata={"generator": "fallback", "mode": "global"},
    )


def _multi_hop_sample(documents: list[dict[str, str]]) -> BenchmarkSample | None:
    if len(documents) < 2:
        return None
    left, right = documents[0], documents[1]
    return BenchmarkSample(
        sample_id="multi-hop-1",
        question=f"How are {left.get('title', 'document A')} and {right.get('title', 'document B')} connected?",
        query_type="multi-hop",
        search_mode=SearchMode.GLOBAL,
        reference_answer="They are connected through information that appears in multiple documents.",
        reference_contexts=(left.get("text", ""), right.get("text", "")),
        source_doc_ids=(left.get("id", ""), right.get("id", "")),
        difficulty="hard",
        metadata={"generator": "fallback", "mode": "multi-hop"},
    )


def _unanswerable_sample(documents: list[dict[str, str]]) -> BenchmarkSample | None:
    if not documents:
        return None
    doc = documents[0]
    return BenchmarkSample(
        sample_id="unanswerable-1",
        question=f"What is the exact unpublished metadata of {doc.get('title', 'this document')}?",
        query_type="unanswerable",
        search_mode=SearchMode.LOCAL,
        reference_answer="The documents do not provide enough information to answer this exactly.",
        reference_contexts=(doc.get("text", ""),),
        source_doc_ids=(doc.get("id", ""),),
        difficulty="hard",
        metadata={"generator": "fallback", "mode": "unanswerable"},
    )


def _serialize(sample: BenchmarkSample) -> dict[str, Any]:
    return {
        "sample_id": sample.sample_id,
        "question": sample.question,
        "query_type": sample.query_type,
        "search_mode": sample.search_mode.value,
        "reference_answer": sample.reference_answer,
        "reference_contexts": list(sample.reference_contexts),
        "expected_entities": list(sample.expected_entities),
        "expected_relationships": list(sample.expected_relationships),
        "expected_community_ids": list(sample.expected_community_ids),
        "source_doc_ids": list(sample.source_doc_ids),
        "difficulty": sample.difficulty,
        "metadata": sample.metadata,
    }


def generate_questions(plan: QuestionGenerationPlan) -> list[BenchmarkSample]:
    documents = _load_documents(plan.source)
    samples: list[BenchmarkSample] = []

    if GenerationMode.LOCAL in plan.modes:
        for index, document in enumerate(documents[: plan.num_questions], start=1):
            samples.append(_local_sample(document, index))
            if len(samples) >= plan.num_questions:
                break

    if GenerationMode.GLOBAL in plan.modes and len(samples) < plan.num_questions:
        sample = _global_sample(documents)
        if sample is not None:
            samples.append(sample)

    if GenerationMode.MULTI_HOP in plan.modes and len(samples) < plan.num_questions:
        sample = _multi_hop_sample(documents)
        if sample is not None:
            samples.append(sample)

    if GenerationMode.UNANSWERABLE in plan.modes and len(samples) < plan.num_questions:
        sample = _unanswerable_sample(documents)
        if sample is not None:
            samples.append(sample)

    samples = samples[: plan.num_questions]
    plan.output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": {
            "subrepo_name": plan.subrepo_name,
            "num_questions": plan.num_questions,
            "modes": [mode.value for mode in plan.modes],
            **plan.metadata,
        },
        "questions": [_serialize(sample) for sample in samples],
    }
    plan.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return samples
