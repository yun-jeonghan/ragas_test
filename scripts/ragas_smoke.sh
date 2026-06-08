#!/usr/bin/env sh

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

if [ "$#" -lt 4 ]; then
  printf '%s\n' "Usage: ragas_smoke.sh SOURCE_DIR BENCHMARK_JSON RESULTS_JSON OUTPUT_DIR" >&2
  exit 1
fi

exec "$SCRIPT_DIR/ragas_pipeline.sh" "$@"
