#!/usr/bin/env sh

set -eu

REPO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
LOCAL_GREV_BIN="$REPO_ROOT/scripts/grev_local.sh"
if [ -x "$LOCAL_GREV_BIN" ]; then
  GREV_BIN=${GREV_BIN:-"$LOCAL_GREV_BIN"}
else
  GREV_BIN=${GREV_BIN:-grev}
fi
GRAPHRAG_BIN=${GRAPHRAG_BIN:-graphrag}
GRAPHRAG_CHAT_MODEL=${GREV_GRAPHRAG_MODEL:-${GREV_RAGAS_MODEL:-${GREV_BENCHMARKQED_MODEL:-}}}
GRAPHRAG_EMBEDDING_MODEL=${GREV_GRAPHRAG_EMBEDDING_MODEL:-${GREV_RAGAS_EMBEDDINGS_MODEL:-${GREV_BENCHMARKQED_EMBEDDINGS_MODEL:-}}}

if [ -f "$REPO_ROOT/.env" ]; then
  set -a
  . "$REPO_ROOT/.env"
  set +a
  GRAPHRAG_CHAT_MODEL=${GREV_GRAPHRAG_MODEL:-${GREV_RAGAS_MODEL:-${GREV_BENCHMARKQED_MODEL:-}}}
  GRAPHRAG_EMBEDDING_MODEL=${GREV_GRAPHRAG_EMBEDDING_MODEL:-${GREV_RAGAS_EMBEDDINGS_MODEL:-${GREV_BENCHMARKQED_EMBEDDINGS_MODEL:-}}}
fi

if [ -z "$GRAPHRAG_CHAT_MODEL" ] || [ -z "$GRAPHRAG_EMBEDDING_MODEL" ]; then
  printf '%s\n' "Missing env. Set GREV_GRAPHRAG_MODEL/GREV_RAGAS_MODEL/GREV_BENCHMARKQED_MODEL and matching embedding vars before running." >&2
  exit 1
fi

TEST_ROOT=${1:-"data/test_$(date +%Y%m%d_%H%M%S)"}
case "$TEST_ROOT" in
  data/test_*)
    ;;
  *)
    printf '%s\n' "Refusing to use non-test path: $TEST_ROOT" >&2
    exit 1
    ;;
esac

INPUT_DIR="$REPO_ROOT/$TEST_ROOT/input"
OUTPUT_DIR="$REPO_ROOT/$TEST_ROOT/output"
LOG_DIR="$OUTPUT_DIR/logs"
WORK_DIR="$OUTPUT_DIR/work"
SUMMARY_FILE="$OUTPUT_DIR/summary.jsonl"

STANDARD_WORKSPACE="$WORK_DIR/graphrag-standard"
ONTOLOGY_WORKSPACE="$WORK_DIR/graphrag-ontology"

SOURCE_INPUT_DIR="$INPUT_DIR/source"
SAMPLE_SOURCE_DIR="$REPO_ROOT/examples/sample_docs_10pages"
BENCHMARK_INPUT_DIR="$INPUT_DIR/benchmark"
RESULTS_INPUT_DIR="$INPUT_DIR/results"
ASSERTION_INPUT_DIR="$INPUT_DIR/assertion"
ONTOLOGY_INPUT_DIR="$INPUT_DIR/ontology"

SMOKE_OUTPUT_DIR="$OUTPUT_DIR/runs/benchmark-qed-smoke"
RETRIEVAL_SMOKE_DIR="$OUTPUT_DIR/runs/retrieval-smoke"
RETRIEVAL_REFERENCE_DIR="$OUTPUT_DIR/runs/retrieval-reference"
RETRIEVAL_SCORE_DIR="$OUTPUT_DIR/runs/retrieval-score"
ASSERTION_SCORE_DIR="$OUTPUT_DIR/runs/assertion-score"
ASSERTION_REPORT_DIR="$OUTPUT_DIR/runs/assertion-report"
REPORT_SMOKE_DIR="$OUTPUT_DIR/runs/report-smoke"
GENERATE_QUESTIONS_DIR="$OUTPUT_DIR/runs/generate-questions"
RAGAS_QUESTIONS_DIR="$OUTPUT_DIR/runs/ragas-generate-questions"
RAGAS_EVAL_DIR="$OUTPUT_DIR/runs/ragas-evaluate"
EVALUATE_DIR="$OUTPUT_DIR/runs/evaluate"
KGGEN_DIR="$OUTPUT_DIR/runs/kggen-mine"
KGCORRECTNESS_DIR="$OUTPUT_DIR/runs/kg-correctness"
OGRAG2_DIR="$OUTPUT_DIR/runs/ograg2"

