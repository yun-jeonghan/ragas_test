from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


METRIC_DESCRIPTIONS: dict[str, str] = {
    "context_precision": "검색된 컨텍스트 중 답변에 실제로 도움이 되는 비율",
    "context_recall": "정답을 뒷받침하는 컨텍스트를 얼마나 빠짐없이 찾았는지",
    "faithfulness": "답변이 검색 컨텍스트에 얼마나 충실한지",
    "answer_relevancy": "질문과 답변이 얼마나 직접적으로 연결되는지",
}


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload
    return {"value": payload}


def _escape_json(value: Any) -> str:
    return html.escape(json.dumps(value, ensure_ascii=False, indent=2))


def _format_metric_value(value: Any) -> str:
    if isinstance(value, (int, float)):
        number = float(value)
        if abs(number - round(number)) < 1e-9:
            return f"{number:.0f}"
        return f"{number:.6f}".rstrip("0").rstrip(".")
    return html.escape(str(value))


def _truncate_text(value: Any, limit: int = 180) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return html.escape(text)
    return html.escape(text[: max(0, limit - 1)].rstrip()) + "&hellip;"


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _details(summary: str, body_html: str, *, open_: bool = False, class_name: str = "") -> str:
    attrs = " open" if open_ else ""
    class_attr = f' class="{class_name}"' if class_name else ""
    return f"""
      <details{class_attr}{attrs}>
        <summary>{html.escape(summary)}</summary>
        {body_html}
      </details>
    """


def _metric_description(metric_name: str) -> str:
    return METRIC_DESCRIPTIONS.get(metric_name, "평가 항목 설명이 아직 등록되지 않았습니다.")


def _chip(label: str, value: Any) -> str:
    return f'<span class="chip"><span>{html.escape(label)}</span><strong>{html.escape(str(value))}</strong></span>'


def _metric_card(metric_name: str, value: Any) -> str:
    return f"""
      <article class="metric-card">
        <div class="metric-title">{html.escape(metric_name)}</div>
        <div class="metric-value">{_format_metric_value(value)}</div>
        <p class="metric-desc">{html.escape(_metric_description(metric_name))}</p>
      </article>
    """


def _render_metric_chart(aggregate: dict[str, Any]) -> str:
    if not aggregate:
        return '<p class="small">No aggregate metrics were found.</p>'

    items = list(aggregate.items())
    max_value = max((float(value) for _, value in items), default=1.0) or 1.0
    bar_width = 110
    chart_height = 220
    chart_width = max(340, 60 + bar_width * len(items))

    bars: list[str] = []
    for index, (metric_name, value) in enumerate(items):
        number = max(0.0, float(value))
        bar_height = int((number / max_value) * 120) if max_value else 0
        x = 40 + index * bar_width
        y = 145 - bar_height
        bars.append(
            f"""
              <g>
                <rect x="{x}" y="{y}" width="66" height="{bar_height}" rx="12" fill="url(#barGradient)" />
                <text x="{x + 33}" y="{y - 8}" text-anchor="middle" class="chart-value">{_format_metric_value(value)}</text>
                <text x="{x + 33}" y="182" text-anchor="middle" class="chart-label">{html.escape(metric_name.replace('_', ' '))}</text>
              </g>
            """
        )

    return f"""
      <div class="chart-wrap">
        <svg viewBox="0 0 {chart_width} {chart_height}" role="img" aria-label="Aggregate metric bar chart">
          <defs>
            <linearGradient id="barGradient" x1="0%" x2="0%" y1="0%" y2="100%">
              <stop offset="0%" stop-color="#4e7cff" />
              <stop offset="100%" stop-color="#1743d1" />
            </linearGradient>
          </defs>
          <line x1="24" y1="145" x2="{chart_width - 18}" y2="145" class="chart-axis" />
          {''.join(bars)}
        </svg>
      </div>
    """


def _artifact_card(title: str, bullets: list[str], payload: dict[str, Any]) -> str:
    bullet_html = "".join(f"<li>{html.escape(str(bullet))}</li>" for bullet in bullets if bullet)
    return f"""
      <article class="artifact-card">
        <h3>{html.escape(title)}</h3>
        <ul class="bullet-list">{bullet_html or '<li class="small">No summary available.</li>'}</ul>
        {_details("Full JSON view", f"<pre>{_escape_json(payload)}</pre>")}
      </article>
    """


def _assertion_prep_bullets(assertion_data: dict[str, Any]) -> list[str]:
    questions = _safe_list(assertion_data.get("questions"))
    stats = _safe_dict(assertion_data.get("stats"))
    metadata = _safe_dict(assertion_data.get("metadata"))
    total_assertions = int(stats.get("total_assertions") or 0)
    valid_assertions = int(stats.get("valid_assertions") or 0)
    bullets = [
        f"{len(questions)} question(s) with assertions.",
        f"{total_assertions} total assertion(s).",
        (
            f"Validation: {'on' if metadata.get('validation_enabled') else 'off'}"
            + (
                f" (min score {metadata.get('min_validation_score')}/5)"
                if metadata.get("validation_enabled") is not None
                else ""
            )
        ),
    ]
    if valid_assertions or total_assertions:
        bullets.append(f"{valid_assertions} valid assertion(s) recorded.")
    else:
        bullets.append("No valid assertions were recorded.")
    return bullets


def _question_assertion_stats(autoq_questions: list[dict[str, Any]]) -> dict[str, int]:
    claim_count = 0
    assertion_count = 0
    questions_with_assertions = 0
    for question in autoq_questions:
        attributes = _safe_dict(question.get("attributes"))
        claim_count += int(attributes.get("claim_count") or 0)
        assertion_count += int(attributes.get("assertion_count") or 0)
        if int(attributes.get("assertion_count") or 0) > 0:
            questions_with_assertions += 1
    return {
        "claim_count": claim_count,
        "assertion_count": assertion_count,
        "questions_with_assertions": questions_with_assertions,
        "question_count": len(autoq_questions),
    }


def _score_row(score: dict[str, Any]) -> str:
    metadata = _safe_dict(score.get("metadata"))
    return f"""
      <tr>
        <td>{html.escape(str(score.get("sample_id", "")))}</td>
        <td>{html.escape(str(score.get("metric_name", "")))}</td>
        <td>{_format_metric_value(score.get("value"))}</td>
        <td>{html.escape(str(metadata.get("question", "")))}</td>
        <td>{html.escape(str(metadata.get("search_mode", "")))}</td>
        <td title="{html.escape(str(score.get('reason') or ''))}">{_truncate_text(score.get("reason") or "No reason provided.", 120)}</td>
      </tr>
    """


