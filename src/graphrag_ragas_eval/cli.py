from __future__ import annotations

from pathlib import Path

import typer

from .config import ProjectPaths
from .eval import DEFAULT_RAGAS_METRICS, RagasRunner, load_benchmark_samples, load_search_results
from .graphrag.loaders import load_graphrag_tables
from .graphrag.workspace import GraphRAGWorkspace, ensure_graph_rag_project, run_graph_rag_index, stage_documents
from .graphrag_runner import ingest_and_index_documents
from .schemas import GraphRAGTableSet

app = typer.Typer(no_args_is_help=True, add_completion=False)
graphrag_app = typer.Typer(no_args_is_help=True, add_completion=False)


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
    model: str = typer.Option("gpt-4o-mini", help="Ragas에서 사용할 LLM 모델"),
    metrics: list[str] = typer.Option(list(DEFAULT_RAGAS_METRICS), help="평가할 metric 이름"),
) -> None:
    samples = load_benchmark_samples(benchmark)
    results = load_search_results(search_results)
    llm = _build_ragas_llm(model)
    runner = RagasRunner(llm=llm, metrics=tuple(metrics))
    run = runner.evaluate_results(samples, results)
    run.write_json(output)
    typer.echo(f"wrote evaluation results to {output}")
    typer.echo(f"aggregate: {run.aggregate()}")


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


def _build_ragas_llm(model: str) -> object:
    try:
        from openai import AsyncOpenAI
        from ragas.llms import llm_factory
    except ImportError as exc:  # pragma: no cover - runtime dependency error path
        raise typer.BadParameter("openai or ragas is not installed") from exc

    client = AsyncOpenAI()
    return llm_factory(model, client=client)