run_count=0
fail_count=0
STATUS_DIR="$OUTPUT_DIR/.step_status"

mkdir -p "$SOURCE_INPUT_DIR" "$BENCHMARK_INPUT_DIR" "$RESULTS_INPUT_DIR" "$ASSERTION_INPUT_DIR" "$ONTOLOGY_INPUT_DIR"
mkdir -p "$LOG_DIR" "$WORK_DIR" "$OUTPUT_DIR/runs" "$SMOKE_OUTPUT_DIR" "$RETRIEVAL_SMOKE_DIR" "$RETRIEVAL_REFERENCE_DIR" "$RETRIEVAL_SCORE_DIR" "$ASSERTION_SCORE_DIR" "$ASSERTION_REPORT_DIR" "$REPORT_SMOKE_DIR" "$GENERATE_QUESTIONS_DIR" "$RAGAS_QUESTIONS_DIR" "$RAGAS_EVAL_DIR" "$EVALUATE_DIR" "$KGGEN_DIR" "$KGCORRECTNESS_DIR" "$OGRAG2_DIR" "$STATUS_DIR"
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

step_status_file() {
  printf '%s/%s.status' "$STATUS_DIR" "$(printf '%s' "$1" | sed 's/[^A-Za-z0-9_.-]/_/g')"
}

mark_step_status() {
  printf '%s\n' "$2" > "$(step_status_file "$1")"
}

read_step_status() {
  status_file=$(step_status_file "$1")
  if [ -f "$status_file" ]; then
    cat "$status_file"
  fi
}

first_failed_dep_file() {
  deps_file=$1
  while IFS= read -r dep; do
    [ -n "$dep" ] || continue
    dep_status=$(read_step_status "$dep" || true)
    if [ "$dep_status" = "failed" ]; then
      printf '%s' "$dep"
      return 0
    fi
  done < "$deps_file"
  return 1
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
    mark_step_status "$step_name" passed
  else
    printf '  err %s (see %s)\n' "$step_name" "$log_file"
    fail_count=$((fail_count + 1))
    mark_step_status "$step_name" failed
  fi
}

run_step_with_deps() {
  step_name=$1
  log_file=$2
  shift 2

  deps_file=$(mktemp "$STATUS_DIR/deps.XXXXXX")
  while [ "$#" -gt 0 ]; do
    if [ "$1" = "--" ]; then
      shift
      break
    fi
    printf '%s\n' "$1" >> "$deps_file"
    shift
  done

  if failed_dep=$(first_failed_dep_file "$deps_file"); then
    rm -f "$deps_file"
    run_count=$((run_count + 1))
    printf '\n[%02d] %s\n' "$run_count" "$step_name"
    printf '  err %s (dependency failed: %s)\n' "$step_name" "$failed_dep"
    printf 'dependency failed: %s\n' "$failed_dep" > "$log_file"
    append_summary "$step_name" 1 "$log_file"
    mark_step_status "$step_name" failed
    fail_count=$((fail_count + 1))
    return 0
  fi

  rm -f "$deps_file"
  run_step "$step_name" "$log_file" "$@"
}

