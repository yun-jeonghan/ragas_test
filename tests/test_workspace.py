from pathlib import Path

from graphrag_ragas_eval.graphrag.workspace import GraphRAGWorkspace, stage_documents


def test_stage_documents_flatten(tmp_path: Path) -> None:
    source = tmp_path / "docs"
    source.mkdir()
    nested = source / "nested"
    nested.mkdir()
    (source / "a.txt").write_text("hello", encoding="utf-8")
    (nested / "b.md").write_text("world", encoding="utf-8")

    workspace = GraphRAGWorkspace(root=tmp_path / "workspace")
    staged = stage_documents(source, workspace)

    assert len(staged) == 2
    assert (workspace.input_dir / "a.txt").exists()
    assert (workspace.input_dir / "nested__b.md").exists()

