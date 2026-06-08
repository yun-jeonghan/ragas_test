from __future__ import annotations

import importlib.util
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class Ograg2EvaluationPlan:
    config_file: Path
    results_dir: Path | None = None
    rewrite: bool = False
    force_map_ontology: bool = False
    only_map_ontology: bool = False
    force_create_kg_triples: bool = False
    force_personal_openai: bool = False
    force_personal_openai_emb_only: bool = False
    extra_args: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Ograg2EvaluationResult:
    command: tuple[str, ...]
    cwd: Path
    config_file: Path
    results_dir: Path | None
    returncode: int


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _vendor_root() -> Path:
    return _repo_root() / "vendor" / "ograg2"


def _ensure_qna_dependency() -> None:
    if importlib.util.find_spec("qna") is None:
        raise RuntimeError(
            "ograg2 evaluation requires the external 'qna' package, but it is not installed in this environment."
        )


def run_ograg2_evaluation(plan: Ograg2EvaluationPlan) -> Ograg2EvaluationResult:
    config_file = plan.config_file.resolve()
    if not config_file.exists():
        raise FileNotFoundError(config_file)

    _ensure_qna_dependency()

    vendor_root = _vendor_root()
    command = [
        sys.executable,
        str(vendor_root / "test_answers.py"),
        "--config_file",
        str(config_file),
    ]
    if plan.results_dir is not None:
        command.extend(["--results_dir", str(plan.results_dir)])
    if plan.force_map_ontology:
        command.append("--force_map_ontology")
    if plan.only_map_ontology:
        command.append("--only_map_ontology")
    if plan.force_create_kg_triples:
        command.append("--force_create_kg_triples")
    if plan.force_personal_openai:
        command.append("--force_personal_openai")
    if plan.force_personal_openai_emb_only:
        command.append("--force_personal_openai_emb_only")
    if plan.rewrite:
        command.append("--rewrite")
    command.extend(plan.extra_args)

    completed = subprocess.run(command, cwd=vendor_root, check=True)
    return Ograg2EvaluationResult(
        command=tuple(command),
        cwd=vendor_root,
        config_file=config_file,
        results_dir=plan.results_dir,
        returncode=completed.returncode,
    )
