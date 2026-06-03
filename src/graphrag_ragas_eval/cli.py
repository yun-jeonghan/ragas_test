from __future__ import annotations

import os
from pathlib import Path

import typer

from .benchmark_qed.autod import AutoDPlan, summarize_dataset
from .benchmark_qed.autoe import AutoEPlan, evaluate_answers
from .benchmark_qed.autoq import AutoQPlan, generate_queries
from .benchmark_qed.retrieval import (
    RetrievalEvaluationPlan,
    RetrievalReferencePlan,
    RetrievalSmokePlan,
    evaluate_retrieval_results,
    generate_retrieval_reference,
    run_benchmark_qed_retrieval_smoke,
)
from .benchmark_qed.smoke import BenchmarkQEDSmokePlan, run_benchmark_qed_smoke
from .config import DEFAULT_CHAT_MODEL, DEFAULT_EMBEDDING_MODEL, ProjectPaths
from .integrations import evaluate_kg_correctness, evaluate_kggen_mine, evaluate_ragas
from .ingest import PdfExtractionPolicy, load_pdf_extraction_policy, normalize_source_tree
from .eval import DEFAULT_RAGAS_METRICS
from .generation.builder import GenerationMode, QuestionGenerationPlan, generate_questions
from .graphrag.loaders import load_graphrag_tables
from .graphrag.workspace import GraphRAGWorkspace, ensure_graph_rag_project, run_graph_rag_index, stage_documents
from .graphrag_runner import ingest_and_index_documents
from .ontology_handler import materialize_graph_rag_prompts
from .post_processor import split_long_nodes_and_append_edges
from .reporting import render_smoke_report
from .schemas import GraphRAGTableSet

app = typer.Typer(no_args_is_help=True, add_completion=False)
graphrag_app = typer.Typer(no_args_is_help=True, add_completion=False)
benchmark_qed_app = typer.Typer(no_args_is_help=True, add_completion=False)
kg_gen_app = typer.Typer(no_args_is_help=True, add_completion=False)
kg_gen_mine_app = typer.Typer(no_args_is_help=True, add_completion=False)
kg_correctness_app = typer.Typer(no_args_is_help=True, add_completion=False)
report_app = typer.Typer(no_args_is_help=True, add_completion=False)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _build_pdf_policy(pdf_mode: str | None = None) -> PdfExtractionPolicy:
    runtime_env = dict(os.environ)
    if pdf_mode is not None:
        runtime_env["GREV_PDF_EXTRACTOR_MODE"] = pdf_mode
    return load_pdf_extraction_policy(runtime_env)


@graphrag_app.command("stage")
def stage(
    source: Path = typer.Option(..., exists=True, file_okay=False, dir_okay=True),
    workspace_root: Path = typer.Option(Path("workspaces/graphrag"), file_okay=False, dir_okay=True),
    clean: bool = typer.Option(False),
    pdf_mode: str | None = typer.Option(
        None,
        help="PDF 추출 모드: chandra_only 또는 mineru_hybrid",
    ),
) -> None:
    workspace = GraphRAGWorkspace(root=workspace_root)
    staged = stage_documents(source, workspace, clean=clean, pdf_policy=_build_pdf_policy(pdf_mode))
    typer.echo(f"staged {len(staged)} canonical txt files into {workspace.input_dir}")


@graphrag_app.command("normalize")
def normalize(
    source: Path = typer.Option(..., exists=True, file_okay=False, dir_okay=True),
    workspace_root: Path = typer.Option(Path("workspaces/graphrag"), file_okay=False, dir_okay=True),
    clean: bool = typer.Option(False),
    pdf_mode: str | None = typer.Option(
        None,
        help="PDF 추출 모드: chandra_only 또는 mineru_hybrid",
    ),
) -> None:
    """Normalize mixed source files into canonical TXT and write an extraction manifest."""

    workspace = GraphRAGWorkspace(root=workspace_root)
    documents = normalize_source_tree(
        source_root=source,
        canonical_root=workspace.canonical_dir,
        manifest_path=workspace.manifests_dir / "extraction.jsonl",
        clean=clean,
        pdf_policy=_build_pdf_policy(pdf_mode),
    )
    typer.echo(f"normalized {len(documents)} documents into {workspace.canonical_dir}")


