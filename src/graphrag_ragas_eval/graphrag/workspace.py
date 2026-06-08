from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..config import DEFAULT_CHAT_MODEL, DEFAULT_EMBEDDING_MODEL
from ..ingest import PdfExtractionPolicy, load_pdf_extraction_policy, normalize_source_tree


@dataclass(frozen=True, slots=True)
class GraphRAGWorkspace:
    root: Path

    @property
    def source_dir(self) -> Path:
        return self.root / "source"

    @property
    def canonical_dir(self) -> Path:
        return self.root / "canonical"

    @property
    def manifests_dir(self) -> Path:
        return self.root / "manifests"

    @property
    def input_dir(self) -> Path:
        return self.root / "input"

    @property
    def output_dir(self) -> Path:
        return self.root / "output"

    @property
    def prompts_dir(self) -> Path:
        return self.root / "prompts"

    @property
    def config_dir(self) -> Path:
        return self.root / "config"

    @property
    def settings_path(self) -> Path:
        return self.root / "settings.yaml"


def _resolve_graphrag_api_key() -> str:
    """Resolve the key GraphRAG should see for init/index runs.

    GraphRAG's generated config always points at ${GRAPHRAG_API_KEY}. When
    that variable is missing, its config loader falls back to the literal
    placeholder from the generated .env file, which then bubbles up as
    "<API_KEY>" in LiteLLM errors. Prefer an explicitly provided key, but
    fall back to the local Ollama-compatible default so the wrapper works
    out of the box on this repo's smoke tests.
    """

    for name in (
        "GRAPHRAG_API_KEY",
        "GREV_GRAPHRAG_API_KEY",
        "GREV_RAGAS_API_KEY",
        "GREV_BENCHMARKQED_API_KEY",
        "GREV_KGGEN_MINE_API_KEY",
    ):
        value = os.environ.get(name)
        if value:
            return value
    return "sk-ollama"


def _resolve_graphrag_api_base() -> str:
    """Resolve the OpenAI-compatible endpoint GraphRAG should call."""

    for name in (
        "GRAPHRAG_API_BASE",
        "GREV_GRAPHRAG_API_BASE",
        "GREV_RAGAS_BASE_URL",
        "GREV_BENCHMARKQED_BASE_URL",
        "GREV_KGGEN_MINE_BASE_URL",
    ):
        value = os.environ.get(name)
        if value:
            return value
    return "http://127.0.0.1:11434/v1"


def _graph_rag_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    env["GRAPHRAG_API_KEY"] = _resolve_graphrag_api_key()
    env["GRAPHRAG_API_BASE"] = _resolve_graphrag_api_base()
    return env


def _write_graph_rag_env_file(workspace: GraphRAGWorkspace, api_key: str) -> None:
    api_base = _resolve_graphrag_api_base()
    dotenv = workspace.root / ".env"
    dotenv.parent.mkdir(parents=True, exist_ok=True)
    if dotenv.exists():
        lines = dotenv.read_text(encoding="utf-8").splitlines()
    else:
        lines = []

    updated: list[str] = []
    replaced = False
    for line in lines:
        if line.startswith("GRAPHRAG_API_KEY="):
            updated.append(f"GRAPHRAG_API_KEY={api_key}")
            replaced = True
        elif line.startswith("GRAPHRAG_API_BASE="):
            updated.append(f"GRAPHRAG_API_BASE={api_base}")
        else:
            updated.append(line)
    if not replaced:
        updated.append(f"GRAPHRAG_API_KEY={api_key}")
    if not any(line.startswith("GRAPHRAG_API_BASE=") for line in updated):
        updated.append(f"GRAPHRAG_API_BASE={api_base}")

    dotenv.write_text("\n".join(updated).rstrip() + "\n", encoding="utf-8", errors="strict")


