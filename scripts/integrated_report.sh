#!/usr/bin/env sh

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
REPORT_RENDERER=${REPORT_RENDERER:-"$SCRIPT_DIR/render_pipeline_report.py"}

if [ "$#" -lt 3 ]; then
  printf '%s\n' "Usage: integrated_report.sh BENCHMARK_SUMMARY_JSONL RAGAS_SUMMARY_JSONL OUTPUT_HTML" >&2
  exit 1
fi

BENCHMARK_SUMMARY=$1
RAGAS_SUMMARY=$2
OUTPUT_HTML=$3

case "$OUTPUT_HTML" in
  /*) : ;;
  *)
    OUTPUT_HTML="$REPO_ROOT/$OUTPUT_HTML"
    ;;
esac

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf '%s\n' "Missing required command: $1" >&2
    exit 1
  fi
}

require_cmd python3

python3 "$REPORT_RENDERER" --title "Integrated Pipeline Report" --output "$OUTPUT_HTML" "$BENCHMARK_SUMMARY" "$RAGAS_SUMMARY"
printf '%s\n' "$OUTPUT_HTML"
