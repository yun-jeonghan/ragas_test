from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

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
    model: str = "gpt-4.1",
    embedding: str = "text-embedding-3-large",
    force: bool = False,
) -> None:
    workspace.root.mkdir(parents=True, exist_ok=True)
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
    subprocess.run(cmd, check=True)


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
    subprocess.run(cmd, check=True)
