#!/usr/bin/env bash
set -euo pipefail
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/_common.sh"
if [[ $# == 0 || ${1:-} == --* ]]; then
    exec "$PY" "$ROOT/tools/course_stages.py" "$@"
fi
BENCH="$1"
shift
if [[ ${1:-baseline} == optimized ]]; then
    exec "$PY" "$ROOT/tools/pipeline.py" all "$BENCH" "$@"
fi
if [[ ${1:-} == baseline ]]; then shift; fi
exec "$PY" "$ROOT/tools/course_stages.py" --benchmark "$BENCH" "$@"
