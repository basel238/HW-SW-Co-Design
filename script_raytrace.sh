#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
case "${1:-stages1-3}" in
    setup) shift; exec bash "$ROOT/scripts/00_setup.sh" "$@" ;;
    compare) shift; exec bash "$ROOT/scripts/04_optimize_compare.sh" raytrace "$@" ;;
    baseline|optimized) exec bash "$ROOT/scripts/run_all.sh" raytrace "$@" ;;
    stages1-3) if [[ $# -gt 0 ]]; then shift; fi ;;
    --*) ;;
    *) echo "Usage: bash script_raytrace.sh [setup|stages1-3|baseline|optimized|compare] [course options]" >&2; exit 2 ;;
esac
exec bash "$ROOT/scripts/13_course_stages.sh" --benchmark raytrace "$@"
