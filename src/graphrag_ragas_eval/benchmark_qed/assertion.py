from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from ..llm import load_llm_runtime_config
from ..upstream_benchmark_qed import (
    build_vendor_model_factory_runtime,
    ensure_autoe_import_shim,
)


@dataclass(frozen=True, slots=True)
class AssertionEvaluationPlan:
    assertion_prep: Path
    answers: Path
    output: Path
    trials: int = 1
    top_k_assertions: int | None = None
    include_score_id_in_prompt: bool = True
    question_id_key: str = "question_id"
    question_text_key: str = "question_text"
    answer_text_key: str = "answer"
    metadata: dict[str, Any] = field(default_factory=dict)


def _read_json_payload(path: Path) -> object:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _coerce_items(payload: object, *, key: str) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        items = payload.get(key, [])
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    return []


def _load_assertion_rows(path: Path) -> pd.DataFrame:
    payload = _read_json_payload(path)
    items = _coerce_items(payload, key="questions")

    rows: list[dict[str, Any]] = []
    for item in items:
        question_id = str(
            item.get("question_id") or item.get("sample_id") or item.get("id") or ""
        )
        question_text = str(
            item.get("question_text") or item.get("question") or item.get("text") or ""
        )
        assertions = item.get("assertions", [])
        if not isinstance(assertions, list):
            continue
        for index, assertion in enumerate(assertions):
            if not isinstance(assertion, dict):
                continue
            statement = str(assertion.get("statement") or assertion.get("assertion") or "")
            if not statement:
                continue
            rows.append(
                {
                    "question_id": question_id,
                    "question_text": question_text,
                    "assertion": statement,
                    "rank": int(assertion.get("rank") or index + 1),
                    "score": assertion.get("score"),
                    "reasoning": assertion.get("reasoning"),
                    "source_count": assertion.get("source_count"),
                }
            )

    return pd.DataFrame(rows)


def _load_answer_rows(path: Path) -> pd.DataFrame:
    payload = _read_json_payload(path)
    items = _coerce_items(payload, key="results")

    rows: list[dict[str, Any]] = []
    for item in items:
        question_id = str(
            item.get("question_id") or item.get("sample_id") or item.get("id") or ""
        )
        question_text = str(
            item.get("question_text") or item.get("question") or item.get("text") or ""
        )
        answer = str(item.get("answer") or item.get("generated_answer") or "")
        if not question_id or not question_text or not answer:
            continue
        rows.append(
            {
                "question_id": question_id,
                "question_text": question_text,
                "answer": answer,
            }
        )

    return pd.DataFrame(rows)


def evaluate_assertion_scores(plan: AssertionEvaluationPlan) -> dict[str, Any]:
    ensure_autoe_import_shim()
    runtime = load_llm_runtime_config(dict(os.environ), prefix="GREV_BENCHMARKQED")
    chat_model, _ = build_vendor_model_factory_runtime(runtime)

    from benchmark_qed.autoe.assertion.aggregation import summarize_standard_scores
    from benchmark_qed.autoe.assertion.standard import get_assertion_scores
    from benchmark_qed.config.llm_config import LLMConfig, LLMProvider

    assertions = _load_assertion_rows(plan.assertion_prep)
    answers = _load_answer_rows(plan.answers)

    llm_config = LLMConfig(
        model=runtime.model,
        api_key=runtime.api_key or "EMPTY",
        llm_provider=LLMProvider.OpenAIChat,
        init_args={"api_base": runtime.base_url or ""},
        call_args={
            "temperature": 0.0,
            "seed": 42,
            **({"max_tokens": runtime.max_tokens} if runtime.max_tokens is not None else {}),
        },
    )

    assertion_scores = get_assertion_scores(
        llm_client=chat_model,
        llm_config=llm_config,
        answers=answers,
        assertions=assertions,
        trials=plan.trials,
        top_k=plan.top_k_assertions,
        include_score_id_in_prompt=plan.include_score_id_in_prompt,
        question_id_key=plan.question_id_key,
        question_text_key=plan.question_text_key,
        answer_text_key=plan.answer_text_key,
    )

    summary_by_assertion, summary_by_question, eval_summary = summarize_standard_scores(
        assertion_scores
    )

    payload = {
        "metadata": {
            "component": "AssertionEvaluation",
            "backend": "benchmark-qed",
            "assertion_prep": str(plan.assertion_prep),
            "answers": str(plan.answers),
            "trials": plan.trials,
            "top_k_assertions": plan.top_k_assertions,
            "include_score_id_in_prompt": plan.include_score_id_in_prompt,
            "question_id_key": plan.question_id_key,
            "question_text_key": plan.question_text_key,
            "answer_text_key": plan.answer_text_key,
            **plan.metadata,
        },
        "scores": assertion_scores.to_dict(orient="records"),
        "summary_by_assertion": summary_by_assertion.to_dict(orient="records"),
        "summary_by_question": summary_by_question.to_dict(orient="records"),
        "aggregate": eval_summary,
    }
    plan.output.parent.mkdir(parents=True, exist_ok=True)
    plan.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
