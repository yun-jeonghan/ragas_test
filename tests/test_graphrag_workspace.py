from __future__ import annotations

from pathlib import Path

from graphrag_ragas_eval.graphrag.workspace import GraphRAGWorkspace, ensure_graph_rag_project, run_graph_rag_index


def test_graph_rag_workspace_injects_api_key_and_updates_dotenv(monkeypatch, tmp_path: Path) -> None:
    workspace = GraphRAGWorkspace(root=tmp_path / "workspace")
    captured: list[dict[str, object]] = []

    def fake_run(cmd, check, env=None):
        captured.append({"cmd": list(cmd), "env": dict(env or {})})
        if list(cmd)[:2] == ["graphrag", "init"]:
            workspace.root.mkdir(parents=True, exist_ok=True)
            (workspace.root / ".env").write_text("GRAPHRAG_API_KEY=<API_KEY>\n", encoding="utf-8")
        return None

    monkeypatch.delenv("GRAPHRAG_API_KEY", raising=False)
    monkeypatch.delenv("GREV_GRAPHRAG_API_KEY", raising=False)
    monkeypatch.delenv("GREV_RAGAS_API_KEY", raising=False)
    monkeypatch.delenv("GREV_BENCHMARKQED_API_KEY", raising=False)
    monkeypatch.delenv("GREV_KGGEN_MINE_API_KEY", raising=False)
    monkeypatch.setattr("graphrag_ragas_eval.graphrag.workspace.subprocess.run", fake_run)

    ensure_graph_rag_project(workspace, model="qwen2.5:0.5b", embedding="nomic-embed-text", force=True)
    run_graph_rag_index(workspace, method="standard", skip_validation=True)

    assert captured[0]["env"]["GRAPHRAG_API_KEY"] == "sk-ollama"
    assert captured[0]["env"]["GRAPHRAG_API_BASE"] == "http://127.0.0.1:11434/v1"
    assert captured[1]["env"]["GRAPHRAG_API_KEY"] == "sk-ollama"
    assert captured[1]["env"]["GRAPHRAG_API_BASE"] == "http://127.0.0.1:11434/v1"
    assert (
        workspace.root / ".env"
    ).read_text(encoding="utf-8") == "GRAPHRAG_API_KEY=sk-ollama\nGRAPHRAG_API_BASE=http://127.0.0.1:11434/v1\n"


def test_graph_rag_workspace_writes_api_base_into_settings(monkeypatch, tmp_path: Path) -> None:
    workspace = GraphRAGWorkspace(root=tmp_path / "workspace")

    def fake_run(cmd, check, env=None):
        if list(cmd)[:2] == ["graphrag", "init"]:
            workspace.root.mkdir(parents=True, exist_ok=True)
            (workspace.root / ".env").write_text("GRAPHRAG_API_KEY=<API_KEY>\n", encoding="utf-8")
            (workspace.root / "settings.yaml").write_text(
                "\n".join(
                    [
                        "completion_models:",
                        "  default_completion_model:",
                        "    model_provider: openai",
                        "    model: qwen2.5:0.5b",
                        "    auth_method: api_key",
                        "    api_key: ${GRAPHRAG_API_KEY}",
                        "embedding_models:",
                        "  default_embedding_model:",
                        "    model_provider: openai",
                        "    model: nomic-embed-text",
                        "    auth_method: api_key",
                        "    api_key: ${GRAPHRAG_API_KEY}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
        return None

    monkeypatch.delenv("GRAPHRAG_API_KEY", raising=False)
    monkeypatch.delenv("GRAPHRAG_API_BASE", raising=False)
    monkeypatch.delenv("GREV_GRAPHRAG_API_BASE", raising=False)
    monkeypatch.delenv("GREV_RAGAS_BASE_URL", raising=False)
    monkeypatch.setattr("graphrag_ragas_eval.graphrag.workspace.subprocess.run", fake_run)

    ensure_graph_rag_project(workspace, model="qwen2.5:0.5b", embedding="nomic-embed-text", force=True)

    settings = (workspace.root / "settings.yaml").read_text(encoding="utf-8")
    assert "api_base: ${GRAPHRAG_API_BASE}" in settings


def test_sample_docs_3pages_fixture_has_at_least_three_files() -> None:
    sample_dir = Path("examples/sample_docs_3pages")
    assert sample_dir.is_dir()
    assert len([path for path in sample_dir.iterdir() if path.is_file()]) >= 3
