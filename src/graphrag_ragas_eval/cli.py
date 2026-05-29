from __future__ import annotations

from pathlib import Path

import typer

from .config import ProjectPaths
from .graphrag.loaders import load_graphrag_tables
from .schemas import GraphRAGTableSet

app = typer.Typer(no_args_is_help=True, add_completion=False)


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