@graphrag_app.command("init")
def init_graphrag(
    source: Path = typer.Option(..., exists=True, file_okay=False, dir_okay=True),
    workspace_root: Path = typer.Option(Path("workspaces/graphrag"), file_okay=False, dir_okay=True),
    clean: bool = typer.Option(False),
    pdf_mode: str | None = typer.Option(
        None,
        help="PDF 추출 모드: chandra_only 또는 mineru_hybrid",
    ),
    force: bool = typer.Option(True),
    model: str = typer.Option(DEFAULT_CHAT_MODEL),
    embedding: str = typer.Option(DEFAULT_EMBEDDING_MODEL),
) -> None:
    workspace = GraphRAGWorkspace(root=workspace_root)
    staged = stage_documents(source, workspace, clean=clean, pdf_policy=_build_pdf_policy(pdf_mode))
    ensure_graph_rag_project(workspace, model=model, embedding=embedding, force=force)
    materialize_graph_rag_prompts(workspace)
    typer.echo(f"staged {len(staged)} canonical txt files and initialized {workspace.root}")


@graphrag_app.command("index")
def index_graphrag(
    source: Path = typer.Option(..., exists=True, file_okay=False, dir_okay=True),
    workspace_root: Path = typer.Option(Path("workspaces/graphrag"), file_okay=False, dir_okay=True),
    clean: bool = typer.Option(False),
    pdf_mode: str | None = typer.Option(
        None,
        help="PDF 추출 모드: chandra_only 또는 mineru_hybrid",
    ),
    force: bool = typer.Option(True),
    model: str = typer.Option(DEFAULT_CHAT_MODEL),
    embedding: str = typer.Option(DEFAULT_EMBEDDING_MODEL),
    method: str = typer.Option("standard"),
    skip_validation: bool = typer.Option(False),
    ontology_path: Path | None = typer.Option(
        None,
        exists=True,
        file_okay=True,
        dir_okay=False,
        help="사용자 온톨로지 JSON 경로. 기본값은 workspace/config/user_ontology.json",
    ),
    postprocess: bool = typer.Option(
        False,
        help="인덱싱 후 긴 description 노드를 분할하고 part_of 엣지를 추가",
    ),
    description_limit: int = typer.Option(
        200,
        min=1,
        help="노드 description 분할 기준 글자 수",
    ),
) -> None:
    result = ingest_and_index_documents(
        source,
        workspace_root,
        clean=clean,
        force_init=force,
        model=model,
        embedding=embedding,
        method=method,
        skip_validation=skip_validation,
        ontology_path=ontology_path,
        postprocess=postprocess,
        description_limit=description_limit,
        pdf_policy=_build_pdf_policy(pdf_mode),
    )
    typer.echo(f"staged {len(result.staged_files)} canonical txt files and indexed {result.workspace_root}")


@graphrag_app.command("postprocess")
def postprocess_graphrag(
    workspace_root: Path = typer.Option(Path("workspaces/graphrag"), file_okay=False, dir_okay=True),
    description_limit: int = typer.Option(
        200,
        min=1,
        help="노드 description 분할 기준 글자 수",
    ),
) -> None:
    workspace = GraphRAGWorkspace(root=workspace_root)
    result = split_long_nodes_and_append_edges(workspace, max_description_length=description_limit)
    typer.echo(
        "postprocessed nodes=%s edges=%s split_parents=%d child_nodes=%d appended_edges=%d"
        % (
            result.nodes_path,
            result.edges_path,
            result.split_parent_count,
            result.created_child_node_count,
            result.created_edge_count,
        )
    )


@app.command()
def evaluate(
    benchmark: Path = typer.Option(..., exists=True, file_okay=True, dir_okay=False, help="평가 질문셋 JSON 또는 JSONL"),
    search_results: Path = typer.Option(..., exists=True, file_okay=True, dir_okay=False, help="GraphRAG 검색 결과 JSON"),
    output: Path = typer.Option(Path("data/results/evaluation.json"), file_okay=True, dir_okay=False, help="평가 결과 저장 경로"),
    model: str | None = typer.Option(None, help="Ragas에서 사용할 LLM 모델"),
    provider: str | None = typer.Option(None, help="openai 또는 vllm"),
    base_url: str | None = typer.Option(None, help="OpenAI-compatible endpoint, vLLM용"),
    api_key: str | None = typer.Option(None, help="OpenAI 또는 vLLM API key"),
    metrics: list[str] = typer.Option(list(DEFAULT_RAGAS_METRICS), help="평가할 metric 이름"),
) -> None:
    run = evaluate_ragas(
        benchmark=benchmark,
        search_results=search_results,
        provider=provider,
        model=model,
        base_url=base_url,
        api_key=api_key,
        metrics=tuple(metrics),
        prefix="GREV_RAGAS",
    )
    run.write_json(output)
    typer.echo(f"wrote evaluation results to {output}")
    typer.echo(f"aggregate: {run.aggregate()}")


