from __future__ import annotations

import json
from pathlib import Path

from graphrag_ragas_eval.graphrag.workspace import GraphRAGWorkspace
from graphrag_ragas_eval.ontology_handler import materialize_graph_rag_prompts


def test_materialize_graph_rag_prompts_injects_user_ontology(tmp_path: Path) -> None:
    workspace = GraphRAGWorkspace(root=tmp_path / "workspace")
    workspace.config_dir.mkdir(parents=True, exist_ok=True)
    ontology_path = workspace.config_dir / "user_ontology.json"
    ontology_path.write_text(
        json.dumps(
            {
                "allowed_types": ["부대", "무기"],
                "extraction_rules": {
                    "prefer_source_grounding": True,
                    "normalize_names": ["alias", "canonical"],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    workspace.prompts_dir.mkdir(parents=True, exist_ok=True)
    (workspace.prompts_dir / "entity_extraction.txt").write_text(
        """### System Role
old system role

### User Role
extract entities
""",
        encoding="utf-8",
    )
    (workspace.prompts_dir / "relationship_extraction.txt").write_text(
        """### System Role
old relationship role

### User Role
extract relationships
""",
        encoding="utf-8",
    )

    materialize_graph_rag_prompts(workspace)

    entity_prompt = (workspace.prompts_dir / "entity_extraction.txt").read_text(encoding="utf-8")
    relationship_prompt = (workspace.prompts_dir / "relationship_extraction.txt").read_text(
        encoding="utf-8"
    )
    assert "부대" in entity_prompt
    assert "무기" in entity_prompt
    assert "prefer_source_grounding" in entity_prompt
    for label in ("is_a", "part_of", "located_in", "causes", "uses", "associated_with", "same_as"):
        assert label in relationship_prompt

