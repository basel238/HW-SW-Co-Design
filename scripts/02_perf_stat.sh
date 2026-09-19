#!/usr/bin/env bash
set -euo pipefail
if [[ ${1:-} == --direct ]]; then
    shift
    exec bash "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/direct/02_perf_stat.sh" "$@"
fi
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/_common.sh"
exec "$PY" "$ROOT/tools/pipeline.py" stat "$@"
