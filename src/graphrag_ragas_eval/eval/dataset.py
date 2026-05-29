from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from ..schemas import BenchmarkSample, SearchMode


def _as_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value)


def load_benchmark_samples(path: Path) -> list[BenchmarkSample]:
    if not path.exists():
        raise FileNotFoundError(path)

    samples: list[BenchmarkSample] = []
    if path.suffix.lower() == ".jsonl":
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            samples.append(_sample_from_dict(json.loads(line)))
        return samples

    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload if isinstance(payload, list) else payload.get("samples", [])
        return [_sample_from_dict(row) for row in rows]

    raise ValueError(f"Unsupported benchmark format: {path.suffix}")


def _sample_from_dict(row: dict[str, Any]) -> BenchmarkSample:
    return BenchmarkSample(
        sample_id=str(row["sample_id"]),
        question=str(row["question"]),
        query_type=str(row.get("query_type", "unknown")),
        search_mode=SearchMode(str(row.get("search_mode", "local"))),
        reference_answer=str(row.get("reference_answer", "")),
        reference_contexts=_as_tuple(row.get("reference_contexts")),
        expected_entities=_as_tuple(row.get("expected_entities")),
        expected_relationships=_as_tuple(row.get("expected_relationships")),
        expected_community_ids=_as_tuple(row.get("expected_community_ids")),
        source_doc_ids=_as_tuple(row.get("source_doc_ids")),
        difficulty=str(row.get("difficulty", "medium")),
        metadata=dict(row.get("metadata", {})),
    )


def to_ragas_rows(samples: Iterable[BenchmarkSample]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sample in samples:
        rows.append(
            {
                "user_input": sample.question,
                "reference": sample.reference_answer,
                "reference_contexts": list(sample.reference_contexts),
                "metadata": {
                    "sample_id": sample.sample_id,
                    "query_type": sample.query_type,
                    "search_mode": sample.search_mode.value,
                    "difficulty": sample.difficulty,
                    **sample.metadata,
                },
            }
        )
    return rows

