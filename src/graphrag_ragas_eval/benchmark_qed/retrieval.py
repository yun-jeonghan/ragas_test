from __future__ import annotations

import asyncio
import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from ..llm import load_llm_runtime_config
from ..graphrag.loaders import load_graphrag_tables
from ..schemas import GraphRAGTableSet
from ..reporting import render_retrieval_smoke_report
from ..upstream_benchmark_qed import (
    build_vendor_llm_config,
    build_vendor_model_factory_runtime,
    ensure_autoe_import_shim,
    ensure_vendor_path,
)


@dataclass(frozen=True, slots=True)
class RetrievalPrepPlan:
    search_results: Path
    output: Path
    context_id_key: str = "chunk_id"
    context_text_key: str = "text"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RetrievalReferencePlan:
    questions: Path
    clusters: Path
    output: Path
    text_units: Path | None = None
    max_questions: int | None = None
    assessor_type: str = "rationale"
    semantic_neighbors: int = 10
    centroid_neighbors: int = 5
    concurrent_requests: int = 16
    include_clusters: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RetrievalEvaluationPlan:
    reference_dir: Path
    clusters: Path
    retrieval_results: Path
    output: Path
    text_units: Path | None = None
    question_sets: tuple[str, ...] = ("default",)
    rag_method_name: str = "benchmark-qed"
    reference_filename: str = "reference.json"
    relevance_threshold: int = 2
    context_id_key: str = "chunk_id"
    context_text_key: str = "text"
    cluster_match_by: str = "text"
    run_significance_test: bool = True
    significance_alpha: float = 0.05
    significance_correction: str = "holm"
    fidelity_metric: str = "js"
    assessor_type: str = "rationale"
    concurrent_requests: int = 16
    max_concurrent: int = 8
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RetrievalSmokePlan:
    benchmark: Path
    search_results: Path
    graphrag_root: Path
    output_dir: Path = Path("/tmp/grev-benchmark-qed-retrieval-smoke")
    report_output: Path | None = None
    question_sets: tuple[str, ...] = ("default",)
    rag_method_name: str = "benchmark-qed"
    reference_filename: str = "reference.json"
    relevance_threshold: int = 2
    cluster_match_by: str = "text"
    run_significance_test: bool = True
    significance_alpha: float = 0.05
    significance_correction: str = "holm"
    fidelity_metric: str = "js"
    assessor_type: str = "rationale"
    semantic_neighbors: int = 10
    centroid_neighbors: int = 5
    concurrent_requests: int = 16
    max_concurrent: int = 8
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RetrievalSmokeResult:
    clusters: Path
    retrieval_reference: Path
    retrieval_results: Path
    retrieval_evaluation: Path
    report: Path


def _coerce_items(payload: object, *, key: str) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        items = payload.get(key, [])
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    return []


