from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _escape_json(value: Any) -> str:
    return html.escape(json.dumps(value, ensure_ascii=False, indent=2))


def _format_metric_value(value: Any) -> str:
    if isinstance(value, (int, float)):
        number = float(value)
        if abs(number - round(number)) < 1e-9:
            return f"{number:.0f}"
        return f"{number:.6f}".rstrip("0").rstrip(".")
    return html.escape(str(value))


def _score_row(score: dict[str, Any]) -> str:
    metadata = score.get("metadata") or {}
    return f"""
      <tr>
        <td>{html.escape(str(score.get("sample_id", "")))}</td>
        <td>{html.escape(str(score.get("metric_name", "")))}</td>
        <td>{_format_metric_value(score.get("value"))}</td>
        <td>{html.escape(str(metadata.get("question", "")))}</td>
        <td>{html.escape(str(metadata.get("search_mode", "")))}</td>
      </tr>
    """


def _context_block(context: dict[str, Any]) -> str:
    payload = {
        "text": context.get("text"),
        "source": context.get("source"),
        "score": context.get("score"),
        "metadata": context.get("metadata", {}),
    }
    return _escape_json(payload)


def render_smoke_report(
    evaluation: Path,
    output: Path,
    *,
    title: str = "GraphRAG + Ragas Smoke Report",
    generated_questions: Path | None = None,
    autod_summary: Path | None = None,
    autoq_questions: Path | None = None,
) -> str:
    evaluation_data = _load_json(evaluation)
    generated_data = _load_json(generated_questions) if generated_questions else None
    autod_data = _load_json(autod_summary) if autod_summary else None
    autoq_data = _load_json(autoq_questions) if autoq_questions else None

    scores = evaluation_data.get("scores", [])
    results = evaluation_data.get("results", [])
    aggregate = evaluation_data.get("aggregate", {})
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    aggregate_cards = []
    for metric_name, value in aggregate.items():
        aggregate_cards.append(
            f"""
            <article class="metric">
              <div class="label">{html.escape(metric_name)}</div>
              <div class="value">{_format_metric_value(value)}</div>
            </article>
            """
        )

    score_rows = "\n".join(_score_row(score) for score in scores)

    result_articles = []
    for result in results:
        contexts = result.get("retrieved_contexts", [])
        result_articles.append(
            f"""
            <article class="result-card">
              <header>
                <h3>{html.escape(str(result.get("sample_id", "")))}</h3>
                <p>{html.escape(str(result.get("question", "")))}</p>
              </header>
              <div class="qa">
                <div><span>Answer</span><strong>{html.escape(str(result.get("answer", "")))}</strong></div>
                <div><span>Search mode</span><strong>{html.escape(str(result.get("search_mode", "")))}</strong></div>
              </div>
              <div class="contexts">
                <h4>Retrieved contexts</h4>
                <pre>{_escape_json([{
                    "text": ctx.get("text"),
                    "source": ctx.get("source"),
                    "score": ctx.get("score"),
                    "metadata": ctx.get("metadata", {}),
                } for ctx in contexts])}</pre>
              </div>
            </article>
            """
        )

    def _summary_card(title_text: str, payload: dict[str, Any] | None) -> str:
        if not payload:
            return ""
        return f"""
          <article class="summary-card">
            <h3>{html.escape(title_text)}</h3>
            <pre>{_escape_json(payload)}</pre>
          </article>
        """

    html_text = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f5f7fb;
      --panel: rgba(255,255,255,0.95);
      --text: #172033;
      --muted: #5f6b85;
      --accent: #2457ff;
      --accent-soft: #e8efff;
      --border: #d9e0ef;
      --good: #0f8a52;
      --shadow: 0 12px 36px rgba(31, 41, 55, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans KR", "Helvetica Neue", Arial, sans-serif;
      background: linear-gradient(180deg, #eef3ff 0%, var(--bg) 18%, var(--bg) 100%);
      color: var(--text);
      line-height: 1.55;
    }}
    .wrap {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 40px 20px 64px;
    }}
    header.hero {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 24px;
      padding: 28px;
      box-shadow: var(--shadow);
    }}
    h1 {{ margin: 0 0 8px; font-size: clamp(2rem, 4vw, 3rem); line-height: 1.1; }}
    .subtitle {{ color: var(--muted); margin: 0; }}
    .chips {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; }}
    .chip {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 8px 12px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      font-size: 0.92rem;
      font-weight: 700;
    }}
    main {{ margin-top: 22px; display: grid; gap: 18px; }}
    section, article.panel {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 22px;
      box-shadow: var(--shadow);
    }}
    h2 {{ margin: 0 0 14px; font-size: 1.25rem; }}
    h3 {{ margin: 0 0 10px; font-size: 1.02rem; }}
    h4 {{ margin: 0 0 8px; font-size: 0.98rem; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 14px;
    }}
    .metric {{
      border: 1px solid var(--border);
      background: #fbfcff;
      border-radius: 16px;
      padding: 16px;
    }}
    .metric .label {{ color: var(--muted); font-size: 0.9rem; }}
    .metric .value {{ font-size: 1.7rem; font-weight: 900; margin-top: 4px; }}
    .note {{
      border-left: 4px solid var(--accent);
      background: #f5f8ff;
      padding: 14px 16px;
      border-radius: 12px;
      color: #2b3550;
    }}
    .table {{
      width: 100%;
      border-collapse: collapse;
      overflow: hidden;
      border-radius: 14px;
      border: 1px solid var(--border);
    }}
    .table th, .table td {{
      border-bottom: 1px solid var(--border);
      padding: 12px 10px;
      text-align: left;
      vertical-align: top;
    }}
    .table th {{
      background: #f3f6ff;
      font-size: 0.92rem;
      color: #31426b;
    }}
    .table tr:last-child td {{ border-bottom: none; }}
    pre {{
      margin: 0;
      padding: 14px;
      overflow: auto;
      border-radius: 14px;
      background: #0f172a;
      color: #d8e4ff;
      font-size: 0.88rem;
      line-height: 1.5;
    }}
    code {{
      background: #eef3ff;
      color: #1d3fab;
      padding: 0.15em 0.35em;
      border-radius: 6px;
    }}
    .small {{ color: var(--muted); font-size: 0.92rem; }}
    .result-card {{
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 18px;
      background: #fff;
      box-shadow: 0 8px 24px rgba(31, 41, 55, 0.04);
    }}
    .result-card + .result-card {{ margin-top: 14px; }}
    .qa {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 10px;
      margin: 14px 0;
    }}
    .qa div {{
      background: #f8faff;
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 12px;
    }}
    .qa span {{ display: block; color: var(--muted); font-size: 0.84rem; }}
    .qa strong {{ display: block; margin-top: 4px; }}
    footer {{ color: var(--muted); font-size: 0.9rem; text-align: center; margin-top: 24px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <header class="hero">
      <h1>{html.escape(title)}</h1>
      <p class="subtitle">TXT-only smoke, question generation, AutoD/AutoQ, and Ragas AutoE results in one page.</p>
      <div class="chips">
        <span class="chip">generated: {html.escape(now)}</span>
        <span class="chip">scores: {len(scores)}</span>
        <span class="chip">results: {len(results)}</span>
        <span class="chip">aggregate metrics: {len(aggregate)}</span>
      </div>
    </header>

    <main>
      <section>
        <h2>Summary</h2>
        <p>
          This report captures the smoke path that succeeded with
          <code>examples/sample_docs/scrooge.txt</code>, then evaluates the saved search result JSON with Ragas.
        </p>
        <div class="note">
          The AutoE run completed with <strong>context_precision = { _format_metric_value(aggregate.get("context_precision", 0)) }</strong>.
        </div>
      </section>

      <section>
        <h2>Aggregate Metrics</h2>
        <div class="grid">
          {''.join(aggregate_cards) if aggregate_cards else '<p class="small">No aggregate metrics were found.</p>'}
        </div>
      </section>

      <section>
        <h2>Scores</h2>
        <table class="table">
          <thead>
            <tr>
              <th>sample_id</th>
              <th>metric</th>
              <th>value</th>
              <th>question</th>
              <th>search mode</th>
            </tr>
          </thead>
          <tbody>
            {score_rows}
          </tbody>
        </table>
      </section>

      <section>
        <h2>Retrieved Contexts</h2>
        {''.join(result_articles) if result_articles else '<p class="small">No search results were found.</p>'}
      </section>

      <section>
        <h2>Supporting Artifacts</h2>
        <div class="grid">
          {_summary_card("Generated Questions", generated_data)}
          {_summary_card("AutoD Summary", autod_data)}
          {_summary_card("AutoQ Questions", autoq_data)}
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