def _score_detail(score: dict[str, Any]) -> str:
    metadata = _safe_dict(score.get("metadata"))
    reason = score.get("reason") or "No reason provided."
    detail_body = f"""
      <div class="detail-grid">
        <div><span>Metric</span><strong>{html.escape(str(score.get("metric_name", "")))}</strong></div>
        <div><span>Sample</span><strong>{html.escape(str(score.get("sample_id", "")))}</strong></div>
        <div><span>Question</span><strong>{html.escape(str(metadata.get("question", "")))}</strong></div>
        <div><span>Search mode</span><strong>{html.escape(str(metadata.get("search_mode", "")))}</strong></div>
      </div>
      <div class="note compact">
        <strong>Metric guide:</strong> {html.escape(_metric_description(str(score.get("metric_name", ""))))}
      </div>
      <div class="stack">
        <div class="block">
          <h4>Reason</h4>
          <pre>{html.escape(str(reason))}</pre>
        </div>
        <div class="block">
          <h4>Metadata</h4>
          <pre>{_escape_json(metadata)}</pre>
        </div>
      </div>
    """
    return _details(
        f"{score.get('sample_id', '')} · {score.get('metric_name', '')} · {score.get('value', '')}",
        detail_body,
        class_name="detail-card",
    )


def _assertion_score_row(score: dict[str, Any]) -> str:
    metadata = _safe_dict(score.get("metadata"))
    question_id = score.get("question_id") or metadata.get("question_id") or ""
    question = score.get("question") or metadata.get("question") or score.get("question_text") or ""
    assertion = score.get("assertion") or score.get("statement") or ""
    reason = score.get("reason") or score.get("reasoning") or score.get("explanation") or ""
    return f"""
      <tr>
        <td>{html.escape(str(question_id))}</td>
        <td>{html.escape(str(question))}</td>
        <td>{html.escape(str(assertion))}</td>
        <td>{_format_metric_value(score.get("score") or score.get("value"))}</td>
        <td title="{html.escape(str(reason or ''))}">{_truncate_text(reason or 'No reason provided.', 120)}</td>
      </tr>
    """


def _context_preview(contexts: list[dict[str, Any]]) -> str:
    if not contexts:
        return '<p class="small">No retrieved contexts were saved for this sample.</p>'
    items = []
    for context in contexts[:3]:
        source = html.escape(str(context.get("source", "")))
        text = _truncate_text(context.get("text") or "", 220)
        items.append(f'<li><span class="source">{source}</span><span class="excerpt">{text}</span></li>')
    return f'<ul class="context-preview">{"".join(items)}</ul>'


def _result_card(result: dict[str, Any]) -> str:
    contexts = _safe_list(result.get("retrieved_contexts"))
    context_dicts = [context for context in contexts if isinstance(context, dict)]
    answer = result.get("answer") or ""
    metadata = _safe_dict(result.get("metadata"))
    body = f"""
      <div class="detail-grid">
        <div><span>Sample</span><strong>{html.escape(str(result.get("sample_id", "")))}</strong></div>
        <div><span>Search mode</span><strong>{html.escape(str(result.get("search_mode", "")))}</strong></div>
      </div>
      <div class="result-answer">
        <span>Answer</span>
        <p>{html.escape(str(answer))}</p>
      </div>
      <div class="result-preview">
        <h4>Retrieved context preview</h4>
        {_context_preview(context_dicts)}
      </div>
      {_details("Full retrieved_contexts JSON", f'<pre>{_escape_json(context_dicts)}</pre>')}
      {_details("Full result metadata", f'<pre>{_escape_json(metadata)}</pre>')}
    """
    return f"""
      <article class="result-card">
        <header>
          <h3>{html.escape(str(result.get("sample_id", "")))}</h3>
          <p>{html.escape(str(result.get("question", "")))}</p>
        </header>
        {body}
      </article>
    """


def _fallback_interpretation(
    *,
    aggregate: dict[str, Any],
    scores: list[dict[str, Any]],
    autod_data: dict[str, Any] | None,
    autoq_data: dict[str, Any] | None,
    report_metadata: dict[str, Any] | None,
) -> str:
    model = (report_metadata or {}).get("chat_model") or (report_metadata or {}).get("model") or "qwen2.5:0.5b"
    provider = (report_metadata or {}).get("provider") or "ollama"
    base_url = (report_metadata or {}).get("base_url") or "http://127.0.0.1:11434/v1"
    sample_count = len(scores)
    metric_count = len(aggregate)
    question_count = len(_safe_list((autoq_data or {}).get("questions")))
    document_count = len(_safe_list((autod_data or {}).get("documents")))
    themes = _safe_list((autod_data or {}).get("themes"))
    lines = [
        f"Model lens: {model} via {provider} ({base_url}).",
        f"This is a smoke run, so {sample_count} score row(s) and {metric_count} aggregate metric(s) should be read as a sanity check rather than a benchmark.",
    ]
    if aggregate:
        for metric_name, value in aggregate.items():
            lines.append(
                f"{metric_name} = {_format_metric_value(value)}. {_metric_description(metric_name)}."
            )
    if autod_data:
        summary = _safe_dict(autod_data.get("benchmark_qed"))
        if summary.get("summary"):
            lines.append(
                "AutoD produced a corpus summary and benchmark_qed summary, which means the document-side path is wired up correctly."
            )
        if document_count:
            lines.append(
                f"AutoD covered {document_count} document(s) and {len(themes)} theme(s)."
            )
    if autoq_data:
        autoq_questions = [
            question for question in _safe_list(autoq_data.get("questions")) if isinstance(question, dict)
        ]
        stats = _question_assertion_stats(autoq_questions)
        lines.append(
            f"AutoQ reported {question_count} question(s); if this is lower than expected, treat it as a generation coverage issue rather than an evaluation failure."
        )
        if stats["claim_count"] or stats["assertion_count"]:
            lines.append(
                "AutoQ claim/assertion coverage: "
                f"{stats['claim_count']} claim(s), {stats['assertion_count']} assertion(s) "
                f"across {stats['questions_with_assertions']} question(s) with assertions."
            )
        if stats["claim_count"] and stats["assertion_count"] == 0:
            lines.append(
                "Claims are being produced, but assertions are still empty; that is a useful signal for the global path and should be called out explicitly."
            )
    if (report_metadata or {}).get("assertion_validation_enabled") is False:
        lines.append(
            "This run used raw assertions with validation disabled, so the next step is to inspect whether assertion generation itself is working before tightening validation thresholds."
        )
    lines.append(
        "If the chat model is qwen2.5:0.5b, this report is best interpreted as a local smoke lens: useful for catching wiring mistakes, not for proving final quality."
    )
    return "\n".join(lines)