def _read_json_payload(path: Path) -> object:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_retrieval_results_payload(
    payload: object,
    *,
    context_id_key: str,
    context_text_key: str,
) -> list[dict[str, Any]]:
    def _normalize_context(context: dict[str, Any]) -> dict[str, str]:
        return {
            context_id_key: str(
                context.get(context_id_key)
                or context.get("source_id")
                or context.get("chunk_id")
                or context.get("source")
                or context.get("id")
                or ""
            ),
            context_text_key: str(
                context.get(context_text_key)
                or context.get("source_text")
                or context.get("text")
                or ""
            ),
        }

    def _normalize_item(item: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(item)
        if "text" not in normalized and "question_text" in normalized:
            normalized["text"] = normalized.get("question_text") or ""
        if "question_text" not in normalized and "text" in normalized:
            normalized["question_text"] = normalized.get("text") or ""
        contexts = normalized.get("context", [])
        if isinstance(contexts, list):
            normalized["context"] = [
                _normalize_context(context)
                for context in contexts
                if isinstance(context, dict)
            ]
        return normalized

    if isinstance(payload, list):
        return [_normalize_item(item) for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        results = payload.get("results", [])
        if isinstance(results, list):
            return [_normalize_item(item) for item in results if isinstance(item, dict)]
    return []


def _load_questions(path: Path, *, max_questions: int | None = None) -> list[Any]:
    ensure_vendor_path()
    from benchmark_qed.autoq.data_model.question import Question

    payload = _read_json_payload(path)
    items = _coerce_items(payload, key="questions")
    questions: list[Question] = []
    for index, item in enumerate(items):
        question_id = str(
            item.get("question_id")
            or item.get("sample_id")
            or item.get("id")
            or f"question-{index}"
        )
        question_text = str(
            item.get("question") or item.get("question_text") or item.get("text") or ""
        )
        if not question_text:
            continue
        questions.append(Question(id=question_id, text=question_text))
        if max_questions is not None and len(questions) >= max_questions:
            break
    return questions


def _load_dataframe(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pd.read_parquet(path)
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in (".json", ".jsonl"):
        return pd.read_json(path, lines=(suffix == ".jsonl"))
    msg = f"Unsupported text units format: {suffix}"
    raise ValueError(msg)


def _load_clusters_with_embeddings(
    clusters_path: Path,
    text_units_path: Path | None = None,
) -> list[Any]:
    ensure_vendor_path()
    from benchmark_qed.autod.data_model.text_unit import TextUnit
    from benchmark_qed.autod.io.text_unit import load_text_units
    from benchmark_qed.autod.sampler.clustering.cluster import TextCluster

    payload = _read_json_payload(clusters_path)
    if not isinstance(payload, list):
        msg = "Clusters JSON must contain a list of clusters"
        raise ValueError(msg)

    text_unit_map: dict[str, TextUnit] = {}
    if text_units_path is not None:
        text_df = _load_dataframe(text_units_path)
        text_units = load_text_units(text_df)
        text_unit_map = {text_unit.id: text_unit for text_unit in text_units}

    clusters: list[TextCluster] = []
    for index, cluster_data in enumerate(payload):
        cluster_id = str(cluster_data.get("cluster_id") or cluster_data.get("id") or index)
        text_units_data = cluster_data.get("text_units", [])
        text_units: list[TextUnit] = []

        if isinstance(text_units_data, list) and text_units_data:
            for unit_data in text_units_data:
                if not isinstance(unit_data, dict):
                    continue
                text_units.append(
                    TextUnit(
                        id=str(unit_data.get("id", "")),
                        short_id=str(unit_data.get("short_id", unit_data.get("id", ""))),
                        text=str(unit_data.get("text", "")),
                        document_id=unit_data.get("document_id"),
                        n_tokens=unit_data.get("n_tokens"),
                        text_embedding=unit_data.get("text_embedding"),
                        cluster_id=unit_data.get("cluster_id", cluster_id),
                        attributes=unit_data.get("attributes"),
                    )
                )
        else:
            text_unit_ids = cluster_data.get("text_unit_ids", [])
            if not isinstance(text_unit_ids, list):
                text_unit_ids = []
            if text_unit_ids and text_units_path is None:
                msg = (
                    "clusters JSON uses text_unit_ids, but no text_units_path was provided"
                )
                raise ValueError(msg)
            for unit_id in text_unit_ids:
                unit = text_unit_map.get(str(unit_id))
                if unit is None:
                    text_units.append(
                        TextUnit(
                            id=str(unit_id),
                            short_id=str(unit_id),
                            text="",
                            cluster_id=cluster_id,
                        )
                    )
                else:
                    text_units.append(
                        TextUnit(
                            id=unit.id,
                            short_id=unit.short_id,
                            text=unit.text,
                            document_id=unit.document_id,
                            n_tokens=unit.n_tokens,
                            text_embedding=unit.text_embedding,
                            cluster_id=cluster_id,
                            attributes=unit.attributes,
                        )
                    )

        clusters.append(TextCluster(id=cluster_id, text_units=text_units))

    return clusters


async def _ensure_embeddings_on_clusters(
    clusters: list[Any],
    embedder: Any,
) -> list[Any]:
    missing_units = [
        text_unit
        for cluster in clusters
        for text_unit in getattr(cluster, "text_units", [])
        if getattr(text_unit, "text_embedding", None) is None and getattr(text_unit, "text", "")
    ]
    if not missing_units:
        return clusters

    embedded_units = await embedder.embed_batch(text_units=missing_units, batch_size=32)
    embedded_by_id = {text_unit.id: text_unit for text_unit in embedded_units}
    for cluster in clusters:
        for text_unit in getattr(cluster, "text_units", []):
            if text_unit.id in embedded_by_id:
                text_unit.text_embedding = embedded_by_id[text_unit.id].text_embedding
    return clusters


def _build_relevance_rater(
    runtime: Any,
    *,
    assessor_type: str,
    concurrent_requests: int,
    cache_dir: Path | None = None,
) -> tuple[Any, Any]:
    ensure_vendor_path()
    ensure_autoe_import_shim()
    from benchmark_qed.autoe.retrieval_metrics.relevance_assessment.bing_rater import (
        BingRelevanceRater,
    )
    from benchmark_qed.autoe.retrieval_metrics.relevance_assessment.rationale_rater import (
        RationaleRelevanceRater,
    )
    from benchmark_qed.autod.data_processor.embedding import TextEmbedder

    chat_model, embedding_model = build_vendor_model_factory_runtime(runtime)
    llm_config = build_vendor_llm_config(runtime, embeddings=False)
    if assessor_type == "bing":
        relevance_rater = BingRelevanceRater(
            llm_client=chat_model,
            llm_config=llm_config,
            cache_dir=cache_dir,
            cache_enabled=cache_dir is not None,
            concurrent_requests=concurrent_requests,
        )
    elif assessor_type == "rationale":
        relevance_rater = RationaleRelevanceRater(
            llm_client=chat_model,
            llm_config=llm_config,
            cache_dir=cache_dir,
            cache_enabled=cache_dir is not None,
            concurrent_requests=concurrent_requests,
        )
    else:
        msg = f"Unsupported retrieval assessor type: {assessor_type}"
        raise ValueError(msg)

    return relevance_rater, TextEmbedder(embedding_model)


def _coerce_fidelity_metric(metric: str) -> Any:
    ensure_vendor_path()
    from benchmark_qed.autoe.retrieval_metrics.scoring.fidelity import FidelityMetric

    normalized = metric.strip().lower()
    if normalized in {"js", "jensen-shannon", "jensen_shannon"}:
        return FidelityMetric.JENSEN_SHANNON
    if normalized in {"tvd", "total-variation", "total_variation"}:
        return FidelityMetric.TOTAL_VARIATION
    msg = f"Unsupported fidelity metric: {metric}"
    raise ValueError(msg)


def _coerce_cluster_ids(value: Any) -> list[str]:
    if value is None:
        return []
    if hasattr(value, "tolist") and not isinstance(value, list):
        value = value.tolist()
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if item not in (None, "")]
    return [str(value)]


def _clusters_from_communities(communities: pd.DataFrame) -> list[dict[str, Any]]:
    clusters: list[dict[str, Any]] = []
    for index, community in enumerate(communities.to_dict(orient="records")):
        text_unit_ids = _coerce_cluster_ids(community.get("text_unit_ids"))
        if not text_unit_ids:
            msg = f"Community row at index {index} does not contain text_unit_ids"
            raise ValueError(msg)
        cluster_id = str(
            community.get("id")
            or community.get("human_readable_id")
            or community.get("community")
            or index
        )
        clusters.append(
            {
                "cluster_id": cluster_id,
                "text_unit_ids": text_unit_ids,
                "metadata": {
                    "community": community.get("community"),
                    "human_readable_id": community.get("human_readable_id"),
                    "level": community.get("level"),
                    "parent": community.get("parent"),
                    "title": community.get("title"),
                    "period": community.get("period"),
                    "size": community.get("size"),
                },
            }
        )
    return clusters


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
                        plan.context_id_key: str(
                            ctx.get("source") or ctx.get("id") or f"context-{index}"
                        ),
                        plan.context_text_key: str(ctx.get("text") or ""),
                        "score": ctx.get("score"),
                        "metadata": ctx.get("metadata", {}),
                    }
                )

        prepared.append(
            {
                "question_id": str(
                    item.get("sample_id") or item.get("question_id") or item.get("question") or ""
                ),
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


def generate_retrieval_reference(plan: RetrievalReferencePlan) -> dict[str, Any]:
    ensure_vendor_path()
    ensure_autoe_import_shim()
    from benchmark_qed.autoe.retrieval_metrics.reference_gen.cluster_relevance import (
        ClusterRelevanceRater,
        build_cluster_references_payload,
    )

    runtime = load_llm_runtime_config(dict(os.environ), prefix="GREV_BENCHMARKQED")
    relevance_rater, embedder = _build_relevance_rater(
        runtime,
        assessor_type=plan.assessor_type,
        concurrent_requests=plan.concurrent_requests,
    )

    clusters = _load_clusters_with_embeddings(plan.clusters, plan.text_units)
    questions = _load_questions(plan.questions, max_questions=plan.max_questions)
    clusters = asyncio.run(_ensure_embeddings_on_clusters(clusters, embedder))

    cluster_rater = ClusterRelevanceRater(
        text_embedder=embedder,
        relevance_rater=relevance_rater,
        corpus=clusters,
        semantic_neighbors=plan.semantic_neighbors,
        centroid_neighbors=plan.centroid_neighbors,
        max_concurrent_clusters=plan.concurrent_requests,
    )
    reference_results = asyncio.run(cluster_rater.assess_batch(questions))

    payload = build_cluster_references_payload(
        reference_results,
        include_clusters=plan.include_clusters,
        clusters=cluster_rater.clusters if plan.include_clusters else None,
    )
    payload["metadata"] = {
        "component": "RetrievalReference",
        "backend": "benchmark-qed",
        "assessor_type": plan.assessor_type,
        "questions": str(plan.questions),
        "clusters": str(plan.clusters),
        "text_units": str(plan.text_units) if plan.text_units is not None else None,
        "question_count": len(questions),
        "cluster_count": len(cluster_rater.clusters),
        "semantic_neighbors": plan.semantic_neighbors,
        "centroid_neighbors": plan.centroid_neighbors,
        "include_clusters": plan.include_clusters,
        **plan.metadata,
    }
    plan.output.parent.mkdir(parents=True, exist_ok=True)
    plan.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def evaluate_retrieval_results(plan: RetrievalEvaluationPlan) -> dict[str, Any]:
    ensure_vendor_path()
    ensure_autoe_import_shim()
    from benchmark_qed.autoe.retrieval import run_retrieval_evaluation

    runtime = load_llm_runtime_config(dict(os.environ), prefix="GREV_BENCHMARKQED")
    relevance_rater, _ = _build_relevance_rater(
        runtime,
        assessor_type=plan.assessor_type,
        concurrent_requests=plan.concurrent_requests,
    )
    clusters = _load_clusters_with_embeddings(plan.clusters, plan.text_units)

    workdir = plan.output.parent / f".{plan.output.stem}.benchmark-qed"
    workdir.mkdir(parents=True, exist_ok=True)
    retrieval_payload = _read_json_payload(plan.retrieval_results)
    retrieval_rows = _normalize_retrieval_results_payload(
        retrieval_payload,
        context_id_key=plan.context_id_key,
        context_text_key=plan.context_text_key,
    )
    normalized_retrieval_results = workdir / "retrieval-results.normalized.json"
    normalized_retrieval_results.write_text(
        json.dumps(retrieval_rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    overall_df = asyncio.run(
        run_retrieval_evaluation(
            relevance_rater=relevance_rater,
            rag_methods=[
                {
                    "name": plan.rag_method_name,
                    "retrieval_results_path": normalized_retrieval_results,
                }
            ],
            question_sets=list(plan.question_sets),
            reference_dir=plan.reference_dir,
            clusters=clusters,
            output_dir=workdir,
            relevance_threshold=plan.relevance_threshold,
            context_id_key=plan.context_id_key,
            context_text_key=plan.context_text_key,
            run_significance_test=plan.run_significance_test,
            significance_alpha=plan.significance_alpha,
            significance_correction=plan.significance_correction,
            fidelity_metric=_coerce_fidelity_metric(plan.fidelity_metric),
            max_concurrent=plan.max_concurrent,
            reference_filename=plan.reference_filename,
            cluster_match_by=plan.cluster_match_by,
        )
    )

    summary_rows = overall_df.to_dict(orient="records") if not overall_df.empty else []
    payload = {
        "metadata": {
            "component": "RetrievalEvaluation",
            "backend": "benchmark-qed",
            "reference_dir": str(plan.reference_dir),
            "clusters": str(plan.clusters),
            "text_units": str(plan.text_units) if plan.text_units is not None else None,
            "retrieval_results": str(plan.retrieval_results),
            "question_sets": list(plan.question_sets),
            "rag_method_name": plan.rag_method_name,
            "relevance_threshold": plan.relevance_threshold,
            "context_id_key": plan.context_id_key,
            "context_text_key": plan.context_text_key,
            "cluster_match_by": plan.cluster_match_by,
            "run_significance_test": plan.run_significance_test,
            "significance_alpha": plan.significance_alpha,
            "significance_correction": plan.significance_correction,
            "fidelity_metric": plan.fidelity_metric,
            **plan.metadata,
        },
        "summary": summary_rows,
        "columns": list(overall_df.columns),
        "rows": len(summary_rows),
        "output_dir": str(workdir),
    }
    plan.output.parent.mkdir(parents=True, exist_ok=True)
    plan.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def run_benchmark_qed_retrieval_smoke(plan: RetrievalSmokePlan) -> RetrievalSmokeResult:
    if plan.output_dir.exists():
        shutil.rmtree(plan.output_dir)
    plan.output_dir.mkdir(parents=True, exist_ok=True)
    report_output = plan.report_output or (plan.output_dir / "retrieval-smoke.html")

    runtime = load_llm_runtime_config(dict(os.environ), prefix="GREV_BENCHMARKQED")
    tables = load_graphrag_tables(GraphRAGTableSet(root=plan.graphrag_root))
    clusters_path = plan.output_dir / "clusters.json"
    clusters_payload = _clusters_from_communities(tables.communities)
    clusters_path.write_text(
        json.dumps(clusters_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    reference_dir = plan.output_dir / "retrieval-reference"
    reference_path = reference_dir / plan.reference_filename
    generate_retrieval_reference(
        RetrievalReferencePlan(
            questions=plan.benchmark,
            clusters=clusters_path,
            text_units=plan.graphrag_root / "text_units.parquet",
            output=reference_path,
            assessor_type=plan.assessor_type,
            semantic_neighbors=plan.semantic_neighbors,
            centroid_neighbors=plan.centroid_neighbors,
            concurrent_requests=plan.concurrent_requests,
            metadata={"smoke": True, **plan.metadata},
        )
    )

    retrieval_results = plan.output_dir / "retrieval-results.json"
    prepare_retrieval_results(
        RetrievalPrepPlan(
            search_results=plan.search_results,
            output=retrieval_results,
            metadata={"smoke": True, **plan.metadata},
        )
    )

    evaluation_path = plan.output_dir / "retrieval-evaluation.json"
    evaluate_retrieval_results(
        RetrievalEvaluationPlan(
            reference_dir=reference_dir,
            clusters=clusters_path,
            text_units=plan.graphrag_root / "text_units.parquet",
            retrieval_results=retrieval_results,
            output=evaluation_path,
            question_sets=plan.question_sets,
            rag_method_name=plan.rag_method_name,
            reference_filename=plan.reference_filename,
            relevance_threshold=plan.relevance_threshold,
            cluster_match_by=plan.cluster_match_by,
            run_significance_test=plan.run_significance_test,
            significance_alpha=plan.significance_alpha,
            significance_correction=plan.significance_correction,
            fidelity_metric=plan.fidelity_metric,
            assessor_type=plan.assessor_type,
            concurrent_requests=plan.concurrent_requests,
            max_concurrent=plan.max_concurrent,
            metadata={"smoke": True, **plan.metadata},
        )
    )

    render_retrieval_smoke_report(
        retrieval_reference=reference_path,
        retrieval_results=retrieval_results,
        retrieval_evaluation=evaluation_path,
        output=report_output,
        title="BenchmarkQED Retrieval Smoke Report",
        report_metadata={
            "chat_model": runtime.model,
            "provider": runtime.provider,
            "base_url": runtime.base_url,
            "embeddings_model": runtime.embeddings_model,
        },
    )

    return RetrievalSmokeResult(
        clusters=clusters_path,
        retrieval_reference=reference_path,
        retrieval_results=retrieval_results,
        retrieval_evaluation=evaluation_path,
        report=report_output,
    )


def _metadata_from_item(item: dict[str, Any]) -> dict[str, Any]:
    metadata = item.get("metadata", {})
    return metadata if isinstance(metadata, dict) else {}
