#!/usr/bin/env sh

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
GREV_BIN=${GREV_BIN:-grev}
GRAPHRAG_BIN=${GRAPHRAG_BIN:-graphrag}
REPORT_RENDERER=${REPORT_RENDERER:-"$SCRIPT_DIR/render_pipeline_report.py"}

if [ -f "$REPO_ROOT/.env" ]; then
  set -a
  . "$REPO_ROOT/.env"
  set +a
fi

GRAPHRAG_CHAT_MODEL=${GREV_GRAPHRAG_MODEL:-${GREV_RAGAS_MODEL:-${GREV_BENCHMARKQED_MODEL:-}}}
GRAPHRAG_EMBEDDING_MODEL=${GREV_GRAPHRAG_EMBEDDING_MODEL:-${GREV_RAGAS_EMBEDDINGS_MODEL:-${GREV_BENCHMARKQED_EMBEDDINGS_MODEL:-}}}
GRAPHRAG_API_BASE=${GRAPHRAG_API_BASE:-${GREV_GRAPHRAG_API_BASE:-${GREV_RAGAS_BASE_URL:-${GREV_BENCHMARKQED_BASE_URL:-}}}}
GRAPHRAG_API_KEY=${GREV_GRAPHRAG_API_KEY:-${GREV_RAGAS_API_KEY:-${GREV_BENCHMARKQED_API_KEY:-}}}

if [ -z "$GRAPHRAG_CHAT_MODEL" ] || [ -z "$GRAPHRAG_EMBEDDING_MODEL" ] || [ -z "$GRAPHRAG_API_BASE" ] || [ -z "$GRAPHRAG_API_KEY" ]; then
  printf '%s\n' "Missing env. Set GREV_GRAPHRAG_MODEL/GREV_RAGAS_MODEL/GREV_BENCHMARKQED_MODEL, embedding variants, GRAPHRAG_API_BASE, and api key env before running." >&2
  exit 1
fi

export GRAPHRAG_API_BASE
export GREV_GRAPHRAG_API_KEY="$GRAPHRAG_API_KEY"
export GREV_RAGAS_MODEL=${GREV_RAGAS_MODEL:-$GRAPHRAG_CHAT_MODEL}
export GREV_BENCHMARKQED_MODEL=${GREV_BENCHMARKQED_MODEL:-$GRAPHRAG_CHAT_MODEL}
export GREV_KGGEN_MINE_MODEL=${GREV_KGGEN_MINE_MODEL:-$GRAPHRAG_CHAT_MODEL}
export GREV_RAGAS_EMBEDDINGS_MODEL=${GREV_RAGAS_EMBEDDINGS_MODEL:-$GRAPHRAG_EMBEDDING_MODEL}
export GREV_BENCHMARKQED_EMBEDDINGS_MODEL=${GREV_BENCHMARKQED_EMBEDDINGS_MODEL:-$GRAPHRAG_EMBEDDING_MODEL}

if [ "$#" -lt 5 ]; then
  printf '%s\n' "Usage: benchmark_pipeline.sh SOURCE_DIR BENCHMARK_JSON RESULTS_JSON ONTOLOGY_JSON OUTPUT_DIR" >&2
  exit 1
fi

SOURCE_DIR=$1
BENCHMARK_JSON=$2
RESULTS_JSON=$3
ONTOLOGY_JSON=$4
OUTPUT_DIR=$5