@benchmark_qed_app.command("autod")
def benchmark_qed_autod(
    source: Path = typer.Option(..., exists=True, file_okay=True, dir_okay=True, help="문서 또는 문서 디렉터리"),
    output: Path = typer.Option(Path("data/benchmark-qed/autod-summary.json"), file_okay=True, dir_okay=False, help="AutoD 결과 저장 경로"),
    target_size: int = typer.Option(10, min=1, help="요약할 문서 개수"),
) -> None:
    payload = summarize_dataset(AutoDPlan(source=source, output=output, target_size=target_size))
    typer.echo(f"wrote AutoD summary to {output}")
    typer.echo(f"documents: {len(payload.get('documents', []))}")


@benchmark_qed_app.command("autoq")
def benchmark_qed_autoq(
    source: Path = typer.Option(..., exists=True, file_okay=True, dir_okay=True, help="문서 또는 문서 디렉터리"),
    output: Path = typer.Option(Path("data/benchmark-qed/autoq-questions.json"), file_okay=True, dir_okay=False, help="AutoQ 결과 저장 경로"),
    num_questions: int = typer.Option(10, min=1, help="생성할 질문 개수"),
    modes: list[str] = typer.Option(["local", "global"], help="local, global, multi-hop, unanswerable"),
) -> None:
    mode_map = {
        "local": GenerationMode.LOCAL,
        "global": GenerationMode.GLOBAL,
        "multi-hop": GenerationMode.MULTI_HOP,
        "unanswerable": GenerationMode.UNANSWERABLE,
    }
    selected_modes = tuple(mode_map[mode] for mode in modes if mode in mode_map)
    plan = AutoQPlan(source=source, output=output, num_questions=num_questions, modes=selected_modes or (GenerationMode.LOCAL, GenerationMode.GLOBAL))
    samples = generate_queries(plan)
    typer.echo(f"wrote {len(samples)} AutoQ questions to {output}")


@benchmark_qed_app.command("autoe")
def benchmark_qed_autoe(
    benchmark: Path = typer.Option(..., exists=True, file_okay=True, dir_okay=False, help="질문셋 JSON 또는 JSONL"),
    search_results: Path = typer.Option(..., exists=True, file_okay=True, dir_okay=False, help="답변 JSON"),
    output: Path = typer.Option(Path("data/benchmark-qed/autoe-evaluation.json"), file_okay=True, dir_okay=False, help="AutoE 결과 저장 경로"),
    provider: str | None = typer.Option(None, help="openai 또는 vllm"),
    model: str | None = typer.Option(None, help="평가용 LLM 모델"),
    base_url: str | None = typer.Option(None, help="OpenAI-compatible endpoint, vLLM용"),
    api_key: str | None = typer.Option(None, help="OpenAI 또는 vLLM API key"),
    metrics: list[str] = typer.Option(list(DEFAULT_RAGAS_METRICS), help="평가할 metric 이름"),
) -> None:
    run = evaluate_answers(
        AutoEPlan(
            benchmark=benchmark,
            search_results=search_results,
            output=output,
            provider=provider,
            model=model,
            base_url=base_url,
            api_key=api_key,
            metrics=tuple(metrics),
        )
    )
    typer.echo(f"wrote AutoE evaluation to {output}")
    typer.echo(f"aggregate: {run.aggregate()}")


