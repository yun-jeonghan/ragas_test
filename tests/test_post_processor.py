from __future__ import annotations

from pathlib import Path

import pandas as pd

from graphrag_ragas_eval.graphrag.workspace import GraphRAGWorkspace
from graphrag_ragas_eval.post_processor import split_long_nodes_and_append_edges


def test_split_long_nodes_and_append_edges(tmp_path: Path) -> None:
    workspace = GraphRAGWorkspace(root=tmp_path / "workspace")
    workspace.output_dir.mkdir(parents=True, exist_ok=True)

    nodes = pd.DataFrame(
        [
            {
                "id": "node-1",
                "description": (
                    "First sentence about a long node. Second sentence extends the explanation. "
                    "Third sentence finishes the description for splitting."
                ),
                "name": "Long Node",
            },
            {
                "id": "node-2",
                "description": "Short node.",
                "name": "Short Node",
            },
        ]
    )
    edges = pd.DataFrame(
        [
            {
                "source_id": "node-1",
                "target_id": "node-2",
                "relationship": "related_to",
            }
        ]
    )
    nodes.to_parquet(workspace.output_dir / "entities.parquet", index=False)
    edges.to_parquet(workspace.output_dir / "relationships.parquet", index=False)

    result = split_long_nodes_and_append_edges(workspace, max_description_length=60)

    assert result.created_child_node_count >= 2
    updated_nodes = pd.read_parquet(workspace.output_dir / "entities.parquet")
    updated_edges = pd.read_parquet(workspace.output_dir / "relationships.parquet")
    assert any(str(value).startswith("node-1::split::") for value in updated_nodes["id"])
    assert "part_of" in set(updated_edges["relationship"].astype(str))
    assert (workspace.output_dir / "entities.parquet.bak").exists()
    assert (workspace.output_dir / "relationships.parquet.bak").exists()

