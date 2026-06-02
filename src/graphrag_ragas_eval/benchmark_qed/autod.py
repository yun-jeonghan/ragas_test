from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..documents import load_documents, summarize_documents
from ..upstream_benchmark_qed import (
    build_vendor_model_factory_runtime,
    ensure_vendor_path,
    model_dump_json_safe,
    write_documents_csv,
)


@dataclass(frozen=True, slots=True)
class AutoDPlan:
    source: Path
    output: Path
    target_size: int = 10
    metadata: dict[str, Any] = field(default_factory=dict)


def summarize_dataset(plan: AutoDPlan) -> dict[str, Any]:
    ensure_vendor_path()
    documents = load_documents(plan.source)
    docs_payload = summarize_documents(documents[: plan.target_size])

    from ..llm import load_llm_runtime_config

    runtime = load_llm_runtime_config(dict(os.environ), prefix="GREV_BENCHMARKQED")
    chat_model, embedding_model = build_vendor_model_factory_runtime(runtime)

    source_rows = [
        {"id": document.id, "title": document.title, "text": document.text}
        for document in documents[: plan.target_size]
    ]
    workdir = plan.output.parent / f".{plan.output.stem}.benchmark-qed"
    workdir.mkdir(parents=True, exist_ok=True)
    input_csv = write_documents_csv(source_rows, workdir / "input.csv")

    from benchmark_qed.autod.data_processor.embedding import TextEmbedder
    from benchmark_qed.autod.sampler.sample_gen import acreate_clustered_sample
    from benchmark_qed.autod.summarization.global_summarizer import GlobalSummarizer
    import tiktoken

    text_embedder = TextEmbedder(embedding_model)
    clustered_sample = asyncio.run(
        acreate_clustered_sample(
            input_path=str(input_csv),
            output_path=str(workdir / "sample"),
            text_embedder=text_embedder,
            num_clusters=max(1, min(plan.target_size, len(source_rows) or 1)),
            num_samples_per_cluster=1,
            input_type="csv",
            text_tag="text",
            metadata_tags=None,
            chunk_size=600,
            chunk_overlap=100,
            file_encoding="utf-8",
            token_encoding="o200k_base",
            random_seed=42,
            input_storage=None,
            output_storage=None,
        )
    )

    token_encoder = tiktoken.get_encoding("o200k_base")
    summarizer = GlobalSummarizer(llm=chat_model, token_encoder=token_encoder)
    summary_result = asyncio.run(summarizer.asummarize(clustered_sample.sample_texts))

    payload = {
        "metadata": {
            "component": "AutoD",
            "target_size": plan.target_size,
            "backend": "benchmark-qed",
            **plan.metadata,
        },
        **docs_payload,
        "benchmark_qed": {
            "summary": summary_result.summary,
            "input_tokens": summary_result.input_tokens,
            "output_tokens": summary_result.output_tokens,
            "llm_calls": summary_result.llm_calls,
            "sample_texts": [model_dump_json_safe(text_unit) for text_unit in clustered_sample.sample_texts],
        },
    }
    plan.output.parent.mkdir(parents=True, exist_ok=True)
    plan.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload
