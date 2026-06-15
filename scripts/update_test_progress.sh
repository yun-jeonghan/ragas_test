#!/usr/bin/env sh

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
STATE_JSON="$REPO_ROOT/.test_progress_state.json"
PROGRESS_MD="$REPO_ROOT/test_progress.md"
COLLECT_OUT="$REPO_ROOT/.test_progress_pytest_collect.txt"
PYTEST_XML="$REPO_ROOT/.test_progress_pytest.xml"
RUN_AT=$(date -u +"%Y-%m-%d %H:%M:%S UTC")
MODE=${1:-all}

source_env_file() {
  file=$1
  if [ -f "$file" ]; then
    set -a
    . "$file"
    set +a
  fi
}

if [ -f "$REPO_ROOT/.env" ]; then
  source_env_file "$REPO_ROOT/.env"
fi

PYTEST_RC=0
MATRIX_RC=0
MATRIX_SUMMARY="$REPO_ROOT/.test_progress_matrix_summary.jsonl"
MATRIX_ROOT="data/test_$(date +%Y%m%d_%H%M%S)_progress"
: > "$MATRIX_SUMMARY"

if [ "$MODE" = "all" ] || [ "$MODE" = "pytest" ]; then
  cd "$REPO_ROOT"
  set +e
  python3 -m pytest --collect-only -q > "$COLLECT_OUT"
  collect_rc=$?
  set -e
  if [ "$collect_rc" -ne 0 ]; then
    PYTEST_RC=$collect_rc
  fi
  set +e
  python3 -m pytest -q --junitxml "$PYTEST_XML" >/dev/null
  PYTEST_RC=$?
  set -e
fi

if [ "$MODE" = "all" ] || [ "$MODE" = "matrix" ]; then
  set +e
  "$SCRIPT_DIR/grev_matrix.sh" "$MATRIX_ROOT"
  MATRIX_RC=$?
  set -e
  cp -f "$REPO_ROOT/$MATRIX_ROOT/output/summary.jsonl" "$MATRIX_SUMMARY"
fi

python3 "$SCRIPT_DIR/render_test_progress.py" \
  "$COLLECT_OUT" \
  "$PYTEST_XML" \
  "$MATRIX_SUMMARY" \
  "$STATE_JSON" \
  "$PROGRESS_MD" \
  "$RUN_AT"

printf '%s\n' "updated: $PROGRESS_MD"
printf '%s\n' "state: $STATE_JSON"

if [ "$PYTEST_RC" -ne 0 ] || [ "$MATRIX_RC" -ne 0 ]; then
  printf '%s\n' "pytest_rc=$PYTEST_RC matrix_rc=$MATRIX_RC" >&2
  exit 1
fi

exit 0
