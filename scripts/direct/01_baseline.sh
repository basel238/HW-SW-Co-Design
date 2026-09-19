#!/usr/bin/env bash
set -euo pipefail
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/_common.sh"
prepare_direct 01_baseline "$@"
[[ ${1:-} == --help ]] && exit 0
positive_integer DIRECT_PROCESSES "${DIRECT_PROCESSES:-20}"
positive_integer DIRECT_VALUES "${DIRECT_VALUES:-3}"
[[ ${DIRECT_WARMUPS:-1} =~ ^[0-9]+$ ]] || { echo "DIRECT_WARMUPS must be nonnegative." >&2; exit 2; }
new_direct_result "Unprofiled direct benchmark entry point. timing.json contains the original benchmark's internal time per call. No custom Python driver. Not compatible with pipeline comparison provenance; use fresh direct runs for both variants. config.json is not used."
run_direct "$PY" "$SOURCE" "${BENCH_ARGS[@]}" --loops 1 \
    --processes "${DIRECT_PROCESSES:-20}" --values "${DIRECT_VALUES:-3}" \
    --warmups "${DIRECT_WARMUPS:-1}" --output "$OUT/timing.json"
"$PY" -m pyperf show "$OUT/timing.json"
