from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Protocol

from ..schemas import GraphRAGSearchResult, RetrievedContext, SearchMode


class SearchBackend(Protocol):
    def search(self, question: str, *, mode: SearchMode, **kwargs: Any) -> GraphRAGSearchResult: ...


class GraphRAGSearcher(ABC):
    @abstractmethod
    def search(self, question: str, *, sample_id: str, **kwargs: Any) -> GraphRAGSearchResult:
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class LocalGraphRAGSearcher(GraphRAGSearcher):
    backend: Any

    def search(self, question: str, *, sample_id: str, **kwargs: Any) -> GraphRAGSearchResult:
        return self.backend.search(question, sample_id=sample_id, mode=SearchMode.LOCAL, **kwargs)


@dataclass(frozen=True, slots=True)
class GlobalGraphRAGSearcher(GraphRAGSearcher):
    backend: Any

    def search(self, question: str, *, sample_id: str, **kwargs: Any) -> GraphRAGSearchResult:
        return self.backend.search(question, sample_id=sample_id, mode=SearchMode.GLOBAL, **kwargs)


@dataclass(frozen=True, slots=True)
class InMemorySearchBackend:
    contexts: tuple[RetrievedContext, ...] = ()

    def search(self, question: str, *, mode: SearchMode, sample_id: str, **kwargs: Any) -> GraphRAGSearchResult:
        answer = kwargs.get("answer") or f"Stub answer for {mode.value}: {question}"
        return GraphRAGSearchResult(
            sample_id=sample_id,
            question=question,
            search_mode=mode,
            answer=answer,
            retrieved_contexts=self.contexts,
            metadata={"backend": "in_memory"},
        )

