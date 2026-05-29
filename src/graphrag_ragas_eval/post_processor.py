from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .graphrag.workspace import GraphRAGWorkspace

logger = logging.getLogger(__name__)

_NODE_ID_CANDIDATES = ("id", "entity_id", "node_id")
_NODE_DESCRIPTION_CANDIDATES = ("description", "text", "summary", "content")
_EDGE_SOURCE_CANDIDATES = ("source", "source_id", "head_id", "from_id")
_EDGE_TARGET_CANDIDATES = ("target", "target_id", "tail_id", "to_id")
_EDGE_RELATION_CANDIDATES = ("relationship", "relation", "type", "kind", "label")
_NL = chr(10)


@dataclass(frozen=True, slots=True)
class PostProcessResult:
    nodes_path: Path
    edges_path: Path
    split_parent_count: int
    created_child_node_count: int
    created_edge_count: int


def _resolve_table_path(workspace: GraphRAGWorkspace, candidates: tuple[str, ...]) -> Path:
    for candidate in candidates:
        path = workspace.output_dir / candidate
        if path.exists():
            return path
    raise FileNotFoundError(
        f"Unable to locate any of {', '.join(candidates)} under {workspace.output_dir}"
    )


def _read_text_value(row: pd.Series, candidates: tuple[str, ...]) -> str:
    for candidate in candidates:
        value = row.get(candidate)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _resolve_first_column(columns: list[str], candidates: tuple[str, ...]) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def _split_description(text: str, *, max_length: int) -> list[str]:
    normalized = " ".join(text.split())
    if len(normalized) <= max_length:
        return [normalized]

    sentences = [part.strip() for part in normalized.split(".") if part.strip()]
    chunks = [f"{sentence}." for sentence in sentences] if sentences else [normalized]
    final: list[str] = []
    for chunk in chunks:
        if len(chunk) <= max_length:
            final.append(chunk.strip())
            continue
        cursor = 0
        while cursor < len(chunk):
            final.append(chunk[cursor : cursor + max_length].strip())
            cursor += max_length
    return [item for item in final if item]


def _build_child_node(
    row: pd.Series,
    *,
    parent_id: str,
    child_id: str,
    child_description: str,
    id_column: str | None,
    description_column: str,
    split_index: int,
) -> dict[str, Any]:
    payload = row.to_dict()
    if id_column is not None:
        payload[id_column] = child_id
    payload[description_column] = child_description
    payload["parent_id"] = parent_id
    payload["split_index"] = split_index
    payload["split_from"] = parent_id
    payload["generated_by"] = "grev.post_processor"
    payload["is_split_child"] = True
    return payload


def _build_part_of_edge(
    row: pd.Series,
    *,
    child_id: str,
    parent_id: str,
    source_column: str | None,
    target_column: str | None,
    relation_column: str | None,
) -> dict[str, Any]:
    payload = row.to_dict()
    if source_column is not None:
        payload[source_column] = child_id
    if target_column is not None:
        payload[target_column] = parent_id
    if relation_column is not None:
        payload[relation_column] = "part_of"
    payload["source_id"] = child_id
    payload["target_id"] = parent_id
    payload["relationship"] = "part_of"
    payload["generated_by"] = "grev.post_processor"
    payload["is_synthetic"] = True
    return payload


