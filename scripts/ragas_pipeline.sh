#!/usr/bin/env sh

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
GREV_BIN=${GREV_BIN:-grev}
REPORT_RENDERER=${REPORT_RENDERER:-"$SCRIPT_DIR/render_pipeline_report.py"}

if [ -f "$REPO_ROOT/.env" ]; then
  set -a
  . "$REPO_ROOT/.env"
  set +a
fi

if [ "$#" -lt 4 ]; then
  printf '%s\n' "Usage: ragas_pipeline.sh SOURCE_DIR BENCHMARK_JSON RESULTS_JSON OUTPUT_DIR" >&2
  exit 1
fi

SOURCE_DIR=$1
BENCHMARK_JSON=$2
RESULTS_JSON=$3
OUTPUT_DIR=$4

case "$OUTPUT_DIR" in
  /*) : ;;
  *)
    OUTPUT_DIR="$REPO_ROOT/$OUTPUT_DIR"
    ;;
esac

LOG_DIR="$OUTPUT_DIR/logs"
WORK_DIR="$OUTPUT_DIR/work"
STAGED_SOURCE_DIR="$WORK_DIR/source"
RAGAS_QUESTIONS_DIR="$OUTPUT_DIR/runs/ragas-generate-questions"
RAGAS_EVAL_DIR="$OUTPUT_DIR/runs/ragas-evaluate"
REPORT_DIR="$OUTPUT_DIR/reports"
SUMMARY_FILE="$OUTPUT_DIR/summary.jsonl"
PIPELINE_REPORT="$REPORT_DIR/ragas-pipeline.html"

if [ -z "${GREV_RAGAS_MODEL:-}" ] || [ -z "${GREV_RAGAS_EMBEDDINGS_MODEL:-}" ]; then
  printf '%s\n' "Missing env. Set GREV_RAGAS_MODEL and GREV_RAGAS_EMBEDDINGS_MODEL before running ragas_pipeline.sh." >&2
  exit 1
fi

run_count=0
fail_count=0

mkdir -p "$LOG_DIR" "$WORK_DIR" "$STAGED_SOURCE_DIR" "$RAGAS_QUESTIONS_DIR" "$RAGAS_EVAL_DIR" "$REPORT_DIR"
: > "$SUMMARY_FILE"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf '%s\n' "Missing required command: $1" >&2
    exit 1
  fi
}

append_summary() {
  step_name=$1
  exit_code=$2
  log_file=$3
  printf '{"step":"%s","exit_code":%s,"log":"%s"}\n' \
    "$step_name" "$exit_code" "$log_file" >> "$SUMMARY_FILE"
}

run_step() {
  step_name=$1
  log_file=$2
  shift 2
  run_count=$((run_count + 1))
  printf '\n[%02d] %s\n' "$run_count" "$step_name"
  if "$@" >"$log_file" 2>&1; then
    rc=0
  else
    rc=$?
  fi
  append_summary "$step_name" "$rc" "$log_file"
  if [ "$rc" -eq 0 ]; then
    printf '  ok  %s\n' "$step_name"
  else
    printf '  err %s (see %s)\n' "$step_name" "$log_file"
    fail_count=$((fail_count + 1))
  fi
}

require_cmd "$GREV_BIN"
require_cmd python3

printf '%s\n' "repo: $REPO_ROOT"
printf '%s\n' "source_dir: $SOURCE_DIR"
printf '%s\n' "benchmark_json: $BENCHMARK_JSON"
printf '%s\n' "results_json: $RESULTS_JSON"
printf '%s\n' "output_dir: $OUTPUT_DIR"
printf '%s\n' "summary: $SUMMARY_FILE"

stage_source() {
  if [ -f "$SOURCE_DIR" ]; then
    source_files="$SOURCE_DIR"
  else
    source_files=$(find "$SOURCE_DIR" -maxdepth 1 -type f -name '*.txt' | sort)
  fi
  if [ -z "$source_files" ]; then
    printf '%s\n' "No .txt files found in source dir: $SOURCE_DIR" >&2
    exit 1
  fi

  base_file="$WORK_DIR/ragas-source-base.txt"
  staged_file="$STAGED_SOURCE_DIR/ragas-source.txt"
  : > "$base_file"
  for file in $source_files; do
    cat "$file" >> "$base_file"
    printf '\n\n' >> "$base_file"
  done
  cp -f "$base_file" "$staged_file"

  word_count=$(wc -w < "$staged_file" | tr -d '[:space:]')
  while [ "$word_count" -lt 180 ]; do
    cat "$base_file" >> "$staged_file"
    word_count=$(wc -w < "$staged_file" | tr -d '[:space:]')
  done
}

stage_source

run_step \
  "ragas generate-questions" \
  "$LOG_DIR/00-ragas-generate-questions.log" \
  "$GREV_BIN" ragas generate-questions --source "$STAGED_SOURCE_DIR" --output "$RAGAS_QUESTIONS_DIR/questions.json" --testset-size ${GREV_RAGAS_TESTSET_SIZE:-1}

run_step \
  "ragas evaluate" \
  "$LOG_DIR/01-ragas-evaluate.log" \
  "$GREV_BIN" ragas evaluate --benchmark "$BENCHMARK_JSON" --search-results "$RESULTS_JSON" --output "$RAGAS_EVAL_DIR/evaluation.json" --metrics context_precision

run_step \
  "pipeline report" \
  "$LOG_DIR/02-ragas-pipeline-report.log" \
  python3 "$REPORT_RENDERER" --title "Ragas Pipeline Report" --output "$PIPELINE_REPORT" "$SUMMARY_FILE"

printf '\n%s\n' "summary written to: $SUMMARY_FILE"
printf '%s\n' "logs written to: $LOG_DIR"
printf '%s\n' "report written to: $PIPELINE_REPORT"
printf '%s\n' "completed steps: $run_count"
printf '%s\n' "failed steps: $fail_count"

if [ "$fail_count" -eq 0 ]; then
  exit 0
fi
exit 1