def _retrieval_interpretation(
    *,
    reference_data: dict[str, Any] | None,
    retrieval_data: dict[str, Any] | None,
    evaluation_data: dict[str, Any] | None,
    report_metadata: dict[str, Any] | None,
) -> str:
    metadata = report_metadata or {}
    model = metadata.get("chat_model") or metadata.get("model") or "qwen2.5:0.5b"
    provider = metadata.get("provider") or "ollama"
    base_url = metadata.get("base_url") or "http://127.0.0.1:11434/v1"
    reference_count = len(_safe_list((reference_data or {}).get("references")))
    retrieval_count = len(_safe_list((retrieval_data or {}).get("results")))
    summary_rows = len(_safe_list((evaluation_data or {}).get("summary")))
    aggregate = _safe_dict((evaluation_data or {}).get("aggregate"))
    lines = [
        f"Model lens: {model} via {provider} ({base_url}).",
        f"Retrieval smoke is wired if reference rows, prepared retrieval rows, and evaluation rows all appear together.",
    ]
    lines.append(f"Reference rows: {reference_count}.")
    lines.append(f"Prepared retrieval rows: {retrieval_count}.")
    lines.append(f"Evaluation summary rows: {summary_rows}.")
    if aggregate:
        for metric_name, value in aggregate.items():
            lines.append(f"{metric_name} = {_format_metric_value(value)}. {_metric_description(metric_name)}.")
    if retrieval_count == 0:
        lines.append("No retrieval rows were prepared, so the scoring path cannot be trusted yet.")
    if reference_count == 0:
        lines.append("No retrieval references were generated, so the benchmark-side reference path is still missing.")
    if not aggregate:
        lines.append("No aggregate retrieval metrics were found.")
    return "\n".join(lines)


def _assertion_interpretation(
    *,
    assertion_data: dict[str, Any] | None,
    report_metadata: dict[str, Any] | None,
) -> str:
    metadata = report_metadata or {}
    model = metadata.get("chat_model") or metadata.get("model") or "qwen2.5:0.5b"
    provider = metadata.get("provider") or "ollama"
    base_url = metadata.get("base_url") or "http://127.0.0.1:11434/v1"
    scores = _safe_list((assertion_data or {}).get("scores"))
    summary_by_assertion = _safe_list((assertion_data or {}).get("summary_by_assertion"))
    summary_by_question = _safe_list((assertion_data or {}).get("summary_by_question"))
    aggregate = _safe_dict((assertion_data or {}).get("aggregate"))
    lines = [
        f"Model lens: {model} via {provider} ({base_url}).",
        "Assertion smoke is wired if score rows, assertion summaries, and per-question summaries all appear together.",
    ]
    lines.append(f"Score rows: {len(scores)}.")
    lines.append(f"Assertion summary rows: {len(summary_by_assertion)}.")
    lines.append(f"Question summary rows: {len(summary_by_question)}.")
    if aggregate:
        for metric_name, value in aggregate.items():
            lines.append(f"{metric_name} = {_format_metric_value(value)}.")
    if not scores:
        lines.append("No assertion score rows were found.")
    if not summary_by_assertion:
        lines.append("No assertion summary rows were found.")
    if not summary_by_question:
        lines.append("No per-question assertion summary rows were found.")
    return "\n".join(lines)


