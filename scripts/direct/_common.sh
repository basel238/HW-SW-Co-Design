#!/usr/bin/env bash
# Shell-only launch support. No tools/*.py code is imported or executed.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
export LC_ALL=C

positive_integer() {
    [[ "$2" =~ ^[1-9][0-9]*$ ]] || { echo "$1 must be a positive integer." >&2; exit 2; }
}

prepare_direct() {
    KIND="$1"; shift
    if [[ ${1:-} == --help || $# == 0 ]]; then
        echo "Usage: bash scripts/direct/${KIND}.sh {nbody|raytrace} [baseline|optimized]"
        echo "See scripts/direct/README.md for settings and measurement boundaries."
        [[ $# != 0 ]] || exit 2
        return
    fi
    BENCH="$1"; VARIANT="${2:-baseline}"
    [[ $# -le 2 && "$BENCH" =~ ^(nbody|raytrace)$ && "$VARIANT" =~ ^(baseline|optimized)$ ]] || {
        echo "Expected nbody|raytrace and optional baseline|optimized." >&2; exit 2;
    }
    PY="$(command -v "${PYTHON_BIN:-$ROOT/.venv/bin/python}")" || {
        echo "Run scripts/00_setup.sh, or set PYTHON_BIN to debug Python." >&2; exit 2;
    }
    [[ "$PY" == /* ]] || PY="$PWD/$PY"
    # This identity check finishes before timing or profiling starts.
    IDENTITY="$("$PY" -c 'import sys, sysconfig, platform
if platform.python_implementation() != "CPython" or sys.version_info < (3, 10) or not sysconfig.get_config_var("Py_DEBUG") or sys.flags.optimize:
    sys.exit("Require debug CPython 3.10+ (Py_DEBUG=1), without -O/-OO.")
import pyperf
if pyperf.__version__ != "2.10.0":
    sys.exit("Require pyperf==2.10.0; run scripts/00_setup.sh.")
print(sys.executable + "\n" + sys.version + "\nPy_DEBUG=1")')" || exit 2
    SOURCE="$ROOT/src/$VARIANT/$BENCH/run_benchmark.py"
    [[ -f "$SOURCE" ]] || { echo "Missing benchmark: $SOURCE" >&2; exit 2; }
    BENCH_ARGS=()
    if [[ "$BENCH" == nbody ]]; then
        positive_integer DIRECT_ITERATIONS "${DIRECT_ITERATIONS:-20000}"
        BENCH_ARGS=(--iterations "${DIRECT_ITERATIONS:-20000}")
        DEFAULT_CALLS=40
    else
        positive_integer DIRECT_WIDTH "${DIRECT_WIDTH:-100}"
        positive_integer DIRECT_HEIGHT "${DIRECT_HEIGHT:-100}"
        [[ ${DIRECT_WIDTH:-100} -ge 2 && ${DIRECT_HEIGHT:-100} -ge 2 ]] || {
            echo "Raytrace dimensions must be at least 2." >&2; exit 2;
        }
        BENCH_ARGS=(--width "${DIRECT_WIDTH:-100}" --height "${DIRECT_HEIGHT:-100}")
        DEFAULT_CALLS=10
    fi
}

new_direct_result() {
    mkdir -p "$ROOT/results"
    OUT="$(mktemp -d "$ROOT/results/direct-$BENCH-$VARIANT-$KIND-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX")"
    printf '%s\n' "$IDENTITY" > "$OUT/interpreter.txt"
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$SOURCE" > "$OUT/source.sha256"
    else
        shasum -a 256 "$SOURCE" > "$OUT/source.sha256"
    fi
    printf '%s\n' "$1" > "$OUT/SCOPE.txt"
    echo "Results: $OUT"
}

run_direct() {
    printf '%q ' "$@" >> "$OUT/commands.sh"
    printf '\n' >> "$OUT/commands.sh"
    local rc=0
    "$@" >> "$OUT/stdout.log" 2>> "$OUT/stderr.log" || rc=$?
    if [[ $rc != 0 ]]; then
        echo "Command failed (exit $rc). See $OUT/stderr.log" >&2
        return "$rc"
    fi
}
