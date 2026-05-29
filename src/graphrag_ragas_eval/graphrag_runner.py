from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .graphrag.workspace import GraphRAGWorkspace, ensure_graph_rag_project, run_graph_rag_index, stage_documents


@dataclass(frozen=True, slots=True)
class GraphRAGRunResult:
    staged_files: tuple[Path, ...]
    workspace_root: Path


def ingest_and_index_documents(
    source_dir: Path,
    workspace_root: Path,
    *,
    clean: bool = False,
    force_init: bool = False,
    model: str = "gpt-4.1",
    embedding: str = "text-embedding-3-large",
    method: str = "standard",
    skip_validation: bool = False,
) -> GraphRAGRunResult:
    workspace = GraphRAGWorkspace(root=workspace_root)
    staged = stage_documents(source_dir, workspace, clean=clean)
    ensure_graph_rag_project(workspace, model=model, embedding=embedding, force=force_init)
    run_graph_rag_index(workspace, method=method, skip_validation=skip_validation)
    return GraphRAGRunResult(staged_files=tuple(staged), workspace_root=workspace.root)

