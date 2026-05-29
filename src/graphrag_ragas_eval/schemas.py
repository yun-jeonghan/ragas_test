from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class SearchMode(str, Enum):
    LOCAL = "local"
    GLOBAL = "global"


@dataclass(frozen=True, slots=True)
class GraphRAGTableSet:
    root: Path
    entities: Path | None = None
    relationships: Path | None = None
    communities: Path | None = None
    community_reports: Path | None = None
    text_units: Path | None = None
    covariates: Path | None = None


@dataclass(frozen=True, slots=True)
class BenchmarkSample:
    sample_id: str
    question: str
    query_type: str
    search_mode: SearchMode
    reference_answer: str
    reference_contexts: tuple[str, ...] = field(default_factory=tuple)
    expected_entities: tuple[str, ...] = field(default_factory=tuple)
    expected_relationships: tuple[str, ...] = field(default_factory=tuple)
    expected_community_ids: tuple[str, ...] = field(default_factory=tuple)
    source_doc_ids: tuple[str, ...] = field(default_factory=tuple)
    difficulty: str = "medium"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RetrievedContext:
    text: str
    source: str | None = None
    score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GraphRAGSearchResult:
    sample_id: str
    question: str
    search_mode: SearchMode
    answer: str
    retrieved_contexts: tuple[RetrievedContext, ...]
    citations: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EvaluationScore:
    sample_id: str
    metric_name: str
    value: float
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

