#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/_common.sh"
exec "$PY" "$ROOT/tools/pipeline.py" pyspy "$@"
