from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..documents import load_documents, summarize_documents


@dataclass(frozen=True, slots=True)
class AutoDPlan:
    source: Path
    output: Path
    target_size: int = 10
    metadata: dict[str, Any] = field(default_factory=dict)


def summarize_dataset(plan: AutoDPlan) -> dict[str, Any]:
    documents = load_documents(plan.source)
    docs_payload = summarize_documents(documents[: plan.target_size])
    payload = {
        "metadata": {
            "component": "AutoD",
            "target_size": plan.target_size,
            **plan.metadata,
        },
        **docs_payload,
    }
    plan.output.parent.mkdir(parents=True, exist_ok=True)
    plan.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload

