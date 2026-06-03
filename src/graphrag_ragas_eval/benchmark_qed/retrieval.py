from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class RetrievalPrepPlan:
    search_results: Path
    output: Path
    context_id_key: str = "chunk_id"
    context_text_key: str = "text"
    metadata: dict[str, Any] = field(default_factory=dict)


def _coerce_items(payload: object, *, key: str) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        items = payload.get(key, [])
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    return []


def prepare_retrieval_results(plan: RetrievalPrepPlan) -> dict[str, Any]:
    payload = json.loads(plan.search_results.read_text(encoding="utf-8"))
    items = _coerce_items(payload, key="results")

    prepared: list[dict[str, Any]] = []
    for item in items:
        contexts = item.get("retrieved_contexts", [])
        context_rows = []
        if isinstance(contexts, list):
            for index, ctx in enumerate(contexts):
                if not isinstance(ctx, dict):
                    continue
                context_rows.append(
                    {
                        plan.context_id_key: str(ctx.get("source") or ctx.get("id") or f"context-{index}"),
                        plan.context_text_key: str(ctx.get("text") or ""),
                        "score": ctx.get("score"),
                        "metadata": ctx.get("metadata", {}),
                    }
                )

        prepared.append(
            {
                "question_id": str(item.get("sample_id") or item.get("question_id") or item.get("question") or ""),
                "question_text": str(item.get("question") or item.get("question_text") or ""),
                "context": context_rows,
                "metadata": {
                    "search_mode": item.get("search_mode"),
                    "backend": "benchmark-qed",
                    **_metadata_from_item(item),
                    **plan.metadata,
                },
            }
        )

    result = {
        "metadata": {
            "component": "RetrievalPrep",
            "backend": "benchmark-qed",
            "source": str(plan.search_results),
            "context_id_key": plan.context_id_key,
            "context_text_key": plan.context_text_key,
            **plan.metadata,
        },
        "results": prepared,
    }
    plan.output.parent.mkdir(parents=True, exist_ok=True)
    plan.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def _metadata_from_item(item: dict[str, Any]) -> dict[str, Any]:
    metadata = item.get("metadata", {})
    return metadata if isinstance(metadata, dict) else {}