def split_long_nodes_and_append_edges(
    workspace: GraphRAGWorkspace,
    *,
    max_description_length: int = 200,
    node_table_name_candidates: tuple[str, ...] = ("entities.parquet", "nodes.parquet"),
    edge_table_name_candidates: tuple[str, ...] = ("relationships.parquet", "edges.parquet"),
) -> PostProcessResult:
    nodes_path = _resolve_table_path(workspace, node_table_name_candidates)
    edges_path = _resolve_table_path(workspace, edge_table_name_candidates)

    logger.info(
        "starting post-processing on nodes=%s and edges=%s with description limit=%d",
        nodes_path,
        edges_path,
        max_description_length,
    )

    nodes = pd.read_parquet(nodes_path)
    edges = pd.read_parquet(edges_path)

    node_columns = list(nodes.columns)
    edge_columns = list(edges.columns)
    id_column = _resolve_first_column(node_columns, _NODE_ID_CANDIDATES)
    description_column = _resolve_first_column(node_columns, _NODE_DESCRIPTION_CANDIDATES)
    if id_column is None:
        raise ValueError(f"No node id column found in {nodes_path}; expected one of {_NODE_ID_CANDIDATES}")
    if description_column is None:
        raise ValueError(
            f"No node description column found in {nodes_path}; expected one of {_NODE_DESCRIPTION_CANDIDATES}"
        )

    source_column = _resolve_first_column(edge_columns, _EDGE_SOURCE_CANDIDATES)
    target_column = _resolve_first_column(edge_columns, _EDGE_TARGET_CANDIDATES)
    relation_column = _resolve_first_column(edge_columns, _EDGE_RELATION_CANDIDATES)

    child_rows: list[dict[str, Any]] = []
    edge_rows: list[dict[str, Any]] = []
    split_parent_count = 0

    for index, row in nodes.iterrows():
        raw_description = _read_text_value(row, (description_column,))
        if len(raw_description) <= max_description_length:
            continue

        parent_id = str(row[id_column])
        split_parts = _split_description(raw_description, max_length=max_description_length)
        if len(split_parts) <= 1:
            logger.warning(
                "node %s exceeded %d characters but could not be split cleanly; leaving as-is",
                parent_id,
                max_description_length,
            )
            continue

        split_parent_count += 1
        logger.warning(
            "splitting node %s into %d child nodes because description length %d exceeded %d",
            parent_id,
            len(split_parts),
            len(raw_description),
            max_description_length,
        )

        for part_index, part in enumerate(split_parts, start=1):
            child_id = f"{parent_id}::split::{part_index}"
            child_rows.append(
                _build_child_node(
                    row,
                    parent_id=parent_id,
                    child_id=child_id,
                    child_description=part,
                    id_column=id_column,
                    description_column=description_column,
                    split_index=part_index,
                )
            )
            edge_rows.append(
                _build_part_of_edge(
                    row,
                    child_id=child_id,
                    parent_id=parent_id,
                    source_column=source_column,
                    target_column=target_column,
                    relation_column=relation_column,
                )
            )
            logger.info(
                "created split child node %s from parent %s with part_of edge",
                child_id,
                parent_id,
            )

    if child_rows:
        child_frame = pd.DataFrame(child_rows)
        nodes = pd.concat([nodes, child_frame], ignore_index=True, sort=False)
    if edge_rows:
        edge_frame = pd.DataFrame(edge_rows)
        edges = pd.concat([edges, edge_frame], ignore_index=True, sort=False)

    nodes_backup = nodes_path.with_suffix(nodes_path.suffix + ".bak")
    edges_backup = edges_path.with_suffix(edges_path.suffix + ".bak")
    if not nodes_backup.exists():
        nodes_path.replace(nodes_backup)
        logger.info("backed up original node parquet to %s", nodes_backup)
    if not edges_backup.exists():
        edges_path.replace(edges_backup)
        logger.info("backed up original edge parquet to %s", edges_backup)

    nodes.to_parquet(nodes_path, index=False)
    edges.to_parquet(edges_path, index=False)

    logger.info(
        "post-processing complete: %d parents split, %d child nodes created, %d part_of edges appended",
        split_parent_count,
        len(child_rows),
        len(edge_rows),
    )
    return PostProcessResult(
        nodes_path=nodes_path,
        edges_path=edges_path,
        split_parent_count=split_parent_count,
        created_child_node_count=len(child_rows),
        created_edge_count=len(edge_rows),
    )