case "$OUTPUT_DIR" in
  /*) : ;;
  *)
    OUTPUT_DIR="$REPO_ROOT/$OUTPUT_DIR"
    ;;
esac

LOG_DIR="$OUTPUT_DIR/logs"
WORK_DIR="$OUTPUT_DIR/work"
SUMMARY_FILE="$OUTPUT_DIR/summary.jsonl"

STANDARD_WORKSPACE="$WORK_DIR/graphrag-standard"
ONTOLOGY_WORKSPACE="$WORK_DIR/graphrag-ontology"
SMOKE_OUTPUT_DIR="$OUTPUT_DIR/runs/benchmark-qed"
RETRIEVAL_SMOKE_DIR="$OUTPUT_DIR/runs/retrieval-smoke"
RETRIEVAL_REFERENCE_DIR="$OUTPUT_DIR/runs/retrieval-reference"
RETRIEVAL_SCORE_DIR="$OUTPUT_DIR/runs/retrieval-score"
ASSERTION_SCORE_DIR="$OUTPUT_DIR/runs/assertion-score"
ASSERTION_REPORT_DIR="$OUTPUT_DIR/runs/assertion-report"
GENERATE_QUESTIONS_DIR="$OUTPUT_DIR/runs/generate-questions"
BENCHMARK_GQ_DIR="$OUTPUT_DIR/runs/benchmark-generate-questions"
AUTOQ_DIR="$OUTPUT_DIR/runs/benchmark-qed-autoq"
AUTOD_DIR="$OUTPUT_DIR/runs/benchmark-qed-autod"
AUTOE_DIR="$OUTPUT_DIR/runs/benchmark-qed-autoe"
EVALUATE_DIR="$OUTPUT_DIR/runs/evaluate"
RAGAS_EVAL_DIR="$OUTPUT_DIR/runs/ragas-evaluate"
KGGEN_DIR="$OUTPUT_DIR/runs/kggen-mine"
KGCORRECTNESS_DIR="$OUTPUT_DIR/runs/kg-correctness"
OGRAG2_DIR="$OUTPUT_DIR/runs/ograg2"
REPORT_DIR="$OUTPUT_DIR/reports"
PIPELINE_REPORT="$REPORT_DIR/benchmark-pipeline.html"

run_count=0
fail_count=0

mkdir -p \
  "$LOG_DIR" \
  "$WORK_DIR" \
  "$SMOKE_OUTPUT_DIR" \
  "$RETRIEVAL_SMOKE_DIR" \
  "$RETRIEVAL_REFERENCE_DIR" \
  "$RETRIEVAL_SCORE_DIR" \
  "$ASSERTION_SCORE_DIR" \
  "$ASSERTION_REPORT_DIR" \
  "$GENERATE_QUESTIONS_DIR" \
  "$BENCHMARK_GQ_DIR" \
  "$AUTOQ_DIR" \
  "$AUTOD_DIR" \
  "$AUTOE_DIR" \
  "$EVALUATE_DIR" \
  "$RAGAS_EVAL_DIR" \
  "$KGGEN_DIR" \
  "$KGCORRECTNESS_DIR" \
  "$OGRAG2_DIR" \
  "$REPORT_DIR"
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
require_cmd "$GRAPHRAG_BIN"
require_cmd python3

printf '%s\n' "repo: $REPO_ROOT"
printf '%s\n' "source_dir: $SOURCE_DIR"
printf '%s\n' "benchmark_json: $BENCHMARK_JSON"
printf '%s\n' "results_json: $RESULTS_JSON"
printf '%s\n' "ontology_json: $ONTOLOGY_JSON"
printf '%s\n' "output_dir: $OUTPUT_DIR"
printf '%s\n' "summary: $SUMMARY_FILE"

run_step \
  "grev init" \
  "$LOG_DIR/00-grev-init.log" \
  "$GREV_BIN" init --root "$OUTPUT_DIR/project-layout"

run_step \
  "graphrag normalize" \
  "$LOG_DIR/01-graphrag-normalize.log" \
  "$GREV_BIN" graphrag normalize --source "$SOURCE_DIR" --workspace-root "$STANDARD_WORKSPACE" --clean

run_step \
  "graphrag stage" \
  "$LOG_DIR/02-graphrag-stage.log" \
  "$GREV_BIN" graphrag stage --source "$SOURCE_DIR" --workspace-root "$STANDARD_WORKSPACE" --clean

run_step \
  "graphrag init" \
  "$LOG_DIR/03-graphrag-init.log" \
  "$GREV_BIN" graphrag init --source "$SOURCE_DIR" --workspace-root "$STANDARD_WORKSPACE" --clean --force --model "$GRAPHRAG_CHAT_MODEL" --embedding "$GRAPHRAG_EMBEDDING_MODEL"

run_step \
  "graphrag index standard" \
  "$LOG_DIR/04-graphrag-index-standard.log" \
  "$GREV_BIN" graphrag index --source "$SOURCE_DIR" --workspace-root "$STANDARD_WORKSPACE" --force --method standard --model "$GRAPHRAG_CHAT_MODEL" --embedding "$GRAPHRAG_EMBEDDING_MODEL"

run_step \
  "graphrag index ontology+postprocess" \
  "$LOG_DIR/05-graphrag-index-ontology.log" \
  "$GREV_BIN" graphrag index --source "$SOURCE_DIR" --workspace-root "$ONTOLOGY_WORKSPACE" --force --method standard --ontology-path "$ONTOLOGY_JSON" --postprocess --description-limit 200 --model "$GRAPHRAG_CHAT_MODEL" --embedding "$GRAPHRAG_EMBEDDING_MODEL"

run_step \
  "graphrag postprocess" \
  "$LOG_DIR/06-graphrag-postprocess.log" \
  "$GREV_BIN" graphrag postprocess --workspace-root "$ONTOLOGY_WORKSPACE" --description-limit 200

run_step \
  "inspect" \
  "$LOG_DIR/07-inspect.log" \
  "$GREV_BIN" inspect --graphrag-root "$ONTOLOGY_WORKSPACE/output"

run_step \
  "benchmark generate-questions" \
  "$LOG_DIR/08-generate-questions.log" \
  "$GREV_BIN" generate-questions --source "$SOURCE_DIR" --output "$GENERATE_QUESTIONS_DIR/generated_questions.json" --num-questions ${GREV_BENCHMARKQED_GENERATED_QUESTIONS:-1} --modes local --modes global --modes multi-hop --modes unanswerable

run_step \
  "benchmark-qed autod" \
  "$LOG_DIR/09-benchmark-qed-autod.log" \
  "$GREV_BIN" benchmark-qed autod --source "$SOURCE_DIR" --output "$AUTOD_DIR/autod-summary.json" --target-size ${GREV_BENCHMARKQED_TARGET_SIZE:-1}

run_step \
  "benchmark-qed autoq" \
  "$LOG_DIR/10-benchmark-qed-autoq.log" \
  "$GREV_BIN" benchmark-qed autoq --source "$SOURCE_DIR" --output "$AUTOQ_DIR/autoq-questions.json" --num-questions ${GREV_BENCHMARKQED_NUM_QUESTIONS:-1} --modes local

run_step \
  "benchmark-qed autoe" \
  "$LOG_DIR/11-benchmark-qed-autoe.log" \
  "$GREV_BIN" benchmark-qed autoe --benchmark "$BENCHMARK_JSON" --search-results "$RESULTS_JSON" --output "$AUTOE_DIR/autoe-evaluation.json" --metrics context_precision

run_step \
  "benchmark-qed smoke" \
  "$LOG_DIR/12-benchmark-qed-smoke.log" \
  "$GREV_BIN" benchmark-qed smoke --source "$SOURCE_DIR" --benchmark "$BENCHMARK_JSON" --search-results "$RESULTS_JSON" --output-dir "$SMOKE_OUTPUT_DIR" --report-output "$SMOKE_OUTPUT_DIR/benchmark-qed-report.html" --target-size ${GREV_BENCHMARKQED_TARGET_SIZE:-1} --num-questions ${GREV_BENCHMARKQED_NUM_QUESTIONS:-1} --modes local --metrics context_precision --title "BenchmarkQED Pipeline Report"

run_step \
  "benchmark-qed retrieval-smoke" \
  "$LOG_DIR/13-benchmark-qed-retrieval-smoke.log" \
  "$GREV_BIN" benchmark-qed retrieval-smoke --benchmark "$BENCHMARK_JSON" --search-results "$RESULTS_JSON" --graphrag-root "$ONTOLOGY_WORKSPACE/output" --output-dir "$RETRIEVAL_SMOKE_DIR" --report-output "$RETRIEVAL_SMOKE_DIR/retrieval-report.html" --question-sets default --rag-method-name benchmark-qed --reference-filename reference.json --relevance-threshold 2 --cluster-match-by id --significance-alpha 0.05 --significance-correction holm --fidelity-metric js --assessor-type rationale --semantic-neighbors 10 --centroid-neighbors 5 --concurrent-requests ${GREV_BENCHMARKQED_CONCURRENT_REQUESTS:-4} --max-concurrent ${GREV_BENCHMARKQED_MAX_CONCURRENT:-4}

run_step \
  "benchmark-qed retrieval-reference" \
  "$LOG_DIR/14-benchmark-qed-retrieval-reference.log" \
  "$GREV_BIN" benchmark-qed retrieval-reference --questions "$BENCHMARK_JSON" --clusters "$RETRIEVAL_SMOKE_DIR/clusters.json" --text-units "$ONTOLOGY_WORKSPACE/output/text_units.parquet" --output "$RETRIEVAL_REFERENCE_DIR/reference.json" --max-questions ${GREV_BENCHMARKQED_NUM_QUESTIONS:-1} --assessor-type rationale --semantic-neighbors 10 --centroid-neighbors 5 --concurrent-requests ${GREV_BENCHMARKQED_CONCURRENT_REQUESTS:-4}

run_step \
  "benchmark-qed retrieval-score" \
  "$LOG_DIR/15-benchmark-qed-retrieval-score.log" \
  "$GREV_BIN" benchmark-qed retrieval-score --reference-dir "$RETRIEVAL_REFERENCE_DIR" --clusters "$RETRIEVAL_SMOKE_DIR/clusters.json" --retrieval-results "$RETRIEVAL_SMOKE_DIR/retrieval-results.json" --output "$RETRIEVAL_SCORE_DIR/retrieval-evaluation.json" --text-units "$ONTOLOGY_WORKSPACE/output/text_units.parquet" --question-sets default --rag-method-name benchmark-qed --reference-filename reference.json --relevance-threshold 2 --context-id-key chunk_id --context-text-key text --cluster-match-by id --significance-alpha 0.05 --significance-correction holm --fidelity-metric js --assessor-type rationale --concurrent-requests ${GREV_BENCHMARKQED_CONCURRENT_REQUESTS:-4} --max-concurrent ${GREV_BENCHMARKQED_MAX_CONCURRENT:-4}

run_step \
  "benchmark-qed assertion-score" \
  "$LOG_DIR/16-benchmark-qed-assertion-score.log" \
  "$GREV_BIN" benchmark-qed assertion-score --assertion-prep "$SMOKE_OUTPUT_DIR/assertion-prep.json" --answers "$RESULTS_JSON" --output "$ASSERTION_SCORE_DIR/assertion-scores.json" --trials ${GREV_BENCHMARKQED_ASSERTION_TRIALS:-1} --top-k-assertions ${GREV_BENCHMARKQED_TOP_K_ASSERTIONS:-1}

run_step \
  "benchmark-qed assertion-report" \
  "$LOG_DIR/17-benchmark-qed-assertion-report.log" \
  "$GREV_BIN" benchmark-qed assertion-report --assertion-scores "$ASSERTION_SCORE_DIR/assertion-scores.json" --output "$ASSERTION_REPORT_DIR/assertion-report.html" --title "BenchmarkQED Assertion Report"

run_step \
  "evaluate" \
  "$LOG_DIR/18-evaluate.log" \
  "$GREV_BIN" evaluate --benchmark "$BENCHMARK_JSON" --search-results "$RESULTS_JSON" --output "$EVALUATE_DIR/evaluation.json" --metrics context_precision

run_step \
  "ragas evaluate" \
  "$LOG_DIR/19-ragas-evaluate.log" \
  "$GREV_BIN" ragas evaluate --benchmark "$BENCHMARK_JSON" --search-results "$RESULTS_JSON" --output "$RAGAS_EVAL_DIR/evaluation.json" --metrics context_precision

run_step \
  "kg-gen mine evaluate" \
  "$LOG_DIR/20-kggen-mine.log" \
  "$GREV_BIN" kg-gen mine evaluate --benchmark "$BENCHMARK_JSON" --search-results "$RESULTS_JSON" --output "$KGGEN_DIR/evaluation.json"

run_step \
  "kg-correctness evaluate" \
  "$LOG_DIR/21-kg-correctness.log" \
  "$GREV_BIN" kg-correctness evaluate --benchmark "$BENCHMARK_JSON" --search-results "$RESULTS_JSON" --output "$KGCORRECTNESS_DIR/evaluation.json"

run_step \
  "ograg2 evaluate" \
  "$LOG_DIR/22-ograg2-evaluate.log" \
  "$GREV_BIN" ograg2 evaluate --config-file "$REPO_ROOT/vendor/ograg2/configs/demo_config.yaml" --results-dir "$OGRAG2_DIR/results" --rewrite --force-map-ontology --force-create-kg-triples

run_step \
  "pipeline report" \
  "$LOG_DIR/23-benchmark-pipeline-report.log" \
  python3 "$REPORT_RENDERER" --title "Benchmark Pipeline Report" --output "$PIPELINE_REPORT" "$SUMMARY_FILE"

printf '\n%s\n' "summary written to: $SUMMARY_FILE"
printf '%s\n' "logs written to: $LOG_DIR"
printf '%s\n' "report written to: $PIPELINE_REPORT"
printf '%s\n' "completed steps: $run_count"
printf '%s\n' "failed steps: $fail_count"

if [ "$fail_count" -eq 0 ]; then
  exit 0
fi
exit 1
