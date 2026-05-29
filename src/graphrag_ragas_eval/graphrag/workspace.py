from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

SUPPORTED_INPUT_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".pdf"}


@dataclass(frozen=True, slots=True)
class GraphRAGWorkspace:
    root: Path

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


def stage_documents(source_dir: Path, workspace: GraphRAGWorkspace, *, clean: bool = False) -> list[Path]:
    if not source_dir.exists():
        raise FileNotFoundError(source_dir)
    if clean and workspace.input_dir.exists():
        shutil.rmtree(workspace.input_dir)
    workspace.root.mkdir(parents=True, exist_ok=True)
    workspace.input_dir.mkdir(parents=True, exist_ok=True)

    staged: list[Path] = []
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_INPUT_EXTENSIONS:
            continue
        target = workspace.input_dir / _safe_relative_name(path, source_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        staged.append(target)
        if path.suffix.lower() == ".pdf":
            extracted = _extract_pdf_text(path)
            if extracted.strip():
                txt_target = target.with_suffix(".txt")
                txt_target.write_text(extracted, encoding="utf-8")
                staged.append(txt_target)
    return staged


def _extract_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    pages: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            pages.append(text.strip())
    return "\n\n".join(pages)


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
