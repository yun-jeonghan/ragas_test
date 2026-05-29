from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..schemas import GraphRAGSearchResult, RetrievedContext, SearchMode


def load_search_results(path: Path) -> list[GraphRAGSearchResult]:
    if not path.exists():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload if isinstance(payload, list) else payload.get("results", [])
    results: list[GraphRAGSearchResult] = []
    for row in rows:
        contexts = tuple(
            RetrievedContext(
                text=str(context.get("text", "")),
                source=context.get("source"),
                score=context.get("score"),
                metadata=dict(context.get("metadata", {})),
            )
            for context in row.get("retrieved_contexts", [])
        )
        results.append(
            GraphRAGSearchResult(
                sample_id=str(row["sample_id"]),
                question=str(row["question"]),
                search_mode=SearchMode(str(row.get("search_mode", "local"))),
                answer=str(row.get("answer", "")),
                retrieved_contexts=contexts,
                citations=tuple(str(item) for item in row.get("citations", [])),
                metadata=dict(row.get("metadata", {})),
            )
        )
    return results