@benchmark_qed_app.command("retrieval-reference")
def benchmark_qed_retrieval_reference(
    questions: Path = typer.Option(..., exists=True, file_okay=True, dir_okay=False, help="질문 JSON 또는 JSONL"),
    clusters: Path = typer.Option(..., exists=True, file_okay=True, dir_okay=False, help="클러스터 JSON"),
    text_units: Path | None = typer.Option(None, exists=True, file_okay=True, dir_okay=False, help="clusters가 text_unit_ids만 가질 때 사용할 text units"),
    output: Path = typer.Option(Path("data/benchmark-qed/retrieval-reference.json"), file_okay=True, dir_okay=False, help="retrieval reference 저장 경로"),
    max_questions: int | None = typer.Option(None, min=1, help="reference 생성에 사용할 질문 수 상한"),
    assessor_type: str = typer.Option("rationale", help="relevance assessor 타입: rationale 또는 bing"),
    semantic_neighbors: int = typer.Option(10, min=1, help="query별 semantic neighbors 수"),
    centroid_neighbors: int = typer.Option(5, min=1, help="query별 centroid neighbors 수"),
    concurrent_requests: int = typer.Option(16, min=1, help="동시 relevance 요청 수"),
    include_clusters: bool = typer.Option(True, help="reference JSON에 clusters를 같이 저장할지 여부"),
) -> None:
    payload = generate_retrieval_reference(
        RetrievalReferencePlan(
            questions=questions,
            clusters=clusters,
            text_units=text_units,
            output=output,
            max_questions=max_questions,
            assessor_type=assessor_type,
            semantic_neighbors=semantic_neighbors,
            centroid_neighbors=centroid_neighbors,
            concurrent_requests=concurrent_requests,
            include_clusters=include_clusters,
        )
    )
    typer.echo(f"wrote retrieval reference to {output}")
    typer.echo(f"references: {len(payload.get('references', []))}")


@benchmark_qed_app.command("retrieval-score")
def benchmark_qed_retrieval_score(
    reference_dir: Path = typer.Option(..., exists=True, file_okay=False, dir_okay=True, help="reference.json 이 들어있는 디렉터리"),
    clusters: Path = typer.Option(..., exists=True, file_okay=True, dir_okay=False, help="클러스터 JSON"),
    retrieval_results: Path = typer.Option(..., exists=True, file_okay=True, dir_okay=False, help="retrieval-results JSON"),
    output: Path = typer.Option(Path("data/benchmark-qed/retrieval-evaluation.json"), file_okay=True, dir_okay=False, help="retrieval 평가 요약 저장 경로"),
    text_units: Path | None = typer.Option(None, exists=True, file_okay=True, dir_okay=False, help="clusters가 text_unit_ids만 가질 때 사용할 text units"),
    question_sets: list[str] = typer.Option(["default"], help="평가할 question set 이름"),
    rag_method_name: str = typer.Option("benchmark-qed", help="평가할 RAG method 이름"),
    reference_filename: str = typer.Option("reference.json", help="reference 파일 이름"),
    relevance_threshold: int = typer.Option(2, min=0, max=3, help="relevance 임계값"),
    context_id_key: str = typer.Option("chunk_id", help="retrieval context ID 키"),
    context_text_key: str = typer.Option("text", help="retrieval context text 키"),
    cluster_match_by: str = typer.Option("text", help="cluster 매칭 기준: text, id, short_id"),
    run_significance_test: bool = typer.Option(True, help="significance test를 수행할지 여부"),
    significance_alpha: float = typer.Option(0.05, min=0.0, max=1.0, help="significance alpha"),
    significance_correction: str = typer.Option("holm", help="p-value correction 방식"),
    fidelity_metric: str = typer.Option("js", help="fidelity metric: js or tvd"),
    assessor_type: str = typer.Option("rationale", help="relevance assessor 타입: rationale 또는 bing"),
    concurrent_requests: int = typer.Option(16, min=1, help="동시 relevance 요청 수"),
    max_concurrent: int = typer.Option(8, min=1, help="평가 동시성 상한"),
) -> None:
    payload = evaluate_retrieval_results(
        RetrievalEvaluationPlan(
            reference_dir=reference_dir,
            clusters=clusters,
            text_units=text_units,
            retrieval_results=retrieval_results,
            output=output,
            question_sets=tuple(question_sets),
            rag_method_name=rag_method_name,
            reference_filename=reference_filename,
            relevance_threshold=relevance_threshold,
            context_id_key=context_id_key,
            context_text_key=context_text_key,
            cluster_match_by=cluster_match_by,
            run_significance_test=run_significance_test,
            significance_alpha=significance_alpha,
            significance_correction=significance_correction,
            fidelity_metric=fidelity_metric,
            assessor_type=assessor_type,
            concurrent_requests=concurrent_requests,
            max_concurrent=max_concurrent,
        )
    )
    typer.echo(f"wrote retrieval evaluation to {output}")
    typer.echo(f"rows: {payload['rows']}")