copy_inputs() {
  sample_source_count=$(find "$SAMPLE_SOURCE_DIR" -maxdepth 1 -type f | wc -l | tr -d ' ')
  if [ "$sample_source_count" -lt 3 ]; then
    printf '%s\n' "Need at least 10 source docs in $SAMPLE_SOURCE_DIR" >&2
    exit 1
  fi

  cp -f "$SAMPLE_SOURCE_DIR"/* "$SOURCE_INPUT_DIR/"
  cp -f "$REPO_ROOT/data/benchmarks/sample_benchmark.json" "$BENCHMARK_INPUT_DIR/sample_benchmark.json"
  cp -f "$REPO_ROOT/data/results/sample_search_results.json" "$RESULTS_INPUT_DIR/sample_search_results.json"

  cat > "$ASSERTION_INPUT_DIR/assertion-prep.json" <<'EOF'
{
  "metadata": {
    "component": "AssertionPrep",
    "backend": "benchmark-qed",
    "source": "script-generated"
  },
  "questions": [
    {
      "question_id": "scrooge-1",
      "question_text": "Who is Scrooge?",
      "assertions": [
        {
          "statement": "The answer should mention Scrooge.",
          "rank": 1
        }
      ]
    }
  ]
}
EOF

  cat > "$ASSERTION_INPUT_DIR/answers.json" <<'EOF'
{
  "results": [
    {
      "sample_id": "scrooge-1",
      "question": "Who is Scrooge?",
      "answer": "Scrooge is a miser who loves money more than people."
    }
  ]
}
EOF

  cat > "$ONTOLOGY_INPUT_DIR/user_ontology.json" <<'EOF'
{
  "allowed_types": ["person", "place", "organization", "object"],
  "extraction_rules": {
    "prefer_source_grounding": true,
    "normalize_names": ["alias", "canonical"],
    "keep_relationship_labels_canonical": true
  }
}
EOF
}

require_cmd "$GREV_BIN"
require_cmd "$GRAPHRAG_BIN"

printf '%s\n' "repo: $REPO_ROOT"
printf '%s\n' "test_root: $TEST_ROOT"
printf '%s\n' "input_dir: $INPUT_DIR"
printf '%s\n' "output_dir: $OUTPUT_DIR"
printf '%s\n' "summary: $SUMMARY_FILE"

copy_inputs

run_step \
  "grev init" \
  "$LOG_DIR/00-grev-init.log" \
  "$GREV_BIN" init --root "$OUTPUT_DIR/project-layout"

run_step \
  "graphrag normalize" \
  "$LOG_DIR/01-graphrag-normalize.log" \
  "$GREV_BIN" graphrag normalize --source "$SOURCE_INPUT_DIR" --workspace-root "$STANDARD_WORKSPACE" --clean

run_step \
  "graphrag stage" \
  "$LOG_DIR/02-graphrag-stage.log" \
  "$GREV_BIN" graphrag stage --source "$SOURCE_INPUT_DIR" --workspace-root "$STANDARD_WORKSPACE" --clean

run_step \
  "graphrag init" \
  "$LOG_DIR/03-graphrag-init.log" \
  "$GREV_BIN" graphrag init --source "$SOURCE_INPUT_DIR" --workspace-root "$STANDARD_WORKSPACE" --clean --force --model "$GRAPHRAG_CHAT_MODEL" --embedding "$GRAPHRAG_EMBEDDING_MODEL"

run_step \
  "graphrag index standard" \
  "$LOG_DIR/04-graphrag-index-standard.log" \
  "$GREV_BIN" graphrag index --source "$SOURCE_INPUT_DIR" --workspace-root "$STANDARD_WORKSPACE" --force --method standard --model "$GRAPHRAG_CHAT_MODEL" --embedding "$GRAPHRAG_EMBEDDING_MODEL"

run_step \
  "graphrag index ontology+postprocess" \
  "$LOG_DIR/05-graphrag-index-ontology.log" \
  "$GREV_BIN" graphrag index --source "$SOURCE_INPUT_DIR" --workspace-root "$ONTOLOGY_WORKSPACE" --force --method standard --ontology-path "$ONTOLOGY_INPUT_DIR/user_ontology.json" --postprocess --description-limit 200 --model "$GRAPHRAG_CHAT_MODEL" --embedding "$GRAPHRAG_EMBEDDING_MODEL"

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
  "$GREV_BIN" generate-questions --source "$SOURCE_INPUT_DIR" --output "$GENERATE_QUESTIONS_DIR/generated_questions.json" --num-questions 1 --modes local --modes global --modes multi-hop --modes unanswerable

run_step \
  "ragas generate-questions" \
  "$LOG_DIR/08b-ragas-generate-questions.log" \
  "$GREV_BIN" ragas generate-questions --source "$SOURCE_INPUT_DIR" --output "$RAGAS_QUESTIONS_DIR/questions.json" --testset-size 1

run_step \
  "benchmark-qed autod" \
  "$LOG_DIR/09-benchmark-qed-autod.log" \
  "$GREV_BIN" benchmark-qed autod --source "$SOURCE_INPUT_DIR" --output "$OUTPUT_DIR/runs/benchmark-qed-autod/autod-summary.json" --target-size 1

run_step \
  "benchmark-qed autoq" \
  "$LOG_DIR/10-benchmark-qed-autoq.log" \
  "$GREV_BIN" benchmark-qed autoq --source "$SOURCE_INPUT_DIR" --output "$OUTPUT_DIR/runs/benchmark-qed-autoq/autoq-questions.json" --num-questions 1 --modes local

run_step \
  "benchmark-qed autoe" \
  "$LOG_DIR/11-benchmark-qed-autoe.log" \
  "$GREV_BIN" benchmark-qed autoe --benchmark "$BENCHMARK_INPUT_DIR/sample_benchmark.json" --search-results "$RESULTS_INPUT_DIR/sample_search_results.json" --output "$OUTPUT_DIR/runs/benchmark-qed-autoe/autoe-evaluation.json" --metrics context_precision

run_step \
  "benchmark-qed smoke" \
  "$LOG_DIR/12-benchmark-qed-smoke.log" \
  "$GREV_BIN" benchmark-qed smoke --source "$SOURCE_INPUT_DIR" --benchmark "$BENCHMARK_INPUT_DIR/sample_benchmark.json" --search-results "$RESULTS_INPUT_DIR/sample_search_results.json" --output-dir "$SMOKE_OUTPUT_DIR" --report-output "$SMOKE_OUTPUT_DIR/benchmark-qed-smoke.html" --target-size 1 --num-questions 1 --modes local --metrics context_precision --title "BenchmarkQED Smoke Report"

run_step \
  "benchmark-qed retrieval-smoke" \
  "$LOG_DIR/13-benchmark-qed-retrieval-smoke.log" \
  "$GREV_BIN" benchmark-qed retrieval-smoke --benchmark "$BENCHMARK_INPUT_DIR/sample_benchmark.json" --search-results "$RESULTS_INPUT_DIR/sample_search_results.json" --graphrag-root "$ONTOLOGY_WORKSPACE/output" --output-dir "$RETRIEVAL_SMOKE_DIR" --report-output "$RETRIEVAL_SMOKE_DIR/retrieval-smoke.html" --question-sets default --rag-method-name benchmark-qed --reference-filename reference.json --relevance-threshold 2 --cluster-match-by id --significance-alpha 0.05 --significance-correction holm --fidelity-metric js --assessor-type rationale --semantic-neighbors 10 --centroid-neighbors 5 --concurrent-requests 4 --max-concurrent 4

run_step \
  "benchmark-qed retrieval-reference" \
  "$LOG_DIR/14-benchmark-qed-retrieval-reference.log" \
  "$GREV_BIN" benchmark-qed retrieval-reference --questions "$BENCHMARK_INPUT_DIR/sample_benchmark.json" --clusters "$RETRIEVAL_SMOKE_DIR/clusters.json" --text-units "$ONTOLOGY_WORKSPACE/output/text_units.parquet" --output "$RETRIEVAL_REFERENCE_DIR/reference.json" --max-questions 1 --assessor-type rationale --semantic-neighbors 10 --centroid-neighbors 5 --concurrent-requests 4

run_step_with_deps \
  "benchmark-qed retrieval-score" \
  "$LOG_DIR/15-benchmark-qed-retrieval-score.log" \
  "benchmark-qed retrieval-reference" "benchmark-qed retrieval-smoke" \
  -- \
  "$GREV_BIN" benchmark-qed retrieval-score --reference-dir "$RETRIEVAL_REFERENCE_DIR" --clusters "$RETRIEVAL_SMOKE_DIR/clusters.json" --retrieval-results "$RETRIEVAL_SMOKE_DIR/retrieval-results.json" --output "$RETRIEVAL_SCORE_DIR/retrieval-evaluation.json" --text-units "$ONTOLOGY_WORKSPACE/output/text_units.parquet" --question-sets default --rag-method-name benchmark-qed --reference-filename reference.json --relevance-threshold 2 --context-id-key chunk_id --context-text-key text --cluster-match-by id --significance-alpha 0.05 --significance-correction holm --fidelity-metric js --assessor-type rationale --concurrent-requests 4 --max-concurrent 4

run_step_with_deps \
  "benchmark-qed assertion-score" \
  "$LOG_DIR/16-benchmark-qed-assertion-score.log" \
  "benchmark-qed smoke" \
  -- \
  "$GREV_BIN" benchmark-qed assertion-score --assertion-prep "$SMOKE_OUTPUT_DIR/assertion-prep.json" --answers "$ASSERTION_INPUT_DIR/answers.json" --output "$ASSERTION_SCORE_DIR/assertion-scores.json" --trials 1 --top-k-assertions 1

run_step_with_deps \
  "benchmark-qed assertion-report" \
  "$LOG_DIR/17-benchmark-qed-assertion-report.log" \
  "benchmark-qed assertion-score" \
  -- \
  "$GREV_BIN" benchmark-qed assertion-report --assertion-scores "$ASSERTION_SCORE_DIR/assertion-scores.json" --output "$ASSERTION_REPORT_DIR/assertion-report.html" --title "BenchmarkQED Assertion Report"

run_step_with_deps \
  "evaluate" \
  "$LOG_DIR/18-evaluate.log" \
  "ragas generate-questions" \
  -- \
  "$GREV_BIN" evaluate --benchmark "$BENCHMARK_INPUT_DIR/sample_benchmark.json" --search-results "$RESULTS_INPUT_DIR/sample_search_results.json" --output "$EVALUATE_DIR/evaluation.json" --metrics context_precision

run_step_with_deps \
  "ragas evaluate" \
  "$LOG_DIR/19-ragas-evaluate.log" \
  "ragas generate-questions" \
  -- \
  "$GREV_BIN" ragas evaluate --benchmark "$BENCHMARK_INPUT_DIR/sample_benchmark.json" --search-results "$RESULTS_INPUT_DIR/sample_search_results.json" --output "$RAGAS_EVAL_DIR/evaluation.json" --metrics context_precision

run_step \
  "kg-gen mine evaluate" \
  "$LOG_DIR/20-kggen-mine.log" \
  "$GREV_BIN" kg-gen mine evaluate --benchmark "$BENCHMARK_INPUT_DIR/sample_benchmark.json" --search-results "$RESULTS_INPUT_DIR/sample_search_results.json" --output "$KGGEN_DIR/evaluation.json"

run_step \
  "kg-correctness evaluate" \
  "$LOG_DIR/21-kg-correctness.log" \
  "$GREV_BIN" kg-correctness evaluate --benchmark "$BENCHMARK_INPUT_DIR/sample_benchmark.json" --search-results "$RESULTS_INPUT_DIR/sample_search_results.json" --output "$KGCORRECTNESS_DIR/evaluation.json"

run_step_with_deps \
  "report smoke" \
  "$LOG_DIR/22-report-smoke.log" \
  "benchmark-qed smoke" "benchmark-qed autod" "benchmark-qed autoq" "benchmark-qed autoe" "benchmark generate-questions" \
  -- \
  "$GREV_BIN" report smoke --evaluation "$SMOKE_OUTPUT_DIR/autoe-evaluation.json" --generated-questions "$GENERATE_QUESTIONS_DIR/generated_questions.json" --autod-summary "$SMOKE_OUTPUT_DIR/autod-summary.json" --autoq-questions "$SMOKE_OUTPUT_DIR/autoq-questions.json" --output "$REPORT_SMOKE_DIR/report.html" --title "GraphRAG + Ragas Smoke Report"

run_step \
  "ograg2 evaluate" \
  "$LOG_DIR/23-ograg2-evaluate.log" \
  "$GREV_BIN" ograg2 evaluate --config-file "$REPO_ROOT/vendor/ograg2/configs/demo_config.yaml" --results-dir "$OGRAG2_DIR/results" --rewrite --force-map-ontology --force-create-kg-triples

printf '\n%s\n' "summary written to: $SUMMARY_FILE"
printf '%s\n' "logs written to: $LOG_DIR"
printf '%s\n' "completed steps: $run_count"
printf '%s\n' "failed steps: $fail_count"

if [ "$fail_count" -eq 0 ]; then
  exit 0
fi
exit 1
