from __future__ import annotations

import os
from pathlib import Path

import typer

from .benchmark_qed.autod import AutoDPlan, summarize_dataset
from .benchmark_qed.autoe import AutoEPlan, evaluate_answers
from .benchmark_qed.autoq import AutoQPlan, generate_queries
from .config import ProjectPaths
from .eval import DEFAULT_RAGAS_METRICS, RagasRunner, load_benchmark_samples, load_search_results
from .generation.builder import GenerationMode, QuestionGenerationPlan, generate_questions
from .graphrag.loaders import load_graphrag_tables
from .graphrag.workspace import GraphRAGWorkspace, ensure_graph_rag_project, run_graph_rag_index, stage_documents
from .graphrag_runner import ingest_and_index_documents
from .llm import build_ragas_embeddings, build_ragas_llm, load_llm_runtime_config
from .schemas import GraphRAGTableSet

app = typer.Typer(no_args_is_help=True, add_completion=False)
graphrag_app = typer.Typer(no_args_is_help=True, add_completion=False)
benchmark_qed_app = typer.Typer(no_args_is_help=True, add_completion=False)


@graphrag_app.command("stage")
def stage(
    source: Path = typer.Option(..., exists=True, file_okay=False, dir_okay=True),
    workspace_root: Path = typer.Option(Path("workspaces/graphrag"), file_okay=False, dir_okay=True),
    clean: bool = typer.Option(False),
) -> None:
    workspace = GraphRAGWorkspace(root=workspace_root)
    staged = stage_documents(source, workspace, clean=clean)
    typer.echo(f"staged {len(staged)} files into {workspace.input_dir}")


@graphrag_app.command("init")
def init_graphrag(
    source: Path = typer.Option(..., exists=True, file_okay=False, dir_okay=True),
    workspace_root: Path = typer.Option(Path("workspaces/graphrag"), file_okay=False, dir_okay=True),
    clean: bool = typer.Option(False),
    force: bool = typer.Option(True),
    model: str = typer.Option("gpt-4.1"),
    embedding: str = typer.Option("text-embedding-3-large"),
) -> None:
    workspace = GraphRAGWorkspace(root=workspace_root)
    staged = stage_documents(source, workspace, clean=clean)
    ensure_graph_rag_project(workspace, model=model, embedding=embedding, force=force)
    typer.echo(f"staged {len(staged)} files and initialized {workspace.root}")


@graphrag_app.command("index")
def index_graphrag(
    source: Path = typer.Option(..., exists=True, file_okay=False, dir_okay=True),
    workspace_root: Path = typer.Option(Path("workspaces/graphrag"), file_okay=False, dir_okay=True),
    clean: bool = typer.Option(False),
    force: bool = typer.Option(True),
    model: str = typer.Option("gpt-4.1"),
    embedding: str = typer.Option("text-embedding-3-large"),
    method: str = typer.Option("standard"),
    skip_validation: bool = typer.Option(False),
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
    )
    typer.echo(f"staged {len(result.staged_files)} files and indexed {result.workspace_root}")


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
    samples = load_benchmark_samples(benchmark)
    results = load_search_results(search_results)
    runtime_env = dict(os.environ)
    if provider is not None:
        runtime_env["GREV_RAGAS_PROVIDER"] = provider
    if model is not None:
        runtime_env["GREV_RAGAS_MODEL"] = model
    if base_url is not None:
        runtime_env["GREV_RAGAS_BASE_URL"] = base_url
    if api_key is not None:
        runtime_env["GREV_RAGAS_API_KEY"] = api_key
    runtime = load_llm_runtime_config(runtime_env, prefix="GREV_RAGAS")
    llm = build_ragas_llm(runtime)
    embeddings = build_ragas_embeddings(runtime)
    runner = RagasRunner(llm=llm, embeddings=embeddings, metrics=tuple(metrics))
    run = runner.evaluate_results(samples, results)
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
) -> None:
    run = evaluate_answers(AutoEPlan(benchmark=benchmark, search_results=search_results, output=output, provider=provider, model=model, base_url=base_url, api_key=api_key))
    typer.echo(f"wrote AutoE evaluation to {output}")
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


@app.callback()
def _main() -> None:
    pass


app.add_typer(graphrag_app, name="graphrag")
app.add_typer(benchmark_qed_app, name="benchmark-qed")