@benchmark_qed_app.command("retrieval-smoke")
def benchmark_qed_retrieval_smoke(
    benchmark: Path = typer.Option(Path("data/benchmarks/sample_benchmark.json"), exists=True, file_okay=True, dir_okay=False, help="질문 JSON 또는 JSONL"),
    search_results: Path = typer.Option(Path("data/results/sample_search_results.json"), exists=True, file_okay=True, dir_okay=False, help="retrieval 결과 JSON"),
    graphrag_root: Path = typer.Option(Path("workspaces/graphrag/output"), file_okay=False, dir_okay=True, help="GraphRAG output root"),
    output_dir: Path = typer.Option(Path("/tmp/grev-benchmark-qed-retrieval-smoke"), file_okay=False, dir_okay=True, help="스모크 산출물 디렉터리"),
    report_output: Path = typer.Option(Path("/tmp/grev-benchmark-qed-retrieval-smoke/retrieval-smoke.html"), file_okay=True, dir_okay=False, help="스모크 리포트 HTML 경로"),
    question_sets: list[str] = typer.Option(["default"], help="평가할 question set 이름"),
    rag_method_name: str = typer.Option("benchmark-qed", help="평가할 RAG method 이름"),
    reference_filename: str = typer.Option("reference.json", help="reference 파일 이름"),
    relevance_threshold: int = typer.Option(2, min=0, max=3, help="relevance 임계값"),
    cluster_match_by: str = typer.Option("text", help="cluster 매칭 기준: text, id, short_id"),
    run_significance_test: bool = typer.Option(True, help="significance test를 수행할지 여부"),
    significance_alpha: float = typer.Option(0.05, min=0.0, max=1.0, help="significance alpha"),
    significance_correction: str = typer.Option("holm", help="p-value correction 방식"),
    fidelity_metric: str = typer.Option("js", help="fidelity metric: js or tvd"),
    assessor_type: str = typer.Option("rationale", help="relevance assessor 타입: rationale 또는 bing"),
    semantic_neighbors: int = typer.Option(10, min=1, help="query별 semantic neighbors 수"),
    centroid_neighbors: int = typer.Option(5, min=1, help="query별 centroid neighbors 수"),
    concurrent_requests: int = typer.Option(16, min=1, help="동시 relevance 요청 수"),
    max_concurrent: int = typer.Option(8, min=1, help="평가 동시성 상한"),
) -> None:
    payload = run_benchmark_qed_retrieval_smoke(
        RetrievalSmokePlan(
            benchmark=benchmark,
            search_results=search_results,
            graphrag_root=graphrag_root,
            output_dir=output_dir,
            report_output=report_output,
            question_sets=tuple(question_sets),
            rag_method_name=rag_method_name,
            reference_filename=reference_filename,
            relevance_threshold=relevance_threshold,
            cluster_match_by=cluster_match_by,
            run_significance_test=run_significance_test,
            significance_alpha=significance_alpha,
            significance_correction=significance_correction,
            fidelity_metric=fidelity_metric,
            assessor_type=assessor_type,
            semantic_neighbors=semantic_neighbors,
            centroid_neighbors=centroid_neighbors,
            concurrent_requests=concurrent_requests,
            max_concurrent=max_concurrent,
        )
    )
    typer.echo(f"wrote clusters to {payload.clusters}")
    typer.echo(f"wrote retrieval reference to {payload.retrieval_reference}")
    typer.echo(f"wrote retrieval results to {payload.retrieval_results}")
    typer.echo(f"wrote retrieval evaluation to {payload.retrieval_evaluation}")
    typer.echo(f"wrote retrieval report to {payload.report}")


