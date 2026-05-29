from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..generation.builder import GenerationMode, QuestionGenerationPlan, generate_questions as _generate_questions


@dataclass(frozen=True, slots=True)
class AutoQPlan:
    source: Path
    output: Path
    num_questions: int = 10
    modes: tuple[GenerationMode, ...] = (GenerationMode.LOCAL, GenerationMode.GLOBAL)
    metadata: dict[str, Any] = field(default_factory=dict)


def generate_queries(plan: AutoQPlan):
    generation_plan = QuestionGenerationPlan(
        source=plan.source,
        output=plan.output,
        num_questions=plan.num_questions,
        modes=plan.modes,
        subrepo_name="benchmark-qed",
        metadata=plan.metadata,
    )
    return _generate_questions(generation_plan)

