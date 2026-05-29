from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from .graphrag.workspace import GraphRAGWorkspace

logger = logging.getLogger(__name__)

STANDARD_RELATION_LABELS: tuple[str, ...] = (
    "is_a",
    "part_of",
    "located_in",
    "causes",
    "uses",
    "associated_with",
    "same_as",
)

_ENTITY_TEMPLATE_NAME = "entity_extraction.txt"
_RELATIONSHIP_TEMPLATE_NAME = "relationship_extraction.txt"
_NL = chr(10)


@dataclass(frozen=True, slots=True)
class UserOntology:
    path: Path
    allowed_types: tuple[str, ...]
    extraction_rules: dict[str, Any]


def load_user_ontology(
    workspace: GraphRAGWorkspace,
    *,
    ontology_path: Path | None = None,
) -> UserOntology | None:
    path = ontology_path or workspace.config_dir / "user_ontology.json"
    if not path.exists():
        logger.info("user ontology not found at %s; skipping dynamic schema injection", path)
        return None

    payload = json.loads(path.read_text(encoding="utf-8"))
    allowed_types = tuple(
        str(item).strip()
        for item in payload.get("allowed_types", [])
        if str(item).strip()
    )
    extraction_rules = payload.get("extraction_rules", {})
    if not isinstance(extraction_rules, dict):
        logger.warning(
            "user ontology extraction_rules should be a mapping; got %s at %s",
            type(extraction_rules).__name__,
            path,
        )
        extraction_rules = {"raw": extraction_rules}

    logger.info(
        "loaded user ontology from %s with %d allowed types and %d extraction rules",
        path,
        len(allowed_types),
        len(extraction_rules),
    )
    return UserOntology(path=path, allowed_types=allowed_types, extraction_rules=extraction_rules)


def _format_rules(extraction_rules: dict[str, Any]) -> str:
    if not extraction_rules:
        return "- (no custom extraction rules provided)"
    lines: list[str] = []
    for key, value in extraction_rules.items():
        if isinstance(value, (dict, list, tuple)):
            rendered = json.dumps(value, ensure_ascii=False, indent=2)
            lines.append(f"- {key}:")
            lines.extend(f"  {line}" for line in rendered.splitlines())
        else:
            lines.append(f"- {key}: {value}")
    return _NL.join(lines)


def build_entity_system_role(ontology: UserOntology | None) -> str:
    allowed_types = ontology.allowed_types if ontology else ()
    extraction_rules = ontology.extraction_rules if ontology else {}
    allowed_type_block = (
        _NL.join(f"- {item}" for item in allowed_types)
        if allowed_types
        else "- (no custom ontology file found; use GraphRAG defaults)"
    )
    return _NL.join(
        [
            "You are an information extraction system for GraphRAG.",
            "Keep extracted entities grounded in the source text and avoid inventing unsupported types.",
            "System constraints:",
            allowed_type_block,
            "Extraction rules:",
            _format_rules(extraction_rules),
            "Return entity candidates that match the ontology when available.",
        ]
    )


def build_relationship_system_role(
    ontology: UserOntology | None,
    relation_labels: Sequence[str] = STANDARD_RELATION_LABELS,
) -> str:
    allowed_types = ontology.allowed_types if ontology else ()
    extraction_rules = ontology.extraction_rules if ontology else {}
    relation_block = _NL.join(f"- {label}" for label in relation_labels)
    allowed_type_block = (
        _NL.join(f"- {item}" for item in allowed_types)
        if allowed_types
        else "- (no custom ontology file found; use source-grounded entity types)"
    )
    return _NL.join(
        [
            "You are a relation extraction and normalization system for GraphRAG.",
            "Normalize every discovered relation into exactly one canonical label.",
            "The only legal relation labels are:",
            relation_block,
            "Constraint: map every discovered relation verb or phrase to one and only one of the seven labels above.",
            "Do not invent labels outside this set.",
            "Entity type context:",
            allowed_type_block,
            "Extraction rules:",
            _format_rules(extraction_rules),
            "Prefer the most specific canonical relation label available.",
        ]
    )


def _replace_system_role_block(template_text: str, new_system_role: str) -> str:
    lines = template_text.splitlines()
    start = None
    end = None
    for index, line in enumerate(lines):
        normalized = line.strip().lower()
        if "system role" in normalized:
            start = index
            for cursor in range(index + 1, len(lines)):
                candidate = lines[cursor].strip().lower()
                if candidate.startswith("### ") or candidate.startswith("## ") or candidate.startswith("# "):
                    if "system role" not in candidate:
                        end = cursor
                        break
                if candidate in {"user role", "assistant role", "task", "instructions"}:
                    end = cursor
                    break
            if end is None:
                end = len(lines)
            break
    if start is None:
        return _NL.join(["### System Role", new_system_role, "", template_text.lstrip()])
    prefix = lines[: start + 1]
    suffix = lines[end:]
    rebuilt = prefix + new_system_role.splitlines() + [""] + suffix
    return _NL.join(rebuilt).strip() + _NL


def _write_prompt_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + _NL, encoding="utf-8")


def materialize_graph_rag_prompts(
    workspace: GraphRAGWorkspace,
    *,
    ontology_path: Path | None = None,
    relation_labels: Sequence[str] = STANDARD_RELATION_LABELS,
) -> list[Path]:
    ontology = load_user_ontology(workspace, ontology_path=ontology_path)
    workspace.prompts_dir.mkdir(parents=True, exist_ok=True)

    entity_prompt_path = workspace.prompts_dir / _ENTITY_TEMPLATE_NAME
    relationship_prompt_path = workspace.prompts_dir / _RELATIONSHIP_TEMPLATE_NAME

    entity_base = (
        entity_prompt_path.read_text(encoding="utf-8")
        if entity_prompt_path.exists()
        else "### System Role" + _NL + _NL + "### User Role" + _NL + "Extract entities from the input text." + _NL
    )
    relationship_base = (
        relationship_prompt_path.read_text(encoding="utf-8")
        if relationship_prompt_path.exists()
        else "### System Role" + _NL + _NL + "### User Role" + _NL + "Extract relationships from the input text." + _NL
    )

    entity_rendered = _replace_system_role_block(entity_base, build_entity_system_role(ontology))
    relationship_rendered = _replace_system_role_block(
        relationship_base,
        build_relationship_system_role(ontology, relation_labels=relation_labels),
    )

    _write_prompt_file(entity_prompt_path, entity_rendered)
    _write_prompt_file(relationship_prompt_path, relationship_rendered)

    logger.info(
        "materialized GraphRAG prompts at %s and %s",
        entity_prompt_path,
        relationship_prompt_path,
    )
    if ontology is not None:
        logger.info("applied ontology-driven prompt injection from %s", ontology.path)
    logger.info("relationship labels limited to: %s", ", ".join(relation_labels))
    return [entity_prompt_path, relationship_prompt_path]