@benchmark_qed_app.command("smoke")
def benchmark_qed_smoke(
    source: Path = typer.Option(Path("examples/sample_docs"), exists=True, file_okay=True, dir_okay=True, help="스모크 입력 문서 또는 디렉터리"),
    benchmark: Path = typer.Option(Path("data/benchmarks/sample_benchmark.json"), exists=True, file_okay=True, dir_okay=False, help="AutoE용 benchmark JSON 또는 JSONL"),
    search_results: Path = typer.Option(Path("data/results/sample_search_results.json"), exists=True, file_okay=True, dir_okay=False, help="AutoE용 search results JSON"),
    output_dir: Path = typer.Option(Path("/tmp/grev-benchmark-qed-smoke"), file_okay=False, dir_okay=True, help="스모크 산출물 디렉터리"),
    report_output: Path = typer.Option(_repo_root() / "reports" / "benchmark-qed-smoke.html", file_okay=True, dir_okay=False, help="스모크 리포트 HTML 경로"),
    target_size: int = typer.Option(1, min=1, help="AutoD에 사용할 문서 수"),
    num_questions: int = typer.Option(1, min=1, help="AutoQ로 생성할 질문 수"),
    modes: list[str] = typer.Option(["local"], help="local, global, multi-hop, unanswerable"),
    metrics: list[str] = typer.Option(list(DEFAULT_RAGAS_METRICS), help="AutoE metric 이름"),
    assertion_validation_enabled: bool = typer.Option(False, help="Assertion 검증을 켤지 여부"),
    assertion_min_validation_score: int = typer.Option(1, min=1, max=5, help="Assertion validation 최소 점수"),
    title: str = typer.Option("BenchmarkQED Smoke Report", help="리포트 제목"),
) -> None:
    result = run_benchmark_qed_smoke(
        BenchmarkQEDSmokePlan(
            source=source,
            benchmark=benchmark,
            search_results=search_results,
            output_dir=output_dir,
            report_output=report_output,
            target_size=target_size,
            num_questions=num_questions,
            modes=tuple(modes),
            metrics=tuple(metrics),
            assertion_validation_enabled=assertion_validation_enabled,
            assertion_min_validation_score=assertion_min_validation_score,
            report_title=title,
        )
    )
    typer.echo(f"wrote AutoD summary to {result.autod_summary}")
    typer.echo(f"wrote AutoQ questions to {result.autoq_questions}")
    typer.echo(f"wrote assertion prep to {result.assertion_prep}")
    typer.echo(f"wrote AutoE evaluation to {result.autoe_evaluation}")
    typer.echo(f"wrote retrieval prep to {result.retrieval_results}")
    typer.echo(f"wrote smoke report to {result.report}")


@kg_gen_mine_app.command("evaluate")
def kg_gen_mine_evaluate(
    benchmark: Path = typer.Option(..., exists=True, file_okay=True, dir_okay=False, help="질문셋 JSON 또는 JSONL"),
    search_results: Path = typer.Option(..., exists=True, file_okay=True, dir_okay=False, help="GraphRAG 검색 결과 JSON"),
    output: Path = typer.Option(Path("data/kggen-mine/evaluation.json"), file_okay=True, dir_okay=False, help="평가 결과 저장 경로"),
    provider: str | None = typer.Option(None, help="openai 또는 vllm"),
    model: str | None = typer.Option(None, help="정답 판정용 LLM 모델"),
    base_url: str | None = typer.Option(None, help="OpenAI-compatible endpoint, vLLM용"),
    api_key: str | None = typer.Option(None, help="OpenAI 또는 vLLM API key"),
    max_tokens: int | None = typer.Option(None, min=1, help="판정용 최대 토큰 수"),
) -> None:
    run = evaluate_kggen_mine(
        benchmark=benchmark,
        search_results=search_results,
        output=output,
        provider=provider,
        model=model,
        base_url=base_url,
        api_key=api_key,
        max_tokens=max_tokens,
    )
    typer.echo(f"wrote correctness evaluation to {output}")
    typer.echo(f"aggregate: {run.aggregate()}")


@kg_correctness_app.command("evaluate")
def kg_correctness_evaluate(
    benchmark: Path = typer.Option(..., exists=True, file_okay=True, dir_okay=False, help="질문셋 JSON 또는 JSONL"),
    search_results: Path = typer.Option(..., exists=True, file_okay=True, dir_okay=False, help="GraphRAG 검색 결과 JSON"),
    output: Path = typer.Option(Path("data/kg-correctness/evaluation.json"), file_okay=True, dir_okay=False, help="평가 결과 저장 경로"),
    provider: str | None = typer.Option(None, help="openai 또는 vllm"),
    model: str | None = typer.Option(None, help="정답 판정용 LLM 모델"),
    base_url: str | None = typer.Option(None, help="OpenAI-compatible endpoint, vLLM용"),
    api_key: str | None = typer.Option(None, help="OpenAI 또는 vLLM API key"),
    max_tokens: int | None = typer.Option(None, min=1, help="판정용 최대 토큰 수"),
) -> None:
    run = evaluate_kg_correctness(
        benchmark=benchmark,
        search_results=search_results,
        output=output,
        provider=provider,
        model=model,
        base_url=base_url,
        api_key=api_key,
        max_tokens=max_tokens,
    )
    typer.echo(f"wrote correctness evaluation to {output}")
    typer.echo(f"aggregate: {run.aggregate()}")