def _write_graph_rag_settings_file(workspace: GraphRAGWorkspace) -> None:
    settings = workspace.settings_path
    if not settings.exists():
        return

    lines = settings.read_text(encoding="utf-8").splitlines()
    updated: list[str] = []
    in_completion = False
    in_embedding = False
    completion_api_base_written = False
    embedding_api_base_written = False

    for line in lines:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))

        if stripped.startswith("completion_models:"):
            in_completion = True
            in_embedding = False
            updated.append(line)
            continue
        if stripped.startswith("embedding_models:"):
            in_completion = False
            in_embedding = True
            updated.append(line)
            continue

        if in_completion and indent >= 4 and stripped.startswith("auth_method:") and not completion_api_base_written:
            updated.append(line)
            updated.append("    api_base: ${GRAPHRAG_API_BASE}")
            completion_api_base_written = True
            continue

        if in_embedding and indent >= 4 and stripped.startswith("auth_method:") and not embedding_api_base_written:
            updated.append(line)
            updated.append("    api_base: ${GRAPHRAG_API_BASE}")
            embedding_api_base_written = True
            continue

        updated.append(line)

    settings.write_text("\n".join(updated).rstrip() + "\n", encoding="utf-8", errors="strict")


def _safe_relative_name(path: Path, base_dir: Path) -> str:
    relative = path.relative_to(base_dir)
    return "__".join(relative.parts)


def stage_documents(
    source_dir: Path,
    workspace: GraphRAGWorkspace,
    *,
    clean: bool = False,
    pdf_policy: PdfExtractionPolicy | None = None,
) -> list[Path]:
    """Normalize a mixed source tree and stage the canonical TXT files for GraphRAG."""

    if not source_dir.exists():
        raise FileNotFoundError(source_dir)
    if clean:
        shutil.rmtree(workspace.input_dir, ignore_errors=True)
        shutil.rmtree(workspace.canonical_dir, ignore_errors=True)
        shutil.rmtree(workspace.manifests_dir, ignore_errors=True)
    workspace.root.mkdir(parents=True, exist_ok=True)
    manifest_path = workspace.manifests_dir / "extraction.jsonl"
    normalize_source_tree(
        source_root=source_dir,
        canonical_root=workspace.canonical_dir,
        manifest_path=manifest_path,
        clean=False,
        pdf_policy=pdf_policy or load_pdf_extraction_policy(os.environ),
    )

    if workspace.input_dir.exists():
        shutil.rmtree(workspace.input_dir)
    workspace.input_dir.mkdir(parents=True, exist_ok=True)

    staged: list[Path] = []
    for path in sorted(workspace.canonical_dir.rglob("*.txt")):
        target = workspace.input_dir / _safe_relative_name(path, workspace.canonical_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        staged.append(target)
    return staged


def ensure_graph_rag_project(
    workspace: GraphRAGWorkspace,
    *,
    model: str = DEFAULT_CHAT_MODEL,
    embedding: str = DEFAULT_EMBEDDING_MODEL,
    force: bool = False,
) -> None:
    workspace.root.mkdir(parents=True, exist_ok=True)
    api_key = _resolve_graphrag_api_key()
    api_base = _resolve_graphrag_api_base()
    cmd = [
        "graphrag",
        "init",
        "--root",
        str(workspace.root),
        "--model",
        model,
        "--embedding",
        embedding,
    ]
    if force:
        cmd.append("--force")
    subprocess.run(cmd, check=True, env=_graph_rag_subprocess_env())
    _write_graph_rag_env_file(workspace, api_key)
    _write_graph_rag_settings_file(workspace)


def run_graph_rag_index(
    workspace: GraphRAGWorkspace,
    *,
    method: str = "standard",
    skip_validation: bool = False,
) -> None:
    cmd = [
        "graphrag",
        "index",
        "--root",
        str(workspace.root),
        "--method",
        method,
    ]
    if skip_validation:
        cmd.append("--skip-validation")
    subprocess.run(cmd, check=True, env=_graph_rag_subprocess_env())
