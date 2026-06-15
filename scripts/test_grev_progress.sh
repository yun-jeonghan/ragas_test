#!/usr/bin/env sh

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
MATRIX_SCRIPT="$SCRIPT_DIR/grev_matrix.sh"
PROGRESS_FILE="$REPO_ROOT/test_progress.md"

TEST_ROOT=${1:-"data/test_$(date +%Y%m%d_%H%M%S)"}

if [ ! -x "$MATRIX_SCRIPT" ]; then
  printf '%s\n' "Missing executable matrix script: $MATRIX_SCRIPT" >&2
  exit 1
fi

set +e
"$MATRIX_SCRIPT" "$TEST_ROOT"
matrix_rc=$?
set -e

SUMMARY_FILE="$REPO_ROOT/$TEST_ROOT/output/summary.jsonl"

if [ ! -f "$SUMMARY_FILE" ]; then
  printf '%s\n' "Summary file not found: $SUMMARY_FILE" >&2
  exit "$matrix_rc"
fi

python3 - "$SUMMARY_FILE" "$PROGRESS_FILE" "$TEST_ROOT" <<'PY'
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
import sys

summary_path = Path(sys.argv[1])
progress_path = Path(sys.argv[2])
test_root = sys.argv[3]

records = []
for line in summary_path.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line:
        continue
    records.append(json.loads(line))

by_step = {record["step"]: record for record in records}

groups = [
    ("Core GraphRAG Flow", [
        "grev init",
        "graphrag normalize",
        "graphrag stage",
        "graphrag init",
        "graphrag index standard",
        "graphrag index ontology+postprocess",
        "graphrag postprocess",
        "inspect",
    ]),
    ("Question Generation", [
        "benchmark generate-questions",
        "ragas generate-questions",
    ]),
    ("BenchmarkQED", [
        "benchmark-qed autod",
        "benchmark-qed autoq",
        "benchmark-qed autoe",
        "benchmark-qed smoke",
        "benchmark-qed retrieval-smoke",
        "benchmark-qed retrieval-reference",
        "benchmark-qed retrieval-score",
        "benchmark-qed assertion-score",
        "benchmark-qed assertion-report",
    ]),
    ("Evaluation Wrappers", [
        "evaluate",
        "ragas evaluate",
        "kg-gen mine evaluate",
        "kg-correctness evaluate",
        "ograg2 evaluate",
        "pipeline report",
    ]),
]

passed = 0
failed = 0
lines: list[str] = []
lines.append("# Test Progress")
lines.append("")
lines.append("This file tracks the latest verified status of the main `grev` flows.")
lines.append("Run `scripts/test_grev_progress.sh` to refresh it from the latest matrix output.")
lines.append("")
lines.append("## Snapshot")
lines.append("")
lines.append(f"- Last verified: {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
lines.append(f"- Test root: `{test_root}`")
lines.append(f"- Summary file: `{summary_path}`")
lines.append("")

for group_name, steps in groups:
    lines.append(f"## {group_name}")
    lines.append("")
    for step in steps:
        record = by_step.get(step)
        if record is None:
            lines.append(f"- [ ] `{step}` - not run")
            continue
        exit_code = record["exit_code"]
        log_path = record["log"]
        if exit_code == 0:
            passed += 1
            lines.append(f"- [x] `{step}` - exit 0")
        else:
            failed += 1
            lines.append(f"- [ ] `{step}` - exit {exit_code}, log `{log_path}`")
    lines.append("")

lines.append("## Result Summary")
lines.append("")
lines.append(f"- Passed: {passed}")
lines.append(f"- Failed: {failed}")
lines.append("")
lines.append("## Notes")
lines.append("")
lines.append("- A checked item means the latest matrix run exited with code `0`.")
lines.append("- Failed steps stay listed here so it is obvious what needs attention next.")

progress_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY

printf '%s\n' "Updated $PROGRESS_FILE from $SUMMARY_FILE"
exit "$matrix_rc"
