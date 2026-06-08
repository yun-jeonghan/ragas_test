#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


def load_summary(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            item = {"step": line, "exit_code": 1, "log": ""}
        if isinstance(item, dict):
            rows.append(item)
    return rows


def status_label(exit_code: object) -> str:
    try:
        return "passed" if int(exit_code) == 0 else "failed"
    except Exception:
        return "unknown"


def render_rows(rows: list[dict[str, object]]) -> tuple[str, int, int]:
    passed = 0
    failed = 0
    rendered: list[str] = []
    for row in rows:
        step = html.escape(str(row.get("step", "")))
        log = html.escape(str(row.get("log", "")))
        exit_code = row.get("exit_code", "")
        try:
            exit_code_int = int(exit_code)
        except Exception:
            exit_code_int = 1
        if exit_code_int == 0:
            passed += 1
        else:
            failed += 1
        rendered.append(
            f"""
            <tr class="{status_label(exit_code)}">
              <td>{step}</td>
              <td>{exit_code_int}</td>
              <td>{html.escape(status_label(exit_code))}</td>
              <td><code>{log}</code></td>
            </tr>
            """
        )
    return "".join(rendered), passed, failed


def build_html(title: str, sections: list[tuple[str, Path, list[dict[str, object]]]]) -> str:
    section_html: list[str] = []
    total_passed = 0
    total_failed = 0
    for label, path, rows in sections:
        table_rows, passed, failed = render_rows(rows)
        total_passed += passed
        total_failed += failed
        section_html.append(
            f"""
            <section class="panel">
              <h2>{html.escape(label)}</h2>
              <p class="meta">summary: <code>{html.escape(str(path))}</code></p>
              <div class="chips">
                <span class="chip ok">passed {passed}</span>
                <span class="chip bad">failed {failed}</span>
                <span class="chip">steps {len(rows)}</span>
              </div>
              <div class="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>step</th>
                      <th>exit</th>
                      <th>status</th>
                      <th>log</th>
                    </tr>
                  </thead>
                  <tbody>
                    {table_rows}
                  </tbody>
                </table>
              </div>
            </section>
            """
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      --bg: #f5f7fb;
      --panel: #ffffff;
      --text: #162033;
      --muted: #5e6b86;
      --border: #dce3f1;
      --ok: #147a4f;
      --bad: #9a4816;
      --chip: #eef3ff;
      --shadow: 0 12px 28px rgba(24, 32, 51, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, "Noto Sans KR", Arial, sans-serif;
      background: radial-gradient(circle at top left, rgba(36, 87, 255, 0.12), transparent 25%), var(--bg);
      color: var(--text);
    }}
    .wrap {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 28px 18px 56px;
    }}
    .hero, .panel {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 22px;
      box-shadow: var(--shadow);
    }}
    .hero {{
      padding: 24px;
      margin-bottom: 18px;
    }}
    h1 {{ margin: 0 0 8px; font-size: clamp(2rem, 4vw, 2.8rem); }}
    h2 {{ margin: 0 0 12px; }}
    .meta {{ color: var(--muted); margin: 0 0 14px; }}
    .chips {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 14px; }}
    .chip {{
      display: inline-flex;
      padding: 7px 12px;
      border-radius: 999px;
      background: var(--chip);
      font-weight: 700;
      border: 1px solid rgba(36, 87, 255, 0.12);
    }}
    .chip.ok {{ color: var(--ok); }}
    .chip.bad {{ color: var(--bad); }}
    .panel {{ padding: 20px; margin-top: 16px; }}
    .table-wrap {{ overflow-x: auto; border: 1px solid var(--border); border-radius: 16px; }}
    table {{ width: 100%; border-collapse: collapse; min-width: 720px; background: #fff; }}
    th, td {{ padding: 11px 10px; text-align: left; vertical-align: top; border-bottom: 1px solid var(--border); }}
    th {{ background: #f4f7ff; }}
    tr:last-child td {{ border-bottom: none; }}
    tr.passed td {{ color: var(--text); }}
    tr.failed td {{ color: var(--bad); }}
    code {{
      background: #eef3ff;
      color: #2244aa;
      padding: 0.15em 0.35em;
      border-radius: 6px;
    }}
    footer {{
      color: var(--muted);
      margin-top: 18px;
      text-align: center;
      font-size: 0.9rem;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <header class="hero">
      <h1>{html.escape(title)}</h1>
      <p class="meta">Combined pipeline report. Passed: {total_passed}. Failed: {total_failed}.</p>
    </header>
    {''.join(section_html)}
    <footer>Rendered by scripts/render_pipeline_report.py</footer>
  </div>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("summaries", nargs="+")
    args = parser.parse_args()

    sections: list[tuple[str, Path, list[dict[str, object]]]] = []
    for summary in args.summaries:
        summary_path = Path(summary)
        sections.append((summary_path.stem, summary_path, load_summary(summary_path)))

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_html(args.title, sections), encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
