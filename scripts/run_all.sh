#!/usr/bin/env bash
set -euo pipefail
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/_common.sh"
exec "$PY" "$ROOT/tools/pipeline.py" all "$@"