@app.command()
def generate_questions(
    source: Path = typer.Option(..., exists=True, file_okay=True, dir_okay=True, help="문서 또는 문서 디렉터리"),
    output: Path = typer.Option(Path("data/benchmarks/generated_questions.json"), file_okay=True, dir_okay=False, help="질문 생성 결과 저장 경로"),
    num_questions: int = typer.Option(10, min=1, help="생성할 질문 개수"),
    modes: list[str] = typer.Option(["local", "global"], help="local, global, multi-hop, unanswerable 중 선택"),
) -> None:
    mode_map = {
        "local": GenerationMode.LOCAL,
        "global": GenerationMode.GLOBAL,
        "multi-hop": GenerationMode.MULTI_HOP,
        "unanswerable": GenerationMode.UNANSWERABLE,
    }
    selected_modes = tuple(mode_map[mode] for mode in modes if mode in mode_map)
    plan = QuestionGenerationPlan(
        source=source,
        output=output,
        num_questions=num_questions,
        modes=selected_modes or (GenerationMode.LOCAL, GenerationMode.GLOBAL),
        subrepo_name="benchmark",
    )
    samples = generate_questions(plan)
    typer.echo(f"wrote {len(samples)} questions to {output}")


@app.command()
def inspect(graphrag_root: Path = typer.Option(..., exists=True, file_okay=False, dir_okay=True)) -> None:
    """Inspect GraphRAG parquet outputs."""
    tables = load_graphrag_tables(GraphRAGTableSet(root=graphrag_root))
    typer.echo(f"entities: {len(tables.entities)}")
    typer.echo(f"relationships: {len(tables.relationships)}")
    typer.echo(f"communities: {len(tables.communities)}")


@app.command()
def init(root: Path = typer.Option(Path.cwd(), file_okay=False, dir_okay=True)) -> None:
    """Show the project path layout that this repo expects."""
    paths = ProjectPaths(root=root)
    typer.echo(f"graphrag_output: {paths.graphrag_output}")
    typer.echo(f"benchmarks: {paths.benchmarks}")
    typer.echo(f"results: {paths.results}")
    typer.echo(f"reports: {paths.reports}")


@report_app.command("smoke")
def report_smoke(
    evaluation: Path = typer.Option(
        Path("data/results/sample_evaluation.json"),
        exists=True,
        file_okay=True,
        dir_okay=False,
        help="Ragas evaluation JSON",
    ),
    generated_questions: Path | None = typer.Option(
        None,
        exists=True,
        file_okay=True,
        dir_okay=False,
        help="Generated questions JSON",
    ),
    autod_summary: Path | None = typer.Option(
        None,
        exists=True,
        file_okay=True,
        dir_okay=False,
        help="AutoD summary JSON",
    ),
    autoq_questions: Path | None = typer.Option(
        None,
        exists=True,
        file_okay=True,
        dir_okay=False,
        help="AutoQ questions JSON",
    ),
    output: Path = typer.Option(
        Path("reports/pdf-smoke-test-report.html"),
        file_okay=True,
        dir_okay=False,
        help="HTML report output path",
    ),
    title: str = typer.Option("GraphRAG + Ragas Smoke Report", help="Report title"),
) -> None:
    render_smoke_report(
        evaluation=evaluation,
        output=output,
        generated_questions=generated_questions,
        autod_summary=autod_summary,
        autoq_questions=autoq_questions,
        title=title,
    )
    typer.echo(f"wrote smoke report to {output}")


@app.callback()
def _main() -> None:
    pass


app.add_typer(graphrag_app, name="graphrag")
app.add_typer(benchmark_qed_app, name="benchmark-qed")
app.add_typer(kg_gen_app, name="kg-gen")
kg_gen_app.add_typer(kg_gen_mine_app, name="mine")
app.add_typer(kg_correctness_app, name="kg-correctness")
app.add_typer(report_app, name="report")
