from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .ontology_handler import materialize_graph_rag_prompts
from .post_processor import split_long_nodes_and_append_edges
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
    ontology_path: Path | None = None,
    postprocess: bool = False,
    description_limit: int = 200,
) -> GraphRAGRunResult:
    workspace = GraphRAGWorkspace(root=workspace_root)
    staged = stage_documents(source_dir, workspace, clean=clean)
    ensure_graph_rag_project(workspace, model=model, embedding=embedding, force=force_init)
    materialize_graph_rag_prompts(workspace, ontology_path=ontology_path)
    run_graph_rag_index(workspace, method=method, skip_validation=skip_validation)
    if postprocess:
        split_long_nodes_and_append_edges(workspace, max_description_length=description_limit)
    return GraphRAGRunResult(staged_files=tuple(staged), workspace_root=workspace.root)