def render_smoke_report(
    evaluation: Path,
    output: Path,
    *,
    title: str = "GraphRAG + Ragas Smoke Report",
    generated_questions: Path | None = None,
    autod_summary: Path | None = None,
    autoq_questions: Path | None = None,
    assertion_prep: Path | None = None,
    assertion_scores: Path | None = None,
    retrieval_results: Path | None = None,
    report_metadata: dict[str, Any] | None = None,
    interpretation: str | None = None,
) -> str:
    evaluation_data = _load_json(evaluation)
    generated_data = _load_json(generated_questions) if generated_questions else None
    autod_data = _load_json(autod_summary) if autod_summary else None
    autoq_data = _load_json(autoq_questions) if autoq_questions else None
    assertion_data = _load_json(assertion_prep) if assertion_prep else None
    assertion_scores_data = _load_json(assertion_scores) if assertion_scores else None
    retrieval_data = _load_json(retrieval_results) if retrieval_results else None

    scores = _safe_list(evaluation_data.get("scores"))
    results = _safe_list(evaluation_data.get("results"))
    aggregate = _safe_dict(evaluation_data.get("aggregate"))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    report_metadata = report_metadata or {}
    interpretation_text = interpretation or _fallback_interpretation(
        aggregate=aggregate,
        scores=[score for score in scores if isinstance(score, dict)],
        autod_data=autod_data,
        autoq_data=autoq_data,
        report_metadata=report_metadata,
    )

    runtime_chips = []
    if report_metadata.get("chat_model"):
        runtime_chips.append(_chip("chat model", report_metadata["chat_model"]))
    if report_metadata.get("provider"):
        runtime_chips.append(_chip("provider", report_metadata["provider"]))
    if report_metadata.get("embeddings_model"):
        runtime_chips.append(_chip("embeddings", report_metadata["embeddings_model"]))
    if report_metadata.get("base_url"):
        runtime_chips.append(_chip("endpoint", report_metadata["base_url"]))
    if report_metadata.get("assertion_validation_enabled") is not None:
        runtime_chips.append(
            _chip(
                "assertions",
                "raw" if not report_metadata.get("assertion_validation_enabled") else "validated",
            )
        )

    overview_cards = [
        _metric_card("scores", len(scores)),
        _metric_card("results", len(results)),
        _metric_card("aggregate metrics", len(aggregate)),
    ]
    if autod_data:
        overview_cards.append(_metric_card("documents", len(_safe_list(autod_data.get("documents")))))
        overview_cards.append(_metric_card("themes", len(_safe_list(autod_data.get("themes")))))
    if autoq_data:
        overview_cards.append(_metric_card("questions", len(_safe_list(autoq_data.get("questions")))))
    if assertion_data:
        overview_cards.append(_metric_card("assertions", len(_safe_list(assertion_data.get("questions")))))
    if assertion_scores_data:
        overview_cards.append(_metric_card("assertion scores", len(_safe_list(assertion_scores_data.get("scores")))))

    aggregate_cards = [_metric_card(metric_name, value) for metric_name, value in aggregate.items()]
    score_rows = "\n".join(_score_row(score) for score in scores if isinstance(score, dict))
    score_details = "\n".join(_score_detail(score) for score in scores if isinstance(score, dict))
    result_cards = "\n".join(_result_card(result) for result in results if isinstance(result, dict))

    autod_bq = _safe_dict((autod_data or {}).get("benchmark_qed"))
    autod_documents = _safe_list((autod_data or {}).get("documents"))
    autod_themes = _safe_list((autod_data or {}).get("themes"))
    autoq_questions_payload = _safe_list((autoq_data or {}).get("questions"))
    autoq_assertion_stats = _question_assertion_stats(
        [question for question in autoq_questions_payload if isinstance(question, dict)]
    )

    autod_bullets = [
        f"{len(autod_documents)} document(s) summarized.",
        f"{len(autod_themes)} theme(s) extracted.",
        autod_data.get("corpus_summary") if autod_data else None,
        autod_bq.get("summary") if autod_bq else None,
    ] if autod_data else []

    autoq_bullets = [
        f"{len(autoq_questions_payload)} question(s) generated.",
        f"Modes: {', '.join(map(str, _safe_list((autoq_data or {}).get('metadata', {}).get('modes')))) or 'not recorded'}.",
        f"Claims: {autoq_assertion_stats['claim_count']}; assertions: {autoq_assertion_stats['assertion_count']}.",
        (
            "Assertions were not populated for this run, so global coverage remains the next thing to tighten."
            if autoq_assertion_stats["assertion_count"] == 0 and autoq_assertion_stats["claim_count"] > 0
            else f"Questions with assertions: {autoq_assertion_stats['questions_with_assertions']}."
        ),
        (
            f"First question: {autoq_questions_payload[0].get('question')}"
            if autoq_questions_payload and isinstance(autoq_questions_payload[0], dict)
            else "No question payload was returned."
        ),
    ] if autoq_data else []

    autoe_bullets = [
        f"{len(scores)} score row(s) across {len(aggregate)} metric(s).",
        f"Results rows: {len(results)}.",
        (
            f"Top metric: {max(aggregate.items(), key=lambda item: float(item[1]))[0]} = {_format_metric_value(max(aggregate.values(), key=lambda value: float(value)))}"
            if aggregate
            else "No aggregate metrics were found."
        ),
    ]
    benchmarkqed_alert = ""
    if assertion_data:
        assertion_stats = _safe_dict(assertion_data.get("stats"))
        total_assertions = int(assertion_stats.get("total_assertions") or 0)
        valid_assertions = int(assertion_stats.get("valid_assertions") or 0)
        if total_assertions == 0:
            benchmarkqed_alert = (
                '<div class="note warning" style="margin-top: 14px;">'
                "Assertion generation did not yield any usable assertions in this run."
                " That means the BenchmarkQED side is still only partially wired for this dataset."
                "</div>"
            )
        elif valid_assertions == 0:
            benchmarkqed_alert = (
                '<div class="note warning" style="margin-top: 14px;">'
                "Assertions were generated, but none were validated as usable."
                " Check the assertion scoring and filtering path."
                "</div>"
            )
    assertion_scores_alert = ""
    if assertion_scores_data and len(_safe_list(assertion_scores_data.get("scores"))) == 0:
        assertion_scores_alert = (
            '<div class="note warning" style="margin-top: 14px;">'
            "Assertion scoring produced no score rows, so the assertion report cannot be trusted yet."
            "</div>"
        )
    retrieval_alert = ""
    if retrieval_data and len(_safe_list(retrieval_data.get("results"))) == 0:
        retrieval_alert = (
            '<div class="note warning" style="margin-top: 14px;">'
            "Retrieval prep produced no rows, so the BenchmarkQED retrieval path is still missing data."
            "</div>"
        )

    artifact_cards = []
    if generated_questions:
        artifact_cards.append(
            _artifact_card(
                "Generated Questions",
                [
                    f"{len(_safe_list((generated_data or {}).get('questions')))} question(s) in the generated payload.",
                    "Open the JSON view for the full sample list.",
                ],
                generated_data or {},
            )
        )
    if retrieval_data:
        artifact_cards.append(
            _artifact_card(
                "Retrieval Prep",
                [
                    f"{len(_safe_list(retrieval_data.get('results')))} retrieval row(s) prepared.",
                    "This normalizes current search results into the vendor retrieval-evaluation shape.",
                ],
                retrieval_data,
            )
        )
    if autod_data:
        artifact_cards.append(_artifact_card("AutoD Summary", autod_bullets, autod_data))
    if autoq_data:
        artifact_cards.append(_artifact_card("AutoQ Questions", autoq_bullets, autoq_data))
    if assertion_data:
        artifact_cards.append(
            _artifact_card(
                "Assertion Prep",
                _assertion_prep_bullets(assertion_data),
                assertion_data,
            )
        )
    if assertion_scores_data:
        artifact_cards.append(
            _artifact_card(
                "Assertion Scores",
                [
                    f"{len(_safe_list(assertion_scores_data.get('scores')))} score row(s) evaluated.",
                    "This evaluates prepared assertions against the answer set.",
                ],
                assertion_scores_data,
            )
        )
    artifact_cards.append(_artifact_card("AutoE Evaluation", autoe_bullets, evaluation_data))

    html_text = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #eef3ff;
      --panel: rgba(255, 255, 255, 0.94);
      --panel-strong: #ffffff;
      --text: #182033;
      --muted: #60708f;
      --accent: #2457ff;
      --accent-soft: #e8efff;
      --border: #d9e0ef;
      --shadow: 0 14px 40px rgba(31, 41, 55, 0.08);
      --success: #0e8b54;
      --warning: #915f00;
    }}
    * {{ box-sizing: border-box; }}
    html, body {{ min-height: 100%; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, "Noto Sans KR", "Helvetica Neue", Arial, sans-serif;
      background:
        radial-gradient(circle at top left, rgba(36, 87, 255, 0.11), transparent 30%),
        linear-gradient(180deg, #eef3ff 0%, #f8fbff 18%, #f8fbff 100%);
      color: var(--text);
      line-height: 1.55;
    }}
    .wrap {{
      max-width: 1220px;
      margin: 0 auto;
      padding: 36px 18px 64px;
    }}
    .hero {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 28px;
      padding: 28px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(10px);
    }}
    .hero h1 {{
      margin: 0 0 10px;
      font-size: clamp(2rem, 4vw, 3rem);
      line-height: 1.08;
      letter-spacing: -0.03em;
    }}
    .subtitle {{
      margin: 0;
      color: var(--muted);
      max-width: 70ch;
    }}
    .chips {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 18px;
    }}
    .chip {{
      display: inline-flex;
      align-items: baseline;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      border: 1px solid rgba(36, 87, 255, 0.12);
      font-size: 0.92rem;
      font-weight: 700;
    }}
    .chip strong {{ font-weight: 800; }}
    main {{
      margin-top: 22px;
      display: grid;
      gap: 18px;
    }}
    section, .panel {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 22px;
      padding: 22px;
      box-shadow: var(--shadow);
    }}
    h2 {{
      margin: 0 0 14px;
      font-size: 1.28rem;
      letter-spacing: -0.02em;
    }}
    h3 {{
      margin: 0 0 10px;
      font-size: 1.02rem;
      letter-spacing: -0.01em;
    }}
    h4 {{
      margin: 0 0 8px;
      font-size: 0.96rem;
    }}
    p {{ margin-top: 0; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 14px;
    }}
    .wide-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 14px;
    }}
    .metric-card, .artifact-card, .result-card, .score-card {{
      background: var(--panel-strong);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 16px;
    }}
    .metric-title {{
      color: var(--muted);
      font-size: 0.9rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .metric-value {{
      margin-top: 6px;
      font-size: 1.8rem;
      font-weight: 900;
      letter-spacing: -0.03em;
    }}
    .metric-desc {{
      margin: 8px 0 0;
      color: var(--muted);
      font-size: 0.92rem;
    }}
    .note {{
      border-left: 4px solid var(--accent);
      background: #f5f8ff;
      padding: 14px 16px;
      border-radius: 14px;
      color: #26314a;
    }}
    .note.compact {{ padding: 12px 14px; }}
    .note strong {{ color: var(--text); }}
    .small {{ color: var(--muted); font-size: 0.92rem; }}
    .bullet-list {{
      margin: 0;
      padding-left: 20px;
      color: var(--text);
    }}
    .bullet-list li + li {{ margin-top: 6px; }}
    .table-wrap {{
      overflow-x: auto;
      border: 1px solid var(--border);
      border-radius: 16px;
      background: white;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 860px;
    }}
    th, td {{
      border-bottom: 1px solid var(--border);
      padding: 12px 10px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      position: sticky;
      top: 0;
      background: #f3f6ff;
      color: #31426b;
      font-size: 0.92rem;
      z-index: 1;
    }}
    tr:last-child td {{ border-bottom: none; }}
    pre {{
      margin: 0;
      padding: 14px;
      border-radius: 14px;
      background: #0f172a;
      color: #d8e4ff;
      overflow: auto;
      font-size: 0.87rem;
      line-height: 1.5;
      white-space: pre-wrap;
      word-break: break-word;
    }}
    code {{
      background: #eef3ff;
      color: #1d3fab;
      padding: 0.15em 0.35em;
      border-radius: 6px;
    }}
    details {{
      border: 1px solid var(--border);
      border-radius: 16px;
      background: white;
      overflow: hidden;
    }}
    details + details {{
      margin-top: 12px;
    }}
    summary {{
      cursor: pointer;
      list-style: none;
      padding: 14px 16px;
      font-weight: 700;
      background: #fafcff;
    }}
    summary::-webkit-details-marker {{ display: none; }}
    details[open] summary {{
      border-bottom: 1px solid var(--border);
      background: #f5f8ff;
    }}
    details > :not(summary) {{
      padding: 16px;
    }}
    .detail-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 10px;
      margin-bottom: 12px;
    }}
    .detail-grid div {{
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 12px;
      background: #fbfcff;
    }}
    .detail-grid span {{
      display: block;
      color: var(--muted);
      font-size: 0.84rem;
      margin-bottom: 4px;
    }}
    .detail-grid strong {{
      display: block;
      overflow-wrap: anywhere;
    }}
    .stack {{
      display: grid;
      gap: 12px;
    }}
    .block {{
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 12px;
      background: #fff;
    }}
    .block pre {{
      margin-top: 8px;
      max-height: 320px;
    }}
    .chart-wrap {{
      overflow-x: auto;
      margin-bottom: 14px;
    }}
    .chart-wrap svg {{
      width: 100%;
      min-width: 360px;
      height: auto;
      display: block;
    }}
    .chart-axis {{
      stroke: #ccd6ee;
      stroke-width: 2;
    }}
    .chart-label {{
      fill: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }}
    .chart-value {{
      fill: var(--text);
      font-size: 13px;
      font-weight: 800;
    }}
    .artifact-card h3,
    .result-card h3 {{
      margin-bottom: 8px;
    }}
    .artifact-card ul {{
      margin-bottom: 12px;
    }}
    .result-card header p {{
      margin-bottom: 0;
      color: var(--muted);
    }}
    .result-answer {{
      margin: 12px 0;
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 12px;
      background: #fafcff;
    }}
    .result-answer span {{
      display: block;
      color: var(--muted);
      font-size: 0.84rem;
    }}
    .result-answer p {{
      margin: 4px 0 0;
      font-weight: 600;
    }}
    .result-preview h4 {{
      margin: 0 0 8px;
    }}
    .context-preview {{
      margin: 0;
      padding-left: 18px;
    }}
    .context-preview li + li {{ margin-top: 8px; }}
    .context-preview .source {{
      display: block;
      font-size: 0.82rem;
      color: var(--muted);
      margin-bottom: 2px;
    }}
    .context-preview .excerpt {{
      display: block;
      color: var(--text);
    }}
    .interpretation {{
      white-space: pre-wrap;
      margin: 0;
      font-size: 0.98rem;
    }}
    footer {{
      color: var(--muted);
      font-size: 0.9rem;
      text-align: center;
      margin-top: 24px;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <header class="hero">
      <h1>{html.escape(title)}</h1>
      <p class="subtitle">
        BenchmarkQED generates benchmark artifacts and runs its own AutoE and retrieval scoring paths. Ragas supplies the metric vocabulary that AutoE uses in this repo.
      </p>
      <div class="chips">
        <span class="chip"><span>generated</span><strong>{html.escape(now)}</strong></span>
        <span class="chip"><span>scores</span><strong>{len(scores)}</strong></span>
        <span class="chip"><span>results</span><strong>{len(results)}</strong></span>
        <span class="chip"><span>aggregate metrics</span><strong>{len(aggregate)}</strong></span>
        {''.join(runtime_chips)}
      </div>
    </header>

    <main>
      <section>
        <h2>Overview</h2>
        <p class="small">
          This is a smoke report, so the numbers are for wiring validation first and quality judgment second.
          Use it to confirm that the BenchmarkQED pipeline, the Ragas metric vocabulary, and report rendering all line up.
        </p>
        <div class="grid">
          {''.join(overview_cards)}
        </div>
        <div class="note" style="margin-top: 14px;">
          The metric descriptions below are short guides for reading the scores, not hard thresholds.
        </div>
      </section>

      <section>
        <h2>BenchmarkQED</h2>
        <p class="small">
          BenchmarkQED-side artifacts: AutoD summarizes the corpus, AutoQ creates questions, Assertion Prep shows whether those questions produced usable assertions, Assertion Scores shows the assertion evaluation rows if they were run, Retrieval Prep normalizes search output for retrieval scoring, and AutoE reports metric scores.
        </p>
        <div class="wide-grid">
          {_artifact_card("AutoD", autod_bullets if autod_data else ["No AutoD payload available."], autod_data or {})}
          {_artifact_card("AutoQ", autoq_bullets if autoq_data else ["No AutoQ payload available."], autoq_data or {})}
          {(_artifact_card("Assertion Prep", _assertion_prep_bullets(assertion_data), assertion_data)) if assertion_data else ""}
          {(_artifact_card("Assertion Scores", [
              f"{len(_safe_list(assertion_scores_data.get('scores')))} score row(s) evaluated." if assertion_scores_data else "No assertion score payload available.",
              "This evaluates prepared assertions against the answer set.",
          ], assertion_scores_data or {})) if assertion_scores_data else ""}
          {(_artifact_card("Retrieval Prep", [
              f"{len(_safe_list(retrieval_data.get('results')))} retrieval row(s) prepared." if retrieval_data else "No retrieval payload available.",
              "This normalizes current search results into the vendor retrieval-evaluation shape.",
          ], retrieval_data or {})) if retrieval_data else ""}
          {_artifact_card("AutoE", autoe_bullets, evaluation_data)}
        </div>
        {benchmarkqed_alert}
        {assertion_scores_alert}
        {retrieval_alert}
      </section>

      <section>
        <h2>Ragas</h2>
        <p class="small">
          Ragas provides the metric vocabulary used by this repo. BenchmarkQED AutoE uses these metric names in smoke runs, but this report does not execute a standalone Ragas pipeline.
        </p>
        <div class="grid">
          {''.join(_metric_card(metric_name, aggregate.get(metric_name, 0)) for metric_name in aggregate)}
          {''.join(_metric_card(metric_name, "—") for metric_name in METRIC_DESCRIPTIONS if metric_name not in aggregate)}
        </div>
        <div class="note" style="margin-top: 14px;">
          The metric names below are the Ragas metrics surfaced in this smoke via BenchmarkQED AutoE.
        </div>
      </section>

      <section>
        <h2>Aggregate Metrics</h2>
        {_render_metric_chart(aggregate)}
        <div class="grid">
          {''.join(aggregate_cards) if aggregate_cards else '<p class="small">No aggregate metrics were found.</p>'}
        </div>
      </section>

      <section>
        <h2>Detailed Scores</h2>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>sample_id</th>
                <th>metric</th>
                <th>value</th>
                <th>question</th>
                <th>search mode</th>
                <th>reason preview</th>
              </tr>
            </thead>
            <tbody>
              {score_rows}
            </tbody>
          </table>
        </div>
        <div class="stack" style="margin-top: 14px;">
          {score_details if score_details else '<p class="small">No score details were found.</p>'}
        </div>
      </section>

      <section>
        <h2>Retrieved Contexts</h2>
        <div class="stack">
          {result_cards if result_cards else '<p class="small">No search results were found.</p>'}
        </div>
      </section>

      <section>
        <h2>Interpretation</h2>
        <div class="note">
          <div class="interpretation">{html.escape(interpretation_text)}</div>
        </div>
      </section>

      <section>
        <h2>Supporting Artifacts</h2>
        <div class="grid">
          {_artifact_card("AutoD Summary", [
              f"{len(autod_documents)} document(s) summarized.",
              f"{len(autod_themes)} theme(s) extracted.",
              autod_data.get("corpus_summary") if autod_data else None,
              autod_bq.get("summary") if autod_bq else None,
          ] if autod_data else ["No AutoD payload available."], autod_data or {})}
          {_artifact_card("AutoQ Questions", [
              f"{len(autoq_questions_payload)} question(s) generated.",
              f"Modes: {', '.join(map(str, _safe_list((autoq_data or {}).get('metadata', {}).get('modes')))) or 'not recorded'}.",
              (
                  f"First question: {autoq_questions_payload[0].get('question')}"
                  if autoq_questions_payload and isinstance(autoq_questions_payload[0], dict)
                  else "No question payload was returned."
              ),
          ] if autoq_data else ["No AutoQ payload available."], autoq_data or {})}
          {_artifact_card("AutoE Evaluation", [
              f"{len(scores)} score row(s) across {len(aggregate)} metric(s).",
              f"Results rows: {len(results)}.",
              (
                  f"Top metric: {max(aggregate.items(), key=lambda item: float(item[1]))[0]} = {_format_metric_value(max(aggregate.values(), key=lambda value: float(value)))}"
                  if aggregate
                  else "No aggregate metrics were found."
              ),
          ], evaluation_data)}
          {(_artifact_card("Generated Questions", [
              f"{len(_safe_list((generated_data or {}).get('questions')))} question(s) in the generated payload.",
              "Open the JSON view for the full sample list.",
          ], generated_data or {})) if generated_questions and generated_questions != autoq_questions else ""}
        </div>
      </section>
    </main>

    <footer>
      Rendered by <code>graphrag_ragas_eval.reporting.render_smoke_report</code>.
    </footer>
  </div>
</body>
</html>
"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html_text, encoding="utf-8")
    return html_text


def render_assertion_report(
    *,
    assertion_scores: Path,
    output: Path,
    title: str = "BenchmarkQED Assertion Report",
    report_metadata: dict[str, Any] | None = None,
    interpretation: str | None = None,
) -> str:
    assertion_data = _load_json(assertion_scores)
    scores = _safe_list(assertion_data.get("scores"))
    summary_by_assertion = _safe_list(assertion_data.get("summary_by_assertion"))
    summary_by_question = _safe_list(assertion_data.get("summary_by_question"))
    aggregate = _safe_dict(assertion_data.get("aggregate"))
    metadata = _safe_dict(assertion_data.get("metadata"))
    report_metadata = report_metadata or {}
    interpretation_text = interpretation or _assertion_interpretation(
        assertion_data=assertion_data,
        report_metadata=report_metadata,
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    runtime_chips = []
    if report_metadata.get("chat_model"):
        runtime_chips.append(_chip("chat model", report_metadata["chat_model"]))
    if report_metadata.get("provider"):
        runtime_chips.append(_chip("provider", report_metadata["provider"]))
    if report_metadata.get("base_url"):
        runtime_chips.append(_chip("endpoint", report_metadata["base_url"]))
    if metadata.get("backend"):
        runtime_chips.append(_chip("backend", metadata["backend"]))

    overview_cards = [
        _metric_card("score rows", len(scores)),
        _metric_card("assertion summaries", len(summary_by_assertion)),
        _metric_card("question summaries", len(summary_by_question)),
        _metric_card("aggregate metrics", len(aggregate)),
    ]

    score_rows = "\n".join(_assertion_score_row(score) for score in scores if isinstance(score, dict))
    assertion_cards = [
        _artifact_card(
            "Assertion Scores",
            [
                f"{len(scores)} score row(s) evaluated.",
                "Open the JSON view for the raw per-assertion rows.",
            ],
            assertion_data,
        ),
        _artifact_card(
            "Summary by Assertion",
            [
                f"{len(summary_by_assertion)} assertion summary row(s).",
                "This shows how each assertion performed across runs.",
            ],
            {"summary_by_assertion": summary_by_assertion},
        ),
        _artifact_card(
            "Summary by Question",
            [
                f"{len(summary_by_question)} question summary row(s).",
                "This groups assertion results by question.",
            ],
            {"summary_by_question": summary_by_question},
        ),
    ]

    html_text = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #eef3ff;
      --panel: rgba(255, 255, 255, 0.94);
      --panel-strong: #ffffff;
      --text: #182033;
      --muted: #60708f;
      --accent: #2457ff;
      --accent-soft: #e8efff;
      --border: #d9e0ef;
      --shadow: 0 14px 40px rgba(31, 41, 55, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    html, body {{ min-height: 100%; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, "Noto Sans KR", "Helvetica Neue", Arial, sans-serif;
      background:
        radial-gradient(circle at top left, rgba(36, 87, 255, 0.11), transparent 30%),
        linear-gradient(180deg, #eef3ff 0%, #f8fbff 18%, #f8fbff 100%);
      color: var(--text);
      line-height: 1.55;
    }}
    .wrap {{
      max-width: 1220px;
      margin: 0 auto;
      padding: 36px 18px 64px;
    }}
    .hero {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 28px;
      padding: 28px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(10px);
    }}
    .hero h1 {{
      margin: 0 0 10px;
      font-size: clamp(2rem, 4vw, 3rem);
      line-height: 1.08;
      letter-spacing: -0.03em;
    }}
    .subtitle {{
      margin: 0;
      color: var(--muted);
      max-width: 70ch;
    }}
    .chips {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 18px;
    }}
    .chip {{
      display: inline-flex;
      align-items: baseline;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      border: 1px solid rgba(36, 87, 255, 0.12);
      font-size: 0.92rem;
      font-weight: 700;
    }}
    .chip strong {{ font-weight: 800; }}
    main {{
      margin-top: 22px;
      display: grid;
      gap: 18px;
    }}
    section {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 22px;
      padding: 22px;
      box-shadow: var(--shadow);
    }}
    h2 {{
      margin: 0 0 14px;
      font-size: 1.28rem;
      letter-spacing: -0.02em;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 14px;
    }}
    .wide-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 14px;
    }}
    .metric-card, .artifact-card {{
      background: var(--panel-strong);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 16px;
    }}
    .metric-title {{
      color: var(--muted);
      font-size: 0.9rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .metric-value {{
      margin-top: 6px;
      font-size: 1.8rem;
      font-weight: 900;
      letter-spacing: -0.03em;
    }}
    .metric-desc {{
      margin: 8px 0 0;
      color: var(--muted);
      font-size: 0.92rem;
    }}
    .note {{
      border-left: 4px solid var(--accent);
      background: #f5f8ff;
      padding: 14px 16px;
      border-radius: 14px;
      color: #26314a;
    }}
    .small {{ color: var(--muted); font-size: 0.92rem; }}
    .bullet-list {{
      margin: 0;
      padding-left: 20px;
      color: var(--text);
    }}
    .bullet-list li + li {{ margin-top: 6px; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      overflow: hidden;
      background: white;
      border-radius: 18px;
      border: 1px solid var(--border);
    }}
    th, td {{
      padding: 12px 10px;
      border-bottom: 1px solid var(--border);
      text-align: left;
      vertical-align: top;
      font-size: 0.92rem;
    }}
    th {{
      background: #f6f9ff;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.06em;
      font-size: 0.78rem;
    }}
    tr:last-child td {{ border-bottom: none; }}
    details {{
      border: 1px solid var(--border);
      border-radius: 16px;
      background: white;
      overflow: hidden;
    }}
    details + details {{ margin-top: 12px; }}
    summary {{
      cursor: pointer;
      list-style: none;
      padding: 14px 16px;
      font-weight: 700;
      background: #fafcff;
    }}
    summary::-webkit-details-marker {{ display: none; }}
    details[open] summary {{
      border-bottom: 1px solid var(--border);
      background: #f5f8ff;
    }}
    details > :not(summary) {{ padding: 16px; }}
    pre {{
      margin: 0;
      padding: 14px;
      border-radius: 14px;
      background: #0f172a;
      color: #d8e4ff;
      overflow: auto;
      font-size: 0.87rem;
      line-height: 1.5;
      white-space: pre-wrap;
      word-break: break-word;
    }}
    footer {{
      color: var(--muted);
      font-size: 0.9rem;
      text-align: center;
      margin-top: 24px;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <header class="hero">
      <h1>{html.escape(title)}</h1>
      <p class="subtitle">
        BenchmarkQED assertion smoke checks assertion scoring and per-question aggregation in one pass.
      </p>
      <div class="chips">
        <span class="chip"><span>generated</span><strong>{html.escape(now)}</strong></span>
        <span class="chip"><span>score rows</span><strong>{len(scores)}</strong></span>
        <span class="chip"><span>assertion summaries</span><strong>{len(summary_by_assertion)}</strong></span>
        <span class="chip"><span>question summaries</span><strong>{len(summary_by_question)}</strong></span>
        {''.join(runtime_chips)}
      </div>
    </header>

    <main>
      <section>
        <h2>Overview</h2>
        <p class="small">
          This is a BenchmarkQED-only assertion report. It intentionally excludes Ragas and focuses on the assertion scoring path.
        </p>
        <div class="grid">
          {''.join(overview_cards)}
        </div>
      </section>

      <section>
        <h2>BenchmarkQED Assertion</h2>
        <div class="wide-grid">
          {''.join(assertion_cards)}
        </div>
      </section>

      <section>
        <h2>Interpretation</h2>
        <div class="note">
          <div class="interpretation">{html.escape(interpretation_text)}</div>
        </div>
      </section>

      <section>
        <h2>Score Details</h2>
        <table>
          <thead>
            <tr>
              <th>question_id</th>
              <th>question</th>
              <th>assertion</th>
              <th>score</th>
              <th>reason</th>
            </tr>
          </thead>
          <tbody>
            {score_rows}
          </tbody>
        </table>
      </section>

      <section>
        <h2>Supporting Artifacts</h2>
        <div class="grid">
          {_artifact_card("Assertion Scores JSON", [
              f"{len(scores)} score row(s).",
              f"Metadata backend: {metadata.get('backend', 'benchmark-qed')}.",
          ], assertion_data)}
          {_artifact_card("Summary by Assertion JSON", [
              f"{len(summary_by_assertion)} summary row(s).",
              "This groups score rows by assertion.",
          ], {"summary_by_assertion": summary_by_assertion})}
          {_artifact_card("Summary by Question JSON", [
              f"{len(summary_by_question)} summary row(s).",
              "This groups score rows by question.",
          ], {"summary_by_question": summary_by_question})}
        </div>
      </section>
    </main>

    <footer>
      Rendered by <code>graphrag_ragas_eval.reporting.render_assertion_report</code>.
    </footer>
  </div>
</body>
</html>
"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html_text, encoding="utf-8")
    return html_text


def render_retrieval_smoke_report(
    *,
    retrieval_reference: Path,
    retrieval_results: Path,
    retrieval_evaluation: Path,
    output: Path,
    title: str = "BenchmarkQED Retrieval Smoke Report",
    report_metadata: dict[str, Any] | None = None,
    interpretation: str | None = None,
) -> str:
    reference_data = _load_json(retrieval_reference)
    retrieval_data = _load_json(retrieval_results)
    evaluation_data = _load_json(retrieval_evaluation)

    reference_rows = _safe_list(reference_data.get("references"))
    retrieval_rows = _safe_list(retrieval_data.get("results"))
    evaluation_scores = _safe_list(evaluation_data.get("summary"))
    evaluation_metadata = _safe_dict(evaluation_data.get("metadata"))
    aggregate = _safe_dict(evaluation_data.get("aggregate"))
    report_metadata = report_metadata or {}
    interpretation_text = interpretation or _retrieval_interpretation(
        reference_data=reference_data,
        retrieval_data=retrieval_data,
        evaluation_data=evaluation_data,
        report_metadata=report_metadata,
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    runtime_chips = []
    if report_metadata.get("chat_model"):
        runtime_chips.append(_chip("chat model", report_metadata["chat_model"]))
    if report_metadata.get("provider"):
        runtime_chips.append(_chip("provider", report_metadata["provider"]))
    if report_metadata.get("embeddings_model"):
        runtime_chips.append(_chip("embeddings", report_metadata["embeddings_model"]))
    if report_metadata.get("base_url"):
        runtime_chips.append(_chip("endpoint", report_metadata["base_url"]))

    overview_cards = [
        _metric_card("reference rows", len(reference_rows)),
        _metric_card("retrieval rows", len(retrieval_rows)),
        _metric_card("evaluation rows", len(evaluation_scores)),
        _metric_card("aggregate metrics", len(aggregate)),
    ]

    html_text = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #eef3ff;
      --panel: rgba(255, 255, 255, 0.94);
      --panel-strong: #ffffff;
      --text: #182033;
      --muted: #60708f;
      --accent: #2457ff;
      --accent-soft: #e8efff;
      --border: #d9e0ef;
      --shadow: 0 14px 40px rgba(31, 41, 55, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    html, body {{ min-height: 100%; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, "Noto Sans KR", "Helvetica Neue", Arial, sans-serif;
      background:
        radial-gradient(circle at top left, rgba(36, 87, 255, 0.11), transparent 30%),
        linear-gradient(180deg, #eef3ff 0%, #f8fbff 18%, #f8fbff 100%);
      color: var(--text);
      line-height: 1.55;
    }}
    .wrap {{
      max-width: 1220px;
      margin: 0 auto;
      padding: 36px 18px 64px;
    }}
    .hero {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 28px;
      padding: 28px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(10px);
    }}
    .hero h1 {{
      margin: 0 0 10px;
      font-size: clamp(2rem, 4vw, 3rem);
      line-height: 1.08;
      letter-spacing: -0.03em;
    }}
    .subtitle {{
      margin: 0;
      color: var(--muted);
      max-width: 70ch;
    }}
    .chips {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 18px;
    }}
    .chip {{
      display: inline-flex;
      align-items: baseline;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      border: 1px solid rgba(36, 87, 255, 0.12);
      font-size: 0.92rem;
      font-weight: 700;
    }}
    .chip strong {{ font-weight: 800; }}
    main {{
      margin-top: 22px;
      display: grid;
      gap: 18px;
    }}
    section {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 22px;
      padding: 22px;
      box-shadow: var(--shadow);
    }}
    h2 {{
      margin: 0 0 14px;
      font-size: 1.28rem;
      letter-spacing: -0.02em;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 14px;
    }}
    .wide-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 14px;
    }}
    .metric-card, .artifact-card {{
      background: var(--panel-strong);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 16px;
    }}
    .metric-title {{
      color: var(--muted);
      font-size: 0.9rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .metric-value {{
      margin-top: 6px;
      font-size: 1.8rem;
      font-weight: 900;
      letter-spacing: -0.03em;
    }}
    .metric-desc {{
      margin: 8px 0 0;
      color: var(--muted);
      font-size: 0.92rem;
    }}
    .note {{
      border-left: 4px solid var(--accent);
      background: #f5f8ff;
      padding: 14px 16px;
      border-radius: 14px;
      color: #26314a;
    }}
    .small {{ color: var(--muted); font-size: 0.92rem; }}
    .bullet-list {{
      margin: 0;
      padding-left: 20px;
      color: var(--text);
    }}
    .bullet-list li + li {{ margin-top: 6px; }}
    details {{
      border: 1px solid var(--border);
      border-radius: 16px;
      background: white;
      overflow: hidden;
    }}
    details + details {{ margin-top: 12px; }}
    summary {{
      cursor: pointer;
      list-style: none;
      padding: 14px 16px;
      font-weight: 700;
      background: #fafcff;
    }}
    summary::-webkit-details-marker {{ display: none; }}
    details[open] summary {{
      border-bottom: 1px solid var(--border);
      background: #f5f8ff;
    }}
    details > :not(summary) {{ padding: 16px; }}
    pre {{
      margin: 0;
      padding: 14px;
      border-radius: 14px;
      background: #0f172a;
      color: #d8e4ff;
      overflow: auto;
      font-size: 0.87rem;
      line-height: 1.5;
      white-space: pre-wrap;
      word-break: break-word;
    }}
    .artifact-card h3 {{ margin: 0 0 8px; }}
    footer {{
      color: var(--muted);
      font-size: 0.9rem;
      text-align: center;
      margin-top: 24px;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <header class="hero">
      <h1>{html.escape(title)}</h1>
      <p class="subtitle">
        BenchmarkQED retrieval smoke checks reference generation, retrieval preparation, and retrieval scoring in one pass.
      </p>
      <div class="chips">
        <span class="chip"><span>generated</span><strong>{html.escape(now)}</strong></span>
        <span class="chip"><span>reference rows</span><strong>{len(reference_rows)}</strong></span>
        <span class="chip"><span>retrieval rows</span><strong>{len(retrieval_rows)}</strong></span>
        <span class="chip"><span>evaluation rows</span><strong>{len(evaluation_scores)}</strong></span>
        {''.join(runtime_chips)}
      </div>
    </header>

    <main>
      <section>
        <h2>Overview</h2>
        <p class="small">
          This is a BenchmarkQED-only retrieval report. It intentionally excludes Ragas and focuses on the retrieval reference and scoring path.
        </p>
        <div class="grid">
          {''.join(overview_cards)}
        </div>
      </section>

      <section>
        <h2>BenchmarkQED Retrieval</h2>
        <div class="wide-grid">
          {_artifact_card("Retrieval Reference", [
              f"{len(reference_rows)} reference row(s) generated.",
              "Open the JSON view for the reference clusters and question relevance labels.",
          ], reference_data)}
          {_artifact_card("Retrieval Prep", [
              f"{len(retrieval_rows)} retrieval row(s) prepared.",
              "This normalizes the search results into the vendor retrieval-evaluation shape.",
          ], retrieval_data)}
          {_artifact_card("Retrieval Evaluation", [
              f"{len(evaluation_scores)} evaluation summary row(s).",
              f"{len(aggregate)} aggregate metric(s) in the payload.",
          ], evaluation_data)}
        </div>
      </section>

      <section>
        <h2>Interpretation</h2>
        <div class="note">
          <div class="interpretation">{html.escape(interpretation_text)}</div>
        </div>
      </section>

      <section>
        <h2>Supporting Artifacts</h2>
        <div class="grid">
          {_artifact_card("Retrieval Reference JSON", [
              f"{len(reference_rows)} reference row(s).",
              "Cluster-level relevance labels live here.",
          ], reference_data)}
          {_artifact_card("Retrieval Results JSON", [
              f"{len(retrieval_rows)} prepared row(s).",
              "These are the normalized search results used by BenchmarkQED retrieval scoring.",
          ], retrieval_data)}
          {_artifact_card("Retrieval Evaluation JSON", [
              f"{len(evaluation_scores)} summary row(s).",
              f"Metadata backend: {evaluation_metadata.get('backend', 'benchmark-qed')}.",
          ], evaluation_data)}
        </div>
      </section>
    </main>

    <footer>
      Rendered by <code>graphrag_ragas_eval.reporting.render_retrieval_smoke_report</code>.
    </footer>
  </div>
</body>
</html>
"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html_text, encoding="utf-8")
    return html_text
